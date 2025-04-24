# LangBotYbProxyPlugin 插件

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![LangBot Version](https://img.shields.io/badge/LangBot-%3E%3D3.4-green)](https://github.com/RockChinQ/LangBot)

## 安装

配置完成 [LangBot主程序](https://github.com/RockChinQ/LangBot) 后，使用管理员账号向机器人发送命令：

```bash
!plugin get https://github.com/shinelin/LangBotYbProxyPlugin.git
```

**功能特性**
- ​智能消息队列管理​
- ​精准时间控制机制，可配置​（3秒活跃窗口 + 20秒总超时）
    - 基础流程里会说明
- ​自动错误恢复与重试​
- ​多场景支持​（群聊自动@回复 + 私聊直连）


**基础流程**
- 用户发送消息到机器人（群/私聊均可）
- 消息自动进入处理队列
- 机器人顺序转发给元宝账号(目前没想到别的场景)
- 元宝的回复自动返回原会话
    - 3秒活跃窗口: 元宝从第一次给你回复消息后，未来三秒回复的消息都是回给你。确保卡片信息是转给你。
    - 20秒总超时：20s内无论如何，你没到元宝回复，都会被踢出队列。

**配置示例**
先放在`main.py`里
```
YUANBAO_ID = "wxid_wi_1d142z0zdj03"
ACTIVE_WINDOW = 3  # 活跃窗口秒数
TOTAL_TIMEOUT = 20 # 总超时秒数
```

**致谢**
- 感谢*元宝*AI
- 感谢Deepseek
- Langbot作者的开源代码和文档


