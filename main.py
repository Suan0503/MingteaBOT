from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
import os
import psycopg2
from datetime import datetime

app = Flask(__name__)

# LINE 機器人設定
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
    try:
        return psycopg2.connect(**conn_info)
    except Exception as e:
        print(f"資料庫連線失敗：{e}")
        return None

# webhook 路徑
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    print("接收到 webhook：", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("簽名驗證失敗")
        abort(400)
    except Exception as e:
        print("處理 webhook 錯誤：", e)
        abort(500)

    return "OK"

# 使用者加入觸發
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
    reply = None

    if not user_input.startswith("09") or len(user_input) != 10:
        reply = "請輸入正確手機號碼格式（09開頭共10碼）"
    else:
        conn = get_db_conn()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT status, verified FROM users WHERE phone = %s", (user_input,))
                row = cur.fetchone()

                if row:
                    status, verified = row
                    if verified:
                        reply = "您已經驗證過囉～"
                    elif status == 'white':
                        cur.execute("UPDATE users SET verified = TRUE WHERE phone = %s", (user_input,))
                        reply = "✅ 驗證成功！歡迎您～"
                    elif status == 'black':
                        reply = None  # 黑名單不回應
                else:
                    cur.execute("""
                        INSERT INTO users (phone, status, source, created_at, verified)
                        VALUES (%s, 'white', 'auto-line', %s, TRUE)
                    """, (user_input, datetime.now()))
                    reply = "✅ 首次驗證成功，已加入白名單～"

                conn.commit()
                cur.close()
            except Exception as e:
                print("資料庫處理錯誤：", e)
            finally:
                conn.close()
        else:
            reply = "🚨 系統忙碌中，請稍後再試"

    if reply:
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        except Exception as e:
            print("LINE 回覆錯誤：", e)
