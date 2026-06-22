import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from .models import AppSetting
from .services.categorizer import seed_defaults
from .routers import uploads, transactions, categories, reports, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("./data/uploads", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Expense & GST Tracker",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads.router)
app.include_router(transactions.router)
app.include_router(categories.router)
app.include_router(reports.router)
app.include_router(settings.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Mount static files LAST so /api/* routes take priority
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
