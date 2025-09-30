import aiohttp
import ssl
import certifi
import re
import os
import json
import time
import random
import asyncio
from datetime import datetime
from typing import List, Dict, Any

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


@register(
    "astrbot_plugin_sha",
    "ChuranNeko",
    "获取GitHub仓库最后5次提交SHA的插件",
    "1.4.1",
    "https://github.com/IGCrystal-NEO/astrbot_plugin_sha",
)

class GitHubShaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._pending_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._data_dir = str(StarTools.get_data_dir("astrbot_plugin_sha"))
        self._pending_path = os.path.join(self._data_dir, "pending_group_requests.json")
        self._error_count_path = os.path.join(self._data_dir, "error_counts.json")
        self._error_counts: Dict[str, Dict[str, Dict[str, int]]] = {}
        self._reset_task: asyncio.Task | None = None
        self._last_reset_date: str = ""

    async def initialize(self):
        try:
            os.makedirs(self._data_dir, exist_ok=True)
            if os.path.exists(self._pending_path):
                with open(self._pending_path, "r", encoding="utf-8") as f:
                    self._pending_cache = json.load(f)
            
            # 加载错误次数数据
            if os.path.exists(self._error_count_path):
                with open(self._error_count_path, "r", encoding="utf-8") as f:
                    self._error_counts = json.load(f)
            
            # 启动定时重置任务
            reset_hour = self.config.get("reset_hour", 4)
            if reset_hour >= 0:
                self._reset_task = asyncio.create_task(self._reset_scheduler())
                logger.info(f"[审阅加群] 已启动定时重置任务，重置时间：每日 {reset_hour}:00")
        except Exception as e:
            logger.error(f"[审阅加群] 加载待审缓存失败: {e}")

    def _save_pending_cache(self) -> None:
        try:
            with open(self._pending_path, "w", encoding="utf-8") as f:
                json.dump(self._pending_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[审阅加群] 保存待审缓存失败: {e}")
    
    def _save_error_counts(self) -> None:
        """保存错误次数数据到文件"""
        try:
            with open(self._error_count_path, "w", encoding="utf-8") as f:
                json.dump(self._error_counts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[审阅加群] 保存错误次数数据失败: {e}")
    
    def _get_today_date(self) -> str:
        """获取今天的日期字符串 (YYYY-MM-DD)"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_error_count(self, group_id: str, user_id: str) -> int:
        """获取用户今日的错误次数"""
        today = self._get_today_date()
        return self._error_counts.get(str(group_id), {}).get(str(user_id), {}).get(today, 0)
    
    def _increment_error_count(self, group_id: str, user_id: str) -> int:
        """增加用户今日的错误次数,返回增加后的次数"""
        today = self._get_today_date()
        group_id = str(group_id)
        user_id = str(user_id)
        
        if group_id not in self._error_counts:
            self._error_counts[group_id] = {}
        if user_id not in self._error_counts[group_id]:
            self._error_counts[group_id][user_id] = {}
        
        current = self._error_counts[group_id][user_id].get(today, 0)
        self._error_counts[group_id][user_id][today] = current + 1
        self._save_error_counts()
        return current + 1
    
    def _is_over_max_attempts(self, group_id: str, user_id: str) -> bool:
        """检查用户今日是否已超过最大错误次数"""
        max_attempts = self.config.get("max_attempts", 3)
        if max_attempts <= 0:
            return False  # 0表示不限制
        
        current_count = self._get_error_count(group_id, user_id)
        return current_count >= max_attempts
    
    async def _reset_scheduler(self) -> None:
        """定时重置任务,每日指定时间重置所有用户的错误次数"""
        while True:
            try:
                reset_hour = self.config.get("reset_hour", 4)
                if reset_hour < 0:
                    logger.info("[审阅加群] 重置时间设置为 -1,停止定时重置任务")
                    break
                
                now = datetime.now()
                today_reset_time = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
                
                # 如果今天的重置时间已过,计算到明天的重置时间
                if now >= today_reset_time:
                    from datetime import timedelta
                    tomorrow_reset_time = today_reset_time + timedelta(days=1)
                    wait_seconds = (tomorrow_reset_time - now).total_seconds()
                else:
                    wait_seconds = (today_reset_time - now).total_seconds()
                
                logger.info(f"[审阅加群] 下次重置时间: {wait_seconds / 3600:.2f} 小时后")
                await asyncio.sleep(wait_seconds)
                
                # 执行重置
                today = self._get_today_date()
                if today != self._last_reset_date:
                    logger.info(f"[审阅加群] 开始重置错误次数计数器 (日期: {today})")
                    # 清空所有旧日期的数据
                    for group_id in list(self._error_counts.keys()):
                        for user_id in list(self._error_counts[group_id].keys()):
                            # 只保留今天的数据
                            user_data = self._error_counts[group_id][user_id]
                            self._error_counts[group_id][user_id] = {
                                k: v for k, v in user_data.items() if k == today
                            }
                            # 如果用户没有今天的数据,删除该用户
                            if not self._error_counts[group_id][user_id]:
                                del self._error_counts[group_id][user_id]
                        # 如果群组没有用户,删除该群组
                        if not self._error_counts[group_id]:
                            del self._error_counts[group_id]
                    
                    self._save_error_counts()
                    self._last_reset_date = today
                    logger.info("[审阅加群] 错误次数计数器重置完成")
                
            except asyncio.CancelledError:
                logger.info("[审阅加群] 定时重置任务已取消")
                break
            except Exception as e:
                logger.error(f"[审阅加群] 定时重置任务异常: {e}")
                await asyncio.sleep(3600)  # 出错后等待1小时再试

    def _remember_request(self, group_id: str, user_id: str, flag: str, sub_type: str, comment: str) -> None:
        group_id = str(group_id)
        user_id = str(user_id)
        self._pending_cache.setdefault(group_id, {})[user_id] = {
            "flag": flag,
            "sub_type": sub_type,
            "comment": comment or "",
            "ts": int(time.time()),
        }

        expire_before = int(time.time()) - 48 * 3600
        for gid in list(self._pending_cache.keys()):
            for uid in list(self._pending_cache[gid].keys()):
                if int(self._pending_cache[gid][uid].get("ts", 0)) < expire_before:
                    del self._pending_cache[gid][uid]
            if not self._pending_cache[gid]:
                del self._pending_cache[gid]
        self._save_pending_cache()

    def _get_cached_request(self, group_id: str, user_id: str) -> Dict[str, Any] | None:
        return self._pending_cache.get(str(group_id), {}).get(str(user_id))

    def _group_join_data_path(self) -> str:
        return os.path.join(str(StarTools.get_data_dir("astrbot_plugin_sha")), "group_join_data.json")

    def _load_group_join_blacklist(self) -> Dict[str, Any]:
        try:
            path = self._group_join_data_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data or {}
        except Exception as e:
            logger.error(f"[审阅加群] 读取黑名单失败: {e}")
        return {}

    def _is_blacklisted(self, group_id: str, user_id: str) -> bool:
        data = self._load_group_join_blacklist()
        reject_ids: Dict[str, List[str]] = data.get("reject_ids", {})
        group_list = reject_ids.get(str(group_id), []) or []
        return str(user_id) in {str(x) for x in group_list}

    def _get_repo_cfg(self) -> tuple[str, str, int]:
        github_repo = self.config.get("github_repo", "AstrBotDevs/AstrBot")
        branch = self.config.get("branch", "master")
        commit_count = self.config.get("commit_count", 5)
        return github_repo, branch, commit_count

    def _is_group_admin(self, event: AiocqhttpMessageEvent, group) -> bool:
        if not group:
            return False
        self_id = str(event.get_self_id())
        admin_ids = [str(x) for x in (group.group_admins or [])]
        owner_id = str(group.group_owner) if group.group_owner else None
        return self_id in admin_ids or (owner_id and self_id == owner_id)

    @staticmethod
    def _match_sha_prefixes(candidates: List[str], recent_shas: List[str]) -> tuple[bool, str | None]:
        for cand in candidates:
            if len(cand) >= 7 and any(s.startswith(cand) for s in recent_shas):
                return True, cand
        return False, None

    def _format_summary(self, approved: int, rejected: int, skipped_blacklist: int, details: List[str]) -> str:
        if approved == 0 and rejected == 0:
            if details:
                return "\n".join(details)
            msg = "没有可审阅的加群申请"
            if skipped_blacklist:
                msg += f"（含黑名单跳过 {skipped_blacklist} 项）"
            return msg
        prefix = f"审阅完成：批准 {approved} 项，拒绝 {rejected} 项"
        if skipped_blacklist:
            prefix += f"，跳过 {skipped_blacklist} 项（黑名单）"
        return prefix + ("\n" + "\n".join(details) if details else "")

    async def _review_request_core(
        self,
        event: AiocqhttpMessageEvent,
        group_id: str,
        user_id: str | None,
        flag: str | None,
        sub_type: str,
        comment: str,
        recent_shas: List[str],
    ) -> Dict[str, Any]:
        """
        统一的单条请求审阅流程，供自动/手动复用。

        返回：
          {
            'outcome': 'approved'|'rejected'|'no_flag'|'skipped_blacklist'|'over_limit'|'error',
            'matched_prefix': str|None,
            'message': str  # 可用于输出的明细行（部分 outcome 可能为空）
            'error_count': int  # 当前错误次数
          }
        """

        if user_id and self._is_blacklisted(group_id, user_id):
            return {"outcome": "skipped_blacklist", "matched_prefix": None, "message": "", "error_count": 0}

        # 先检查用户今日是否已超过错误上限 (不是刚好达到,而是已经超过)
        if user_id and self._is_over_max_attempts(group_id, user_id):
            # 已经超过上限,需要拒绝请求并设置拒绝理由
            if flag:
                try:
                    await event.bot.set_group_add_request(
                        flag=str(flag),
                        sub_type=sub_type or "add",
                        approve=False,
                        reason="请明天再来答题哦"
                    )
                except Exception as e:
                    logger.error(f"拒绝超限用户失败 user={user_id}, flag={flag}: {e}")
            
            return {
                "outcome": "over_limit",
                "matched_prefix": None,
                "message": f"{user_id}: 今日错误次数已达上限,已静默拒绝",
                "error_count": self._get_error_count(group_id, user_id)
            }

        if not flag:
            return {
                "outcome": "no_flag",
                "matched_prefix": None,
                "message": f"{user_id}: 申请缺少凭据，无法处理",
                "error_count": 0
            }

        sha_candidates = self._extract_sha_candidates(comment)
        matched, matched_prefix = self._match_sha_prefixes(sha_candidates, recent_shas)

        try:
            reject_no_sha_msgs = [
                "不对哦，再好好想想吧～不知道的话可以去 GitHub 看看哦",
                "还差点意思呢，去 GitHub 检查一下再来试试吧～",
                "没看到像提交号的东西呢，去 GitHub 检查一下再来叭～",
            ]
            reject_mismatch_msgs = [
                "看起来不是最新提交的呢，再核对一下吧～",
                "好像对不上最新提交耶，确认下再试～",
            ]

            if matched and matched_prefix:
                reason_text = ""
            else:
                reason_text = (
                    random.choice(reject_no_sha_msgs)
                    if not sha_candidates
                    else random.choice(reject_mismatch_msgs)
                )

            await event.bot.set_group_add_request(
                flag=str(flag),
                sub_type=sub_type or "add",
                approve=matched,
                reason=reason_text,
            )
            
            if matched:
                return {
                    "outcome": "approved",
                    "matched_prefix": matched_prefix,
                    "message": f"{user_id}: 已批准 (匹配 {matched_prefix})",
                    "error_count": 0
                }
            else:
                # 回答错误,增加错误次数
                if user_id:
                    error_count = self._increment_error_count(group_id, user_id)
                    max_attempts = self.config.get("max_attempts", 3)
                    
                    # 检查是否刚好达到上限(这是最后一次机会)
                    if max_attempts > 0 and error_count == max_attempts:
                        return {
                            "outcome": "rejected_final",  # 新状态: 最后一次拒绝,需要发送特殊消息
                            "matched_prefix": matched_prefix,
                            "message": f"{user_id}: 已拒绝 (达到错误上限)",
                            "error_count": error_count
                        }
                else:
                    error_count = 0
                
                return {
                    "outcome": "rejected",
                    "matched_prefix": matched_prefix,
                    "message": f"{user_id}: 已拒绝 (未匹配)",
                    "error_count": error_count
                }
        except Exception as e:
            logger.error(f"处理申请失败 user={user_id}, flag={flag}: {e}")
            return {
                "outcome": "error",
                "matched_prefix": matched_prefix,
                "message": f"{user_id}: 处理失败",
                "error_count": 0
            }

    @filter.regex(r"(?i)\bhash\b")
    async def on_hash_keyword(self, event: AstrMessageEvent):
        """全局监听：消息包含单词 'hash' 时触发（不依赖唤醒前缀）"""
        async for res in self.get_github_sha(event):
            yield res

    @filter.command("sha")
    async def get_github_sha(self, event: AstrMessageEvent):
        """获取GitHub仓库指定分支的最新提交SHA"""
        try:
            github_repo, branch, commit_count = self._get_repo_cfg()
            github_api_url = f"https://api.github.com/repos/{github_repo}/commits"

            if github_repo == "AstrBotDevs/AstrBot":
                reminder_msg = (
                    f"📌 当前使用默认仓库: {github_repo}\n"
                    "💡 提示: 可在插件管理页面配置其他GitHub仓库地址\n"
                    "格式: owner/repo (例如: microsoft/vscode)"
                )
                yield event.plain_result(reminder_msg)

            logger.debug(f"开始获取 {github_repo} 仓库的提交SHA...")

            ssl_ctx = ssl.create_default_context(cafile=certifi.where())

            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                params = {"sha": branch, "per_page": commit_count}

                async with session.get(github_api_url, params=params) as response:
                    if response.status == 200:
                        commits = await response.json()

                        if not commits:
                            yield event.plain_result("❌ 未找到任何提交记录")
                            return

                        result_lines = [
                            f"🔍 {github_repo} 仓库 ({branch} 分支) 最后{commit_count}次提交 SHA：\n"
                        ]

                        for i, commit in enumerate(commits, 1):
                            sha = commit["sha"]
                            message = commit["commit"]["message"].split("\n")[
                                0
                            ]
                            author = commit["commit"]["author"]["name"]
                            date = commit["commit"]["author"]["date"][
                                :10
                            ]

                            result_lines.append(f"{i}. {sha} - {message}")
                            result_lines.append(f"   作者: {author} | 日期: {date}\n")

                        result_text = "\n".join(result_lines)
                        yield event.plain_result(result_text)

                        logger.debug(f"成功获取 {github_repo} 的GitHub提交SHA")

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

    async def _fetch_recent_commit_shas(self) -> List[str]:
        """返回最近配置数量的提交 SHA 列表（完整 40 位）。"""
        github_repo = self.config.get("github_repo", "AstrBotDevs/AstrBot")
        branch = self.config.get("branch", "master")
        commit_count = self.config.get("commit_count", 5)
        github_api_url = f"https://api.github.com/repos/{github_repo}/commits"

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            params = {"sha": branch, "per_page": commit_count}
            async with session.get(github_api_url, params=params) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"GitHub API 请求失败，状态码: {response.status}"
                    )
                commits = await response.json()
                return [c["sha"] for c in commits if "sha" in c]

    @staticmethod
    def _extract_sha_candidates(text: str) -> List[str]:
        """从文本中提取可能的 SHA 前缀（至少7位）。"""
        if not text:
            return []
        candidates = re.findall(r"\b[a-fA-F0-9]{7,40}\b", text)

        dedup = []
        for c in candidates:
            c = c.lower()
            if c not in dedup:
                dedup.append(c)
        return dedup

    # 已移除手动"审阅加群"命令，所有加群请求通过自动审阅处理

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.ALL, priority=1)
    async def capture_group_add_requests(self, event: AiocqhttpMessageEvent):
        """监听 OneBot 请求事件，缓存 flag 以便离线审批。"""
        try:
            raw = getattr(event.message_obj, "raw_message", None)
            if not isinstance(raw, dict):
                return
            if raw.get("post_type") != "request" or raw.get("request_type") != "group":
                return
            sub_type = raw.get("sub_type") or "add"
            if sub_type not in {"add", "invite"}:
                return
            group_id = raw.get("group_id")
            user_id = raw.get("user_id")
            flag = raw.get("flag")
            comment = raw.get("comment") or ""
            if group_id and user_id and flag:
                self._remember_request(str(group_id), str(user_id), str(flag), str(sub_type), str(comment))
                logger.debug(
                    f"[审阅加群] 缓存请求: group_id={group_id}, user_id={user_id}, sub_type={sub_type}, flag_len={len(str(flag))}"
                )

                if bool(self.config.get("auto_review_on_request", True)):
                    try:
                        # 检查群聊白名单
                        enabled_groups = self.config.get("enabled_groups", [])
                        if enabled_groups and str(group_id) not in [str(g) for g in enabled_groups]:
                            logger.debug(
                                f"[审阅加群] auto-skip (not in enabled_groups) group_id={group_id}"
                            )
                            return

                        group = await event.get_group(group_id=str(group_id))
                        if not self._is_group_admin(event, group):
                            logger.debug(
                                f"[审阅加群] auto-skip (not admin) group_id={group_id}, user_id={user_id}"
                            )
                            return

                        if self._is_blacklisted(str(group_id), str(user_id)):
                            logger.debug(
                                f"[审阅加群] auto-skip (blacklist) group_id={group_id}, user_id={user_id}"
                            )
                            return

                        recent_shas = [s.lower() for s in await self._fetch_recent_commit_shas()]
                        outcome = await self._review_request_core(
                            event=event,
                            group_id=str(group_id),
                            user_id=str(user_id),
                            flag=str(flag),
                            sub_type=sub_type,
                            comment=str(comment),
                            recent_shas=recent_shas,
                        )

                        gid = str(group_id)
                        uid = str(user_id)
                        if gid in self._pending_cache and uid in self._pending_cache[gid]:
                            del self._pending_cache[gid][uid]
                            self._save_pending_cache()

                        try:
                            avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=100"
                            
                            if outcome["outcome"] == "over_limit":
                                # 已经超过错误次数上限,静默拒绝,不发送任何消息
                                logger.info(f"[审阅加群] 用户 {user_id} 已超过错误上限,静默拒绝")
                            elif outcome["outcome"] == "rejected_final":
                                # 最后一次错误(刚好达到上限),发送特殊提示消息
                                error_count = outcome.get("error_count", 0)
                                notice = f"[CQ:image,file={avatar_url}]\n用户 {user_id} 已经连续{error_count}次回答错误啦，这个笨蛋今天进不了这个群啦"
                                await event.bot.send_group_msg(group_id=gid, message=notice)
                                logger.info(f"[审阅加群] 用户 {user_id} 达到错误上限 ({error_count}次)")
                            elif outcome["outcome"] == "approved":
                                # 通过申请
                                matched = outcome.get("matched_prefix") or ""
                                notice = (
                                    f"审阅结果：已通过用户 {user_id} 的加群申请"
                                    + (f"（匹配提交 {matched[:7]}）" if matched else "")
                                    + "，欢迎加入！"
                                )
                                message_with_avatar = f"[CQ:image,file={avatar_url}]\n{notice}"
                                await event.bot.send_group_msg(group_id=gid, message=message_with_avatar)
                            elif outcome["outcome"] == "rejected":
                                # 拒绝申请,显示当前错误次数和剩余机会
                                error_count = outcome.get("error_count", 0)
                                max_attempts = self.config.get("max_attempts", 3)
                                attempts_info = ""
                                if max_attempts > 0:
                                    remaining = max_attempts - error_count
                                    if remaining > 0:
                                        attempts_info = f"\n剩余尝试机会：{remaining}次"
                                
                                notice = (
                                    f"审阅结果：已拒绝用户 {user_id} 的加群申请\n"
                                    f"{(comment or '').strip() or '无'}"
                                    f"{attempts_info}"
                                )
                                message_with_avatar = f"[CQ:image,file={avatar_url}]\n{notice}"
                                await event.bot.send_group_msg(group_id=gid, message=message_with_avatar)

                        except Exception as e:
                            logger.error(f"[审阅加群] 发送群内通知失败 group_id={group_id}, user_id={user_id}: {e}")

                        logger.debug(f"[审阅加群] auto-processed outcome={outcome['outcome']} group_id={group_id}, user_id={user_id}")
                    except Exception as e:
                        logger.error(f"[审阅加群] auto-review 异常: {e}")
        except Exception as e:
            logger.error(f"[审阅加群] capture_group_add_requests 异常: {e}")

    async def terminate(self):
        """插件卸载时的清理工作"""
        if self._reset_task and not self._reset_task.done():
            self._reset_task.cancel()
            try:
                await self._reset_task
            except asyncio.CancelledError:
                pass
            logger.info("[审阅加群] 已取消定时重置任务")
        logger.info("GitHub SHA 插件已卸载")
