import json, os
from pathlib import Path
class Settings:
    def __init__(self):
        path=Path(os.getenv("CONFIG_FILE","config.json"))
        data=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.APP_NAME=data.get("app_name","Sistema Controlo"); self.HOST=data.get("host","0.0.0.0"); self.PORT=int(data.get("port",80))
        self.DATABASE_URL=data.get("database_url","sqlite:///./database/controlo.db"); self.SESSION_SECRET=data.get("session_secret","dev-secret-change-me")
        self.ADMIN_USERNAME=data.get("admin_username","admin"); self.ADMIN_PASSWORD=data.get("admin_password","admin123"); self.DEMO_MODE=bool(data.get("demo_mode",True)); self.SERVER_URL=str(data.get("server_url","")).rstrip("/")
settings=Settings()
