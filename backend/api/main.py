"""FastAPI entry point. The browser talks only to this API; only the backend holds keys."""

from typing import Optional

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from hg.config import get_settings
from hg.flow import service
from hg.flow.checkpoint import checkpointer_kind
from hg.flow.service import CaseView, FlowError, Sample
from hg.schemas import AuditEntry, Choice, HeirInputs

DISCLAIMER = "Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical."

app = FastAPI(title="HeritageGuard API", description=DISCLAIMER, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(FlowError)
def flow_error(_: Request, exc: FlowError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


class NewCase(BaseModel):
    sample_id: Optional[str] = None
    beneficiary_id: Optional[str] = None


class FieldCorrection(BaseModel):
    document_id: str
    value: str


class ApprovalBody(BaseModel):
    approved: bool = True
    note: str = ""


class ChoiceBody(BaseModel):
    choice: Choice
    opt_in_rmd_deposit: bool = False


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "notice": DISCLAIMER, "checkpointer": checkpointer_kind()}


@app.get("/samples")
def samples() -> list[Sample]:
    return service.list_samples()


@app.post("/cases")
def create_case(body: NewCase) -> CaseView:
    return service.create_case(body.sample_id, body.beneficiary_id)


@app.post("/cases/{case_id}/documents")
async def upload_documents(case_id: str, files: list[UploadFile] = File(...)) -> CaseView:
    uploads = [(f.filename or "upload", await f.read(), f.content_type or "application/octet-stream") for f in files]
    return service.add_documents(case_id, uploads)


@app.patch("/cases/{case_id}/fields/{field}")
def correct_field(case_id: str, field: str, body: FieldCorrection) -> CaseView:
    return service.correct_field(case_id, field, body.document_id, body.value)


@app.post("/cases/{case_id}/submit-for-review")
def submit_for_review(case_id: str) -> CaseView:
    """Send remaining needs-review items (no failures) to estate operations."""
    return service.submit_for_review(case_id)


@app.post("/cases/{case_id}/approve")
def approve(case_id: str, body: Optional[ApprovalBody] = None) -> CaseView:
    body = body or ApprovalBody()
    return service.approve(case_id, body.approved, note=body.note)


@app.post("/cases/{case_id}/simulate")
def simulate(case_id: str, inputs: HeirInputs) -> CaseView:
    return service.simulate(case_id, inputs)


@app.post("/cases/{case_id}/choice")
def choose(case_id: str, body: ChoiceBody) -> CaseView:
    return service.choose(case_id, body.choice, body.opt_in_rmd_deposit)


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> CaseView:
    return service.get_case(case_id)


@app.get("/cases/{case_id}/graph")
def case_graph(case_id: str) -> dict:
    return service.case_graph(case_id)


@app.get("/cases/{case_id}/audit")
def audit(case_id: str) -> list[AuditEntry]:
    return service.audit_entries(case_id)


@app.get("/cases/{case_id}/ai-log")
def ai_log(case_id: str) -> list[dict]:
    return service.ai_log(case_id)


@app.get("/cases/{case_id}/documents/{document_id}/file")
def document_file(case_id: str, document_id: str) -> Response:
    name, data = service.document_file(case_id, document_id)
    media = "application/pdf" if data[:4] == b"%PDF" else "application/octet-stream"
    return Response(data, media_type=media, headers={"Content-Disposition": f'inline; filename="{name}"'})
