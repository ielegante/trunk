import os
from contextlib import asynccontextmanager

from app.api.auth_routes import router as auth_router
from app.api.docs_routes import router as docs_router
from app.api.git_routes import router as git_router
from app.api.locking_routes import router as locking_router
from app.api.merge_routes import router as merge_router
from app.api.pdf_routes import router as pdf_router

# from app.api.power_user_routes import router as power_user_router  # Disabled in simplified architecture
# from app.api.reference_routes import router as reference_router  # Temporarily disabled for simplified architecture
from app.api.template_routes import router as template_router
from app.api.word_routes import router as word_router
from app.config import settings
from app.database import close_database, init_database

# from app.security.sqlite_rate_limiter import SQLiteRateLimitMiddleware  # Temporarily disabled
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_database()
    yield
    # Shutdown
    close_database()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Configure CORS for Chrome extension
# Get allowed origins from environment or use defaults
allowed_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "chrome-extension://*,http://localhost:3000,http://localhost:8080",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware (temporarily disabled for testing)
# app.add_middleware(
#     SQLiteRateLimitMiddleware,
#     calls_per_hour=100,
#     per_ip=True,
#     exclude_paths=["/health", "/", "/docs", "/openapi.json"],
# )

# Include routers
app.include_router(auth_router)
app.include_router(git_router)
app.include_router(docs_router)
app.include_router(merge_router)
app.include_router(word_router)
app.include_router(template_router)
# app.include_router(reference_router)  # Temporarily disabled for simplified architecture
app.include_router(locking_router, prefix="/locks", tags=["Document Locking"])
app.include_router(pdf_router, prefix="/pd", tags=["PDF Processing"])
# app.include_router(
#     power_user_router, prefix="/power-user", tags=["Power User Git Access"]
# )  # Disabled in simplified architecture


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "trunk-backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
