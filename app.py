import os
import psycopg2
from flask import Flask, render_template_string, request, redirect, url_for
import datetime

app = Flask(__name__)

# 管理用パスワード
ADMIN_PASS = "admin123"

# データベース接続 (Renderのpostgresql://をpostgres://に自動置換)
def get_db():
    url = os.environ.get('DATABASE_URL')
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)
    return psycopg2.connect(url, sslmode='require')

# テーブル初期化
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS classes (id SERIAL PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS threads (id SERIAL PRIMARY KEY, cid INT, title TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS posts (id SERIAL PRIMARY KEY, tid INT, n TEXT, b TEXT, d TEXT)")
    conn.commit()
    cur.close()
    conn.close()

# 起動時にDB準備
init_db()

# HTMLテンプレート (変数名を HTML に統一)
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>テキスト掲示板</title>
    <style>
        body { font-family: sans-serif; background-color: #efefef; color: #000; padding: 15px; }
        h1 { font-size: 1.5em; }
        a { color: #0000ff; text-decoration: none; }
        hr { border: 0; border-top: 1px double #999; margin: 10px 0; }
        .post { margin-bottom: 20px; border-bottom: 1px solid #ccc; padding-bottom: 10px; }
        .form-box { background: #fff; border: 1px solid #999; padding: 10px; display: inline-block; }
        textarea { width: 90%; height: 100px; }
    </style>
</head>
<body>
    <h1><a href="/">掲示板メニュー</a></h1><hr>
    {% if v == 'menu' %}
        <h2>クラス一覧</h2>
        <ul>{% for c in items %}<li><a href="/c/{{c[0]}}"><b>{{c[1]}}</b></a></li>{% endfor %}</ul>
        <hr><div class="form-box">
            <form method="POST" action="/add_class">クラス名: <input type="text" name="cn" required> <input type="submit" value="作成"></form>
        </div>
    {% elif v == 'class' %}
        <h2>クラス: {{cname}}</h2><p><a href="/">[戻る]</a></p><hr>
        <div class="form-box">
            <form method="POST" action="/c/{{cid}}/new">
                タイ: <input type="text" name="t" required> 名: <input type="text" name="n" value="名無し"><br>
                本文:<br><textarea name="b" required></textarea><br><input type="submit" value="スレ立て">
            </form>
        </div><hr>
        <h3>スレッド一覧</h3>
        <ul>{% for t in items %}<li><a href="/c/{{cid}}/t/{{t[0]}}">{{t[2]}}</a></li>{% endfor %}</ul>
    {% elif v == 'thread' %}
        <h2>{{tname}}</h2><p><a href="/c/{{cid}}">[戻る]</a></p><hr>
        {% for p in items %}
        <div class="post">
            {{loop.index}}: <b>{{p[2]}}</b> [{{p[4]}}] <a href="?r={{loop.index}}#f">[返信]</a>
            <form method="POST" action="/del_p/{{cid}}/{{tid}}/{{p[0]}}" style="display:inline;">
                <input type="password" name="pw" placeholder="pass" style="width:40px;"><input type="submit" value="消">
            </form><br>
            <div style="margin-left:20px;">{{p[3]|replace('\\n','<br>')|safe}}</div>
        </div>
        {% endfor %}
        <hr>
        {% if items|length < 500 %}
            <div class="form-box" id="f">
                <h3>書込 ({{items|length}}/500)</h3>
                <form method="POST" action="/c/{{cid}}/t/{{tid}}/p">
                    名: <input type="text" name="n" value="名無し"><br>
                    本文:<br><textarea name="b" required>{{r_txt}}</textarea><br><input type="submit" value="書き込む">
                </form>
            </div>
        {% endif %}
    {% endif %}
</body></html>
"""

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM classes ORDER BY id ASC")
    res = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='menu', items=res)

@app.route('/add_class', methods=['POST'])
def add_class():
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO classes (name) VALUES (%s)", (request.form['cn'],))
    conn.commit(); cur.close(); conn.close()
    return redirect('/')

@app.route('/c/<int:cid>')
def v_class(cid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT name FROM classes WHERE id=%s", (cid,))
    cname = cur.fetchone()[0]
    cur.execute("SELECT id, cid, title FROM threads WHERE cid=%s ORDER BY id DESC", (cid,))
    res = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='class', cid=cid, cname=cname, items=res)

@app.route('/c/<int:cid>/new', methods=['POST'])
def new_t(cid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO threads (cid, title) VALUES (%s, %s) RETURNING id", (cid, request.form['t']))
    tid = cur.fetchone()[0]
    cur.execute("INSERT INTO posts (tid, n, b, d) VALUES (%s, %s, %s, %s)", (tid, request.form['n'], request.form['b'], datetime.datetime.now().strftime('%m/%d %H:%M')))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('v_thread', cid=cid, tid=tid))

@app.route('/c/<int:cid>/t/<int:tid>')
def v_thread(cid, tid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT title FROM threads WHERE id=%s", (tid,))
    tname = cur.fetchone()[0]
    cur.execute("SELECT id, tid, n, b, d FROM posts WHERE tid=%s ORDER BY id ASC", (tid,))
    res = cur.fetchall(); cur.close(); conn.close()
    r = request.args.get('r')
    return render_template_string(HTML, v='thread', cid=cid, tid=tid, tname=tname, items=res, r_txt=f'>>{r}\\n' if r else "")

@app.route('/c/<int:cid>/t/<int:tid>/p', methods=['POST'])
def post(cid, tid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT count(*) FROM posts WHERE tid=%s", (tid,))
    if cur.fetchone()[0] < 500:
        cur.execute("INSERT INTO posts (tid, n, b, d) VALUES (%s, %s, %s, %s)", (tid, request.form['n'], request.form['b'], datetime.datetime.now().strftime('%m/%d %H:%M')))
        conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('v_thread', cid=cid, tid=tid))

@app.route('/del_p/<int:cid>/<int:tid>/<int:pid>', methods=['POST'])
def del_p(cid, tid, pid):
    if request.form.get('pw') == ADMIN_PASS:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE id=%s", (pid,))
        conn.commit(); cur.close(); conn.close()
    return redirect(url_for('v_thread', cid=cid, tid=tid))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
