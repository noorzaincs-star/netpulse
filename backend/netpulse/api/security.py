import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from netpulse.core.config import PUBLIC_DEMO_TARGETS


async def require_admin(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    settings = request.app.state.settings
    if not settings.public_demo_mode:
        return
    if not settings.admin_token:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "admin_auth_unavailable",
                "message": "Admin writes are disabled because ADMIN_TOKEN is not configured.",
            },
        )
    scheme, separator, supplied_token = (authorization or "").partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(
            supplied_token.encode("utf-8"),
            settings.admin_token.encode("utf-8"),
        )
    ):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            detail={"code": "admin_auth_required", "message": "A valid admin bearer token is required."},
        )


AdminRequired = Depends(require_admin)


def demo_device_ids():
    from sqlalchemy import select

    from netpulse.models import Device

    return select(Device.id).where(Device.hostname.in_(PUBLIC_DEMO_TARGETS))


def visible_demo_hosts(request: Request) -> frozenset[str] | None:
    if request.app.state.settings.public_demo_mode:
        return PUBLIC_DEMO_TARGETS
    return None
