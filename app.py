import os
import psycopg2
from flask import Flask, render_template_string, request, redirect, url_for
import datetime

app = Flask(__name__)

# Renderの環境変数からDB接続情報を取得
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# 初期テーブル作成
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS classes (id SERIAL PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS threads (id SERIAL PRIMARY KEY, cid INT, title TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS posts (id SERIAL PRIMARY KEY, tid INT, n TEXT, b TEXT, d TEXT)")
    conn.commit()
    cur.close()
    conn.close()

# 起動時にテーブル作成
init_db()

# --- HTMLとルートはこれまでのPython版とほぼ同じですが、SQL文だけPostgreSQL用に少し調整 ---
# (※ 文字数制限のため、ここには主要な変更点のみ記載)
@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM classes ORDER BY id ASC")
    classes = cur.fetchall()
    cur.close(); conn.close()
    return render_template_string(HTML_TEMPLATE, v='menu', classes=classes)

# (以下、他のルートも同様に psycopg2 の書き方に合わせます)

if __name__ == '__main__':
    # Renderのポート指定に対応
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
