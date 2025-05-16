import pandas as pd
import psycopg2
import os
from datetime import datetime

# 讀取 CSV 名單
df = pd.read_csv("line_users.csv")

# PostgreSQL 連線資訊（從 Railway 的環境變數取得）
conn_info = {
    "host": os.environ.get("PGHOST"),
    "port": os.environ.get("PGPORT"),
    "dbname": os.environ.get("PGDATABASE"),
    "user": os.environ.get("PGUSER"),
    "password": os.environ.get("PGPASSWORD")
}

# 建立資料表語法
create_table_sql = """
CREATE TABLE IF NOT EXISTS users (
    phone TEXT PRIMARY KEY,
    status TEXT CHECK (status IN ('white', 'black')),
    source TEXT,
    note TEXT,
    job TEXT,
    created_at TIMESTAMP,
    verified BOOLEAN DEFAULT FALSE
);
"""

# 寫入資料函式
def import_data():
    try:
        conn = psycopg2.connect(**conn_info)
        cur = conn.cursor()
        cur.execute(create_table_sql)

        for _, row in df.iterrows():
            cur.execute("""
                INSERT INTO users (phone, status, source, note, job, created_at, verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (phone) DO NOTHING
            """, (
                row['phone'],
                row['status'],
                row['source'],
                row['note'],
                row['job'],
                row['created_at'],
                row['verified']
            ))

        conn.commit()
        cur.close()
        conn.close()
        print("✅ 匯入成功！")
    except Exception as e:
        print("❌ 匯入失敗：", e)

if __name__ == "__main__":
    import_data()
