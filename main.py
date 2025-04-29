import asyncio
from datetime import datetime, timedelta
from collections import deque
from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.platform.types import MessageChain, Plain, At
from pkg.plugin.events import GroupNormalMessageReceived, PersonNormalMessageReceived
from pkg.platform.types import message as platform_message
import xml.etree.ElementTree as ET
import yaml, os
from typing import List, Optional, Type
@register(
    name="LangBotMessageProxy",
    description="Langbot消息传话筒",
    version="0.3",
    author="shinelinxx"
)
class LangBotMessageProxy(BasePlugin):
    
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.message_queue = deque()  # (user_id, group_id, message, req_time)
        self.processing = {}  # user_id: (group_id, first_reply_time, last_reply_time)
        self.lock = asyncio.Lock()
        self.config = self._load_config()
        # 第三者接收的消息类型
        self._other_accept_msg_type = [
            platform_message.WeChatForwardLink,
            platform_message.WeChatAppMsg,
            platform_message.WeChatForwardImage,
            platform_message.WeChatForwardFile,
        ]
        # 第三者回复的保留的消息类型
        self._other_reply_msg_type = [
            platform_message.WeChatForwardLink,
            platform_message.Plain,
        ]

    def _load_config(self):
        """优先加载config.yml，不存在则使用config-template.yml"""
        config_files = ['config.yml', 'config-template.yml']
        for file in config_files:
            path = os.path.join(os.path.dirname(__file__), file)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
        raise FileNotFoundError(f"config is not valid")

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
                    if (now - first).total_seconds() > self.config["TOTAL_TIMEOUT"]
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
            # 发送到第三者
            await self.host.send_active_message(
                adapter=self.host.get_platform_adapters()[0],
                target_type="person",
                target_id=self.config["OTHER_ID"],
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


    def _process_msg_filter(
            self, 
            message_chain: Optional[platform_message.MessageChain],
            filter: List[Type[platform_message.MessageComponent]],
            )->platform_message.MessageChain:
        if message_chain is None:
            return platform_message.MessageChain()
        message_list = []
        for component in message_chain:
            if isinstance(component, platform_message.Quote):
                for item in component.origin:
                    if type(item) in filter:
                        message_list.append(item)
            elif type(component) in filter:
                message_list.append(component)
        return platform_message.MessageChain(message_list)

    async def _handle_other_reply(self, ctx: EventContext):
        """处理第三者回复"""
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
                message= self._process_msg_filter(reply, self._other_reply_msg_type)
            )
            self.ap.logger.info(f"成功投递回复 [用户:{current_user}]")

            # 检查活跃窗口
            async with self.lock:
                if (datetime.now() - self.processing[current_user][2]).total_seconds() > self.config["ACTIVE_WINDOW"]:
                    self.ap.logger.info(f"活跃窗口结束 [用户:{current_user}]")
                    del self.processing[current_user]
                    await self._process_next()
                    
        except Exception as e:
            self.ap.logger.error(f"回复处理失败: {str(e)}")
        finally:
            ctx.prevent_default()

@handler(GroupNormalMessageReceived)
async def handle_group_message(self, ctx: EventContext):
    """处理群消息"""
    try:
        group_id = None \
            if ctx.event.launcher_id == ctx.event.sender_id \
                else ctx.event.launcher_id
        
        # 机器人接收的消息处理
        if ctx.event.sender_id != self.config["OTHER_ID"]:
            # 提取消息
            send_to_other_message = self._process_msg_filter(
                ctx.event.query.message_chain,
                self._other_accept_msg_type
            )
            
            # 仅当包含目标类型时处理
            if len(send_to_other_message) > 0:
                async with self.lock:
                    self.message_queue.append((
                        ctx.event.sender_id,
                        group_id,
                        send_to_other_message,
                        datetime.now()
                    ))
                    self.ap.logger.info(f"接收群消息 [队列:{len(self.message_queue)}]")
                    ctx.prevent_default()  # 阻断默认行为
    except Exception as e:
        self.ap.logger.error(f"群消息接收异常: {str(e)}")

@handler(PersonNormalMessageReceived)
async def handle_private_message(self, ctx: EventContext):
    """统一消息入口"""
    try:
        if ctx.event.sender_id == self.config["OTHER_ID"]:
            return await self._handle_other_reply(ctx)
        
        # 机器人接收的消息处理
        if ctx.event.sender_id != self.config["OTHER_ID"]:
            # 提取消息
            send_to_other_message = self._process_msg_filter(
                ctx.event.query.message_chain,
                self._other_accept_msg_type
            )
            # 仅当包含目标类型时处理
            if len(send_to_other_message) > 0:
                async with self.lock:
                    self.message_queue.append((
                        ctx.event.sender_id,
                        None,
                        send_to_other_message,
                        datetime.now()
                    ))
                    self.ap.logger.info(f"接收私聊消息 [用户:{ctx.event.sender_id}]")
                    ctx.prevent_default()  # 阻断默认行为

    except Exception as e:
        self.ap.logger.error(f"私聊处理异常: {str(e)}, line:{e.__traceback__.tb_lineno}")