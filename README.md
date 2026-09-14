# Index Progress Hub

一个面向多人协作的、只追加（append-only）的索引文档与进度仓库。每次上传都是一条新记录，已合并的记录不允许修改、重命名或删除。

## 设计目标

- 上传者只在自己的 `submissions/<GitHub 用户名>/` 目录中新增独立记录。
- 每条记录使用 `UTC 时间戳 + 随机后缀`，避免两人产生同一路径。
- Pull Request 校验拒绝覆盖、删除、跨用户目录提交和非法元数据。
- 合并后自动构建 `catalog` 分支的 `api/progress.json`，GPT 只需读取这一个稳定接口。
- 人类上传与 GPT 访问使用分离权限：上传者走 PR，GPT 仅使用 Contents 只读权限。

## 上传一条进度

1. 从 `main` 新建分支，例如 `upload/your-name/20260914-a`。
2. 在 `submissions/<你的 GitHub 用户名>/<record_id>/` 新建目录。
3. 复制 `examples/submission.json`，填写进度，并把文档放在同一目录。
4. 提交 Pull Request；等待 `Validate immutable submission` 通过后合并。

`record_id` 格式为 `YYYYMMDDTHHMMSSZ-8位小写十六进制数`，例如 `20260914T103000Z-9f4a2c1d`。详细见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## GPT 读取

GPT Action 配置位于 `gpt/openapi.yaml`，GPT 指令位于 `gpt/GPT_INSTRUCTIONS.md`。仓库是私有时，为 GPT 单独创建一个细粒度 GitHub token，仅授予本仓库 `Contents: Read-only`，不要复用你的个人全权限 token。

GPT 读取的稳定资源：

```text
GET https://api.github.com/repos/Richard0721/index-progress-hub/contents/api/progress.json?ref=catalog
Accept: application/vnd.github.raw+json
Authorization: Bearer <read-only token>
```

## 管理员设置

要把“不覆盖”变成强制规则，`main` 必须禁止直接 push，并要求 PR 的 `Validate immutable submission` 检查通过。当前仓库为私有且 GitHub 账户无 Pro，GitHub 不允许启用该规则。可选方案：

- 保持私有：升级 GitHub Pro，启用规则后再给成员 `Write` 权限。
- 改为公开：免费启用规则；上传者通过 fork + PR，无需给 `Write` 权限。

GitHub Project 看板不会自动授予仓库权限。
