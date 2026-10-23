"""Protected gateway endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from dev_meter.infrastructure.database.models import Service
from dev_meter.infrastructure.database.session import get_db_session
from dev_meter.services.gateway import (
    count_requests_today,
    find_active_api_key,
    forward_request,
    record_usage,
)

router = APIRouter(prefix="/v1")


def parse_bearer_token(authorization: str | None) -> str:
    """Parse an Authorization header without exposing its value."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return token


@router.post("/gateway/{service_id}")
async def gateway(
    service_id: UUID,
    request: Request,
    session: Session = Depends(get_db_session),
) -> Response:
    """Authenticate, quota-check, and forward a JSON request."""
    token = parse_bearer_token(request.headers.get("authorization"))
    api_key = find_active_api_key(session, service_id, token)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if (
        count_requests_today(session, api_key.id)
        >= request.app.state.default_request_limit
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily request limit reached",
        )

    try:
        body = await request.json()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be valid JSON",
        ) from error

    service = session.get(Service, str(service_id))
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    allowed_headers = {}
    if content_type := request.headers.get("content-type"):
        allowed_headers["content-type"] = content_type
    if accept := request.headers.get("accept"):
        allowed_headers["accept"] = accept

    response, duration_ms, succeeded = await forward_request(
        request.app.state.http_client,
        service,
        body,
        allowed_headers,
    )
    record_usage(
        session,
        api_key,
        service,
        response.status_code if response is not None else None,
        duration_ms,
        succeeded,
    )
    if response is None:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Upstream service unavailable"},
        )
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return JSONResponse(
                status_code=response.status_code,
                content=response.json(),
            )
        except ValueError:
            pass
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=content_type or None,
    )
