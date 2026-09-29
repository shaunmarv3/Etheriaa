"""Upload endpoints (spec 5.1, 5.2, 10). Shapes match the frontend's api.ts:
upload -> {document_id, filename, status, page_count}; list -> {documents: [...]}.
Another user's document is reported as not found, never as forbidden."""

from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from etheria.auth.dependencies import ClientMetaDep, CurrentUserId, RateLimiterDep
from etheria.core.errors import (
    AppError,
    NotFound,
    PayloadTooLarge,
    ServiceUnavailable,
    UnsupportedMediaType,
)
from etheria.db.models import Document
from etheria.db.repositories import audit
from etheria.db.repositories import documents as repo
from etheria.ingestion.schemas import IngestInput
from etheria.ingestion.storage import FileStore
from etheria.ingestion.temporal import TASK_QUEUE, connect, workflow_id
from etheria.ingestion.validation import MAX_BYTES, UploadRejected, inspect_upload
from etheria.ingestion.workflow import IngestDocumentWorkflow

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOADS_PER_HOUR = 10


def file_store(request: Request) -> FileStore:
    return request.app.state.file_store


async def temporal_client(request: Request) -> Any:
    state = request.app.state
    if state.temporal is None:
        state.temporal = await connect(state.settings)
    return state.temporal


StoreDep = Annotated[FileStore, Depends(file_store)]


def _rejected(e: UploadRejected) -> AppError:
    if e.code == "file_too_large":
        return PayloadTooLarge(e.message)
    if e.code == "unsupported_type":
        return UnsupportedMediaType(e.message)
    return AppError(e.message, code=e.code)


def _upload_body(doc: Document) -> dict[str, Any]:
    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status,
        "page_count": doc.page_count,
    }


def _list_item(doc: Document) -> dict[str, Any]:
    return {
        **_upload_body(doc),
        "file_type": "pdf" if doc.mime_type == "application/pdf" else "image",
        "uploaded_at": doc.uploaded_at.isoformat(),
        "doc_type": doc.doc_type,
        "summary": doc.summary,
        "report_date": doc.report_date.isoformat() if doc.report_date else None,
    }


@router.post("/", status_code=201)
async def upload(
    request: Request,
    file: UploadFile,
    user_id: CurrentUserId,
    limiter: RateLimiterDep,
    meta: ClientMetaDep,
    store: StoreDep,
) -> Response:
    await limiter.enforce(f"upload:{user_id}", UPLOADS_PER_HOUR, 3600)
    data = await file.read(MAX_BYTES + 1)
    try:
        info = inspect_upload(data, file.filename)
    except UploadRejected as e:
        raise _rejected(e) from None

    db = request.app.state.db
    async with db.for_user(user_id) as s:
        existing = await repo.get_by_sha(s, user_id, info.sha256)
    if existing is not None:
        return JSONResponse(_upload_body(existing), status_code=200)

    storage_key = store.save(data)
    try:
        async with db.for_user(user_id) as s:
            doc = await repo.create(
                s,
                user_id=user_id,
                filename=info.display_name,
                mime_type=info.mime_type,
                storage_key=storage_key,
                sha256=info.sha256,
                size_bytes=len(data),
                page_count=info.page_count,
            )
            await audit.record(
                s,
                "upload",
                user_ref=str(user_id),
                ip=meta.ip,
                user_agent=meta.user_agent,
                resource_type="document",
                resource_id=str(doc.id),
            )
    except IntegrityError:
        # A concurrent upload of the same file won the unique (user_id, sha256)
        # race after our duplicate check: answer as for a duplicate.
        store.delete(storage_key)
        async with db.for_user(user_id) as s:
            existing = await repo.get_by_sha(s, user_id, info.sha256)
        if existing is None:
            raise
        return JSONResponse(_upload_body(existing), status_code=200)
    except BaseException:
        store.delete(storage_key)
        raise

    try:
        client = await temporal_client(request)
        await client.start_workflow(
            IngestDocumentWorkflow.run,
            IngestInput(document_id=doc.id, user_id=user_id),
            id=workflow_id(doc.id),
            task_queue=TASK_QUEUE,
        )
    except Exception:
        # No workflow means the document would sit in "pending" forever: undo it.
        async with db.for_user(user_id) as s:
            await repo.delete(s, user_id, doc.id)
        store.delete(storage_key)
        raise ServiceUnavailable(
            "Document processing is unavailable, try again shortly", code="ingestion_unavailable"
        ) from None
    return JSONResponse(_upload_body(doc), status_code=201)


@router.get("/")
async def list_documents(request: Request, user_id: CurrentUserId) -> dict[str, Any]:
    async with request.app.state.db.for_user(user_id) as s:
        docs = await repo.list_for_user(s, user_id)
    return {"documents": [_list_item(d) for d in docs]}


@router.get("/{document_id}/download")
async def download(
    request: Request,
    document_id: UUID,
    user_id: CurrentUserId,
    meta: ClientMetaDep,
    store: StoreDep,
) -> Response:
    async with request.app.state.db.for_user(user_id) as s:
        doc = await repo.get(s, user_id, document_id)
        if doc is None:
            raise NotFound("Document not found")
        await audit.record(
            s,
            "download",
            user_ref=str(user_id),
            ip=meta.ip,
            user_agent=meta.user_agent,
            resource_type="document",
            resource_id=str(doc.id),
        )
    try:
        content = store.read(doc.storage_key)
    except FileNotFoundError:
        raise NotFound("Document file not found") from None
    return Response(
        content,
        media_type=doc.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.filename)}"},
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    request: Request,
    document_id: UUID,
    user_id: CurrentUserId,
    meta: ClientMetaDep,
    store: StoreDep,
) -> Response:
    async with request.app.state.db.for_user(user_id) as s:
        storage_key = await repo.delete(s, user_id, document_id)
        if storage_key is None:
            raise NotFound("Document not found")
        await audit.record(
            s,
            "document_delete",
            user_ref=str(user_id),
            ip=meta.ip,
            user_agent=meta.user_agent,
            resource_type="document",
            resource_id=str(document_id),
        )
    store.delete(storage_key)
    return Response(status_code=204)
