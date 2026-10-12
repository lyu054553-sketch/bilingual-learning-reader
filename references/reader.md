# 固定阅读网页与数据

使用 `assets/reader-template.html`。它是本次 Google Labs HTML 布局的通用版本，保留原 CSS、章节导航、对照行和词典面板，去掉所有朗读，补上生词 JSON 导入导出和跨篇显示。只替换 `<script id="app-data" type="application/json">` 内的 `__DATA__` 参数。不直接把原文插进 HTML，模板会转义显示文本。

## 生成数据

使用当前 Agent 的文件能力和熟悉的工具生成 UTF-8 JSON，形状如下。标题、词汇、章节和数量都是当前文章内容，以下只是最小的结构示例，不作为真实文章使用。

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
  "chapters": [{"id":0,"title":"第一节"}],
  "pairs": [{
    "n":1,"source_id":1,"chapter":0,
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
    "kind":"bilingual-learning-library","schema_version":1,
    "library_id":"example-library","revision":0,
    "favorites":{},"processed_operation_ids":[]
  },
  "license":"词库许可文本；使用外部词库时保留。"
}
```

## 字段约定

- `meta.article_id` 全库唯一且稳定，用于文章目录与浏览器缓存。`source_type` 可为 article、document、youtube、subtitle。YouTube 使用规范化视频 URL；有实际时长才提供 `duration_seconds`。
- `chapters.id` 从 0 连续编号；每行 chapter 对应有效章节。章节可有 `time`，无视频时间不填。
- `pairs.n` 是正整数且全篇唯一，默认从 1 连续编号。source_id 或另存的原始对应文件用于覆盖检查。`en`、`zh` 为纯文本。`time` 可为 HH:MM:SS。`locator` 使用实际段落、页面或字幕位置；`source_url` 可指向具体来源章节。
- `pairs.meanings` 按文中词小写或 canonical key 提供当前句子的语境义，同词不同语境分别写。模板优先使用它，其次 `dict.context_meaning`，再次重点词学习释义；都没有则明确显示一般释义，不冒充语境结论。
- `dict` 的键是实际英文 token 小写、弯引号转直引号。entry 可有 `key/head/zh/en/ipa/pos/context_meaning/tip/base/study`。仅提供可靠音标；不支持音频字段。用可靠的 head 和 key 处理原形，派生词分开。`study` 控制黄色高亮；重点词列表 `vocab` 按词条去重。
- 模板按英文单词和缩写点击；含数字的专业缩写可在词汇提示或原文结构区说明，必要时调整 tokenizer，并检查对应键、点击和存档一起改变。
- 未查询到的一般释义保留未知提示；提供语境解释并注明整理来源。不要用占位含义填满字典来声称查询成功。
- `library` 嵌入生成时正式文件的完整快照，包括 removed 条目与已处理操作编号。所有跨篇例句随个人生词保留，即使本篇没出现该词也能在生词本展开。

## 写出 HTML

可用 Python 标准库完成替换；没有固定执行脚本依赖：

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
- “导出同步记录”产生带底本和稳定操作编号的 JSON。不清空未确认操作，重复导出仍可安全交给 Agent 去重。
- “导入最新生词本”接受正式文件，不接受同步包。核对库 ID、格式与版本，拒绝回退或同版本不同内容。按正式库的确认编号清除已合并的本页操作，保留未决操作。
- 更高版本的同词状态与本页旧操作冲突时，网页保留正式值并提示交给 Agent。同步逻辑和恢复规则见 library.md。
- “导出词表”保存 active 生词及跨篇例句到 CSV，供复习；不是完整同步备份。

## 检查与预览

先检查全篇编号、章节覆盖、译文、词典 key、重点词数据和正式生词快照。代表性检查包括普通词、重点词、缩写、未知词和同词不同语境。

涉及模板变更时，在可用浏览器工具中检查桌面左右对照、手机无横向溢出、键盘查词与关闭面板、搜索、收藏、JSON 导出及正式库导入。只在本地预览，遵守当前浏览器工具的协议和文件访问限制；不可绕过安全拒绝。结束时清理自己启动的临时预览服务，不修改用户已打开的页面。

不要把“Skill 通过格式验证”说成“任意网站抓取都已测试”。交付时如实说明实际检查范围。
