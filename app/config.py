import os
from dotenv import load_dotenv
load_dotenv()
class Settings:
    APP_NAME=os.getenv("APP_NAME","Sistema Controlo"); HOST=os.getenv("HOST","0.0.0.0"); PORT=int(os.getenv("PORT","80"))
    DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./database/controlo.db"); SESSION_SECRET=os.getenv("SESSION_SECRET","dev-secret-change-me")
    ADMIN_USERNAME=os.getenv("ADMIN_USERNAME","admin"); ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","admin123")
    DEMO_MODE=os.getenv("DEMO_MODE","true").lower()=="true"; SERVER_URL=os.getenv("SERVER_URL","").rstrip("/")
settings=Settings()
