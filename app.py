import os
import psycopg2
import random
from flask import Flask, render_template_string, request, redirect, url_for, flash, make_response
import datetime

app = Flask(__name__)
app.secret_key = "bbs_secret_key"

# 管理用共通パスワード
ADMIN_PASS = "admin123"

# データベース接続関数（エラー回避処理付き）
def get_db():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise ValueError("DATABASE_URL is not set in Environment Variables")
    # Renderの postgresql:// を postgres:// に変換（psycopg2の仕様対策）
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)
    return psycopg2.connect(url, sslmode='require')

# テーブル初期化
def init_db():
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS classes (id INT PRIMARY KEY, name TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS threads (id SERIAL PRIMARY KEY, cid INT, title TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS posts (id SERIAL PRIMARY KEY, tid INT, n TEXT, b TEXT, d TEXT, pw TEXT)")
        
        cur.execute("SELECT count(*) FROM classes WHERE id = 1")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO classes (id, name) VALUES (1, '一般クラス')")
        
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Database Init Error: {e}")
    finally:
        if conn:
            conn.close()

# 起動時に実行
init_db()

# --- ここからHTMLとルート (変数名は 'HTML' に統一) ---
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>テキスト掲示板</title>
    <style>
        body { font-family: monospace; background-color: #eee; padding: 15px; color: #333; }
        .form-box { background: #fff; border: 1px solid #ccc; padding: 10px; margin: 10px 0; display: inline-block; width: 95%; }
        .del-btn { background: #ffcccc; cursor: pointer; font-size: 0.75em; }
        .post { border-bottom: 1px solid #ccc; padding: 5px 0; }
    </style>
</head>
<body>
    <h1><a href="/">掲示板メニュー</a></h1><hr>
    {% with messages = get_flashed_messages() %}{% if messages %}{% for m in messages %}<p style="color:red;">{{m}}</p>{% endfor %}{% endif %}{% endwith %}

    {% if v == 'menu' %}
        {% if new_cid %}<p style="color:blue;">新クラスID: <b>{{new_cid}}</b> (忘れないで下さい)</p>{% endif %}
        <h2>クラス一覧</h2>
        <ul>
        {% for c in items %}
            <li style="margin-bottom:10px;">
                <b>{{c[1]}}</b> 
                <form method="POST" action="/check_id/{{c[0]}}" style="display:inline;">
                    {% if c[0] == 1 %} <input type="submit" value="入る">
                    {% else %} ID: <input type="text" name="in_id" style="width:45px;" required> <input type="submit" value="入室">{% endif %}
                </form>
                {% if c[0] != 1 %}
                <form method="POST" action="/del_c/{{c[0]}}" style="display:inline; margin-left:10px;">
                    <input type="password" name="pw" placeholder="pass" style="width:40px;"><input type="submit" value="消" class="del-btn">
                </form>
                {% endif %}
            </li>
        {% endfor %}
        </ul>
        <hr><div class="form-box">
            <form method="POST" action="/add_class">クラス名: <input type="text" name="cn" required> <input type="submit" value="作成"></form>
        </div>

    {% elif v == 'class' %}
        <h2>クラス: {{cname[0]}}</h2><a href="/">[戻る]</a><hr>
        <div class="form-box">
            <form method="POST" action="/c/{{cid}}/new">
                タイ: <input type="text" name="t" required> 名: <input type="text" name="n" value="{{saved_name}}"><br>
                本文: <textarea name="b" required style="width:90%;"></textarea><br>
                削パス: <input type="text" name="pw" style="width:50px;"><input type="submit" value="スレ立て">
            </form>
        </div><hr>
        <ul>{% for t in items %}<li><a href="/c/{{cid}}/t/{{t[0]}}">{{t[2]}}</a></li>{% endfor %}</ul>

    {% elif v == 'thread' %}
        <h2>{{tname[0]}}</h2><a href="/c/{{cid}}">[戻る]</a><hr>
        {% for p in items %}
        <div class="post">
            {{loop.index}}: <b>{{p[2]}}</b> [{{p[4]}}] <a href="?r={{loop.index}}#f">[返信]</a>
            <form method="POST" action="/del_p/{{cid}}/{{tid}}/{{p[0]}}" style="display:inline;">
                <input type="password" name="del_pw" placeholder="パス" style="width:40px;"><input type="submit" value="消" class="del-btn">
            </form><br>
            <div style="white-space: pre-wrap; margin-left:10px;">{{p[3]}}</div>
        </div>
        {% endfor %}
        <div class="form-box" id="f">
            <form method="POST" action="/c/{{cid}}/t/{{tid}}/p">
                名: <input type="text" name="n" value="{{saved_name}}"> 削パス: <input type="text" name="pw" style="width:50px;"><br>
                <textarea name="b" required style="width:90%;">{{r_txt}}</textarea><br><input type="submit" value="書込">
            </form>
        </div>
    {% endif %}
</body></html>
"""

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM classes ORDER BY id ASC")
    res = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='menu', items=res, new_cid=request.args.get('new_cid'))

@app.route('/add_class', methods=['POST'])
def add_class():
    conn = get_db(); cur = conn.cursor()
    new_id = random.randint(10000, 99999)
    cur.execute("INSERT INTO classes (id, name) VALUES (%s, %s)", (new_id, request.form['cn']))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('index', new_cid=new_id))

@app.route('/check_id/<int:cid>', methods=['POST'])
def check_id(cid):
    if cid == 1 or str(request.form.get('in_id')) == str(cid):
        return redirect(url_for('v_class', cid=cid))
    flash("IDが違います"); return redirect(url_for('index'))

@app.route('/c/<int:cid>')
def v_class(cid):
    saved_name = request.cookies.get('user_name', '名無し')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT name FROM classes WHERE id=%s", (cid,))
    c_res = cur.fetchone()
    cur.execute("SELECT id, cid, title FROM threads WHERE cid=%s ORDER BY id DESC", (cid,))
    threads = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='class', cid=cid, cname=c_res, items=threads, saved_name=saved_name)

@app.route('/c/<int:cid>/new', methods=['POST'])
def new_t(cid):
    name = request.form['n']
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO threads (cid, title) VALUES (%s, %s) RETURNING id", (cid, request.form['t']))
    tid = cur.fetchone()[0]
    cur.execute("INSERT INTO posts (tid, n, b, d, pw) VALUES (%s, %s, %s, %s, %s)", (tid, name, request.form['b'], datetime.datetime.now().strftime('%m/%d %H:%M'), request.form.get('pw')))
    conn.commit(); cur.close(); conn.close()
    resp = make_response(redirect(url_for('v_thread', cid=cid, tid=tid)))
    resp.set_cookie('user_name', name, max_age=60*60*24*30)
    return resp

@app.route('/c/<int:cid>/t/<int:tid>')
def v_thread(cid, tid):
    saved_name = request.cookies.get('user_name', '名無し')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT title FROM threads WHERE id=%s", (tid,))
    t_res = cur.fetchone()
    cur.execute("SELECT id, tid, n, b, d FROM posts WHERE tid=%s ORDER BY id ASC", (tid,))
    posts = cur.fetchall(); cur.close(); conn.close()
    r = request.args.get('r')
    return render_template_string(HTML, v='thread', cid=cid, tid=tid, tname=t_res, items=posts, r_txt=f'>>{r}\\n' if r else "", saved_name=saved_name)

@app.route('/c/<int:cid>/t/<int:tid>/p', methods=['POST'])
def post(cid, tid):
    name = request.form['n']
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO posts (tid, n, b, d, pw) VALUES (%s, %s, %s, %s, %s)", (tid, name, request.form['b'], datetime.datetime.now().strftime('%m/%d %H:%M'), request.form.get('pw')))
    conn.commit(); cur.close(); conn.close()
    resp = make_response(redirect(url_for('v_thread', cid=cid, tid=tid)))
    resp.set_cookie('user_name', name, max_age=60*60*24*30)
    return resp

@app.route('/del_p/<int:cid>/<int:tid>/<int:pid>', methods=['POST'])
def del_p(cid, tid, pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT pw FROM posts WHERE id=%s", (pid,))
    res = cur.fetchone()
    if res and (res[0] == request.form.get('del_pw') or request.form.get('del_pw') == ADMIN_PASS):
        cur.execute("DELETE FROM posts WHERE id=%s", (pid,))
        conn.commit(); flash("削除しました")
    else: flash("パスワードが違います")
    cur.close(); conn.close()
    return redirect(url_for('v_thread', cid=cid, tid=tid))

@app.route('/del_c/<int:cid>', methods=['POST'])
def del_c(cid):
    if cid != 1 and request.form.get('pw') == ADMIN_PASS:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE tid IN (SELECT id FROM threads WHERE cid=%s)", (cid,))
        cur.execute("DELETE FROM threads WHERE cid=%s", (cid,))
        cur.execute("DELETE FROM classes WHERE id=%s", (cid,))
        conn.commit(); cur.close(); conn.close()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
