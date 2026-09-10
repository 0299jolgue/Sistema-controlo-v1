from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

DATABASE_PATH = None
if settings.DATABASE_URL.startswith("sqlite:///"):
    raw_path = settings.DATABASE_URL.removeprefix("sqlite:///")
    if raw_path != ":memory:":
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_PATH = db_path
        settings.DATABASE_URL = f"sqlite:///{db_path}"

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from . import models
    if DATABASE_PATH:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
