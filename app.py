import os
import psycopg2
import random
from flask import Flask, render_template_string, request, redirect, url_for, flash
import datetime

app = Flask(__name__)
app.secret_key = "secret_key_for_flash" # エラー表示用

def get_db():
    url = os.environ.get('DATABASE_URL')
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)
    return psycopg2.connect(url, sslmode='require')

def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS classes (id INT PRIMARY KEY, name TEXT)") # SERIALからINTに変更
    cur.execute("CREATE TABLE IF NOT EXISTS threads (id SERIAL PRIMARY KEY, cid INT, title TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS posts (id SERIAL PRIMARY KEY, tid INT, n TEXT, b TEXT, d TEXT)")
    
    cur.execute("SELECT count(*) FROM classes WHERE name = %s", ("一般クラス",))
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO classes (id, name) VALUES (%s, %s)", (1, "一般クラス"))
    conn.commit(); cur.close(); conn.close()

init_db()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>テキスト掲示板</title>
    <style>
        body { font-family: monospace; background-color: #eee; padding: 15px; }
        .form-box { background: #fff; border: 1px solid #ccc; padding: 10px; margin: 10px 0; display: inline-block; }
        .del-btn { background: #ffcccc; cursor: pointer; font-size: 0.8em; }
    </style>
</head>
<body>
    <h1><a href="/">掲示板メニュー</a></h1><hr>
    {% with messages = get_flashed_messages() %}{% if messages %}{% for m in messages %}<p style="color:red;">{{m}}</p>{% endfor %}{% endif %}{% endwith %}

    {% if v == 'menu' %}
        <h2>クラス一覧</h2>
        <ul>
        {% for cid, name in items %}
            <li>
                <b>{{name}}</b> 
                <form method="POST" action="/check_id/{{cid}}" style="display:inline;">
                    {% if name == '一般クラス' %}
                        <input type="submit" value="入る">
                    {% else %}
                        ID: <input type="text" name="in_id" style="width:50px;" required> <input type="submit" value="入室">
                    {% endif %}
                </form>
                {% if name != '一般クラス' %}
                <form method="POST" action="/del_c/{{cid}}" style="display:inline; margin-left:10px;">
                    <input type="submit" value="削除" class="del-btn" onclick="return confirm('削除しますか？')">
                </form>
                {% endif %}
            </li>
        {% endfor %}
        </ul>
        <hr>
        <div class="form-box">
            <h3>新規クラス作成</h3>
            <form method="POST" action="/add_class">
                クラス名: <input type="text" name="cn" required> <input type="submit" value="作成">
            </form>
            {% if new_cid %}<p style="color:blue;">作成成功！ID: <b>{{new_cid}}</b> (忘れないでください)</p>{% endif %}
        </div>

    {% elif v == 'class' %}
        <h2>クラス: {{cname}}</h2><a href="/">[戻る]</a><hr>
        <div class="form-box">
            <h3>新スレを立てる</h3>
            <form method="POST" action="/c/{{cid}}/new">
                タイ: <input type="text" name="t" required> 名: <input type="text" name="n" value="名無し"><br>
                本文:<br><textarea name="b" required style="width:90%;"></textarea><br>
                <input type="submit" value="スレッド作成">
            </form>
        </div><hr>
        <h3>スレッド一覧</h3>
        <ul>
        {% for tid, title in items %}
            <li><a href="/c/{{cid}}/t/{{tid}}">{{title}}</a></li>
        {% endfor %}
        </ul>
    {% elif v == 'thread' %}
        <!-- スレ内表示は前回と同様 -->
        <h2>{{tname}}</h2><a href="/c/{{cid}}">[クラスへ戻る]</a><hr>
        {% for pid, tid, n, b, d in items %}
        <div style="border-bottom:1px solid #ccc; margin-bottom:10px;">
            {{loop.index}}: <b>{{n}}</b> [{{d}}] <a href="?r={{loop.index}}#f">[返信]</a><br>
            <div style="white-space: pre-wrap; margin-left:10px;">{{b}}</div>
        </div>
        {% endfor %}
        <div class="form-box" id="f">
            <form method="POST" action="/c/{{cid}}/t/{{tid}}/p">
                名: <input type="text" name="n" value="名無し"><br>
                <textarea name="b" required>{{r_txt}}</textarea><br><input type="submit" value="書込">
            </form>
        </div>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM classes ORDER BY id ASC")
    res = cur.fetchall(); cur.close(); conn.close()
    new_cid = request.args.get('new_cid')
    return render_template_string(HTML, v='menu', items=res, new_cid=new_cid)

@app.route('/add_class', methods=['POST'])
def add_class():
    conn = get_db(); cur = conn.cursor()
    # 5桁のランダムIDを生成
    new_id = random.randint(10000, 99999)
    cur.execute("INSERT INTO classes (id, name) VALUES (%s, %s)", (new_id, request.form['cn']))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('index', new_cid=new_id))

@app.route('/check_id/<int:cid>', methods=['POST'])
def check_id(cid):
    if cid == 1: return redirect(url_for('v_class', cid=cid)) # 一般クラス
    in_id = request.form.get('in_id')
    if str(in_id) == str(cid):
        return redirect(url_for('v_class', cid=cid))
    else:
        flash("IDが正しくありません")
        return redirect(url_for('index'))

@app.route('/c/<int:cid>')
def v_class(cid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT name FROM classes WHERE id=%s", (cid,))
    c = cur.fetchone()
    if not c: return redirect('/')
    cur.execute("SELECT id, title FROM threads WHERE cid=%s ORDER BY id DESC", (cid,))
    threads = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='class', cid=cid, cname=c[0], items=threads)

@app.route('/c/<int:cid>/new', methods=['POST'])
def new_t(cid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO threads (cid, title) VALUES (%s, %s) RETURNING id", (cid, request.form['t']))
    tid = cur.fetchone()[0]
    cur.execute("INSERT INTO posts (tid, n, b, d) VALUES (%s, %s, %s, %s)", (tid, request.form['n'], request.form['b'], datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('v_thread', cid=cid, tid=tid))

@app.route('/c/<int:cid>/t/<int:tid>')
def v_thread(cid, tid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT title FROM threads WHERE id=%s", (tid,))
    t = cur.fetchone()
    cur.execute("SELECT * FROM posts WHERE tid=%s ORDER BY id ASC", (tid,))
    posts = cur.fetchall(); cur.close(); conn.close()
    r = request.args.get('r')
    return render_template_string(HTML, v='thread', cid=cid, tid=tid, tname=t[0], items=posts, r_txt=f'>>{r}\\n' if r else "")

@app.route('/c/<int:cid>/t/<int:tid>/p', methods=['POST'])
def post(cid, tid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO posts (tid, n, b, d) VALUES (%s, %s, %s, %s)", (tid, request.form['n'], request.form['b'], datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('v_thread', cid=cid, tid=tid))

@app.route('/del_c/<int:cid>', methods=['POST'])
def del_c(cid):
    if cid != 1:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE tid IN (SELECT id FROM threads WHERE cid=%s)", (cid,))
        cur.execute("DELETE FROM threads WHERE cid=%s", (cid,))
        cur.execute("DELETE FROM classes WHERE id=%s", (cid,))
        conn.commit(); cur.close(); conn.close()
    return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
