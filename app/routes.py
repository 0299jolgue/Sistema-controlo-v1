import json,secrets
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,Form,HTTPException,Request,WebSocket,WebSocketDisconnect
from fastapi.responses import HTMLResponse,RedirectResponse
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import Device,EnrollmentToken,Command,Message,Notification,ApkBuild,LogEvent,AppSetting
from .services import verify_password,ADMIN_PASSWORD_HASH,issue_enrollment,add_log,device_hash_token,seed_demo
router=APIRouter();connections={}
def page(request,name,**ctx):
 db=next(get_db());seed_demo(db);ctx.update(app_name=settings.APP_NAME,server_url=settings.SERVER_URL or str(request.base_url).rstrip("/"));r=request.app.state.templates.TemplateResponse(request=request,name=name,context=ctx);db.close();return r
def guard(request):
 if not request.session.get("admin"):raise HTTPException(401,"Authentication required")
@router.get("/",response_class=HTMLResponse)
async def index(request):return RedirectResponse("/dashboard" if request.session.get("admin") else "/login",303)
@router.get("/login",response_class=HTMLResponse)
async def login_page(request):return page(request,"login.html",error=None)
@router.post("/login")
async def login(request,username:str=Form(...),password:str=Form(...)):
 if username==settings.ADMIN_USERNAME and verify_password(password,ADMIN_PASSWORD_HASH):request.session["admin"]=True;return RedirectResponse("/dashboard",303)
 return page(request,"login.html",error="Credenciais inválidas.")
@router.get("/logout")
async def logout(request):request.session.clear();return RedirectResponse("/login",303)
@router.get("/dashboard",response_class=HTMLResponse)
async def dashboard(request,db:Session=Depends(get_db)):guard(request);seed_demo(db);return page(request,"dashboard.html",devices=db.query(Device).all(),recent=db.query(LogEvent).order_by(LogEvent.created_at.desc()).limit(8).all())
@router.get("/devices",response_class=HTMLResponse)
async def devices(request,db:Session=Depends(get_db)):guard(request);seed_demo(db);return page(request,"devices.html",devices=db.query(Device).all(),enrollments=db.query(EnrollmentToken).order_by(EnrollmentToken.created_at.desc()).limit(10).all())
@router.post("/devices/enrollment")
async def enrollment(request,db:Session=Depends(get_db)):guard(request);issue_enrollment(db);add_log(db,"enrollment","Nova inscrição criada.");return RedirectResponse("/devices",303)
@router.post("/devices/{device_id}/rename")
async def rename(request,device_id:int,name:str=Form(...),db:Session=Depends(get_db)):guard(request);d=db.get(Device,device_id);d.name=name.strip()[:120] or d.name;db.commit();add_log(db,"device_renamed",f"Nome alterado para {d.name}",d.id);return RedirectResponse(f"/devices/{device_id}",303)
@router.post("/devices/{device_id}/revoke")
async def revoke(request,device_id:int,db:Session=Depends(get_db)):guard(request);d=db.get(Device,device_id);d.authorized=False;d.online=False;db.commit();add_log(db,"revocation",f"Acesso revogado: {d.name}",d.id,"warning");return RedirectResponse("/devices",303)
@router.get("/devices/{device_id}",response_class=HTMLResponse)
async def device(request,device_id:int,db:Session=Depends(get_db)):guard(request);d=db.get(Device,device_id);return page(request,"device.html",device=d,commands=db.query(Command).filter_by(device_id=device_id).order_by(Command.created_at.desc()).limit(20).all(),messages=db.query(Message).filter_by(device_id=device_id).order_by(Message.created_at.desc()).limit(20).all(),logs=db.query(LogEvent).filter_by(device_id=device_id).order_by(LogEvent.created_at.desc()).limit(30).all())
async def send(device_id,event):
 ws=connections.get(device_id)
 if ws:await ws.send_json(event);return True
 return False
