import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import admin, assets, auth, general, projects
from app.core.config import get_settings
from app.services.jobs import log_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("forja.api")
settings = get_settings()

app = FastAPI(title=f"{settings.app_name} API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json",
              redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/media/"):
        response.headers.setdefault("Cache-Control", "no-store")
    if time.time() - start > 5:
        log.warning("requisição lenta %s %s %.1fs", request.method, request.url.path, time.time() - start)
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", []) if x not in ("body", "query", "path"))
        msg = str(e.get("msg", "")).replace("Value error, ", "")
        errors.append({"field": loc, "message": msg})
    detail = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors)
    return JSONResponse(status_code=422, content={"detail": detail or "dados inválidos", "errors": errors})


@app.exception_handler(StarletteHTTPException)
async def http_handler(_: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    ref = uuid.uuid4().hex[:8]
    log.exception("erro não tratado [%s] %s %s", ref, request.method, request.url.path)
    log_error("api", f"[{ref}] {request.method} {request.url.path}: {exc}", exc)
    return JSONResponse(status_code=500, content={"detail": f"Erro interno (ref. {ref})"})


for r in (auth.router, projects.router, assets.router, general.router, admin.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.app_name}
