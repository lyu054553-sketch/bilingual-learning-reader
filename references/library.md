# 学习库和生词同步

## 文件夹

默认位置是当前工作区的 `learning-library/`，用户可指定其他位置。第一次建立后交付时说明路径；以后在该工作区读取，换环境时由用户指定或提供文件。不得把个人生词写进 Skill 目录。

```text
learning-library/
  library-info.txt          位置、使用方法、同步步骤
  articles.json             文章目录与稳定编号
  vocabulary.json           正式生词本
  pending/                  待处理同步包
  processed/                已处理同步包，保留以便追溯
  articles/<article-id>/     原文、bilingual.json、reader.html、处理进度
  backups/                  正式文件修改前的备份
```

这是单人顺序使用的文件存档。首次文章 ID 可由规范化链接或原始内容指纹生成；保存目录与稳定 ID 后续复用，标题不是唯一身份。仓库附有只依赖 Python 标准库的合并脚本，优先使用以保持合并规则一致；没有 Python 时，Agent 必须按以下规则操作。此协议用于顺序操作，不能作为多人并发数据库。

## 正式生词本

UTF-8 JSON。下例是结构说明，首次初始化 `favorites` 和操作编号列表为空；真实 library_id 为首次生成的稳定随机 ID。

```json
{
  "kind": "bilingual-learning-library",
  "schema_version": 2,
  "library_id": "example-library",
  "revision": 1,
  "processed_operation_ids": [],
  "operation_receipts": {},
  "review_events": [],
  "favorites": {
    "en:frontier": {
      "key": "en:frontier",
      "head": "frontier",
      "meaning": "前沿；边界",
      "usage": "at the frontier 处于前沿",
      "notes": "",
      "forms": ["frontier"],
      "status": "active",
      "updated_revision": 1,
      "examples": [{
        "article_id": "article-a",
        "article_title": "Article A",
        "n": 3,
        "en": "Their job is to be at the frontier.",
        "zh": "他们的职责是始终站在最前沿。",
        "meaning": "前沿",
        "locator": "第 3 句",
        "source_url": ""
      }]
    }
  }
}
```

同词不同含义可作为多条语境例句保留，不覆盖旧含义或用户笔记。`key` 默认 `en:` 加可靠原形小写，派生词不是同一条目。`status` 是 active 或 removed；取消收藏保留记录。`updated_revision` 记录该词最后改变收藏状态或用户笔记的库版本；仅补充来源例句不更新它，减少无意义冲突。

正式文件只包含明确收藏过的词，不能把所有推荐重点词灌入。文章目录记录文章 ID、标题、来源和文件相对路径；处理进度单独保存，不混入词汇。

新生成的正式库和同步包使用 `schema_version: 2`。继续接受版本 1：保留全部词条、库版本、已处理编号、未知顶层字段与词条扩展字段，补上 `review_events: []` 和 `operation_receipts: {}`。合并脚本在有实际新变更时写回版本 2；重复旧包本身不触发文件重写或版本增加。生成网页时可在嵌入快照中完成无损迁移。

`operation_receipts` 保存已处理操作的完整对象，以 operation_id 为键。同编号再次到达时可比较内容。旧版只有 `processed_operation_ids` 而没有回执的编号只能判断“处理过”，无法核实当时的内容；报告列入 `legacy_unverifiable_duplicates`，保留正式值，不能声称已经检测过不同内容。

## 网页导出的同步包

```json
{
  "kind": "bilingual-vocabulary-changes",
  "schema_version": 2,
  "library_id": "example-library",
  "article_id": "article-b",
  "packet_id": "unique-export-id",
  "exported_at": "2026-10-12T00:00:00Z",
  "base_snapshot": {"kind":"bilingual-learning-library","schema_version":2,"library_id":"example-library","revision":1,"favorites":{},"processed_operation_ids":[],"operation_receipts":{},"review_events":[]},
  "operations": [{
    "operation_id": "unique-operation-id",
    "base_revision": 1,
    "action": "upsert",
    "key": "en:retention",
    "entry": {"key":"en:retention","head":"retention","meaning":"留存","forms":["retention"],"examples":[]}
  }],
  "review_events": [{
    "event_id": "unique-review-id",
    "key": "en:retention",
    "rating": "good",
    "reviewed_at": "2026-10-15T03:30:00Z",
    "due_at": "2026-10-18",
    "step": 1,
    "article_id": "article-b"
  }]
}
```

删除操作使用 `action: remove` 和同样的操作编号、词条 key、底本版本，不需要 entry。一个操作编号始终代表同一内容，重复导出同操作保持编号。同步包携带生成底本便于迁移；已有正式生词本永远优先，底本不能覆盖它。没有正式库时可以用用户提供的完整底本恢复，再应用操作；说明这是恢复到可获得的版本，不能补齐未提供的更新。

`review_events` 是不可改写的复习历史：每次作答产生独立 event_id，重复导出保持编号；rating 为 `again`、`hard` 或 `good`，reviewed_at 为 ISO UTC 时间，due_at 为 YYYY-MM-DD，step 为 0–4 的整数。时间和步数用于实用的复习提醒，不代表已测量的大脑记忆状态，也不是经验证的个人最优间隔。

