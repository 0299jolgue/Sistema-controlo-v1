import json
import sqlite3
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
DEFAULT = {"app_name":"Sistema Controlo","host":"0.0.0.0","port":80,"admin_username":"admin","admin_password":"admin123","demo_mode":True}

def load_config():
    data = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    data = {**DEFAULT, **data}
    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    return data

CFG = load_config()
DB = ROOT / "database" / "controlo.db"
DB.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title=CFG["app_name"])
SESSIONS = set()

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

@app.on_event("startup")
async def startup():
    c=db()
    c.execute("CREATE TABLE IF NOT EXISTS devices (id INTEGER PRIMARY KEY, name TEXT NOT NULL, model TEXT, online INTEGER DEFAULT 0)")
    c.commit()
    c.close()

@app.get("/health")
async def health():
    return {"status":"ok","app":CFG["app_name"]}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.cookies.get("session") in SESSIONS:
        return RedirectResponse("/dashboard", 303)
    return RedirectResponse("/login", 303)

@app.get("/login", response_class=HTMLResponse)
async def login():
    return HTMLResponse("""<!doctype html><html lang="pt"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login</title><body style="font-family:Arial;background:#10151c;color:white;display:grid;place-items:center;min-height:100vh"><form method="post" style="background:#18202a;padding:30px;border-radius:12px;width:320px"><h1>Sistema Controlo</h1><p>Entrar no painel</p><input name="username" placeholder="Utilizador" required style="width:100%;padding:10px;margin:8px 0"><input type="password" name="password" placeholder="Password" required style="width:100%;padding:10px;margin:8px 0"><button style="width:100%;padding:11px">Entrar</button></form></body></html>""")

@app.post("/login")
async def login_post(username: str=Form(...), password: str=Form(...)):
    if username == CFG["admin_username"] and password == CFG["admin_password"]:
        token = __import__("secrets").token_urlsafe(24)
        SESSIONS.add(token)
        r=RedirectResponse("/dashboard",303)
        r.set_cookie("session",token,httponly=True,samesite="lax")
        return r
    return HTMLResponse("<h1>Credenciais inválidas</h1><a href='/login'>Voltar</a>",401)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if request.cookies.get("session") not in SESSIONS:
        return RedirectResponse("/login",303)
    c=db()
    devices=c.execute("SELECT * FROM devices ORDER BY id DESC").fetchall()
    c.close()
    rows="".join(f"<tr><td>{d['name']}</td><td>{d['model'] or '—'}</td><td>{'Online' if d['online'] else 'Offline'}</td></tr>" for d in devices)
    return HTMLResponse(f"""<!doctype html><html lang="pt"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{CFG["app_name"]}</title><style>body{{font-family:Arial;background:#0d1117;color:#eee;margin:0;padding:30px}}.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:20px}}a{{color:#8ab4f8}}table{{width:100%;border-collapse:collapse}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #30363d}}</style><div class="card"><h1>{CFG["app_name"]}</h1><p>Servidor online.</p><p><a href="/health">Health check</a> · <a href="/logout">Sair</a></p></div><div class="card"><h2>Dispositivos</h2><table><tr><th>Nome</th><th>Modelo</th><th>Estado</th></tr>{rows or "<tr><td colspan='3'>Nenhum dispositivo.</td></tr>"}</table></div></html>""")

@app.get("/logout")
async def logout(request: Request):
    SESSIONS.discard(request.cookies.get("session",""))
    r=RedirectResponse("/login",303)
    r.delete_cookie("session")
    return r

if __name__ == "__main__":
    uvicorn.run(app, host=CFG["host"], port=CFG["port"], proxy_headers=True, forwarded_allow_ips="*")
