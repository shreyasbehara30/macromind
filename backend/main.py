from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
# pyrefly: ignore [missing-import]
from slowapi.errors import RateLimitExceeded
from core.config import settings
from contextlib import asynccontextmanager
from services.realtime.finnhub_ws import finnhub_ws_client
from services.realtime.polling import polling_service

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background services
    await finnhub_ws_client.start()
    polling_service.start()
    yield
    # Cleanup background services
    await finnhub_ws_client.stop()
    polling_service.stop()

app = FastAPI(
    title="MacroMind API",
    description="Backend API for MacroMind Fintech Application",
    version="1.0.0",
    lifespan=lifespan
)

# Add slowapi limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):(3000|3001|3002)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.get("/api/health")
@limiter.limit("60/minute")
async def health_check(request: Request):
    return {"status": "healthy", "version": "1.0.0"}

from api.routes import router as api_router
app.include_router(api_router, prefix="/api")

