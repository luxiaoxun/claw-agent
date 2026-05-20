# https://pypi.org/project/wecom-aibot-python-sdk/
import asyncio
import os
from dotenv import load_dotenv
from aibot import WSClient, WSClientOptions, generate_req_id

# 加载 .env 文件中的环境变量
load_dotenv()

# 1. 创建客户端实例
ws_client = WSClient(
    WSClientOptions(
        bot_id=os.getenv('WECHAT_BOT_ID'),  # 企业微信后台获取的机器人 ID
        secret=os.getenv('WECHAT_BOT_SECRET'),  # 企业微信后台获取的机器人 Secret
    )
)


# 2. 监听认证成功
@ws_client.on('authenticated')
def on_authenticated():
    print('🔐 认证成功')


# 3. 监听文本消息并进行流式回复
@ws_client.on('message.text')
async def on_text(frame):
    content = frame.get('body', {}).get('text', {}).get('content', '')
    print(f'收到文本: {content}')

    stream_id = generate_req_id('stream')

    # 发送流式中间内容
    await ws_client.reply_stream(frame, stream_id, '正在思考中...', False)

    # 发送最终结果
    await asyncio.sleep(1)
    await ws_client.reply_stream(frame, stream_id, f'你好！你说的是: "{content}"', True)


# 4. 监听进入会话事件（发送欢迎语）
@ws_client.on('event.enter_chat')
async def on_enter_chat(frame):
    await ws_client.reply_welcome(frame, {
        'msgtype': 'text',
        'text': {'content': '您好！我是智能助手，有什么可以帮您的吗？'},
    })


def main():
    # 5. 启动（便捷方法，内部管理事件循环）
    ws_client.run()


if __name__ == "__main__":
    main()
