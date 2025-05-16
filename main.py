from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
import os, psycopg2

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        database=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD")
    )

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🎉 歡迎加入～請輸入你的手機號碼進行驗證（只允許一次）")
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text.strip()
    user_id = event.source.user_id

    if not user_input.startswith("09") or len(user_input) != 10:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入正確手機號碼（格式為09開頭共10碼）")
        )
        return

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT status, verified FROM users WHERE phone = %s", (user_input,))
    row = cur.fetchone()

    if row:
        status, verified = row
        if verified:
            msg = "您已經驗證過囉～"
        elif status == 'white':
            cur.execute("UPDATE users SET verified = TRUE WHERE phone = %s", (user_input,))
            msg = "✅ 驗證成功！歡迎您～"
        elif status == 'black':
            msg = None  # 黑名單不回覆
    else:
        cur.execute(
            "INSERT INTO users (phone, status, source, created_at, verified) VALUES (%s, 'white', 'auto-line', NOW(), TRUE)",
            (user_input,))
        msg = "✅ 首次驗證成功，已加入白名單～"

    conn.commit()
    cur.close()
    conn.close()

    if msg:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

# Railway 運行
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
