from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import applications, demo, documents, findings, investigations, reports
from app.core.config import settings
from app.core.database import engine

app = FastAPI(
    title=settings.APP_NAME,
    version="0.6.0",
    description="Autonomous Green Finance Intelligence: evidence-based decision support.",
)


# Added before the CORS middleware, so it sits inside it: error responses still get CORS headers
# and the browser can show the real message instead of a generic network error.
@app.middleware("http")
async def report_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"[:400]})


app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    # Any project hosted on vercel.app (demo convenience; the API holds only synthetic data).
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications.router)
app.include_router(documents.router)
app.include_router(investigations.router)
app.include_router(findings.router)
app.include_router(reports.router)
app.include_router(demo.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"database": "connected"}