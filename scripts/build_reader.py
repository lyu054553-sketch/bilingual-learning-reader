#!/usr/bin/env python3
"""Validate bilingual content and generate one self-contained reading page."""

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from library_io import (DataError, atomic_write, integer, migrate_library, nonempty,
                        read_json, require, valid_key)


TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:['’][A-Za-z]+)?")
TIME = re.compile(r"\d{2,}:[0-5]\d:[0-5]\d\Z")


def normalize(word):
    return word.lower().replace("’", "'")


def validate_url(value, where):
    require(isinstance(value, str), where + " 必须是字符串")
    if not value:
        return
    try:
        parsed = urlsplit(value)
        require(parsed.scheme in ("https", "http") and bool(parsed.hostname) and not parsed.username and not parsed.password,
                where + " 只能使用无凭据的 HTTP/HTTPS 来源链接")
        require(not re.search(r"[\x00-\x20]", value), where + " 包含空白或控制字符")
    except ValueError as exc:
        raise DataError(where + " 不是有效链接") from exc


def validate_time(value, where):
    require(isinstance(value, str) and bool(TIME.fullmatch(value)), where + " 必须是 HH:MM:SS")


def dictionary_key(token, entry):
    return entry.get("key") or "en:" + normalize(entry.get("head") or token)


def validate_data(data, strict_dictionary=False):
    require(isinstance(data, dict), "文章数据必须是 JSON 对象")
    meta = data.get("meta")
    require(isinstance(meta, dict), "缺少 meta")
    for field in ("article_id", "title_en", "title_zh", "source_note", "dictionary_source"):
        require(nonempty(meta.get(field)), "meta." + field + " 不能为空")
    require(meta.get("source_type") in ("article", "document", "youtube", "subtitle"), "meta.source_type 无效")
    validate_url(meta.get("source_url", ""), "meta.source_url")
    if meta["source_type"] == "youtube":
        require(nonempty(meta.get("source_url")), "YouTube 文稿必须保留视频来源链接")
    if "duration_seconds" in meta:
        require(type(meta["duration_seconds"]) in (int, float) and meta["duration_seconds"] > 0, "视频时长必须为正数")
    chapters, pairs = data.get("chapters"), data.get("pairs")
    require(isinstance(chapters, list) and bool(chapters), "chapters 必须是非空数组")
    require(isinstance(pairs, list) and bool(pairs), "pairs 必须是非空数组")
    for index, chapter in enumerate(chapters):
        require(isinstance(chapter, dict) and integer(chapter.get("id")) and chapter["id"] == index,
                "chapters.id 必须从 0 连续编号")
        require(nonempty(chapter.get("title")), "章节标题不能为空")
        if chapter.get("time"):
            validate_time(chapter["time"], "章节 time")
    used_chapters, tokens = set(), set()
    for index, row in enumerate(pairs, start=1):
        prefix = "第 {} 句".format(index)
        require(isinstance(row, dict) and integer(row.get("n")) and row["n"] == index, "pairs.n 必须从 1 连续编号，且没有缺号或重号")
        require(nonempty(row.get("en")) and bool(TOKEN.search(row["en"])) and nonempty(row.get("zh")), prefix + " 缺少英文原句或对应译文")
        require(integer(row.get("chapter")) and 0 <= row["chapter"] < len(chapters), prefix + " 的章节引用无效")
        source_id = row.get("source_id")
        has_source_id = nonempty(source_id) or (integer(source_id) and source_id >= 0)
        require(has_source_id or nonempty(row.get("locator")) or nonempty(row.get("time")), prefix + " 缺少可追溯的 source_id、locator 或 time")
        if row.get("time"):
            validate_time(row["time"], prefix + " time")
        validate_url(row.get("source_url", ""), prefix + " source_url")
        meanings = row.get("meanings", {})
        require(isinstance(meanings, dict) and all(nonempty(k) and nonempty(v) for k, v in meanings.items()), prefix + " 的语境释义必须是词到非空释义的映射")
        used_chapters.add(row["chapter"])
        tokens.update(normalize(match.group()) for match in TOKEN.finditer(row["en"]))
    require(used_chapters == set(range(len(chapters))), "存在没有正文的空章节")
    for chapter in chapters:
        questions = chapter.get("practice", [])
        require(isinstance(questions, list), "章节 practice 必须是数组")
        row_ids = {row["n"] for row in pairs if row["chapter"] == chapter["id"]}
        question_ids = set()
        for question in questions:
            require(isinstance(question, dict) and nonempty(question.get("id")), "练习题缺少稳定 id")
            require(question["id"] not in question_ids, "同章节练习题 id 重复：" + question["id"])
            question_ids.add(question["id"])
            require(nonempty(question.get("question")) and nonempty(question.get("answer")), "练习题缺少 question 或 answer")
            require(question.get("kind", "recall") in ("recall", "transfer"), "练习题 kind 只支持 recall 或 transfer")
            evidence = question.get("evidence")
            require(isinstance(evidence, list) and bool(evidence) and all(integer(n) and n in row_ids for n in evidence),
                    "练习题 evidence 必须引用至少一个本章真实句子编号")

    dictionary, vocab = data.get("dict"), data.get("vocab")
    require(isinstance(dictionary, dict), "dict 必须是词典对象")
    require(isinstance(vocab, list), "vocab 必须是数组，可以为空")
    study_keys, actual_keys = set(), set()
    for token, entry in dictionary.items():
        require(isinstance(token, str) and token == normalize(token) and bool(TOKEN.fullmatch(token)), "词典键必须对应小写英文 token：" + str(token))
        require(isinstance(entry, dict), "词典条目必须是对象：" + token)
        for field in ("head", "zh", "en", "ipa", "pos", "context_meaning", "tip", "base"):
            if field in entry:
                require(isinstance(entry[field], str), "词典 {}.{} 必须是字符串".format(token, field))
        key = dictionary_key(token, entry)
        require(valid_key(key), "词典 key 无效：" + token)
        require(any(nonempty(entry.get(k)) for k in ("zh", "en")) or (entry.get("unknown") is True and nonempty(entry.get("tip"))),
                "词典 {} 缺少一般释义；未知词请设置 unknown:true 并用 tip 解释。".format(token))
        if token in tokens:
            actual_keys.add(key)
        if "study" in entry and entry["study"] is not None and entry["study"] is not False:
            study = entry["study"]
            require(isinstance(study, dict) and nonempty(study.get("word")) and nonempty(study.get("meaning")), "重点词 study 缺少 word/meaning：" + token)
            require(isinstance(study.get("usage", ""), str), "重点词 usage 必须是字符串：" + token)
            require(token in tokens, "高亮词未出现在正文：" + token)
            study_keys.add(key)

    vocab_keys = set()
    for word in vocab:
        require(isinstance(word, dict) and nonempty(word.get("word")) and nonempty(word.get("meaning")), "vocab 条目缺少 word 或 meaning")
        require(isinstance(word.get("usage", ""), str), "vocab usage 必须是字符串")
        token = normalize(word["word"])
        entry = dictionary.get(token, {})
        key = word.get("key") or dictionary_key(token, entry)
        require(valid_key(key), "重点词 key 无效：" + word["word"])
        require(key not in vocab_keys, "重点词按原形重复：" + key)
        require(key in actual_keys and key in study_keys, "重点词没有对应的正文及 study 高亮数据：" + word["word"])
        vocab_keys.add(key)
    require(study_keys == vocab_keys, "dict.study 与 vocab 重点词列表不一致")
    missing = sorted(tokens - set(dictionary))
    require(not strict_dictionary or not missing, "有 {} 个可点击词缺少释义或明确未知说明：{}".format(len(missing), ", ".join(missing[:30])))
    data["library"] = migrate_library(data.get("library"))
    require(isinstance(data.get("license", ""), str), "license 必须是字符串")
    return {"sentences": len(pairs), "chapters": len(chapters), "dictionary_entries": len(dictionary),
            "highlighted_words": len(vocab), "tokens_without_dictionary": missing,
            "warnings": (["{} 个词只有页面的未知词提示；补充释义后可用 --strict-dictionary 阻止遗漏。".format(len(missing))] if missing else [])}


def main():
    parser = argparse.ArgumentParser(description="校验文章数据并生成可离线阅读的互动 HTML；无需第三方依赖。")
    parser.add_argument("--data", required=True, type=Path, help="bilingual.json")
    parser.add_argument("--output", required=True, type=Path, help="生成的 HTML 文件")
    parser.add_argument("--strict-dictionary", action="store_true", help="所有正文 token 必须有释义或明确 unknown 说明")
    args = parser.parse_args()
    try:
        template_path = Path(__file__).resolve().parent.parent / "assets" / "reader-template.html"
        require(args.output.resolve() not in (args.data.resolve(), template_path.resolve()), "输出路径不能覆盖源 JSON 或 Skill 模板")
        data = read_json(args.data)
        report = validate_data(data, strict_dictionary=args.strict_dictionary)
        template = template_path.read_text(encoding="utf-8")
        require(template.count("__DATA__") == 1, "模板必须恰好含一个 __DATA__ 插入位置；本次没有写出网页")
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        require(json.loads(payload) == data, "嵌入数据校验失败")
        html = template.replace("__DATA__", payload, 1)
        report["backup"] = atomic_write(args.output, html, backup=True)
        report["output"] = str(args.output)
        report["note"] = "结构校验不能替代原文覆盖核对、翻译审校或学习效果评估。"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (DataError, OSError, UnicodeError) as exc:
        print("生成失败：" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
