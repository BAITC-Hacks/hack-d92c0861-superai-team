"""Owner: Damir. Read endpoints work. The three explicit 501 routes are MVP work items."""
from __future__ import annotations
from contextlib import asynccontextmanager
import hmac
import os
from pathlib import Path
from typing import Annotated
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from ai.engine import recommend
from backend.data_loader import Dataset, load_dataset
from backend.domain import build_context, profile
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


def not_implemented(feature: str):
    raise HTTPException(501, detail={"code": "NOT_IMPLEMENTED", "message": feature+" — задача backend"})


def create_app(dataset: Dataset | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        load_dotenv(ROOT/".env", override=False)
        folder = Path(os.getenv("DATA_DIR", "docs"))
        if not folder.is_absolute(): folder = ROOT/folder
        application.state.dataset = dataset if dataset is not None else load_dataset(folder)
        hr_token = os.getenv("HR_TOKEN", "")
        employee_token = os.getenv("EMPLOYEE_TOKEN", "")
        if hr_token and hr_token == employee_token:
            raise RuntimeError("HR_TOKEN and EMPLOYEE_TOKEN must be different")
        application.state.auth = {"hr": hr_token, "employee": employee_token,
                                  "employee_id": os.getenv("EMPLOYEE_ID", "E0001")}
        yield

    app = FastAPI(title="Career Quest — starter API", version="1.0.0", lifespan=lifespan)

    @app.get("/api/health")
    def health(request: Request):
        data = request.app.state.dataset
        return {"status": "ok", "stage": "starter", "as_of_date": data.as_of_date,
                "data_version": data.version, "employees_count": len(data.employees)}

    @app.get("/api/auth/me")
    def me(user=Depends(identity)):
        return user

    @app.get("/api/employees")
    def employees(request: Request, user=Depends(require_hr)):
        return [{k: e[k] for k in ("employee_id", "full_name", "role", "grade", "department")}
                for e in request.app.state.dataset.employees.values()]

    @app.get("/api/employees/{employee_id}", response_model=ProfileResponse)
    def get_profile(employee_id: str, request: Request, user=Depends(identity)):
        data = request.app.state.dataset
        authorize_employee(employee_id, user, data)
        return profile(data, employee_id)

    @app.get("/api/employees/{employee_id}/recommendations", response_model=RecommendationResponse)
    async def recommendations(employee_id: str, request: Request, user=Depends(identity)):
        data = request.app.state.dataset
        authorize_employee(employee_id, user, data)
        # TODO Damir: cache by (employee_id, data.version, model config), invalidate on writes.
        return await recommend(build_context(data, employee_id))

    @app.get("/api/events")
    def events(request: Request, user=Depends(identity)):
        return list(request.app.state.dataset.events.values())

    @app.get("/api/skills")
    def skills(request: Request, user=Depends(identity)):
        data = request.app.state.dataset
        return {"skills": list(data.skills.values()), "role_profiles": list(data.role_profiles.values())}

    @app.post("/api/employees/{employee_id}/complete", response_model=CompletionResponse)
    def complete(employee_id: str, body: CompletionRequest, request: Request, user=Depends(identity)):
        authorize_employee(employee_id, user, request.app.state.dataset)
        # TODO Damir: transactional state + optimistic version + durable idempotency ledger.
        # Recheck eligibility on server; client must NEVER submit skill levels/gain/role.
        not_implemented("Сохранение завершения и обновление прогресса")

    @app.post("/api/admin/import", response_model=ImportResponse)
    async def import_data(
        request: Request,
        employees: Annotated[UploadFile | None, File()] = None,
        history: Annotated[UploadFile | None, File()] = None,
        user=Depends(require_hr),
    ):
        # TODO Damir: multipart fields 'employees' (wrapped JSON), 'history' (CSV).
        # At least one file; max 5 MiB per file; MERGE not replace; validate assembled snapshot.
        # Unknown references or conflicting record IDs => 422 and NO partial writes.
        not_implemented("Импорт дополнительных профилей и истории")

    @app.get("/api/hr/overview", response_model=HRResponse)
    def hr_overview(request: Request, user=Depends(require_hr)):
        # TODO Damir: deterministic aggregation, NO 200 LLM calls.
        not_implemented("HR-сводка")

    dist = ROOT/"frontend"/"dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app

app = create_app()
