from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
import os
import psycopg2

app = Flask(__name__)

# LINE 機器人設定（從 Railway 環境變數讀取）
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# PostgreSQL 連線資訊
conn_info = {
    "host": os.getenv("PGHOST"),
    "port": os.getenv("PGPORT"),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD")
}

# 建立資料庫連線
def get_db_conn():
    return psycopg2.connect(**conn_info)

# LINE 官方驗證時有時會打 /webhook，也給它個 OK 防錯
@app.route("/webhook", methods=['POST'])
def webhook_ping():
    return 'Webhook working.', 200

# LINE Webhook 進入點
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# 使用者加入時
@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🎉 歡迎加入～請輸入您的手機號碼進行驗證（只允許一次）")
    )

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text.strip()

    if not user_input.startswith("09") or len(user_input) != 10:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入正確手機號碼格式（09開頭共10碼）")
        )
        return

    conn = get_db_conn()
    cur = conn.cursor()

    # 查詢該手機是否存在於名單中
    cur.execute("SELECT status, verified FROM users WHERE phone = %s", (user_input,))
    row = cur.fetchone()

    reply = None

    if row:
        status, verified = row
        if verified:
            reply = "您已經驗證過囉～"
        elif status == 'white':
            cur.execute("UPDATE users SET verified = TRUE WHERE phone = %s", (user_input,))
            reply = "✅ 驗證成功！歡迎您～"
        elif status == 'black':
            reply = None  # 黑名單不處理、不回應
    else:
        # 沒在名單中，自動新增為白名單 + 驗證成功
        cur.execute("""
            INSERT INTO users (phone, status, source, created_at, verified)
            VALUES (%s, 'white', 'auto-line', NOW(), TRUE)
        """, (user_input,))
        reply = "✅ 首次驗證成功，已加入白名單～"

    conn.commit()
    cur.close()
    conn.close()

    if reply:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
