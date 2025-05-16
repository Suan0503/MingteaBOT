from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage

import os

app = Flask(__name__)

# LINE SDK 設定
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# Webhook 路徑
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# 使用者加好友時回覆
@handler.add(FollowEvent)
def handle_follow_event(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        reply = ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="🎉 歡迎加入測試機器人～請回覆任意文字！")]
        )
        line_bot_api.reply_message(reply)

# 處理一般文字訊息（純測試）
@handler.add(MessageEvent)
def handle_text_message(event):
    if isinstance(event.message, TextMessageContent):
        user_input = event.message.text.strip()
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply = ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"你剛剛說的是：「{user_input}」")]
            )
            line_bot_api.reply_message(reply)

if __name__ == "__main__":
    app.run()
