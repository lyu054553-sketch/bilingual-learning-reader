# 固定阅读网页与数据

使用 `assets/reader-template.html`：暖白纸张、墨绿控件、柔黄重点词，电脑全文左右对照与右侧词典，手机逐句上下对照。模板包含全文阅读、按句揭示、词汇自测和 JSON 同步，没有朗读。只替换 `<script id="app-data" type="application/json">` 内的 `__DATA__` 参数；不要逐篇另做设计。

## 生成数据

使用当前 Agent 的文件能力和熟悉的工具生成 UTF-8 JSON，形状如下。标题、词汇和数量都是当前文章内容，以下只是最小的结构示例，不作为真实文章使用。

```json
{
  "meta": {
    "article_id": "article-a",
    "title_en": "An English article title",
    "title_zh": "中文标题",
    "subtitle": "作者或来源，可省略",
    "eyebrow": "BILINGUAL READING / 双语精读",
    "source_type": "article",
    "source_url": "",
    "source_note": "完整正文，依据用户提供的文章整理。",
    "dictionary_source": "Agent 整理"
  },
  "pairs": [{
    "n":1,"source_id":1,
    "en":"Their job is to be at the frontier.",
    "zh":"他们的职责是始终站在最前沿。",
    "locator":"第 1 段",
    "meanings":{"frontier":"前沿"}
  }],
  "dict": {
    "frontier": {
      "key":"en:frontier","head":"frontier",
      "zh":"前沿；边界",
      "study":{"word":"frontier","meaning":"前沿","usage":"at the frontier 处于前沿"}
    }
  },
  "vocab": [{"word":"frontier","meaning":"前沿","usage":"at the frontier 处于前沿"}],
  "library": {
    "kind":"bilingual-learning-library","schema_version":2,
    "library_id":"example-library","revision":0,
    "favorites":{},"processed_operation_ids":[],
    "review_events":[],"operation_receipts":{}
  },
  "license":"词库许可文本；使用外部词库时保留。"
}
```

## 字段约定

- `meta.article_id` 全库唯一且稳定，用于文章目录与浏览器缓存。`source_type` 可为 article、document、youtube、subtitle。YouTube 使用规范化视频 URL；有实际时长才提供 `duration_seconds`。
- 新数据无需 `chapters`、`pairs.chapter` 或 `practice` 字段。旧数据可保留这些字段，生成器忽略它们；始终按 `pairs` 原始顺序展示全文，不读取旧缓存中的章节选择。可运行示例见 [demo.json](../examples/demo.json)。
- `pairs.n` 是正整数且全篇唯一，默认从 1 连续编号。source_id 或另存的原始对应文件用于覆盖检查。`en`、`zh` 为纯文本。`time` 可为 HH:MM:SS。`locator` 使用实际段落、页面或字幕位置；`source_url` 可指向具体来源章节。
- `pairs.meanings` 按文中词小写或 canonical key 提供当前句子的语境义，同词不同语境分别写。模板优先使用它，其次 `dict.context_meaning`，再次重点词学习释义；都没有则明确显示一般释义，不冒充语境结论。
- `dict` 的键是实际英文 token 小写、弯引号转直引号。entry 可有 `key/head/zh/en/ipa/pos/context_meaning/tip/base/study`。仅提供可靠音标；不支持音频字段。用可靠的 head 和 key 处理原形，派生词分开。`study` 控制黄色高亮；重点词列表 `vocab` 按词条去重。
- 模板按 `[A-Za-z][A-Za-z0-9]*(?:['’][A-Za-z]+)?` 分词，支持 B2、D7 等带数字缩写；弯引号归一为直引号。连字符词和多词搭配的说明写在词条笔记中，不能假定它们都是一个点击单元。
- 未查询到的一般释义用 `unknown:true` 和明确 `tip` 说明，页面保留未知提示。不要用“含义待确认”填满字典来假装完成词义整理。`--strict-dictionary` 检查每个 token 有释义或明确未知说明，不验证释义正确性。
- `library` 嵌入生成时正式文件的完整快照，包括 removed 条目与已处理操作编号。所有跨篇例句随个人生词保留，即使本篇没出现该词也能在生词本展开。

## 生成、校验与重建

优先使用随 Skill 附带的 Python 3 标准库脚本，不需要安装包：

