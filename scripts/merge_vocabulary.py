#!/usr/bin/env python3
"""Merge exported reader changes without a database or third-party packages."""

import argparse
import copy
import json
from pathlib import Path
import sys

from library_io import (DataError, canonical, migrate_library, nonempty, read_json,
                        require, validate_event, validate_library,
                        validate_operation, write_json)


def load_packet(path):
    packet = read_json(path)
    require(isinstance(packet, dict) and packet.get("kind") == "bilingual-vocabulary-changes", str(path) + " 不是同步包")
    require(type(packet.get("schema_version")) is int and packet["schema_version"] in (1, 2), str(path) + " 的同步版本不受支持")
    require(all(nonempty(packet.get(k)) for k in ("library_id", "article_id", "packet_id")), str(path) + " 缺少库、文章或导出编号")
    require(isinstance(packet.get("operations"), list), str(path) + " 的 operations 必须是数组")
    require(isinstance(packet.get("review_events", []), list), str(path) + " 的 review_events 必须是数组")
    for operation in packet["operations"]:
        validate_operation(operation, str(path) + " 的操作")
    for event in packet.get("review_events", []):
        validate_event(event, str(path) + " 的复习记录")
    if "base_snapshot" in packet:
        validate_library(packet["base_snapshot"])
        require(packet["base_snapshot"]["library_id"] == packet["library_id"], "同步包底本与库 ID 不一致")
    return packet


def colliding_ids(items, field):
    seen, collisions = {}, set()
    for item in items:
        key, payload = item[field], canonical(item)
        if key in seen and seen[key] != payload:
            collisions.add(key)
        seen[key] = payload
    return collisions


def merge(library, packets):
    base = migrate_library(library)
    result = copy.deepcopy(base)
    report = {"kind": "bilingual-merge-report", "library_id": base["library_id"],
              "revision_before": base["revision"], "revision_after": base["revision"],
              "changed": False, "operations_applied": [], "review_events_added": [],
              "duplicates": [], "legacy_unverifiable_duplicates": [], "conflicts": []}
    operations = [operation for packet in packets for operation in packet["operations"]]
    events = [event for packet in packets for event in packet.get("review_events", [])]
    op_collisions = colliding_ids(operations, "operation_id")
    event_collisions = colliding_ids(events, "event_id")
    done = set(result["processed_operation_ids"])
    handled_ops, handled_events = set(), set()
    state_changes = set()

    def conflict(kind, item, reason):
        identifier = item["operation_id" if kind == "operation" else "event_id"]
        report["conflicts"].append({"type": kind, "id": identifier, "key": item["key"], "reason": reason})

    for operation in operations:
        oid, key = operation["operation_id"], operation["key"]
        if oid in handled_ops:
            continue
        handled_ops.add(oid)
        if oid in op_collisions:
            conflict("operation", operation, "本批相同 operation_id 对应不同内容；请为修改后的操作使用新编号。")
            continue
        if oid in done:
            receipt = result["operation_receipts"].get(oid)
            if receipt is not None and canonical(receipt) != canonical(operation):
                conflict("operation", operation, "同一 operation_id 的内容与正式回执不同，已保留原记录。")
            elif receipt is None:
                report["legacy_unverifiable_duplicates"].append(oid)
            else:
                report["duplicates"].append(oid)
            continue
        if operation["base_revision"] > base["revision"]:
            conflict("operation", operation, "操作底本版本比正式库更新；请提供最新正式库。")
            continue
        initial = base["favorites"].get(key)
        if initial and initial["updated_revision"] > operation["base_revision"]:
            conflict("operation", operation, "该词的收藏状态或笔记已在底本之后改变；已保留正式值。")
            continue
        previous = result["favorites"].get(key)
        if operation["action"] == "remove":
            if previous and previous["status"] != "removed":
                previous["status"] = "removed"
                state_changes.add(key)
        else:
            incoming = copy.deepcopy(operation["entry"])
            if previous is None:
                incoming["status"] = "active"
                incoming.setdefault("notes", "")
                incoming["updated_revision"] = base["revision"]
                result["favorites"][key] = incoming
                state_changes.add(key)
            else:
                # Preserve existing notes, definitions and unknown fields. New
                # extension fields may be added, but cannot overwrite saved ones.
                for field, value in incoming.items():
                    previous.setdefault(field, value)
                previous["forms"] = list(dict.fromkeys(previous["forms"] + incoming["forms"]))
                examples = previous["examples"]
                for example in incoming["examples"]:
                    match = next((old for old in examples if all(old.get(k) == example.get(k)
                                 for k in ("article_id", "n", "en"))), None)
                    if match is None:
                        examples.append(example)
                    else:
                        for field, value in example.items():
                            match.setdefault(field, value)
                if previous["status"] != "active":
                    state_changes.add(key)
                previous["status"] = "active"
        done.add(oid)
        result["processed_operation_ids"].append(oid)
        result["operation_receipts"][oid] = copy.deepcopy(operation)
        report["operations_applied"].append(oid)

    event_index = {event["event_id"]: event for event in result["review_events"]}
    for event in events:
        eid = event["event_id"]
        if eid in handled_events:
            continue
        handled_events.add(eid)
        if eid in event_collisions:
            conflict("review_event", event, "本批相同 event_id 对应不同内容；复习历史不可改写。")
            continue
        if eid in event_index:
            if canonical(event_index[eid]) != canonical(event):
                conflict("review_event", event, "同一 event_id 的内容与正式记录不同，已保留原记录。")
            else:
                report["duplicates"].append(eid)
            continue
        if event["key"] not in result["favorites"]:
            conflict("review_event", event, "复习记录没有对应历史词条；先合并该词的收藏记录。")
            continue
        result["review_events"].append(copy.deepcopy(event))
        event_index[eid] = event
        report["review_events_added"].append(eid)

    # Migration is written with the next real acknowledged change. Replaying a
    # legacy packet alone neither rewrites the file nor increments its revision.
    changed = canonical(result) != canonical(base)
    if changed:
        result["revision"] += 1
        for key in state_changes:
            result["favorites"][key]["updated_revision"] = result["revision"]
        validate_library(result)
    report["changed"] = changed
    report["revision_after"] = result["revision"]
    return result, report


