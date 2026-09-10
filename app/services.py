import hashlib,hmac,secrets
from datetime import datetime,timedelta,timezone
from .config import settings
from .models import EnrollmentToken,LogEvent,Device
def hash_password(v):
 salt=secrets.token_bytes(16); d=hashlib.pbkdf2_hmac("sha256",v.encode(),salt,120000); return salt.hex()+":"+d.hex()
def verify_password(v,s):
 try:
  sh,dh=s.split(":",1); d=hashlib.pbkdf2_hmac("sha256",v.encode(),bytes.fromhex(sh),120000); return hmac.compare_digest(d.hex(),dh)
 except ValueError:return False
ADMIN_PASSWORD_HASH=hash_password(settings.ADMIN_PASSWORD)
def make_token():return secrets.token_urlsafe(24)
def issue_enrollment(db,minutes=15):
 t=EnrollmentToken(token=make_token(),expires_at=datetime.now(timezone.utc)+timedelta(minutes=minutes));db.add(t);db.commit();db.refresh(t);return t
def add_log(db,event_type,description,device_id=None,status="info"):db.add(LogEvent(device_id=device_id,event_type=event_type,description=description,status=status));db.commit()
def device_hash_token(raw):return hashlib.sha256(raw.encode()).hexdigest()
def seed_demo(db):
 if not settings.DEMO_MODE or db.query(Device).count(): return
 ds=[Device(internal_id="demo-pixel-8",name="Pixel 8 — Demo",manufacturer="Google",model="Pixel 8",android_version="15",agent_version="1.0.0",battery=84,network="Wi-Fi",ip_address="192.168.1.42",online=True,device_token_hash=device_hash_token("demo-token-1")),Device(internal_id="demo-samsung-s23",name="Galaxy S23 — Demo",manufacturer="Samsung",model="SM-S911B",android_version="14",agent_version="1.0.0",battery=37,network="5G",ip_address="10.0.0.21",online=False,device_token_hash=device_hash_token("demo-token-2"))];db.add_all(ds);db.commit()
