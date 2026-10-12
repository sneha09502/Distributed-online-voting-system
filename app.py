from flask import Flask,request, redirect, session, render_template_string, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-demo-secret"
DB_NAME = "voting.db"

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Online Voting System</title>
<style>
body{font-family:Arial,sans-serif;background:#f3f6fb;margin:0;color:#182230}
header{background:#172554;color:white;padding:22px;text-align:center}
main{max-width:760px;margin:28px auto;padding:22px;background:white;border-radius:14px;box-shadow:0 4px 18px #0001}
a{color:#1d4ed8} input,button,select{padding:10px;margin:6px 0;width:100%;box-sizing:border-box}
button{background:#1d4ed8;color:white;border:0;border-radius:6px;cursor:pointer}
.card{padding:14px;margin:10px 0;border:1px solid #dbe3ef;border-radius:9px}
.msg{background:#eff6ff;padding:10px;border-radius:6px;margin:8px 0}
nav a{margin:0 8px}
small{color:#64748b}
</style>
</head>
<body><header><h1>Distributed Online Voting System</h1><p>College mini-project prototype</p></header>
<main>
<nav><a href="/">Home</a><a href="/results">Results</a>{% if user %}<a href="/logout">Logout</a>{% else %}<a href="/login">Login</a><a href="/register">Register</a>{% endif %}</nav>
{% for message in get_flashed_messages() %}<div class="msg">{{message}}</div>{% endfor %}
{{content|safe}}

</main></body></html>
"""

def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            has_voted INTEGER NOT NULL DEFAULT 0
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS candidates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS votes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            candidate_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(id)
        )""")
        count = con.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        if count == 0:
            con.executemany("INSERT INTO candidates(name) VALUES(?)",
                            [("Candidate A",), ("Candidate B",), ("Candidate C",)])

def page(content):
    return render_template_string(PAGE, content=content, user=session.get("username"))

@app.route("/")
def home():
    if not session.get("user_id"):
        content = """<h2>Welcome</h2><p>Register or log in to participate in the demo election.</p>
        <div class="card"><b>How it works</b><p>Users log in, choose one candidate, and the system prevents a second vote from the same account.</p></div>"""
    else:
        with db() as con:
            user = con.execute("SELECT has_voted FROM users WHERE id=?", (session["user_id"],)).fetchone()
            candidates = con.execute("SELECT * FROM candidates ORDER BY id").fetchall()
        if user["has_voted"]:
            content = "<h2>Thank you!</h2><p>Your account has already cast a vote.</p><p><a href='/results'>View results</a></p>"
        else:
            options = "".join(f"<option value='{c['id']}'>{c['name']}</option>" for c in candidates)
            content = f"""<h2>Cast your vote</h2><form method="post" action="/vote">
            <label>Select a candidate</label><select name="candidate_id" required>{options}</select>
            <button type="submit">Submit vote</button></form>"""
    return page(content)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 6:
            flash("Use a username of at least 3 characters and password of at least 6 characters.")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                                (username, generate_password_hash(password)))
                flash("Registration successful. Please log in.")
                return redirect("/login")
            except sqlite3.IntegrityError:
                flash("That username is already registered.")
    content = """<h2>Create account</h2><form method="post">
    <label>Username</label><input name="username" required minlength="3">
    <label>Password</label><input name="password" type="password" required minlength="6">
    <button>Register</button></form>"""
    return page(content)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")
        flash("Invalid username or password.")
    content = """<h2>Login</h2><form method="post">
    <label>Username</label><input name="username" required>
    <label>Password</label><input name="password" type="password" required>
    <button>Login</button></form>"""
    return page(content)

@app.route("/vote", methods=["POST"])
def vote():
    if not session.get("user_id"):
        flash("Please log in before voting.")
        return redirect("/login")
    candidate_id = request.form.get("candidate_id", type=int)
    with db() as con:
        user = con.execute("SELECT has_voted FROM users WHERE id=?", (session["user_id"],)).fetchone()
        candidate = con.execute("SELECT id FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not user or not candidate:
            flash("Invalid vote request.")
        elif user["has_voted"]:
            flash("This account has already voted.")
        else:
            try:
                con.execute("INSERT INTO votes(user_id,candidate_id) VALUES(?,?)",
                            (session["user_id"], candidate_id))
                con.execute("UPDATE users SET has_voted=1 WHERE id=?", (session["user_id"],))
                flash("Vote recorded successfully.")
            except sqlite3.IntegrityError:
                flash("A vote has already been recorded for this account.")
    return redirect("/")

@app.route("/results")
def results():
    with db() as con:
        rows = con.execute("""SELECT c.name, COUNT(v.id) AS total
        FROM candidates c LEFT JOIN votes v ON c.id=v.candidate_id
        GROUP BY c.id ORDER BY total DESC, c.name""").fetchall()
    content = "<h2>Election results</h2>"
    for row in rows:
        content += f"<div class='card'><b>{row['name']}</b><p>Votes: {row['total']}</p></div>"
    return page(content)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)