```sh
python3 scripts/build_reader.py --data /path/to/bilingual.json --output /path/to/reader.html --strict-dictionary
```

命令路径相对于 Skill 根目录；实际运行时传当前文件的路径。它检查编号、中英是否非空、词典覆盖、重点词一致性、库格式和安全嵌入。失败不会写出半个页面；替换现有页面前保留备份。其报告不等于翻译审校或全文覆盖的证明。

新增内容用 v2 库和同步包；工具读取 v1 并保留旧词、笔记、例句、移除状态和已处理编号。旧 HTML 不支持 v2 时，用旧 `bilingual.json` 和最新正式库重新生成；先保留其未同步导出，不清空缓存来“解决”兼容性问题。

### 没有 Python 的环境

Agent 可按同一数据约定校验并安全替换；下面展示转义原则：

```python
import json
from pathlib import Path
payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
html = template.read_text(encoding='utf-8').replace('__DATA__', payload)
out.write_text(html, encoding='utf-8')
```

`data`、`template`、`out` 使用当前任务的实际变量和路径。把 `<` 转义，防止原文中出现 `</script>` 提前结束数据块；生成后确认没有遗留参数。页面文本和链接由模板转义，来源链接仅允许 HTTP/HTTPS。保存到该文章目录的 reader.html；在要求单独输出的环境复制到交付目录并链接副本。

## 生词交互

- 缓存按库 ID 和文章 ID 隔离，避免多篇文章相互覆盖。正式生词本全库共享；本页未同步操作单独保存。缓存失败仍支持当前会话和导出，并提示用户。
- 缓存无法解析时不覆盖旧缓存；导出包可附 `unreadable_cache` 原始字符串供 Agent 恢复。它不是正式快照，不能直接执行或自动覆盖正式库。先保留该文件，核对可恢复的操作再合并。
- “导出同步记录”产生带底本和稳定操作编号的 JSON。不清空未确认操作，重复导出仍可安全交给 Agent 去重。
- “导入最新生词本”接受正式文件，不接受同步包。核对库 ID、格式与版本，拒绝回退或同版本不同内容。按正式库的确认编号清除已合并的本页操作，保留未决操作。
- 更高版本的同词状态与本页旧操作冲突时，网页保留正式值并提示交给 Agent。同步逻辑和恢复规则见 library.md。
- “导出词表”保存 active 生词及跨篇例句到 CSV，供复习；不是完整同步备份。

## 学习交互

- 默认中英对照。“先读英文”保留对应位置，但逐句隐藏中文；读者可随时揭示或恢复全部对照。
- 复习仅使用 active 收藏且有可用释义的词；到期/从未复习优先，也能提前练习全部。一次一个词，中文初始隐藏、原句可作提示，揭示后才自评；跳过不写记录。
- 三种自评为“没想起来 / 有些费力 / 较轻松”。默认步长表是 1、3、7、14、30 天：没想起来回到第 0 档，费力维持原档，较轻松前进一档（初次从第 0 档开始）。这是可解释的启发式，用户可选今天或之后的日期覆盖它。
- `reviewed_at` 记录 UTC 时刻，`due_at` 是本机本地日历日期；换时区仍按日期提醒。用事件时刻排序取最近一次的日期，设备时钟错误时应提示用户核对，不能据此测量个人遗忘曲线。
- 收藏与复习共用导出入口，页面显示待同步条数。事件不改变收藏状态，已移除的词不因旧复习记录重新出现。
- 屏幕滚动条只反映阅读位置，收藏数只表示词条数，不显示学习成绩。

## 检查与预览

先检查全篇编号、完整原文覆盖、译文、词典 key、重点词数据和正式生词快照。代表性检查包括普通词、重点词、缩写、未知词和同词不同语境。

涉及模板变更时，检查桌面与 320–390px 手机布局、键盘查词与关闭、搜索、收藏、按句揭示、全文展示且无目录或文章理解输入框、复习揭示前不能自评、跳过、日期调整、导出后由脚本合并再导入的完整链路。只更换数据时以结构校验和代表性语义核对为主。遵守预览工具的访问限制，结束后清理自己启动的临时服务。

不要把“Skill 通过格式验证”说成“任意网站抓取都已测试”。交付时如实说明实际检查范围。
