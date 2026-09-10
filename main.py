import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.json"
DEFAULTS = {
    "app_name": "Sistema Controlo",
    "host": "0.0.0.0",
    "port": 80,
    "admin_username": "admin",
    "admin_password": "admin123",
    "session_secret": "change-this-secret",
    "server_url": "",
    "demo_mode": True,
}


def load_config():
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULTS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    cfg = {**DEFAULTS, **data}
    cfg["port"] = int(cfg["port"])
    return cfg


CFG = load_config()
DB_PATH = ROOT / "database" / "controlo.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
SESSIONS = set()
SOCKETS = {}
app = FastAPI(title=CFG["app_name"], docs_url="/api/docs", redoc_url=None)


def now():
    return datetime.now(timezone.utc).isoformat()


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS devices(id INTEGER PRIMARY KEY AUTOINCREMENT,internal_id TEXT UNIQUE NOT NULL,name TEXT NOT NULL,manufacturer TEXT,model TEXT,android_version TEXT,agent_version TEXT,battery INTEGER DEFAULT 0,network TEXT DEFAULT 'Unknown',ip_address TEXT DEFAULT '',online INTEGER DEFAULT 0,authorized INTEGER DEFAULT 1,token TEXT DEFAULT '',last_seen TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS enrollment_tokens(id INTEGER PRIMARY KEY AUTOINCREMENT,token TEXT UNIQUE NOT NULL,expires_at TEXT NOT NULL,used INTEGER DEFAULT 0,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS commands(id INTEGER PRIMARY KEY AUTOINCREMENT,device_id INTEGER,type TEXT,payload TEXT,status TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,device_id INTEGER,body TEXT,status TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,device_id INTEGER,app_name TEXT,title TEXT,content TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,device_id INTEGER,event_type TEXT,description TEXT,status TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS apk_builds(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,version TEXT,status TEXT,created_at TEXT);
    """)
    if CFG["demo_mode"] and c.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 0:
        t = now()
        c.execute("INSERT INTO devices(internal_id,name,manufacturer,model,android_version,agent_version,battery,network,ip_address,online,authorized,last_seen,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",("demo-pixel-8","Pixel 8 — Demo","Google","Pixel 8","15","1.0.0",84,"Wi-Fi","192.168.1.42",1,1,t,t))
        c.execute("INSERT INTO devices(internal_id,name,manufacturer,model,android_version,agent_version,battery,network,ip_address,online,authorized,last_seen,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",("demo-galaxy-s23","Galaxy S23 — Demo","Samsung","SM-S911B","14","1.0.0",37,"5G","10.0.0.21",0,1,t,t))
        c.execute("INSERT INTO logs(event_type,description,status,created_at) VALUES(?,?,?,?)",("demo","Demo Mode inicializado.","success",t))
    c.commit(); c.close()


def html_escape(x):
    return str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")


def auth(req):
    if req.cookies.get("sc_session") not in SESSIONS:
        raise HTTPException(401, "Authentication required")


def shell(title, content):
    nav = "<a href='/dashboard'>Geral</a><a href='/devices'>Dispositivos</a><a href='/apk-builder'>APK Builder</a><a href='/apks'>APKs</a><a href='/logs'>Logs</a><a href='/settings'>Definições</a>"
    return f"<!doctype html><html lang='pt'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html_escape(title)}</title><style>{CSS}</style></head><body><aside><div class='brand'>◈ {html_escape(CFG['app_name'])}</div>{nav}<div class='foot'>DEMO: {str(CFG['demo_mode']).upper()}<a href='/logout'>Sair</a></div></aside><main><header><span>Administração</span><span>{html_escape(CFG['server_url']) or 'URL automática'}</span></header>{content}</main></body></html>"


def log(event, desc, device_id=None, status="info"):
    c=conn(); c.execute("INSERT INTO logs(device_id,event_type,description,status,created_at) VALUES(?,?,?,?,?)",(device_id,event,desc,status,now())); c.commit(); c.close()


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/health")
async def health():
    return {"status":"ok","app":CFG["app_name"],"port":CFG["port"]}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse("/dashboard" if request.cookies.get("sc_session") in SESSIONS else "/login", 303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.cookies.get("sc_session") in SESSIONS: return RedirectResponse("/dashboard",303)
    return HTMLResponse(f"<!doctype html><html lang='pt'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Login</title><style>{CSS}</style></head><body class='login'><div class='loginbox'><div class='brand'>◈ {html_escape(CFG['app_name'])}</div><h1>Entrar</h1><p>Painel administrativo</p><form method='post'><label>Utilizador<input name='username' required></label><label>Password<input type='password' name='password' required></label><button>Entrar</button></form></div></body></html>")


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username == CFG["admin_username"] and password == CFG["admin_password"]:
        token = secrets.token_urlsafe(32); SESSIONS.add(token); r = RedirectResponse("/dashboard",303); r.set_cookie("sc_session",token,httponly=True,samesite="lax",max_age=43200); return r
    return HTMLResponse("<h1>Credenciais inválidas</h1><a href='/login'>Voltar</a>",401)


@app.get("/logout")
async def logout(request: Request):
    SESSIONS.discard(request.cookies.get("sc_session", "")); r=RedirectResponse("/login",303); r.delete_cookie("sc_session"); return r


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    auth(request); c=conn(); ds=c.execute("SELECT * FROM devices ORDER BY id DESC").fetchall(); ls=c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 8").fetchall(); c.close(); total=len(ds); online=sum(int(d["online"]) for d in ds)
    rows=''.join(f"<tr><td><a href='/devices/{d['id']}'>{html_escape(d['name'])}</a></td><td>{html_escape(d['model'])}</td><td><span class='status {'on' if d['online'] else 'off'}'>{'Online' if d['online'] else 'Offline'}</span></td><td>{d['battery']}%</td></tr>" for d in ds)
    activity=''.join(f"<div class='activity'><b>{html_escape(x['event_type'])}</b><span>{html_escape(x['description'])}</span><small>{html_escape(x['created_at'])}</small></div>" for x in ls)
    body=f"<section class='head'><div><h1>Geral</h1><p>Estado atual da plataforma.</p></div></section><div class='grid4'><div class='card'><small>Total</small><strong>{total}</strong></div><div class='card'><small>Online</small><strong>{online}</strong></div><div class='card'><small>Offline</small><strong>{total-online}</strong></div><div class='card'><small>Modo</small><strong>{'Demo' if CFG['demo_mode'] else 'Real'}</strong></div></div><div class='cols'><div class='panel'><h2>Dispositivos</h2><table><tr><th>Nome</th><th>Modelo</th><th>Estado</th><th>Bateria</th></tr>{rows or '<tr><td colspan=4>Nenhum.</td></tr>'}</table></div><div class='panel'><h2>Atividade</h2>{activity or '<p class=muted>Sem eventos.</p>'}</div></div>"
    return HTMLResponse(shell("Geral",body))


@app.get("/devices", response_class=HTMLResponse)
async def devices(request: Request):
    auth(request); c=conn(); ds=c.execute("SELECT * FROM devices ORDER BY id DESC").fetchall(); ts=c.execute("SELECT * FROM enrollment_tokens ORDER BY id DESC LIMIT 10").fetchall(); c.close()
    rows=''.join(f"<tr><td><a href='/devices/{d['id']}'>{html_escape(d['name'])}</a></td><td>{'Online' if d['online'] else 'Offline'}</td><td>{html_escape(d['manufacturer'])} {html_escape(d['model'])}</td><td>{html_escape(d['android_version'])}</td><td>{d['battery']}%</td><td>{html_escape(d['network'])}</td></tr>" for d in ds)
    tokens=''.join(f"<tr><td><code>{html_escape(t['token'])}</code></td><td>{html_escape(t['expires_at'])}</td><td>{'Usado' if t['used'] else 'Disponível'}</td></tr>" for t in ts)
    return HTMLResponse(shell("Dispositivos",f"<section class='head'><div><h1>Dispositivos</h1><p>Dispositivos autorizados.</p></div><form method='post' action='/devices/enrollment'><button>+ Nova inscrição</button></form></section><div class='panel'><table><tr><th>Nome</th><th>Estado</th><th>Modelo</th><th>Android</th><th>Bateria</th><th>Rede</th></tr>{rows}</table></div><div class='panel'><h2>Tokens de inscrição</h2><table><tr><th>Token</th><th>Expira</th><th>Estado</th></tr>{tokens or '<tr><td colspan=3>Nenhum token.</td></tr>'}</table></div>"))


@app.post("/devices/enrollment")
async def create_enrollment(request: Request):
    auth(request); token=secrets.token_urlsafe(20); exp=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(); c=conn(); c.execute("INSERT INTO enrollment_tokens(token,expires_at,created_at) VALUES(?,?,?)",(token,exp,now())); c.commit(); c.close(); log("enrollment","Nova inscrição criada."); return RedirectResponse("/devices",303)


@app.get("/devices/{device_id}", response_class=HTMLResponse)
async def device_page(request: Request, device_id: int):
    auth(request); c=conn(); d=c.execute("SELECT * FROM devices WHERE id=?",(device_id,)).fetchone(); cs=c.execute("SELECT * FROM commands WHERE device_id=? ORDER BY id DESC LIMIT 20",(device_id,)).fetchall(); ms=c.execute("SELECT * FROM messages WHERE device_id=? ORDER BY id DESC LIMIT 20",(device_id,)).fetchall(); ls=c.execute("SELECT * FROM logs WHERE device_id=? ORDER BY id DESC LIMIT 30",(device_id,)).fetchall(); c.close()
    if not d: raise HTTPException(404,"Dispositivo não encontrado")
    cmd=''.join(f"<tr><td>#{x['id']}</td><td>{html_escape(x['type'])}</td><td>{html_escape(x['status'])}</td><td>{html_escape(x['created_at'])}</td></tr>" for x in cs); msgs=''.join(f"<div class='activity'><b>{html_escape(x['status'])}</b><span>{html_escape(x['body'])}</span></div>" for x in ms); logs=''.join(f"<div class='activity'><b>{html_escape(x['event_type'])}</b><span>{html_escape(x['description'])}</span><small>{html_escape(x['created_at'])}</small></div>" for x in ls)
    body=f"<section class='head'><div><a href='/devices'>← Dispositivos</a><h1>{html_escape(d['name'])}</h1><p>{html_escape(d['manufacturer'])} {html_escape(d['model'])} · {html_escape(d['internal_id'])}</p></div></section><div class='grid4'><div class='card'><small>Estado</small><strong>{'Online' if d['online'] else 'Offline'}</strong></div><div class='card'><small>Bateria</small><strong>{d['battery']}%</strong></div><div class='card'><small>Android</small><strong>{html_escape(d['android_version'])}</strong></div><div class='card'><small>Rede</small><strong>{html_escape(d['network'])}</strong></div></div><div class='cols'><div class='panel'><h2>Overview</h2><form method='post' action='/devices/{device_id}/rename'><label>Nome<input name='name' value='{html_escape(d['name'])}' required></label><button>Guardar</button></form><p>IP: {html_escape(d['ip_address']) or '—'}</p><p>Agent: {html_escape(d['agent_version'])}</p><p>Última comunicação: {html_escape(d['last_seen'])}</p><form method='post' action='/devices/{device_id}/revoke'><button class='danger' onclick=\"return confirm('Revogar dispositivo?')\">Revogar</button></form></div><div class='panel'><h2>Messages</h2><form method='post' action='/api/devices/{device_id}/messages'><textarea name='body' rows='3' required></textarea><button>Enviar</button></form>{msgs}</div></div><div class='cols'><div class='panel'><h2>Controls</h2><form method='post' action='/api/devices/{device_id}/commands'><input type='hidden' name='type' value='device.lock'><input type='hidden' name='payload' value='{}'><button>Bloquear</button></form><form method='post' action='/api/devices/{device_id}/commands'><input type='hidden' name='type' value='screen.start'><input type='hidden' name='payload' value='{{\"consent_required\":true}}'><button>Iniciar Screen</button></form><p class='muted'>Captura e controlo usam apenas APIs oficiais e consentimento.</p></div><div class='panel'><h2>Logs</h2>{logs}</div></div><div class='panel'><h2>Commands</h2><table><tr><th>ID</th><th>Tipo</th><th>Estado</th><th>Data</th></tr>{cmd or '<tr><td colspan=4>Nenhum.</td></tr>'}</table></div>"
    return HTMLResponse(shell(d["name"],body))


@app.post("/devices/{device_id}/rename")
async def rename(request: Request, device_id:int, name:str=Form(...)):
    auth(request); c=conn(); c.execute("UPDATE devices SET name=? WHERE id=?",(name.strip()[:120],device_id)); c.commit(); c.close(); log("device_renamed",f"Nome alterado para {name.strip()[:120]}",device_id); return RedirectResponse(f"/devices/{device_id}",303)


@app.post("/devices/{device_id}/revoke")
async def revoke(request: Request, device_id:int):
    auth(request); c=conn(); d=c.execute("SELECT name FROM devices WHERE id=?",(device_id,)).fetchone(); c.execute("UPDATE devices SET authorized=0,online=0 WHERE id=?",(device_id,)); c.commit(); c.close(); SOCKETS.pop(device_id,None)
    if d: log("revocation",f"Acesso revogado: {d['name']}",device_id,"warning")
    return RedirectResponse("/devices",303)


async def send_device(device_id,payload):
    ws=SOCKETS.get(device_id)
    if not ws:return False
    try: await ws.send_json(payload); return True
    except Exception: SOCKETS.pop(device_id,None); return False


@app.post("/api/devices/{device_id}/messages")
async def message(request:Request, device_id:int, body:str=Form(...)):
    auth(request); body=body.strip()[:4000]; c=conn(); cur=c.execute("INSERT INTO messages(device_id,body,status,created_at) VALUES(?,?,?,?)",(device_id,body,"Pending",now())); mid=cur.lastrowid; c.commit(); c.close(); sent=await send_device(device_id,{"type":"message","id":mid,"body":body}); c=conn(); c.execute("UPDATE messages SET status=? WHERE id=?",("Sent" if sent else "Pending",mid)); c.commit(); c.close(); log("message","Mensagem enviada.",device_id); return RedirectResponse(f"/devices/{device_id}",303)


@app.post("/api/devices/{device_id}/commands")
async def command(request:Request, device_id:int, type:str=Form(...), payload:str=Form("{}")):
    auth(request)
    try: obj=json.loads(payload)
    except json.JSONDecodeError: raise HTTPException(400,"Payload JSON inválido")
    c=conn(); cur=c.execute("INSERT INTO commands(device_id,type,payload,status,created_at) VALUES(?,?,?,?,?)",(device_id,type[:80],payload,"Pending",now())); cid=cur.lastrowid; c.commit(); c.close(); sent=await send_device(device_id,{"type":"command","id":cid,"command":type[:80],"payload":obj}); c=conn(); c.execute("UPDATE commands SET status=? WHERE id=?",("Sent" if sent else "Pending",cid)); c.commit(); c.close(); log("command",f"{type[:80]} enviado.",device_id); return RedirectResponse(f"/devices/{device_id}",303)


@app.post("/api/enroll")
async def enroll(request:Request):
    data=await request.json(); token=str(data.get("token","")); c=conn(); t=c.execute("SELECT * FROM enrollment_tokens WHERE token=? AND used=0",(token,)).fetchone()
    if not t: c.close(); raise HTTPException(401,"Token inválido")
    try: expired=datetime.fromisoformat(t["expires_at"]) < datetime.now(timezone.utc)
    except ValueError: expired=True
    if expired: c.close(); raise HTTPException(401,"Token expirado")
    secret=secrets.token_urlsafe(32); iid=str(data.get("internal_id") or secrets.token_hex(8)); created=now(); c.execute("UPDATE enrollment_tokens SET used=1 WHERE id=?",(t["id"])); c.execute("INSERT INTO devices(internal_id,name,manufacturer,model,android_version,agent_version,battery,network,ip_address,online,authorized,token,last_seen,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(iid,str(data.get("name") or "Android device")[:120],str(data.get("manufacturer") or "Unknown")[:120],str(data.get("model") or "Unknown")[:120],str(data.get("android_version") or "Unknown")[:60],str(data.get("agent_version") or "1.0.0")[:60],0,"Unknown","",0,1,secret,created,created)); c.commit(); did=c.execute("SELECT id FROM devices WHERE internal_id=?",(iid,)).fetchone()[0]; c.close(); log("enrollment",f"Dispositivo inscrito: {iid}",did,"success")
    return {"device_id":did,"device_token":secret,"server_url":CFG["server_url"] or str(request.base_url).rstrip("/")}


@app.websocket("/ws/device")
async def websocket_device(ws:WebSocket):
    await ws.accept(); token=ws.headers.get("x-device-token",""); c=conn(); d=c.execute("SELECT * FROM devices WHERE token=? AND authorized=1",(token,)).fetchone()
    if not d: c.close(); await ws.close(1008); return
    did=d["id"]; SOCKETS[did]=ws; c.execute("UPDATE devices SET online=1,last_seen=? WHERE id=?",(now(),did)); c.commit(); c.close(); log("connected",f"{d['name']} conectado.",did,"success")
    try:
        await ws.send_json({"type":"hello","device_id":did})
        while True:
            data=await ws.receive_json(); c=conn(); c.execute("UPDATE devices SET last_seen=?,battery=?,network=?,ip_address=? WHERE id=?",(now(),int(data.get("battery",d["battery"])),str(data.get("network",d["network"]))[:80],str(data.get("ip",d["ip_address"]))[:64],did))
            if data.get("type")=="notification": c.execute("INSERT INTO notifications(device_id,app_name,title,content,created_at) VALUES(?,?,?,?,?)",(did,str(data.get("app",""))[:120],str(data.get("title",""))[:200],str(data.get("content",""))[:4000],now()))
            c.commit(); c.close()
    except WebSocketDisconnect: pass
    finally:
        SOCKETS.pop(did,None); c=conn(); c.execute("UPDATE devices SET online=0 WHERE id=?",(did,)); c.commit(); c.close(); log("disconnected",f"{d['name']} desconectado.",did,"warning")


@app.get("/logs",response_class=HTMLResponse)
async def logs_page(request:Request):
    auth(request); c=conn(); ls=c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 300").fetchall(); c.close(); rows=''.join(f"<tr><td>{html_escape(x['created_at'])}</td><td>{html_escape(x['device_id'] or '—')}</td><td>{html_escape(x['event_type'])}</td><td>{html_escape(x['description'])}</td><td>{html_escape(x['status'])}</td></tr>" for x in ls); return HTMLResponse(shell("Logs",f"<section class='head'><div><h1>Logs</h1><p>Histórico de eventos.</p></div></section><div class='panel'><table><tr><th>Data</th><th>Device</th><th>Tipo</th><th>Descrição</th><th>Estado</th></tr>{rows}</table></div>"))


@app.get("/apk-builder",response_class=HTMLResponse)
async def builder(request:Request):
    auth(request); return HTMLResponse(shell("APK Builder",f"<section class='head'><div><h1>APK Builder</h1><p>Sem URL manual.</p></div></section><div class='panel narrow'><form method='post'><label>Nome<input name='name' value='Android Agent' required></label><label>Versão<input name='version' value='1.0.0' required></label><p class='notice'>Servidor: {html_escape(CFG['server_url']) or 'automático'}</p><button>Gerar build</button></form></div>"))


@app.post("/apk-builder")
async def builder_post(request:Request,name:str=Form("Android Agent"),version:str=Form("1.0.0")):
    auth(request); c=conn(); c.execute("INSERT INTO apk_builds(name,version,status,created_at) VALUES(?,?,?,?)",(name[:120],version[:60],"Completed",now())); c.commit(); c.close(); return RedirectResponse("/apks",303)


@app.get("/apks",response_class=HTMLResponse)
async def apks(request:Request):
    auth(request); c=conn(); bs=c.execute("SELECT * FROM apk_builds ORDER BY id DESC").fetchall(); c.close(); rows=''.join(f"<tr><td>{html_escape(b['name'])}</td><td>{html_escape(b['version'])}</td><td>{html_escape(b['created_at'])}</td><td>{html_escape(b['status'])}</td></tr>" for b in bs); return HTMLResponse(shell("APKs",f"<section class='head'><div><h1>APKs</h1><p>Histórico de builds.</p></div></section><div class='panel'><table><tr><th>Nome</th><th>Versão</th><th>Data</th><th>Estado</th></tr>{rows or '<tr><td colspan=4>Nenhum build.</td></tr>'}</table></div>"))


@app.get("/settings",response_class=HTMLResponse)
async def settings_page(request:Request):
    auth(request); return HTMLResponse(shell("Definições",f"<section class='head'><div><h1>Definições</h1><p>config.json</p></div></section><div class='panel narrow'><form method='post'><label>Nome<input name='app_name' value='{html_escape(CFG['app_name'])}'></label><label>Server URL<input name='server_url' value='{html_escape(CFG['server_url'])}'></label><label>Demo<select name='demo_mode'><option value='true' {'selected' if CFG['demo_mode'] else ''}>Ativo</option><option value='false' {'selected' if not CFG['demo_mode'] else ''}>Desativado</option></select></label><button>Guardar</button></form></div>"))


@app.post("/settings")
async def settings_save(request:Request,app_name:str=Form("Sistema Controlo"),server_url:str=Form(""),demo_mode:str=Form("true")):
    auth(request); CFG["app_name"]=app_name[:120]; CFG["server_url"]=server_url.rstrip("/")[:240]; CFG["demo_mode"]=demo_mode=="true"; CONFIG_FILE.write_text(json.dumps(CFG,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); return RedirectResponse("/settings",303)


CSS="""
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,Arial;background:#090c11;color:#eef2f7}aside{position:fixed;inset:0 auto 0 0;width:230px;background:#0f141b;border-right:1px solid #202936;padding:24px 15px;display:flex;flex-direction:column}aside a{display:block;color:#aeb8c7;text-decoration:none;padding:10px 12px;border-radius:8px;margin:2px 0}aside a:hover{background:#19212c;color:#fff}.brand{font-weight:800;font-size:18px;margin-bottom:28px}.foot{margin-top:auto;display:flex;justify-content:space-between;color:#7d8897;font-size:12px}.foot a{padding:0}.main,main{margin-left:230px;padding:22px 28px}.main header,main header{display:flex;justify-content:space-between;border-bottom:1px solid #1e2632;padding-bottom:14px;margin-bottom:26px;color:#7f8998;font-size:13px}.head{display:flex;justify-content:space-between;align-items:end;margin-bottom:18px}.head h1{margin:.2em 0;font-size:30px}.head p{color:#8994a3;margin:0}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}.card,.panel{background:#11161e;border:1px solid #202a38;border-radius:13px;padding:17px;margin-bottom:16px}.card small{display:block;color:#8792a2;text-transform:uppercase;font-size:11px}.card strong{display:block;font-size:27px;margin-top:7px}.cols{display:grid;grid-template-columns:2fr 1fr;gap:16px}.panel h2{margin-top:0}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #202733;font-size:13px}th{color:#7f8998}a{color:#d9e7ff}button{background:#e9eef5;color:#0c1118;border:0;border-radius:8px;padding:10px 14px;font-weight:750;cursor:pointer;margin-top:8px}.danger{background:#572027;color:#ffb8be}label{display:grid;gap:7px;color:#b8c3d0;font-size:13px;margin:11px 0}input,textarea,select{width:100%;background:#0a0e14;color:#eef2f7;border:1px solid #293343;border-radius:8px;padding:10px}.activity{display:grid;grid-template-columns:110px 1fr;gap:8px;padding:9px 0;border-bottom:1px solid #202733}.activity small{grid-column:2;color:#707c8c}.muted{color:#7f8998}.notice{background:#101b29;border:1px solid #27384d;padding:11px;border-radius:9px}.status{padding:4px 8px;border-radius:999px;font-size:11px}.status.on{background:#113722;color:#76e39e}.status.off{background:#3b1a20;color:#ff969f}.login{min-height:100vh;display:grid;place-items:center;background:#080b10}.loginbox{width:min(420px,92vw);background:#11161e;border:1px solid #27303d;border-radius:15px;padding:28px}.loginbox button{width:100%}@media(max-width:950px){aside{position:static;width:auto;height:auto}.main,main{margin-left:0;padding:16px}.grid4{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}}@media(max-width:600px){.grid4{grid-template-columns:1fr}.head{align-items:start;gap:10px;flex-direction:column}}
"""

if __name__ == "__main__":
    uvicorn.run(app, host=CFG["host"], port=CFG["port"], proxy_headers=True, forwarded_allow_ips="*")
