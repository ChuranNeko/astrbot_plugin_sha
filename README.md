# astrbot_plugin_sha

获取任意 GitHub 仓库指定分支最近 N 次提交的完整 SHA，并发送到会话中。

- **触发指令**: `/sha`（需严格匹配，仅此一个词）
- **默认仓库**: `AstrBotDevs/AstrBot`（未配置时会提示可在 WebUI 修改）
- **显示内容**: 完整 SHA、提交信息首行、作者、日期

## 安装

复制本仓库链接安装

## 配置（WebUI 可视化）
本插件支持在 WebUI 中修改配置，Schema 位于 `_conf_schema.json`：

- `github_repo` (string): 仓库地址，格式 `owner/repo`，示例 `microsoft/vscode`。默认 `AstrBotDevs/AstrBot`。
- `branch` (string): 分支名，示例 `master`、`main`，默认 `master`。
- `commit_count` (int): 拉取的提交数量，默认 `5`（建议 1-10）。

说明：若保持默认仓库，触发指令时会先在会话中提示“可在插件管理页面配置仓库”。

## 使用
- 在任意支持的平台发送：`/sha`
- 机器人将返回配置的仓库、分支下最近 N 条提交，包含：
  - 完整 40 位 SHA
  - 提交信息首行
  - 作者与日期（UTC 日期的前 10 位）

## 注意事项
- GitHub API 匿名访问存在速率限制；在高频使用场景请注意控制调用频率或配置网络代理。
- 部分平台对消息长度有上限，若 `commit_count` 过大可能导致消息过长。
