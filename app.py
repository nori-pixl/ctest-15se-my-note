import os
import psycopg2
import random
from flask import Flask, render_template_string, request, redirect, url_for, flash, make_response
import datetime

app = Flask(__name__)
app.secret_key = "secret_key_for_flash"

# 管理用共通パスワード（スレやクラスを消す時に使えます。初期値: admin123）
ADMIN_PASS = "admin123"

def get_db():
    url = os.environ.get('DATABASE_URL')
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)
    return psycopg2.connect(url, sslmode='require')

def init_db():
    conn = get_db(); cur = conn.cursor()
    # テーブル作成（カラム不足によるエラーを防止）
    cur.execute("CREATE TABLE IF NOT EXISTS classes (id INT PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS threads (id SERIAL PRIMARY KEY, cid INT, title TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS posts (id SERIAL PRIMARY KEY, tid INT, n TEXT, b TEXT, d TEXT, pw TEXT)")
    
    # 「一般クラス」を自動作成
    cur.execute("SELECT count(*) FROM classes WHERE id = 1")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO classes (id, name) VALUES (1, '一般クラス')")
    
    conn.commit(); cur.close(); conn.close()

# 起動時に構造をチェック
init_db()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>テキスト掲示板</title>
    <style>
        body { font-family: monospace; background-color: #eee; padding: 15px; color: #333; }
        h1 { font-size: 1.5em; }
        a { color: #0000ff; text-decoration: none; }
        .form-box { background: #fff; border: 1px solid #ccc; padding: 10px; margin: 10px 0; display: inline-block; width: 95%; }
        .del-btn { background: #ffcccc; border: 1px solid #f99; cursor: pointer; font-size: 0.75em; padding: 2px 4px; }
        .post { border-bottom: 1px solid #ccc; padding: 5px 0; }
        .id-notice { background: #fff9c4; border: 2px solid #fbc02d; padding: 10px; margin: 10px 0; font-weight: bold; color: #f57f17; }
    </style>
</head>
<body>
    <h1><a href="/">掲示板メニュー</a></h1><hr>
    {% with messages = get_flashed_messages() %}{% if messages %}{% for m in messages %}<p style="color:red;">{{m}}</p>{% endfor %}{% endif %}{% endwith %}

    {% if v == 'menu' %}
        {% if new_cid %}<div class="id-notice">【新クラスID】 {{new_cid}} (入室に必要です)</div>{% endif %}
        <h2>クラス一覧</h2>
        <ul>
        {% for cid, name in items %}
            <li style="margin-bottom:12px;">
                <b>{{name}}</b> 
                <form method="POST" action="/check_id/{{cid}}" style="display:inline;">
                    {% if cid == 1 %} <input type="submit" value="入る">
                    {% else %} ID: <input type="text" name="in_id" maxlength="5" style="width:45px;" required> <input type="submit" value="入室">{% endif %}
                </form>
                {% if cid != 1 %}
                <form method="POST" action="/del_c/{{cid}}" style="display:inline; margin-left:10px;">
                    <input type="password" name="pw" placeholder="pass" style="width:40px;">
                    <input type="submit" value="クラス削除" class="del-btn" onclick="return confirm('全データが消えますがOK？')">
                </form>
                {% endif %}
            </li>
        {% endfor %}
        </ul>
        <hr>
        <div class="form-box">
            <h3>クラスを追加する</h3>
            <form method="POST" action="/add_class">
                クラス名: <input type="text" name="cn" required> <input type="submit" value="作成（ID自動発行）">
            </form>
        </div>

    {% elif v == 'class' %}
        <h2>クラス: {{cname}}</h2><a href="/">[戻る]</a><hr>
        <div class="form-box">
            <h3>新スレッド作成</h3>
            <form method="POST" action="/c/{{cid}}/new">
                タイ: <input type="text" name="t" required> 名: <input type="text" name="n" value="{{saved_name}}"><br>
                本文:<br><textarea name="b" required style="width:90%; height:60px;"></textarea><br>
                削パス: <input type="text" name="pw" style="width:60px;" placeholder="任意">
                <input type="submit" value="スレッド作成">
            </form>
        </div><hr>
        <h3>スレッド一覧</h3>
        <ul>
        {% for tid, title in items %}
            <li>
                <a href="/c/{{cid}}/t/{{tid}}">{{title}}</a>
                <form method="POST" action="/del_t/{{cid}}/{{tid}}" style="display:inline; margin-left:10px;">
                    <input type="password" name="pw" placeholder="pass" style="width:40px;">
                    <input type="submit" value="スレ削除" class="del-btn" onclick="return confirm('削除しますか？')">
                </form>
            </li>
        {% endfor %}
        </ul>

    {% elif v == 'thread' %}
        <h2>{{tname}}</h2><a href="/c/{{cid}}">[戻る]</a><hr>
        {% for pid, tid, n, b, d, pw in items %}
        <div class="post">
            {{loop.index}}: <b>{{n}}</b> [{{d}}] <a href="?r={{loop.index}}#f">[返信]</a>
            <form method="POST" action="/del_p/{{cid}}/{{tid}}/{{pid}}" style="display:inline;">
                <input type="password" name="del_pw" placeholder="パス" style="width:40px;"><input type="submit" value="消" class="del-btn">
            </form><br>
            <div style="white-space: pre-wrap; margin-left:10px;">{{b}}</div>
        </div>
        {% endfor %}
        <div class="form-box" id="f">
            <form method="POST" action="/c/{{cid}}/t/{{tid}}/p">
                名: <input type="text" name="n" value="{{saved_name}}"> 削パス: <input type="text" name="pw" style="width:60px;"><br>
                <textarea name="b" required style="width:90%; height:80px;">{{r_txt}}</textarea><br>
                <input type="submit" value="書き込む">
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
    flash("IDが間違っています。"); return redirect(url_for('index'))

@app.route('/c/<int:cid>')
def v_class(cid):
    saved_name = request.cookies.get('user_name', '名無し')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT name FROM classes WHERE id=%s", (cid,))
    c_res = cur.fetchone()
    cur.execute("SELECT id, title FROM threads WHERE cid=%s ORDER BY id DESC", (cid,))
    threads = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='class', cid=cid, cname=c_res[0] if c_res else "", items=threads, saved_name=saved_name)

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
    cur.execute("SELECT id, tid, n, b, d, pw FROM posts WHERE tid=%s ORDER BY id ASC", (tid,))
    posts = cur.fetchall(); cur.close(); conn.close()
    r = request.args.get('r')
    return render_template_string(HTML, v='thread', cid=cid, tid=tid, tname=t_res[0] if t_res else "", items=posts, r_txt=f'>>{r}\\n' if r else "", saved_name=saved_name)

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

@app.route('/del_t/<int:cid>/<int:tid>', methods=['POST'])
def del_t(cid, tid):
    if request.form.get('pw') == ADMIN_PASS:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE tid=%s", (tid,))
        cur.execute("DELETE FROM threads WHERE id=%s", (tid,))
        conn.commit(); cur.close(); conn.close()
    else: flash("管理パスワードが違います")
    return redirect(url_for('v_class', cid=cid))

@app.route('/del_c/<int:cid>', methods=['POST'])
def del_c(cid):
    if cid != 1 and request.form.get('pw') == ADMIN_PASS:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE tid IN (SELECT id FROM threads WHERE cid=%s)", (cid,))
        cur.execute("DELETE FROM threads WHERE cid=%s", (cid,))
        cur.execute("DELETE FROM classes WHERE id=%s", (cid,))
        conn.commit(); cur.close(); conn.close()
    else: flash("管理パスワードが違います")
    return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
