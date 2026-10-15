"""Shared standard-library validation and atomic file writing for reader tools."""

import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid


class DataError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DataError(message)


def integer(value):
    return type(value) is int


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def valid_key(key):
    return isinstance(key, str) and key.startswith("en:") and 3 < len(key) < 200


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON 中存在重复字段：" + key)
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                          object_pairs_hook=_unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(DataError("JSON 不接受 " + value)))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataError("无法读取 JSON {}：{}".format(path, exc)) from exc


def validate_examples(examples, where):
    require(isinstance(examples, list), where + " 的 examples 必须是数组")
    for example in examples:
        require(isinstance(example, dict), where + " 的例句必须是对象")
        require(all(isinstance(example.get(k), str) for k in ("article_id", "en", "zh")),
                where + " 的例句缺少 article_id、en 或 zh")


def validate_entry(entry, key, where, revision=None):
    require(valid_key(key) and isinstance(entry, dict) and entry.get("key") == key, where + " 的词条 key 无效")
    require(nonempty(entry.get("head")) and isinstance(entry.get("meaning"), str), where + " 缺少 head 或 meaning")
    require(isinstance(entry.get("forms"), list) and all(isinstance(s, str) for s in entry["forms"]),
            where + " 的 forms 必须是字符串数组")
    validate_examples(entry.get("examples"), where)
    if "notes" in entry:
        require(isinstance(entry["notes"], str), where + " 的 notes 必须是字符串")
    if revision is not None:
        require(entry.get("status") in ("active", "removed"), where + " 的收藏状态无效")
        require(integer(entry.get("updated_revision")) and 0 <= entry["updated_revision"] <= revision,
                where + " 的 updated_revision 超出库版本")


def validate_event(event, where):
    require(isinstance(event, dict), where + " 必须是对象")
    require(nonempty(event.get("event_id")) and valid_key(event.get("key")), where + " 缺少有效 event_id/key")
    require(event.get("rating") in ("again", "hard", "good"), where + " 的 rating 无效")
    require(integer(event.get("step")) and 0 <= event["step"] <= 4, where + " 的 step 必须是 0–4 整数")
    require(nonempty(event.get("article_id")), where + " 缺少 article_id")
    try:
        stamp = event.get("reviewed_at", "")
        require(isinstance(stamp, str) and (stamp.endswith("Z") or stamp.endswith("+00:00")),
                where + " 的 reviewed_at 必须是 ISO UTC 时间")
        moment = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        require("T" in stamp and moment.utcoffset() == dt.timedelta(0), where + " 的 reviewed_at 必须是 ISO UTC 时间")
        date = dt.date.fromisoformat(event.get("due_at", ""))
        require(date.isoformat() == event["due_at"], where + " 的 due_at 必须是 YYYY-MM-DD")
    except (ValueError, TypeError) as exc:
        raise DataError(where + " 的日期格式无效") from exc


def validate_operation(operation, where):
    require(isinstance(operation, dict), where + " 必须是对象")
    require(nonempty(operation.get("operation_id")), where + " 缺少 operation_id")
    require(valid_key(operation.get("key")), where + " 的 key 无效")
    require(integer(operation.get("base_revision")) and operation["base_revision"] >= 0, where + " 的 base_revision 无效")
    require(operation.get("action") in ("upsert", "remove"), where + " 的 action 无效")
    if operation["action"] == "upsert":
        validate_entry(operation.get("entry"), operation["key"], where)


def validate_library(library):
    require(isinstance(library, dict) and library.get("kind") == "bilingual-learning-library", "这不是正式生词本")
    require(type(library.get("schema_version")) is int and library["schema_version"] in (1, 2), "不支持的生词本 schema_version")
    require(nonempty(library.get("library_id")), "生词本缺少 library_id")
    require(integer(library.get("revision")) and library["revision"] >= 0, "生词本 revision 无效")
    require(isinstance(library.get("favorites"), dict), "生词本 favorites 必须是对象")
    ids = library.get("processed_operation_ids")
    require(isinstance(ids, list) and all(nonempty(item) for item in ids) and len(set(ids)) == len(ids),
            "processed_operation_ids 必须是无重复的编号数组")
    for key, entry in library["favorites"].items():
        validate_entry(entry, key, "词条 " + key, library["revision"])
    events = library.get("review_events", [])
    require(isinstance(events, list), "review_events 必须是数组")
    seen = set()
    for event in events:
        validate_event(event, "复习记录")
        require(event["event_id"] not in seen, "正式库复习编号重复：" + event["event_id"])
        require(event["key"] in library["favorites"], "复习记录没有对应历史词条：" + event["key"])
        seen.add(event["event_id"])
    receipts = library.get("operation_receipts", {})
    require(isinstance(receipts, dict), "operation_receipts 必须是对象")
    for oid, operation in receipts.items():
        validate_operation(operation, "操作回执 " + oid)
        require(oid == operation["operation_id"] and oid in ids, "操作回执与已处理编号不一致：" + oid)
    return library


def migrate_library(library):
    result = copy.deepcopy(validate_library(library))
    result["schema_version"] = 2
    result.setdefault("review_events", [])
    result.setdefault("operation_receipts", {})
    return result


def atomic_write(path, text, backup=False):
    """Write in the destination directory; preserve an existing file before replace."""
    path = Path(path)
    require(not path.is_symlink(), "为避免覆盖链接目标，请直接指定正式文件：" + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if backup and path.exists():
            backup_dir = path.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_path = backup_dir / (path.stem + "-" + stamp + "-" + uuid.uuid4().hex[:8] + path.suffix)
            shutil.copy2(path, backup_path)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return str(backup_path) if backup_path else None


def write_json(path, value, backup=False):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    json.loads(text)
    return atomic_write(path, text, backup=backup)
