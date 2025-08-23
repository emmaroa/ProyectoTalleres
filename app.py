
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from functools import wraps
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "auth.db")

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ----- DB helpers -----
def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(error):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin','captura','lectura'))
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            endpoint TEXT,
            method TEXT,
            path TEXT,
            meta TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # seed users if empty
    cur = db.execute("SELECT COUNT(*) as c FROM users")
    if cur.fetchone()["c"] == 0:
        users = [
            ("admin",   generate_password_hash("Admin123!"),   "admin"),
            ("captura", generate_password_hash("Captura123!"), "captura"),
            ("lectura", generate_password_hash("Lectura123!"), "lectura"),
        ]
        db.executemany("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", users)
        db.commit()

def log_event(action, meta=None):
    try:
        db = get_db()
        uid = session.get('user_id')
        uname = session.get('username')
        db.execute(
            "INSERT INTO audit_logs (user_id, username, action, endpoint, method, path, meta) VALUES (?,?,?,?,?,?,?)",
            (uid, uname, action, request.endpoint, request.method, request.path, meta)
        )
        db.commit()
    except Exception:
        pass

@app.before_request
def before_request():
    init_db()
    if request.endpoint not in ('static',) and session.get('user_id'):
        if request.method == 'GET':
            log_event('view')

# ----- Auth & Roles -----
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login", next=request.path))
            if session.get("role") not in roles:
                flash("No tienes permisos para acceder a esta sección.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            log_event('login_ok')
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        flash("Credenciales inválidas.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    log_event('logout')
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))

# ----- Routes -----
@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/parque")
@login_required
def parque():
    return render_template("parque.html")

@app.route("/peticiones")
@roles_required("admin","captura")
def peticiones():
    return render_template("peticiones.html")

@app.route("/vales")
@roles_required("admin","captura")
def vales():
    return render_template("vales.html")

@app.route("/seguimiento")
@roles_required("admin","lectura","captura")
def seguimiento():
    return render_template("seguimiento.html")

@app.route("/copiar")
@roles_required("admin")
def copiar():
    return render_template("copiar.html")

# ---- Admin: Usuarios/Permisos (ABM) ----
@app.route("/admin/usuarios", methods=["GET", "POST"])
@roles_required("admin")
def admin_usuarios():
    db = get_db()
    if request.method == "POST":
        act = request.form.get("action")
        if act == "create":
            username = request.form.get("username","").strip()
            password = request.form.get("password","")
            role = request.form.get("role","lectura")
            if username and password and role in ("admin","captura","lectura"):
                try:
                    db.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                               (username, generate_password_hash(password), role))
                    db.commit()
                    log_event("user_create", username)
                    flash(f"Usuario '{username}' creado.", "success")
                except sqlite3.IntegrityError:
                    flash("Ese usuario ya existe.", "error")
            else:
                flash("Datos inválidos.", "error")
        elif act == "update_role":
            uid = request.form.get("user_id")
            role = request.form.get("role")
            if role in ("admin","captura","lectura"):
                db.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
                db.commit()
                log_event("user_role_change", f"{uid} -> {role}")
                flash("Rol actualizado.", "success")
        elif act == "reset_pwd":
            uid = request.form.get("user_id")
            newpwd = request.form.get("newpwd","")
            if newpwd:
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(newpwd), uid))
                db.commit()
                log_event("user_pwd_reset", uid)
                flash("Contraseña actualizada.", "success")
        elif act == "delete":
            uid = request.form.get("user_id")
            if str(session.get("user_id")) == str(uid):
                flash("No puedes eliminar tu propio usuario.", "error")
            else:
                db.execute("DELETE FROM users WHERE id=?", (uid,))
                db.commit()
                log_event("user_delete", uid)
                flash("Usuario eliminado.", "success")
        return redirect(url_for("admin_usuarios"))

    users = db.execute("SELECT id, username, role FROM users ORDER BY username").fetchall()
    return render_template("admin_usuarios.html", users=users)

# ---- Admin: Movimientos ----
@app.route("/admin/movimientos")
@roles_required("admin")
def admin_movimientos():
    db = get_db()
    q = request.args.get("q","").strip()
    params = []
    sql = "SELECT id, username, action, endpoint, method, path, meta, created_at FROM audit_logs"
    if q:
        sql += " WHERE username LIKE ? OR action LIKE ? OR endpoint LIKE ? OR path LIKE ?"
        like = f"%{q}%"
        params = [like, like, like, like]
    sql += " ORDER BY id DESC LIMIT 300"
    rows = db.execute(sql, params).fetchall()
    return render_template("admin_movimientos.html", rows=rows, q=q)

if __name__ == "__main__":
    app.run(debug=True)
