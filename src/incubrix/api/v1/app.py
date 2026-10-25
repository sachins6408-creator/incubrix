from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from incubrix.core.config import settings
from incubrix.core.errors import IncuBrixError
from incubrix.core.logging import logger
from incubrix.api.v1.routes import media, sessions, jobs, health

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="IncuBrix Prompt-Based Video Editing Engine: A complete, functional video editor transforming natural-language instructions into deterministic timeline edits and real FFmpeg rendered videos.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local and web preview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler for structured errors
@app.exception_handler(IncuBrixError)
async def incubrix_exception_handler(request: Request, exc: IncuBrixError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

# Include Routers
app.include_router(health.router)
app.include_router(media.router, prefix=settings.API_V1_PREFIX)
app.include_router(sessions.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)

# Mount static frontend
if settings.STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(settings.STATIC_DIR), html=True), name="static")