def main():
    parser = argparse.ArgumentParser(description="合并生词及复习 JSON；使用 Python 标准库。")
    parser.add_argument("--library", required=True, type=Path, help="正式 vocabulary.json")
    parser.add_argument("--packet", required=True, action="append", type=Path, help="可重复指定，按命令顺序合并")
    parser.add_argument("--output-report", type=Path, help="可选的 JSON 合并报告")
    parser.add_argument("--initialize-from-packet", action="store_true", help="正式文件不存在时，明确允许使用第一个包的完整底本恢复")
    args = parser.parse_args()
    try:
        inputs = {args.library.resolve(), *(path.resolve() for path in args.packet)}
        require(not args.output_report or args.output_report.resolve() not in inputs, "报告路径不能覆盖正式库或同步包")
        require(args.library.resolve() not in {path.resolve() for path in args.packet}, "正式库与同步包路径不能相同")
        packets = [load_packet(path) for path in args.packet]
        exists = args.library.exists()
        original_text = args.library.read_bytes() if exists else None
        if exists:
            library = validate_library(read_json(args.library))
        else:
            require(args.initialize_from_packet, "正式生词本不存在；请先建立新库，或明确使用 --initialize-from-packet 恢复底本")
            require("base_snapshot" in packets[0], "首个同步包没有完整底本，无法恢复")
            library = validate_library(packets[0]["base_snapshot"])
        require(all(packet["library_id"] == library["library_id"] for packet in packets), "同步包属于其他学习库；本次未写入任何内容")
        result, report = merge(library, packets)
        report["initialized_from_packet"] = not exists
        report["backup"] = None
        if report["changed"] or not exists:
            if exists:
                require(args.library.read_bytes() == original_text, "正式生词本在处理中发生变化；请顺序运行并重试")
            else:
                require(not args.library.exists(), "正式生词本已由其他进程创建；请重新读取后重试")
            report["backup"] = write_json(args.library, result, backup=exists)
        if args.output_report:
            write_json(args.output_report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if report["conflicts"] else 0
    except (DataError, OSError) as exc:
        print("合并失败：" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
