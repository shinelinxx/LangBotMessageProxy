# LangBotMessageProxy 插件

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![LangBot Version](https://img.shields.io/badge/LangBot-%3E%3D3.4-green)](https://github.com/RockChinQ/LangBot)

## 安装

配置完成 [LangBot主程序](https://github.com/RockChinQ/LangBot) 后，使用管理员账号向机器人发送命令：

```bash
!plugin get https://github.com/shinelin/LangBotMessageProxy.git
```

**功能特性**
- ​智能消息队列管理​
- ​精准时间控制机制，可配置​（3秒活跃窗口 + 20秒总超时）
- ​自动错误恢复与重试​
- ​多场景支持​（群聊自动@回复 + 私聊直连）


**基础流程**
- 用户发送消息到机器人（群/私聊均可）
- 消息自动进入处理队列
- 机器人顺序转发给第三者账号
- 第三者账号的回复自动返回原会话
    - 3秒活跃窗口: 第三者账号从第一次给机器人回复消息后，未来三秒回复的消息都是回给机器人的。
    - 20秒总超时：20s内无论如何，机器人没有收到第三者回复，消息都会被踢出队列。

**配置示例**
先放在`config.yml`里
```
OTHER_ID: xxxxxx # 自己去日志捞
ACTIVE_WINDOW = 3  # 活跃窗口秒数
TOTAL_TIMEOUT = 20 # 总超时秒数
```

**致谢**
- 感谢*元宝*AI
- 感谢Deepseek
- Langbot作者的开源代码和文档


