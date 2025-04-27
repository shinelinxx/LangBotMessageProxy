import xml.etree.ElementTree as ET
from typing import Optional, Type
from pkg.platform.types import message as platform_message
from pkg.platform.types import MessageChain

class MsgTypeHandler:
    """消息处理器（支持动态扩展解析策略）"""
    
    def __init__(self, logger):
        self.logger = logger
        self._init_handlers()
        self._init_xml_parsers()

    def _init_handlers(self):
        """初始化消息类型处理器映射"""
        self.msg_handlers = {
            'Quote': self._handle_quote,
            'WeChatForwardImage': self._handle_wechat_forward_image,
            'WeChatForwardFile':  self._handle_wechat_forward_file,
            'Voice': self._handler_not_process
        }

    def _init_xml_parsers(self):
        """初始化XML标签解析器映射"""
        self.xml_parsers = {
            'appmsg': self._parse_appmsg,
            'img': self._parse_wechat_forward_image,
        }

    def process_message(self, message: MessageChain) -> MessageChain:
        """消息处理入口方法"""
        for msg_type, handler in self.msg_handlers.items():
            if message.has(getattr(platform_message, msg_type)):
                return handler(message)
        return self._handle_default(message)

    def _handle_quote(self, message: MessageChain) -> MessageChain:
        """处理引用消息（含XML嵌套结构）"""
        quote = message.get_first(platform_message.Quote)
        if not (quote and quote.origin):
            return MessageChain()
        if plain := quote.origin.get_first(platform_message.Plain):
            if not any(xml_word in plain.text 
                for xml_word in ["<xml", "<appmsg>", "<msg>"]):
                    # 引用是纯文本，这里要怎么弄，没想好
                return MessageChain([plain])
            return self._parse_xml_content(plain.text)
        return MessageChain()

    def _parse_xml_content(self, xml_str: str) -> MessageChain:
        """安全解析XML内容"""
        try:
            root = ET.fromstring(xml_str)
            for tag, parser in self.xml_parsers.items():
                if root.find(tag):
                    return parser(root)
        except ET.ParseError as e:
            self.logger.error(f"XML解析失败: {str(e)} {xml_str}")
        return MessageChain()

    def _parse_appmsg(self, element: ET.Element) -> MessageChain:
        """解析应用消息（支持多类型扩展）"""
        app_msg = element.find("appmsg")
        if app_msg:
            msg_type = app_msg.findtext("type")
            app_msg_str = ET.tostring(app_msg, encoding='unicode')
            xml_str = ET.tostring(element, encoding='unicode')
            if msg_type == "5":
                return MessageChain([platform_message.WeChatForwardLink(xml_data=xml_str)])
            if msg_type == "6":
                return MessageChain([platform_message.WeChatForwardFile(xml_data=xml_str)])
            return MessageChain([platform_message.WeChatAppMsg(app_msg=app_msg_str)])
        return MessageChain()

    def _parse_wechat_forward_image(self, element: ET.Element) -> MessageChain:
        """解析图片消息"""
        xml_str = ET.tostring(element, encoding='unicode')
        return MessageChain([platform_message.WeChatForwardImage(xml_data=xml_str)])

    def _handle_wechat_forward_image(self, message: MessageChain) -> MessageChain:
        """处理图片消息"""
        if image := message.get_first(platform_message.WeChatForwardImage):
            return MessageChain([image.__class__(xml_data=image.xml_data)])
        return MessageChain()

    def _handle_wechat_forward_file(self, message: MessageChain) -> MessageChain:
        """处理文件消息（留扩展点）"""
        if file := message.get_first(platform_message.WeChatForwardFile):
            return MessageChain([file.__class__(xml_data=file.xml_data)])
        return MessageChain()

    def _handle_default(self, message: MessageChain) -> MessageChain:
        """默认处理策略"""
        self.logger.info(f"普通消息: {str(message)}")
        return message.copy()
    
    def _handler_not_process(self, message: MessageChain) -> MessageChain:
        """默认不处理策略"""
        self.logger.info(f"不处理消息: {str(message)}")
        return MessageChain()
    
    def register_handler(self, msg_type: str, handler: callable):
        """动态注册消息处理器"""
        self.msg_handlers[msg_type] = handler

    def register_xml_parser(self, tag: str, parser: callable):
        """动态注册XML解析器"""
        self.xml_parsers[tag] = parser