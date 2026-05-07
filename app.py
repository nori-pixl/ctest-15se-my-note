import os, psycopg2, random, datetime
from flask import Flask, render_template_string, request, redirect, url_for, make_response, flash

app = Flask(__name__)
app.secret_key = "bbs_secret_key"

# データベース接続
def get_db():
    # RenderのURLをPythonが読み込める形式に変換
    url = "postgresql://bbs_db_9adp_user:JehILZQrfktFiwHD1si2KVZ4L7UQeyu9@dpg-d7uamctckfvc73eqppsg-a/bbs_db_9adp"
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)
    return psycopg2.connect(url, sslmode='require')

# テーブル初期化
def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS classes (id INT PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS threads (id SERIAL PRIMARY KEY, cid INT, title TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS posts (id SERIAL PRIMARY KEY, tid INT, n TEXT, b TEXT, d TEXT, pw TEXT)")
    cur.execute("SELECT count(*) FROM classes WHERE id = 1")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO classes (id, name) VALUES (1, '一般クラス')")
    conn.commit(); cur.close(); conn.close()

init_db()

# あの頃の操作感のHTML
HTML = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>掲示板</title><style>body{font-family:monospace;background:#eee;padding:15px;} .box{background:#fff;border:1px solid #ccc;padding:10px;margin:10px 0; display:inline-block; width:95%;} .del-btn{background:#ffcccc;cursor:pointer;font-size:0.8em; border:1px solid #999;}</style></head>
<body>
    <h1><a href="/">掲示板メニュー</a></h1><hr>
    {% if v == 'menu' %}
        {% if new_cid %}<p style="color:blue;">新クラスID: <b>{{new_cid}}</b></p>{% endif %}
        <h2>クラス一覧</h2>
        <ul>{% for c in items %}
            <li style="margin-bottom:10px;"><b>{{c[1]}}</b> 
                <form method="POST" action="/check_id/{{c[0]}}" style="display:inline;">
                    {% if c[0] == 1 %}<input type="submit" value="入る">
                    {% else %}ID:<input name="in_id" style="width:50px;" required><input type="submit" value="入室">{% endif %}
                </form>
                {% if c[0] != 1 %}<form method="POST" action="/del_c/{{c[0]}}" style="display:inline; margin-left:10px;"><input type="submit" value="削除" class="del-btn" onclick="return confirm('削除？')"></form>{% endif %}
            </li>
        {% endfor %}</ul>
        <hr><div class="box"><h3>新規クラス追加</h3><form method="POST" action="/add_c">名: <input name="cn"><input type="submit" value="作成"></form></div>
    {% elif v == 'class' %}
        <h2>クラス: {{cname}}</h2><a href="/">[戻る]</a><hr>
        <div class="box"><h3>新スレを立てる</h3><form method="POST" action="/c/{{cid}}/new">タイ: <input name="t" required> 名: <input name="n" value="{{sn}}"><br>本文: <textarea name="b" required style="width:95%;"></textarea><br><input type="submit" value="スレ立て"></form></div>
        <hr><h3>スレッド一覧</h3><ul>{% for t in items %}<li><a href="/c/{{cid}}/t/{{t[0]}}">{{t[2]}}</a><form method="POST" action="/del_t/{{cid}}/{{t[0]}}" style="display:inline; margin-left:10px;"><input type="submit" value="削除" class="del-btn"></form></li>{% endfor %}</ul>
    {% elif v == 'thread' %}
        <h2>{{tname}}</h2><a href="/c/{{cid}}">[戻る]</a><hr>
        {% for p in items %}
            <div style="border-bottom:1px solid #ccc; margin-bottom:10px;">{{loop.index}}: <b>{{p[2]}}</b> [{{p[4]}}] <a href="?r={{loop.index}}#f">[返信]</a><br><div style="white-space:pre-wrap;margin-left:10px;">{{p[3]}}</div></div>
        {% endfor %}
        <div class="box" id="f"><h3>書き込み</h3><form method="POST" action="/c/{{cid}}/t/{{tid}}/p">名: <input name="n" value="{{sn}}"><br><textarea name="b" required style="width:95%;height:100px;">{{r_txt}}</textarea><br><input type="submit" value="書込"></form></div>
    {% endif %}
</body></html>
"""

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM classes ORDER BY id ASC")
    res = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='menu', items=res, new_cid=request.args.get('new_cid'))

@app.route('/add_c', methods=['POST'])
def add_c():
    nid = random.randint(10000, 99999)
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO classes (id, name) VALUES (%s, %s)", (nid, request.form['cn']))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('index', new_cid=nid))

@app.route('/check_id/<int:cid>', methods=['POST'])
def check_id(cid):
    if cid == 1 or request.form.get('in_id') == str(cid):
        return redirect(url_for('v_class', cid=cid))
    return redirect('/')

@app.route('/c/<int:cid>')
def v_class(cid):
    sn = request.cookies.get('un', '名無し')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT name FROM classes WHERE id=%s", (cid,))
    cn = cur.fetchone()[0]
    cur.execute("SELECT * FROM threads WHERE cid=%s ORDER BY id DESC", (cid,))
    ts = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='class', cid=cid, cname=cn, items=ts, sn=sn)

@app.route('/c/<int:cid>/new', methods=['POST'])
def new_t(cid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO threads (cid, title) VALUES (%s, %s) RETURNING id", (cid, request.form['t']))
    tid = cur.fetchone()[0]
    cur.execute("INSERT INTO posts (tid, n, b, d) VALUES (%s, %s, %s, %s)", (tid, request.form['n'], request.form['b'], datetime.datetime.now().strftime('%m/%d %H:%M')))
    conn.commit(); cur.close(); conn.close()
    resp = make_response(redirect(url_for('v_class', cid=cid)))
    resp.set_cookie('un', request.form['n'])
    return resp

@app.route('/c/<int:cid>/t/<int:tid>')
def v_thread(cid, tid):
    sn = request.cookies.get('un', '名無し')
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT title FROM threads WHERE id=%s", (tid,))
    tn = cur.fetchone()[0]
    cur.execute("SELECT * FROM posts WHERE tid=%s ORDER BY id ASC", (tid,))
    ps = cur.fetchall(); cur.close(); conn.close()
    return render_template_string(HTML, v='thread', cid=cid, tid=tid, tname=tn, items=ps, sn=sn, r_txt=f'>>{request.args.get("r")}\\n' if request.args.get("r") else "")

@app.route('/c/<int:cid>/t/<int:tid>/p', methods=['POST'])
def post(cid, tid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO posts (tid, n, b, d) VALUES (%s, %s, %s, %s)", (tid, request.form['n'], request.form['b'], datetime.datetime.now().strftime('%m/%d %H:%M')))
    conn.commit(); cur.close(); conn.close()
    resp = make_response(redirect(url_for('v_thread', cid=cid, tid=tid)))
    resp.set_cookie('un', request.form['n'])
    return resp

@app.route('/del_c/<int:cid>', methods=['POST'])
def del_c(cid):
    if cid != 1:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE tid IN (SELECT id FROM threads WHERE cid=%s)", (cid,))
        cur.execute("DELETE FROM threads WHERE cid=%s", (cid,))
        cur.execute("DELETE FROM classes WHERE id=%s", (cid,))
        conn.commit(); cur.close(); conn.close()
    return redirect('/')

@app.route('/del_t/<int:cid>/<int:tid>', methods=['POST'])
def del_t(cid, tid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM posts WHERE tid=%s", (tid,))
    cur.execute("DELETE FROM threads WHERE id=%s", (tid,))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('v_class', cid=cid))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