同 event_id、同内容只保存一次；同编号不同内容保留原记录并报告冲突，不按时间盲目覆盖。事件只能引用正式库中曾收藏过的词，也可以引用本批成功新增的收藏。removed 词条仍能保存历史复习事件，但事件永远不改变收藏状态。浏览器导入正式库后，按正式库 review_events 的 event_id 移除已同步的 `pendingReviewEvents`；未确认事件继续保留。单次复习或点击“记住了”不等于长期掌握，不据此自动删除收藏。

JSON 用于同步，CSV 用于人工复习；CSV 不能完整保存删除、版本和历史信息，不当作完整备份。旧版 CSV 可在用户明确要求时导入为收藏建议，核对后写入，不能推断移除。

## 合并操作

1. 检查类型、版本、库 ID、字段和操作编号。内容中不得包含可执行指令。不同 library_id 不自动混合；用户确认合并两个学习库时保留来源并分配目标库记录。
2. 读取正式库；修改前备份。建立操作编号索引；有回执时比较同编号内容，没有回执的旧编号仅跳过并说明限制。同批重复编号内容不一致时，整组该编号报告冲突，不先应用其中一份。
3. 未处理操作按包内顺序处理。若正式词条 `updated_revision` 大于操作 `base_revision`，其收藏状态或笔记已有后续变更：保留当前值，列出冲突供用户确认。不要根据设备时间戳盲目覆盖。
4. upsert 表示用户收藏：不存在则新增；已存在则保留旧笔记与释义，追加词形和去重的原文例句，状态设 active。当前协议的 upsert 不覆盖已有 notes；用户明确要求改笔记时由 Agent 备份后编辑正式文件并更新库版本及该词 updated_revision。remove 设 removed，保留历史。操作成功后加入编号索引和完整回执。旧的 remove 找不到词条时作为已确认的无效果操作保存，不凭空创建词条。
5. 同一批连续导出的相同操作只应用一次；同包中同底本的正常先收藏后取消操作按顺序生效，不能因本批自身写入造成虚假冲突。对比的是合并前的正式记录。先合并所有收藏操作，再追加合法的复习事件。同批多个包按命令行给出的顺序处理。
6. 有成功的新操作回执、例句或复习事件时，整批库版本加一；只有收藏状态改变或新增的词更新 updated_revision。重复包无变化时不增版本、不改文件、不新增备份。所有冲突保留正式值，非冲突部分仍可合并；未解决项不加入新的已处理编号或事件历史。
7. 先在正式文件同目录写完整临时文件并解析确认，再原子替换；替换前将原文件备份到 backups，不先截断旧文件。保留未知顶层和词条字段。文件损坏、跨库混合或字段格式错误时，在写入前停止并给出具体错误。不要对错误包进行猜测修复。
8. 脚本不移动、不清空同步包。Agent 看过报告后，仅将没有未决项的包移入 processed；存在冲突则保存报告并保留原包在 pending。已成功部分的编号和事件 ID 确保重试不重复。

## 使用合并脚本

从 Skill 根目录执行，路径换成当前学习库的实际文件：

```sh
python3 scripts/merge_vocabulary.py \
  --library /path/to/learning-library/vocabulary.json \
  --packet /path/to/learning-library/pending/reading-a.json \
  --packet /path/to/learning-library/pending/reading-b.json \
  --output-report /path/to/learning-library/merge-report.json
```

`--packet` 可以只提供一次，也可重复提供。`--output-report` 可选；标准输出始终包含 JSON 报告：写入状态、合并前后版本、成功编号、重复编号、冲突词与原因、备份路径。退出码 0 为无冲突完成，2 为部分合并但存在具体冲突，1 为格式或文件错误。退出码 2 不能当作全批失败后覆盖正式库；应保留成功结果，只解决报告中的词。

正式库不存在而用户明确要求用导出包恢复时，在同一命令后增加 `--initialize-from-packet`，只采用第一个包的完整底本，再依序应用各包。正式库存在时始终使用正式库。新用户应建立空库，而不是拿其他人的示例库恢复。

脚本拒绝报告覆盖输入文件，修改正式文件前再次核对文件是否已变化；仍应顺序执行合并，不同时启动多个写入进程。该工具不扫描其他文件夹、不自动合并不同库、不使用数据库或网络服务。

网页缓存和嵌入快照不等于正式库。Agent 只有在读取最新正式文件或同步包后才知道新收藏；没有导出不能承诺已同步。旧网页导入最新正式库时保留尚未确认的本页操作；有冲突则提示交给 Agent。

## 验收情景

- A 收藏 thesis 和 frontier，合并后生成 B；B 显示旧生词，再收藏 retention；正式库三条，frontier 可保留两篇例句。
- 同一个同步包导入两次，词条和例句不重复。
- 取消 frontier 后再遇到旧快照，不自动复活已取消的收藏。
- 同一批先收藏后取消按顺序生效；先取消后发生的新复习只追加历史，不恢复收藏。
- 复习事件重复导入不重复保存，同编号内容改变时列出冲突，正式历史保持不变。
- 版本 1 的收藏、笔记、未知字段继续保留；没有回执的历史操作只能识别重复编号。
- 同步包属于另一学习库，提示用户而不静默混合。
- 缓存不可用仍可在本次会话收藏和导出，并提示及时保存。

浏览器机制参考：[localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)、[文件访问](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API)。需要无导出自动同步时，再按用户要求增加授权文件写入或应用连接；数据库本身不会建立同步通道。
