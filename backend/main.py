"""Owner: Damir. API, authorization and single-worker persistent runtime state."""
from __future__ import annotations
from contextlib import asynccontextmanager
import hmac
import hashlib
import json
import os
from pathlib import Path
from typing import Annotated
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from ai.engine import recommend
from backend.data_loader import Dataset, DatasetError, load_dataset
from backend.domain import build_context, profile
from backend.reporting import overview
from backend.storage import OperationError, RuntimeStore
from shared.contracts import (CompletionRequest, CompletionResponse, HRResponse,
                             ImportResponse, ProfileResponse, RecommendationResponse)

ROOT = Path(__file__).resolve().parents[1]
bearer = HTTPBearer(auto_error=False)


def identity(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, detail={"code": "UNAUTHORIZED", "message": "Bearer token required"},
                            headers={"WWW-Authenticate": "Bearer"})
    cfg = request.app.state.auth
    if cfg["hr"] and hmac.compare_digest(credentials.credentials, cfg["hr"]):
        return {"role": "hr", "employee_id": None}
    if cfg["employee"] and hmac.compare_digest(credentials.credentials, cfg["employee"]):
        return {"role": "employee", "employee_id": cfg["employee_id"]}
    raise HTTPException(401, detail={"code": "UNAUTHORIZED", "message": "Invalid token"},
                        headers={"WWW-Authenticate": "Bearer"})


def require_hr(user=Depends(identity)):
    if user["role"] != "hr":
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "HR access required"})
    return user


def authorize_employee(employee_id: str, user: dict, data: Dataset):
    if user["role"] != "hr" and user["employee_id"] != employee_id:
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Not your profile"})
    if employee_id not in data.employees:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Employee not found"})


def model_configuration() -> str:
    # Include credentials by digest only, so changing provider credentials refreshes fallback.
    config = {k: v for k, v in os.environ.items() if k.startswith(('LLM_', 'AI_'))}
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def create_app(dataset: Dataset | None = None, storage_path: str | Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        load_dotenv(ROOT/".env", override=False)
        folder = Path(os.getenv("DATA_DIR", "docs"))
        if not folder.is_absolute(): folder = ROOT/folder
        hr_token = os.getenv("HR_TOKEN", "")
        employee_token = os.getenv("EMPLOYEE_TOKEN", "")
        if hr_token and hr_token == employee_token:
            raise RuntimeError("HR_TOKEN and EMPLOYEE_TOKEN must be different")
        application.state.auth = {"hr": hr_token, "employee": employee_token,
                                  "employee_id": os.getenv("EMPLOYEE_ID", "E0001")}
        path = storage_path
        if path is None:
            # Explicit fixture datasets are isolated unless a persistence path is requested.
            path = ':memory:' if dataset is not None else os.getenv('STATE_PATH', '.local/career_quest.sqlite3')
        if str(path) != ':memory:' and not Path(path).is_absolute():
            path = ROOT / path
        store = RuntimeStore(dataset if dataset is not None else load_dataset(folder), path)
        application.state.store = store
        application.state.recommendation_cache = {}
        try:
            yield
        finally:
            store.close()

    app = FastAPI(title="Career Quest API", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(OperationError)
    async def operation_error(request: Request, exc: OperationError):
        return JSONResponse(status_code=exc.status, content={'detail': {'code': exc.code, 'message': str(exc)}})

    @app.exception_handler(DatasetError)
    async def dataset_error(request: Request, exc: DatasetError):
        return JSONResponse(status_code=422, content={'detail': {'code': 'INVALID_DATASET', 'message': str(exc)}})

    @app.get("/api/health")
    def health(request: Request):
        data = request.app.state.store.data
        return {"status": "ok", "stage": "runtime", "as_of_date": data.as_of_date,
                "data_version": data.version, "employees_count": len(data.employees)}

    @app.get("/api/auth/me")
    def me(user=Depends(identity)):
        return user

    @app.get("/api/employees")
    def employees(request: Request, user=Depends(require_hr)):
        return [{k: e[k] for k in ("employee_id", "full_name", "role", "grade", "department")}
                for e in request.app.state.store.data.employees.values()]

    @app.get("/api/employees/{employee_id}", response_model=ProfileResponse)
    def get_profile(employee_id: str, request: Request, user=Depends(identity)):
        data = request.app.state.store.data
        authorize_employee(employee_id, user, data)
        return profile(data, employee_id)

    @app.get("/api/employees/{employee_id}/recommendations", response_model=RecommendationResponse)
    async def recommendations(employee_id: str, request: Request, user=Depends(identity)):
        store = request.app.state.store
        data = store.data
        authorize_employee(employee_id, user, data)
        key = (employee_id, data.version, model_configuration())
        cache = request.app.state.recommendation_cache
        with store.lock:
            cached = cache.get(key)
        if cached is not None:
            return cached
        result = await recommend(build_context(data, employee_id))
        with store.lock:
            # A provider request may finish after an import/completion has committed.
            transient_failure = result.fallback_reason in {"AI_TIMEOUT", "AI_PROVIDER_ERROR", "INVALID_AI_RESPONSE"}
            if store.data.version == data.version and key[2] == model_configuration() and not transient_failure:
                if len(cache) >= 512:
                    cache.pop(next(iter(cache)))
                cache[key] = result
        return result

    @app.get("/api/events")
    def events(request: Request, user=Depends(identity)):
        return list(request.app.state.store.data.events.values())

    @app.get("/api/skills")
    def skills(request: Request, user=Depends(identity)):
        data = request.app.state.store.data
        return {"skills": list(data.skills.values()), "role_profiles": list(data.role_profiles.values())}

    @app.post("/api/employees/{employee_id}/complete", response_model=CompletionResponse)
    def complete(employee_id: str, body: CompletionRequest, request: Request, user=Depends(identity)):
        store = request.app.state.store
        with store.lock:
            authorize_employee(employee_id, user, store.data)
            before = store.data.version
            result = store.complete(employee_id, body, user)
            if store.data.version != before:
                request.app.state.recommendation_cache.clear()
        return result

    @app.post("/api/admin/import", response_model=ImportResponse)
    async def import_data(
        request: Request,
        employees: Annotated[UploadFile | None, File()] = None,
        history: Annotated[UploadFile | None, File()] = None,
        user=Depends(require_hr),
    ):
        async def read_upload(upload: UploadFile | None) -> bytes | None:
            if upload is None:
                return None
            limit = 5 * 1024 * 1024
            raw = await upload.read(limit + 1)
            if len(raw) > limit:
                raise DatasetError('Maximum upload size is 5 MiB per file')
            return raw
        employees_raw = await read_upload(employees)
        history_raw = await read_upload(history)
        store = request.app.state.store
        with store.lock:
            before = store.data.version
            result = store.import_files(employees_raw, history_raw)
            if store.data.version != before:
                request.app.state.recommendation_cache.clear()
        return result

    @app.get("/api/hr/overview", response_model=HRResponse)
    def hr_overview(request: Request, user=Depends(require_hr)):
        return overview(request.app.state.store.data)

    dist = ROOT/"frontend"/"dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app

app = create_app()
