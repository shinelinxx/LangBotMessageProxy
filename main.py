import asyncio
from datetime import datetime, timedelta
from collections import deque
from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.platform.types import MessageChain, Plain, At
from pkg.plugin.events import GroupNormalMessageReceived, PersonNormalMessageReceived

YUANBAO_ID = "wxid_wi_1d142z0zdj03" # yuanbao
ACTIVE_WINDOW = 3  # 活跃窗口秒数
TOTAL_TIMEOUT = 20 # 总超时秒数

@register(
    name="LangBotYbProxyPlugin",
    description="LangBot元宝代理插件",
    version="0.1",
    author="shinelin"
)
class LangBotYbProxyPlugin(BasePlugin):
    
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.message_queue = deque()  # (user_id, group_id, message, req_time)
        self.processing = {}  # user_id: (group_id, first_reply_time, last_reply_time)
        self.lock = asyncio.Lock()

    async def initialize(self):
        asyncio.create_task(self._queue_monitor())

    async def _queue_monitor(self):
        """队列状态监视器"""
        while True:
            async with self.lock:
                now = datetime.now()
                
                # 清理超时请求
                expired_users = [
                    uid for uid, (gid, first, last) in self.processing.items()
                    if (now - first).total_seconds() > TOTAL_TIMEOUT
                ]
                for uid in expired_users:
                    self.ap.logger.warning(f"总超时移除用户 [用户:{uid}]")
                    del self.processing[uid]

                # 处理队列前进条件
                if not self.processing and self.message_queue:
                    await self._process_next()
                
            await asyncio.sleep(1)

    async def _process_next(self):
        """处理下一条消息"""
        user_id, group_id, message, _ = self.message_queue.popleft()
        
        try:
            # 发送到元宝
            await self.host.send_active_message(
                adapter=self.host.get_platform_adapters()[0],
                target_type="person",
                target_id=YUANBAO_ID,
                message=message  # 修正参数名,文档不对。
            )
            self.ap.logger.info(f"已提交处理 [用户:{user_id}]")
            
            # 记录处理状态
            self.processing[user_id] = (
                group_id,
                datetime.now(),  # 首次处理时间
                datetime.now()   # 最后回复时间
            )
            
        except Exception as e:
            self.ap.logger.error(f"提交处理失败 [用户:{user_id}] 错误:{str(e)}")

    @handler(GroupNormalMessageReceived)
    async def handle_group_message(self, ctx: EventContext):
        """处理群消息"""
        try:
            group_id = ctx.event.query.message_event.group.id
            async with self.lock:
                self.message_queue.append((
                    ctx.event.sender_id,
                    group_id,
                    ctx.event.query.message_chain,
                    datetime.now()
                ))
                self.ap.logger.info(f"接收群消息 [队列:{len(self.message_queue)}]")
                
        except Exception as e:
            self.ap.logger.error(f"群消息接收异常: {str(e)}")
        finally:
            ctx.prevent_default()

    @handler(PersonNormalMessageReceived)
    async def handle_private_message(self, ctx: EventContext):
        """统一消息入口"""
        if ctx.event.sender_id == YUANBAO_ID:
            return await self._handle_yuanbao_reply(ctx)
            
        try:
            async with self.lock:
                self.message_queue.append((
                    ctx.event.sender_id,
                    None,
                    ctx.event.query.message_chain,
                    datetime.now()
                ))
                self.ap.logger.info(f"接收私聊消息 [用户:{ctx.event.sender_id}]")
                
        except Exception as e:
            self.ap.logger.error(f"私聊处理异常: {str(e)}")
        finally:
            ctx.prevent_default()

    async def _handle_yuanbao_reply(self, ctx: EventContext):
        """处理元宝回复"""
        try:
            current_user = next(iter(self.processing.keys()), None)
            if not current_user:
                self.ap.logger.warning("收到游离回复")
                return

            # 更新最后回复时间
            group_id, first_time, _ = self.processing[current_user]
            self.processing[current_user] = (group_id, first_time, datetime.now())
            self.ap.logger.debug(f"更新活跃时间 [用户:{current_user}]")

            # 转发回复
            reply = ctx.event.query.message_chain.copy()
            if group_id:
                reply.insert(0, At(target=current_user))
                
            await self.host.send_active_message(
                adapter=self.host.get_platform_adapters()[0],
                target_type="group" if group_id else "person",
                target_id=group_id or current_user,
                message=reply
            )
            self.ap.logger.info(f"成功投递回复 [用户:{current_user}]")

            # 检查活跃窗口
            async with self.lock:
                if (datetime.now() - self.processing[current_user][2]).total_seconds() > ACTIVE_WINDOW:
                    self.ap.logger.info(f"活跃窗口结束 [用户:{current_user}]")
                    del self.processing[current_user]
                    await self._process_next()
                    
        except Exception as e:
            self.ap.logger.error(f"回复处理失败: {str(e)}")
        finally:
            ctx.prevent_default()