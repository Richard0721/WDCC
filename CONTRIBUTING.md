# 上传索引文档

## 目录约定

每次上传必须创建新目录：

```text
submissions/<github-user>/<record-id>/
  submission.json
  <one-or-more source files>
```

不得修改、重命名或删除已合并的 `submissions/` 文件。更新进度时创建一条新记录，历史记录保留。

## 生成 record-id

PowerShell 示例：

```powershell
$recordId = "$(Get-Date -AsUTC -Format 'yyyyMMddTHHmmssZ')-$(-join ((0..7) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) }))"
$recordId
```

## submission.json

参考 `examples/submission.json`。字段含义：

- `record_id`：必须与目录名一致。
- `index_name`：索引/任务的稳定名称；同一索引的多次进度使用相同名称。
- `status`：`not_started`、`in_progress`、`blocked` 或 `complete`。
- `progress_percent`：0–100 整数。
- `updated_at`：UTC ISO 8601 时间。
- `submitted_by`：PR 发起人的 GitHub 用户名。
- `summary`：给 GPT 阅读的简短进度说明。
- `source_files`：同目录下的文档文件名列表。

允许格式：`.json`、`.csv`、`.tsv`、`.md`、`.txt`、`.xlsx`、`.xls`、`.pdf` 和 `.docx`。单文件最大 25 MiB，单条记录最大 50 MiB。为了让 GPT 直接理解文档内容，优先使用 CSV、Markdown 或 JSON。

## Pull Request

- 一个 PR 可以新增多条记录，但只能位于发起人自己的目录中。
- 如果另一个 PR 先合并，请先更新当前分支再合并。
- 只有校验通过的 PR 才可合并。
