from flask import Flask, request, abort
from linebot.v3.messaging import MessagingApi, Configuration
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, FollowEvent, TextMessageContent
from linebot.exceptions import InvalidSignatureError
import os
import psycopg2
from datetime import datetime

app = Flask(__name__)

# LINE API 設定
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)
line_bot_api = MessagingApi(configuration)

# 資料庫連線設定
conn_info = {
    "host": os.getenv("PGHOST"),
    "port": os.getenv("PGPORT"),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD")
}

def get_db_conn():
    try:
        return psycopg2.connect(**conn_info)
    except Exception as e:
        print(f"❌ 資料庫連線失敗：{e}")
        return None

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ 簽名錯誤")
        abort(400)
    except Exception as e:
        print("❌ webhook handler 錯誤：", e)
        abort(500)

    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    try:
        line_bot_api.push_message(
            to=user_id,
            messages=[{"type": "text", "text": "🎉 歡迎加入～請輸入手機號碼驗證（僅一次）"}]
        )
    except Exception as e:
        print(f"❌ LINE 回應錯誤：{e}")

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_input = event.message.text.strip()
    user_id = event.source.user_id
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
                        reply = None
                else:
                    cur.execute("""
                        INSERT INTO users (phone, status, source, created_at, verified)
                        VALUES (%s, 'white', 'auto-line', %s, TRUE)
                    """, (user_input, datetime.now()))
                    reply = "✅ 首次驗證成功，已加入白名單～"

                conn.commit()
                cur.close()
            except Exception as e:
                print(f"❌ 資料庫處理錯誤：{e}")
            finally:
                conn.close()
        else:
            reply = "🚨 系統忙碌中，請稍後再試"

    if reply:
        try:
            line_bot_api.push_message(
                to=user_id,
                messages=[{"type": "text", "text": reply}]
            )
        except Exception as e:
            print(f"❌ 回覆訊息錯誤：{e}")
