import os, psycopg2, random, datetime
from flask import Flask, render_template_string, request, redirect, url_for, make_response, flash

app = Flask(__name__)
app.secret_key = "secret_bbs_key"

def get_db():
    # ご提示いただいた新しいDB URLを使用
    url = "postgresql://bbs_db_9adp_user:JehILZQrfktFiwHD1si2KVZ4L7UQeyu9@dpg-d7uamctckfvc73eqppsg-a/bbs_db_9adp"
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)
    return psycopg2.connect(url, sslmode='require')

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS classes (id INT PRIMARY KEY, name TEXT, pw TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS threads (id SERIAL PRIMARY KEY, cid INT, title TEXT, pw TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS posts (id SERIAL PRIMARY KEY, tid INT, n TEXT, b TEXT, d TEXT, pw TEXT)")
            cur.execute("SELECT count(*) FROM classes WHERE id = 1")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO classes (id, name, pw) VALUES (1, '一般クラス', 'none')")
        conn.commit()

init_db()

HTML = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>秘密の掲示板</title><style>
    body{font-family:monospace;background:#eee;padding:15px;}
    .box{background:#fff;border:1px solid #ccc;padding:10px;margin:10px 0;width:95%;max-width:500px;}
    .post{border-bottom:1px solid #ccc;padding:10px 0;}
    .del-btn{background:#ffcccc;cursor:pointer;font-size:0.8em;}
</style></head>
<body>
    <h1><a href="/">掲示板メニュー</a></h1><hr>
    {% with msgs = get_flashed_messages() %}{% for m in msgs %}<p style="color:red;">{{m}}</p>{% endfor %}{% endwith %}

    {% if v == 'menu' %}
        <h2>表示中のクラス</h2>
        <ul>
        {% for cid, name in items %}
            <li style="margin-bottom:10px;">
                <a href="/c/{{cid}}"><b>{{name}}</b></a>
                {% if cid != 1 %}
                <form method="POST" action="/remove_from_list/{{cid}}" style="display:inline;margin-left:10px;">
                    <input type="submit" value="非表示にする" style="font-size:0.7em;">
                </form>
                {% endif %}
            </li>
        {% endfor %}
        </ul>
        <hr>
        <div class="box">
            <h3>知っているクラスを呼び出す</h3>
            <form method="POST" action="/find_class">
                5桁のクラスID: <input name="fid" style="width:60px;" required> <input type="submit" value="表示に追加">
            </form>
        </div>
        <div class="box">
            <h3>新しいクラスを秘密で作る</h3>
            <form method="POST" action="/add_c">
                クラス名: <input name="cn" required><br>
                管理パス: <input name="cpw" type="password" style="width:80px;" required placeholder="削除用"><br>
                <input type="submit" value="作成（ID自動発行）">
            </form>
            {% if new_cid %}<p style="color:blue;">作成成功！ID: <b>{{new_cid}}</b><br>このIDを教えた人だけが呼び出せます。</p>{% endif %}
        </div>

    {% elif v == 'class' %}
        <h2>クラス: {{cname}}</h2><a href="/">[戻る]</a><hr>
        <div class="box">
            <h3>新スレを立てる</h3>
            <form method="POST" action="/c/{{cid}}/new">
                タイ: <input name="t" required> 名: <input name="n" value="{{sn}}"><br>
                本文: <br><textarea name="b" required style="width:95%;"></textarea><br>
                削除パス: <input name="tpw" type="password" style="width:60px;" required><br>
                <input type="submit" value="スレッド作成">
            </form>
        </div>
        <hr><h3>スレッド一覧</h3>
        <ul>{% for tid, title in items %}
            <li style="margin-bottom:10px;">
                <a href="/c/{{cid}}/t/{{tid}}">{{title}}</a>
                <form method="POST" action="/del_t/{{cid}}/{{tid}}" style="display:inline;margin-left:10px;">
                    パス: <input type="password" name="pw" style="width:40px;"> <input type="submit" value="削除" class="del-btn">
                </form>
            </li>
        {% endfor %}</ul>
        <hr>
        <form method="POST" action="/del_c/{{cid}}">
            クラスごと完全削除: パス <input type="password" name="pw" style="width:60px;"> <input type="submit" value="クラス削除" class="del-btn">
        </form>

    {% elif v == 'thread' %}
        <h2>{{tname}}</h2><a href="/c/{{cid}}">[戻る]</a><hr>
        {% for pid, tid, n, b, d, pw in items %}
            <div class="post">
                {{loop.index}}: <b>{{n}}</b> [{{d}}] <a href="?r={{loop.index}}#f">[返信]</a>
                <form method="POST" action="/del_p/{{cid}}/{{tid}}/{{pid}}" style="display:inline;margin-left:10px;">
                    パス: <input type="password" name="pw" style="width:40px;"> <input type="submit" value="消" class="del-btn">
                </form><br>
                <div style="white-space:pre-wrap;margin-left:10px;">{{b}}</div>
            </div>
        {% endfor %}
        <div class="box" id="f">
            <form method="POST" action="/c/{{cid}}/t/{{tid}}/p">
                名: <input name="n" value="{{sn}}"> パス: <input name="pw" type="password" style="width:50px;"><br>
                <textarea name="b" required style="width:95%;height:100px;">{{r_txt}}</textarea><br><input type="submit" value="書き込む">
            </form>
        </div>
    {% endif %}
</body></html>
"""

@app.route('/')
def index():
    # 表示リストをCookieから読み込む
    view_list = request.cookies.get('view_list', '1').split(',')
    items = []
    with get_db() as conn:
        with conn.cursor() as cur:
            for vid in view_list:
                cur.execute("SELECT id, name FROM classes WHERE id=%s", (int(vid),))
                res = cur.fetchone()
                if res: items.append(res)
    return render_template_string(HTML, v='menu', items=items, new_cid=request.args.get('new_cid'))

@app.route('/find_class', methods=['POST'])
def find_class():
    fid = request.form.get('fid')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM classes WHERE id=%s", (int(fid),))
            res = cur.fetchone()
    if res:
        view_list = request.cookies.get('view_list', '1').split(',')
        if str(fid) not in view_list:
            view_list.append(str(fid))
        resp = make_response(redirect('/'))
        resp.set_cookie('view_list', ','.join(view_list), max_age=60*60*24*30)
        return resp
    flash("そのIDのクラスは見つかりません"); return redirect('/')

@app.route('/add_c', methods=['POST'])
def add_c():
    nid = random.randint(10000, 99999)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO classes (id, name, pw) VALUES (%s, %s, %s)", (nid, request.form['cn'], request.form['cpw']))
        conn.commit()
    # 作成者も表示リストに追加
    view_list = request.cookies.get('view_list', '1').split(',')
    view_list.append(str(nid))
    resp = make_response(redirect(url_for('index', new_cid=nid)))
    resp.set_cookie('view_list', ','.join(view_list), max_age=60*60*24*30)
    return resp

@app.route('/remove_from_list/<int:cid>', methods=['POST'])
def remove_from_list(cid):
    view_list = request.cookies.get('view_list', '1').split(',')
    if str(cid) in view_list: view_list.remove(str(cid))
    resp = make_response(redirect('/'))
    resp.set_cookie('view_list', ','.join(view_list), max_age=60*60*24*30)
    return resp

@app.route('/c/<int:cid>')
def v_class(cid):
    sn = request.cookies.get('un', '名無し')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM classes WHERE id=%s", (cid,))
            cn = cur.fetchone()
            cur.execute("SELECT id, title FROM threads WHERE cid=%s ORDER BY id DESC", (cid,))
            ts = cur.fetchall()
    return render_template_string(HTML, v='class', cid=cid, cname=cn[0], items=ts, sn=sn)

@app.route('/c/<int:cid>/new', methods=['POST'])
def new_t(cid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO threads (cid, title, pw) VALUES (%s, %s, %s) RETURNING id", (cid, request.form['t'], request.form['tpw']))
            tid = cur.fetchone()[0]
            cur.execute("INSERT INTO posts (tid, n, b, d, pw) VALUES (%s, %s, %s, %s, %s)", (tid, request.form['n'], request.form['b'], datetime.datetime.now().strftime('%m/%d %H:%M'), request.form['tpw']))
        conn.commit()
    resp = make_response(redirect(url_for('v_thread', cid=cid, tid=tid)))
    resp.set_cookie('un', request.form['n']); return resp

@app.route('/c/<int:cid>/t/<int:tid>')
def v_thread(cid, tid):
    sn = request.cookies.get('un', '名無し')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM threads WHERE id=%s", (tid,))
            tn = cur.fetchone()
            cur.execute("SELECT id, tid, n, b, d, pw FROM posts WHERE tid=%s ORDER BY id ASC", (tid,))
            ps = cur.fetchall()
    return render_template_string(HTML, v='thread', cid=cid, tid=tid, tname=tn[0], items=ps, sn=sn, r_txt=f'>>{request.args.get("r")}\\n' if request.args.get("r") else "")

@app.route('/c/<int:cid>/t/<int:tid>/p', methods=['POST'])
def post(cid, tid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO posts (tid, n, b, d, pw) VALUES (%s, %s, %s, %s, %s)", (tid, request.form['n'], request.form['b'], datetime.datetime.now().strftime('%m/%d %H:%M'), request.form['pw']))
        conn.commit()
    resp = make_response(redirect(url_for('v_thread', cid=cid, tid=tid)))
    resp.set_cookie('un', request.form['n']); return resp

@app.route('/del_c/<int:cid>', methods=['POST'])
def del_c(cid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pw FROM classes WHERE id=%s", (cid,))
            pw = cur.fetchone()
            if pw and pw[0] == request.form.get('pw'):
                cur.execute("DELETE FROM posts WHERE tid IN (SELECT id FROM threads WHERE cid=%s)", (cid,))
                cur.execute("DELETE FROM threads WHERE cid=%s", (cid,))
                cur.execute("DELETE FROM classes WHERE id=%s", (cid,))
                conn.commit(); return redirect('/')
    flash("パスワードが違います"); return redirect(url_for('v_class', cid=cid))

@app.route('/del_t/<int:cid>/<int:tid>', methods=['POST'])
def del_t(cid, tid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pw FROM threads WHERE id=%s", (tid,))
            pw = cur.fetchone()
            if pw and pw[0] == request.form.get('pw'):
                cur.execute("DELETE FROM posts WHERE tid=%s", (tid,))
                cur.execute("DELETE FROM threads WHERE id=%s", (tid,))
                conn.commit(); return redirect(url_for('v_class', cid=cid))
    flash("パスワードが違います"); return redirect(url_for('v_class', cid=cid))

@app.route('/del_p/<int:cid>/<int:tid>/<int:pid>', methods=['POST'])
def del_p(cid, tid, pid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pw FROM posts WHERE id=%s", (pid,))
            pw = cur.fetchone()
            if pw and pw[0] == request.form.get('pw'):
                cur.execute("DELETE FROM posts WHERE id=%s", (pid,))
                conn.commit(); return redirect(url_for('v_thread', cid=cid, tid=tid))
    flash("パスワードが違います"); return redirect(url_for('v_thread', cid=cid, tid=tid))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
