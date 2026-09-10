from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from .config import settings
from .db import init_db
from .routes import router

def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)
    app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET, max_age=43200, same_site="lax")
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.state.templates = Jinja2Templates(directory="templates")
    init_db()
    app.include_router(router)
    return app
