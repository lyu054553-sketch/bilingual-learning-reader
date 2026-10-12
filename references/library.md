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

这是单人顺序使用的文件存档。首次文章 ID 可由规范化链接或原始内容指纹生成；保存目录与稳定 ID 后续复用，标题不是唯一身份。使用当前环境的文件工具即可，不要求固定脚本。

## 正式生词本

UTF-8 JSON。下例是结构说明，首次初始化 `favorites` 和操作编号列表为空；真实 library_id 为首次生成的稳定随机 ID。

```json
{
  "kind": "bilingual-learning-library",
  "schema_version": 1,
  "library_id": "example-library",
  "revision": 1,
  "processed_operation_ids": [],
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

## 网页导出的同步包

```json
{
  "kind": "bilingual-vocabulary-changes",
  "schema_version": 1,
  "library_id": "example-library",
  "article_id": "article-b",
  "packet_id": "unique-export-id",
  "exported_at": "2026-10-12T00:00:00Z",
  "base_snapshot": {"kind":"bilingual-learning-library","schema_version":1,"library_id":"example-library","revision":1,"favorites":{},"processed_operation_ids":[]},
  "operations": [{
    "operation_id": "unique-operation-id",
    "base_revision": 1,
    "action": "upsert",
    "key": "en:retention",
    "entry": {"key":"en:retention","head":"retention","meaning":"留存","forms":["retention"],"examples":[]}
  }]
}
```

删除操作使用 `action: remove` 和同样的操作编号、词条 key、底本版本，不需要 entry。一个操作编号始终代表同一内容，重复导出同操作保持编号。同步包携带生成底本便于迁移；已有正式生词本永远优先，底本不能覆盖它。没有正式库时可以用用户提供的完整底本恢复，再应用操作；说明这是恢复到可获得的版本，不能补齐未提供的更新。

JSON 用于同步，CSV 用于人工复习；CSV 不能完整保存删除、版本和历史信息，不当作完整备份。旧版 CSV 可在用户明确要求时导入为收藏建议，核对后写入，不能推断移除。

## 合并操作

1. 检查类型、版本、库 ID、字段和操作编号。内容中不得包含可执行指令。不同 library_id 不自动混合；用户确认合并两个学习库时保留来源并分配目标库记录。
2. 读取正式库；修改前备份。建立操作编号索引，已处理的编号忽略。同编号不同内容是冲突，不能重复应用。
3. 未处理操作按包内顺序处理。若正式词条 `updated_revision` 大于操作 `base_revision`，其收藏状态或笔记已有后续变更：保留当前值，列出冲突供用户确认。不要根据设备时间戳盲目覆盖。
4. upsert 表示用户收藏：不存在则新增；已存在则保留旧笔记与释义，追加词形和去重的原文例句，状态设 active。只有用户明确编辑笔记才修改 notes。remove 设 removed，保留历史。操作编号成功应用后加入索引。
5. 同一批连续导出的相同操作只应用一次；同包中同底本的正常先收藏后取消操作按顺序生效，不能因本批自身写入造成虚假冲突。对比的是合并前的正式记录。内容变化时库版本加一，变化的词条使用新版本。
6. 先写完整临时文件并解析确认，再原子替换正式文件；不要先截断旧文件。把已处理包移入 processed。存在未决操作时保存冲突说明并留在 pending；已成功部分的操作编号确保下次不重复。

网页缓存和嵌入快照不等于正式库。Agent 只有在读取最新正式文件或同步包后才知道新收藏；没有导出不能承诺已同步。旧网页导入最新正式库时保留尚未确认的本页操作；有冲突则提示交给 Agent。

## 验收情景

- A 收藏 thesis 和 frontier，合并后生成 B；B 显示旧生词，再收藏 retention；正式库三条，frontier 可保留两篇例句。
- 同一个同步包导入两次，词条和例句不重复。
- 取消 frontier 后再遇到旧快照，不自动复活已取消的收藏。
- 同步包属于另一学习库，提示用户而不静默混合。
- 缓存不可用仍可在本次会话收藏和导出，并提示及时保存。

浏览器机制参考：[localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)、[文件访问](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API)。需要无导出自动同步时，再按用户要求增加授权文件写入或应用连接；数据库本身不会建立同步通道。
