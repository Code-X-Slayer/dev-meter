"""Service and API-key HTTP endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dev_meter.api.dependencies import get_current_identity
from dev_meter.api.schemas import (
    ApiKeyCreate,
    ApiKeyMetadata,
    ApiKeyResponse,
    ServiceCreate,
    ServiceResponse,
)
from dev_meter.infrastructure.database.session import get_db_session
from dev_meter.services.registry import (
    create_api_key,
    create_service,
    get_service,
    list_api_keys,
    list_services,
    revoke_api_key,
)

router = APIRouter(prefix="/v1")


@router.post(
    "/services",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_service(
    payload: ServiceCreate,
    session: Session = Depends(get_db_session),
    owner_id: str = Depends(get_current_identity),
) -> ServiceResponse:
    """Register a service for the authenticated administrator."""
    try:
        return create_service(
            session,
            owner_id,
            payload.name,
            str(payload.upstream_base_url),
        )
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service with this name already exists",
        ) from error


@router.get("/services", response_model=list[ServiceResponse])
def get_services(
    session: Session = Depends(get_db_session),
    owner_id: str = Depends(get_current_identity),
) -> list[ServiceResponse]:
    """List services for the authenticated administrator."""
    return list_services(session, owner_id)


@router.post(
    "/services/{service_id}/keys",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_api_key(
    service_id: UUID,
    payload: ApiKeyCreate,
    session: Session = Depends(get_db_session),
    owner_id: str = Depends(get_current_identity),
) -> ApiKeyResponse:
    """Create an API key and return its secret exactly once."""
    service = get_service(session, owner_id, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )
    key, secret = create_api_key(session, service, payload.name)
    return ApiKeyResponse(
        id=UUID(key.id),
        service_id=UUID(key.service_id),
        name=key.name,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        revoked_at=key.revoked_at,
        secret=secret,
    )


@router.get(
    "/services/{service_id}/keys",
    response_model=list[ApiKeyMetadata],
)
def get_api_keys(
    service_id: UUID,
    session: Session = Depends(get_db_session),
    owner_id: str = Depends(get_current_identity),
) -> list[ApiKeyMetadata]:
    """List API-key metadata without exposing secrets or hashes."""
    service = get_service(session, owner_id, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )
    return list_api_keys(session, service)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(
    key_id: UUID,
    session: Session = Depends(get_db_session),
    owner_id: str = Depends(get_current_identity),
) -> None:
    """Revoke an active API key."""
    if not revoke_api_key(session, owner_id, key_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active API key not found",
        )