@router.post("/api/devices/{device_id}/commands")
async def command(request,device_id:int,type:str=Form(...),payload:str=Form("{}"),db:Session=Depends(get_db)):guard(request);d=db.get(Device,device_id);json.loads(payload);c=Command(device_id=device_id,type=type[:80],payload=payload);db.add(c);db.commit();db.refresh(c);ok=await send(device_id,{"type":"command","id":c.id,"command":c.type,"payload":json.loads(c.payload)});c.status="Sent" if ok else "Pending";db.commit();add_log(db,"command",f"{c.type} → {d.name}",device_id);return RedirectResponse(f"/devices/{device_id}",303)
@router.post("/api/devices/{device_id}/messages")
async def message(request,device_id:int,body:str=Form(...),db:Session=Depends(get_db)):guard(request);d=db.get(Device,device_id);m=Message(device_id=device_id,body=body[:4000]);db.add(m);db.commit();db.refresh(m);ok=await send(device_id,{"type":"message","id":m.id,"body":m.body});m.status="Sent" if ok else "Pending";db.commit();add_log(db,"message",f"Mensagem enviada para {d.name}",device_id);return RedirectResponse(f"/devices/{device_id}",303)
@router.post("/api/enroll")
async def api_enroll(request,db:Session=Depends(get_db)):
 data=await request.json();t=db.query(EnrollmentToken).filter_by(token=str(data.get("token","")),used=False).first();now=datetime.now(timezone.utc)
 if not t or t.expires_at.replace(tzinfo=timezone.utc)<now:raise HTTPException(401,"Invalid or expired enrollment token")
 t.used=True;secret=secrets.token_urlsafe(32);d=Device(internal_id=str(data.get("internal_id",secrets.token_hex(5))),name=str(data.get("name","Android device"))[:120],manufacturer=str(data.get("manufacturer","Unknown"))[:120],model=str(data.get("model","Unknown"))[:120],android_version=str(data.get("android_version","Unknown"))[:60],agent_version=str(data.get("agent_version","0.1.0"))[:60],device_token_hash=device_hash_token(secret),authorized=True);db.add(d);db.commit();db.refresh(d);add_log(db,"enrollment",f"Dispositivo inscrito: {d.name}",d.id,"success");return {"device_id":d.id,"device_token":secret,"server_url":settings.SERVER_URL or str(request.base_url).rstrip("/")}
@router.websocket("/ws/device")
async def ws_device(ws:WebSocket):
 await ws.accept();db=next(get_db());d=db.query(Device).filter_by(device_token_hash=device_hash_token(ws.headers.get("x-device-token","")),authorized=True).first()
 if not d:await ws.close(1008);db.close();return
 connections[d.id]=ws;d.online=True;d.last_seen=datetime.now(timezone.utc);db.commit()
 try:
  await ws.send_json({"type":"hello","device_id":d.id})
  while True:
   data=await ws.receive_json();d.last_seen=datetime.now(timezone.utc)
   if data.get("type")=="heartbeat":d.battery=int(data.get("battery",d.battery));d.network=str(data.get("network",d.network));d.ip_address=str(data.get("ip",""))[:64]
   elif data.get("type")=="notification":db.add(Notification(device_id=d.id,app_name=str(data.get("app",""))[:120],title=str(data.get("title",""))[:200],content=str(data.get("content",""))[:4000]))
   db.commit()
 except WebSocketDisconnect:pass
 finally:
  connections.pop(d.id,None);d.online=False;db.commit();add_log(db,"disconnected",f"{d.name} desconectado.",d.id,"warning");db.close()
@router.get("/logs",response_class=HTMLResponse)
async def logs(request,db:Session=Depends(get_db)):guard(request);return page(request,"logs.html",logs=db.query(LogEvent).order_by(LogEvent.created_at.desc()).limit(300).all())
@router.get("/apk-builder",response_class=HTMLResponse)
async def builder(request):guard(request);return page(request,"apk_builder.html")
@router.post("/apk-builder")
async def build(request,name:str=Form("Android Agent"),version:str=Form("1.0.0"),db:Session=Depends(get_db)):guard(request);db.add(ApkBuild(name=name[:120],version=version[:60],status="Completed",artifact_path="android/app/build/outputs/apk/debug/app-debug.apk"));db.commit();return RedirectResponse("/apks",303)
@router.get("/apks",response_class=HTMLResponse)
async def apks(request,db:Session=Depends(get_db)):guard(request);return page(request,"apks.html",builds=db.query(ApkBuild).order_by(ApkBuild.created_at.desc()).all())
@router.get("/settings",response_class=HTMLResponse)
async def settings_page(request,db:Session=Depends(get_db)):guard(request);return page(request,"settings.html",values={x.key:x.value for x in db.query(AppSetting).all()})
@router.post("/settings")
async def settings_save(request,platform_name:str=Form("Sistema Controlo"),server_url:str=Form(""),db:Session=Depends(get_db)):
 guard(request)
 for k,v in {"platform_name":platform_name[:120],"server_url":server_url.rstrip("/")[:240]}.items():
  r=db.query(AppSetting).filter_by(key=k).first()
  if r:r.value=v
  else:db.add(AppSetting(key=k,value=v))
 db.commit();return RedirectResponse("/settings",303)
