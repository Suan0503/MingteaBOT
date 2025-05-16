from flask import Flask, request, abort
import os
import psycopg2

from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, Configuration, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

app = Flask(__name__)

# LINE Bot 設定
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)
line_bot_api = MessagingApi(configuration)

# PostgreSQL 設定
conn_info = {
    "host": os.getenv("PGHOST"),
    "port": os.getenv("PGPORT"),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD")
}

def get_db_conn():
    return psycopg2.connect(**conn_info)

# Webhook 接收端點
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Webhook error: {e}")
        abort(400)
    return "OK"

# 加好友事件
@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    reply_token = event.reply_token
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="🎉 歡迎加入～請輸入您的手機號碼進行驗證（只允許一次）")]
        )
    )

# 處理文字訊息
@handler.add(MessageEvent)
def handle_message(event):
    if not isinstance(event.message, TextMessageContent):
        return

    user_input = event.message.text.strip()
    reply_token = event.reply_token

    if not user_input.startswith("09") or len(user_input) != 10:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="請輸入正確手機號碼格式（09開頭共10碼）")]
            )
        )
        return

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT status, verified FROM users WHERE phone = %s", (user_input,))
    row = cur.fetchone()

    reply = None
    if row:
        status, verified = row
        if verified:
            reply = "您已經驗證過囉～"
        elif status == "white":
            cur.execute("UPDATE users SET verified = TRUE WHERE phone = %s", (user_input,))
            reply = "✅ 驗證成功！歡迎您～"
        elif status == "black":
            reply = None  # 黑名單不回覆
    else:
        cur.execute("""
            INSERT INTO users (phone, status, source, created_at, verified)
            VALUES (%s, 'white', 'auto-line', NOW(), TRUE)
        """, (user_input,))
        reply = "✅ 首次驗證成功，已加入白名單～"

    conn.commit()
    cur.close()
    conn.close()

    if reply:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

if __name__ == "__main__":
    app.run(port=5000)
