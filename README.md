<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_sha?name=astrbot_plugin_sha&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_sha

![Python Versions](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10-blue)
![License](https://img.shields.io/github/license/ChuranNeko/astrbot_plugin_sha)
![Version](https://img.shields.io/badge/version-1.4.1-green)

</div>


## 功能简介

基于原仓库 [IGCrystal-NEO/astrbot_plugin_sha](https://github.com/IGCrystal-NEO/astrbot_plugin_sha) 的 fork 版本，提供以下功能：

- **SHA 查询**
  - 命令触发：`/sha` 或唤醒后包含 `hash` 关键词
  - 显示指定仓库最近 N 次提交的完整 SHA、提交信息、作者和日期
  
- **自动审阅加群**（QQ 群专用）
  - 自动处理入群申请，验证用户提交的 GitHub SHA 前缀
  - 支持错误次数限制（每日重置）
  - 支持黑名单过滤
  - 需机器人为群管理员或群主
  
- **默认仓库**：`AstrBotDevs/AstrBot`（可在 WebUI 自定义配置）

## 安装

在 Astrbot 插件商店搜索 `astrbot_plugin_sha` 进行安装(推荐方式)。

或自己 clone 此仓库到 Astrbot 插件目录：

```
git clone https://github.com/ChuranNeko/astrbot_plugin_sha /data/plugins
```


## 配置

本插件支持在 WebUI 插件管理页面修改配置，配置项说明如下：

### 基础配置
- **`github_repo`** (string)：GitHub 仓库地址，格式 `owner/repo`
  - 默认：`AstrBotDevs/AstrBot`
  - 示例：`microsoft/vscode`
  
- **`branch`** (string)：分支名称
  - 默认：`master`
  - 示例：`main`、`dev`
  
- **`commit_count`** (int)：获取的提交数量
  - 默认：`5`
  - 范围：建议 1-10

- **`enabled_groups`** (array)：启用自动审阅的群组 ID 列表（白名单）
  - 默认：`[]`（空数组表示所有群组）
  - 示例：`["123456789", "1145235245"]`

### 审阅加群配置
- **`auto_review_on_request`** (bool)：是否自动审阅入群申请(需要提前在webui配置好需要启用的群组)
  - 默认：`true`
  
- **`enabled_groups`** (array)：启用自动审阅的群组 ID 列表（白名单）
  - 默认：`[]`（空数组表示所有群组）
  - 示例：`["123456789", "987654321"]`
  
- **`max_attempts`** (int)：每日最大错误尝试次数
  - 默认：`3`
  - 设置为 `0` 表示不限制
  
- **`reset_hour`** (int)：每日错误计数重置时间（小时，0-23）
  - 默认：`4`（凌晨 4 点）
  - 设置为 `-1` 禁用自动重置

**说明**：使用默认仓库时，触发 `/sha` 命令会提示可在插件管理页面自定义配置。

## 使用说明

### SHA 查询
在任意支持的平台发送以下指令：
- **命令方式**：`/sha`
- **关键词方式**：唤醒机器人后发送包含 `hash` 的消息

**返回内容**：
- 完整 40 位 SHA 值
- 提交信息首行
- 作者名称
- 提交日期（UTC 格式前 10 位）

### 自动审阅加群（QQ 群专用）

**工作原理**：
1. 用户申请加群时在验证信息中填写 GitHub SHA 前缀（至少 7 位）
2. 插件自动获取配置仓库的最近提交列表
3. 验证用户提交的 SHA 是否匹配（大小写不敏感）
4. 匹配成功则批准，失败则拒绝并提示

**错误限制机制**：
- 每个用户每日有最多 `max_attempts` 次错误机会
- 达到上限后当日无法再次申请，会收到"请明天再来答题"的提示
- 每日 `reset_hour` 时刻自动重置错误计数

**黑名单功能**：
- 位于 `reject_ids` 中的用户会被自动跳过，不进行审阅

**前置条件**：
- 机器人必须是群管理员或群主
- 群组在 `enabled_groups` 白名单中（若配置了白名单）
- `auto_review_on_request` 设置为 `true`

## 注意事项

- **平台限制**：自动审阅加群功能仅支持 QQ 群聊（基于 OneBot 协议）
- **权限要求**：机器人必须拥有群管理员或群主权限
- **API 限制**：GitHub API 匿名访问有速率限制（60 次/小时），高频使用建议配置 GitHub Token
- **消息长度**：部分平台对消息长度有限制，`commit_count` 过大可能导致消息被截断
- **数据持久化**：
  - 待审请求缓存 48 小时自动过期
  - 错误计数数据每日自动清理旧数据

## FAQ

### Q: 为什么没有自动审阅加群申请？
**A**: 请检查以下几点：
- 机器人是否为群管理员或群主
- `auto_review_on_request` 是否设置为 `true`
- 群组是否在 `enabled_groups` 白名单中（若配置了白名单）
- 机器人是否正常连接到 QQ

### Q: 用户验证 SHA 总是失败？
**A**: 可能的原因：
- 验证信息中的 SHA 前缀长度不足 7 位
- 仓库或分支配置错误，使用 `/sha` 命令验证配置是否正确
- GitHub API 速率限制导致获取失败，稍后重试
- SHA 前缀不在配置的 `commit_count` 范围内

### Q: 用户提示"今日错误次数已达上限"？
**A**: 用户当日已达到 `max_attempts` 配置的错误次数限制，需等待每日 `reset_hour` 时刻自动重置

### Q: 如何管理黑名单？
**A**: 黑名单数据存储在 `data/astrbot_plugin_sha/group_join_data.json` 文件中，格式如下：
```json
{
  "reject_ids": {
    "群号": ["用户QQ号1", "用户QQ号2"]
  }
}
```

## 版本信息

- **当前版本**：v1.4.1
- **Fork 自**：[IGCrystal-NEO/astrbot_plugin_sha](https://github.com/IGCrystal-NEO/astrbot_plugin_sha)
- **当前仓库**：[ChuranNeko/astrbot_plugin_sha](https://github.com/ChuranNeko/astrbot_plugin_sha)

## License

本项目采用与原仓库相同的开源协议。
