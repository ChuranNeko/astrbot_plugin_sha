from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import aiohttp


@register(
    "astrbot_plugin_sha",
    "IGCrystal",
    "获取GitHub仓库最后5次提交SHA的插件",
    "1.0.0",
    "https://github.com/IGCrystal-NEO/astrbot_plugin_sha",
)
class GitHubShaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        # 从配置获取仓库信息
        self.github_repo = self.config.get("github_repo", "AstrBotDevs/AstrBot")
        self.branch = self.config.get("branch", "master")
        self.commit_count = self.config.get("commit_count", 5)
        self.github_api_url = f"https://api.github.com/repos/{self.github_repo}/commits"

    @filter.command("sha")
    async def get_github_sha(self, event: AstrMessageEvent):
        """获取GitHub仓库指定分支的最新提交SHA"""
        try:
            # 检查是否使用默认配置，如果是则提醒用户
            if self.github_repo == "AstrBotDevs/AstrBot":
                reminder_msg = (
                    f"📌 当前使用默认仓库: {self.github_repo}\n"
                    "💡 提示: 可在插件管理页面配置其他GitHub仓库地址\n"
                    "格式: owner/repo (例如: microsoft/vscode)\n\n"
                )
                yield event.plain_result(reminder_msg)

            logger.info(f"开始获取 {self.github_repo} 仓库的提交SHA...")

            # 从GitHub API获取指定数量的提交
            async with aiohttp.ClientSession() as session:
                params = {
                    "sha": self.branch,  # 使用配置的分支
                    "per_page": self.commit_count,  # 使用配置的提交数量
                }

                async with session.get(self.github_api_url, params=params) as response:
                    if response.status == 200:
                        commits = await response.json()

                        if not commits:
                            yield event.plain_result("❌ 未找到任何提交记录")
                            return

                        # 构建回复消息
                        result_lines = [
                            f"🔍 {self.github_repo} 仓库 ({self.branch} 分支) 最后{self.commit_count}次提交 SHA：\n"
                        ]

                        for i, commit in enumerate(commits, 1):
                            sha = commit["sha"]  # 显示完整的SHA
                            message = commit["commit"]["message"].split("\n")[
                                0
                            ]  # 只取第一行提交信息
                            author = commit["commit"]["author"]["name"]
                            date = commit["commit"]["author"]["date"][
                                :10
                            ]  # 只取日期部分

                            result_lines.append(f"{i}. {sha} - {message}")
                            result_lines.append(f"   作者: {author} | 日期: {date}\n")

                        result_text = "\n".join(result_lines)
                        yield event.plain_result(result_text)

                        logger.info(f"成功获取 {self.github_repo} 的GitHub提交SHA")

                    else:
                        error_msg = f"GitHub API 请求失败，状态码: {response.status}"
                        logger.error(error_msg)
                        yield event.plain_result(f"❌ {error_msg}")

        except aiohttp.ClientError as e:
            error_msg = f"网络请求错误: {str(e)}"
            logger.error(error_msg)
            yield event.plain_result(f"❌ {error_msg}")

        except Exception as e:
            error_msg = f"获取提交SHA时发生错误: {str(e)}"
            logger.error(error_msg)
            yield event.plain_result(f"❌ {error_msg}")

    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info("GitHub SHA 插件已卸载")
