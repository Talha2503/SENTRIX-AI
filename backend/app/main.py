from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import applications, documents, findings, investigations
from app.core.config import settings
from app.core.database import engine

app = FastAPI(
    title=settings.APP_NAME,
    version="0.4.0",
    description="Autonomous Green Finance Intelligence: evidence-based decision support.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications.router)
app.include_router(documents.router)
app.include_router(investigations.router)
app.include_router(findings.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"database": "connected"}