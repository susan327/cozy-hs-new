import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "news.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    image TEXT,
    timestamp TEXT NOT NULL
);
""")

conn.commit()
conn.close()

print("✅ postsテーブル作成完了！（news.db）")
