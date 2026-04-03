import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.database import get_db
from ...core.security import (
    RedisManager,
    create_access_token,
    generate_magic_link_token,
    hash_password,
    verify_password,
    verify_token,
)
from ...models.models import AuthenticationAttempt, AuthMethod, TicketStatus, User, UserRole
from ...schemas.schemas import (
    MagicLinkRequest,
    MagicLinkVerify,
    MessageResponse,
    PasswordLoginRequest,
    SetupPasswordRequest,
    TokenResponse,
    UserResponse,
)
from ...services.email_service import email_service
from ...services.ticket_service import TicketService


def set_auth_cookie(response: Response, token: str) -> None:
    """Set httpOnly authentication cookie with secure settings."""
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.AUTH_COOKIE_PATH,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.AUTH_COOKIE_DOMAIN or None,
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the authentication cookie."""
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path=settings.AUTH_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN or None,
    )

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Rate limiting constants
AUTH_RATE_LIMIT_REQUESTS = 5  # Max requests per window
AUTH_RATE_LIMIT_WINDOW = 60  # Window in seconds (1 minute)


async def check_auth_rate_limit(request: Request):
    """
    Rate limit authentication endpoints by IP address.
    Raises 429 Too Many Requests if limit exceeded.
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"auth:{client_ip}"

    allowed, remaining = await RedisManager.check_rate_limit(
        rate_key, AUTH_RATE_LIMIT_REQUESTS, AUTH_RATE_LIMIT_WINDOW
    )

    if not allowed:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
            headers={"Retry-After": str(AUTH_RATE_LIMIT_WINDOW)},
        )

    return remaining


@router.post("/magic-link", response_model=MessageResponse)
async def request_magic_link(
    request: MagicLinkRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Request a magic link for passwordless authentication.
    Sends an email with a one-time login link.
    Rate limited to prevent abuse.
    """
    # Check rate limit
    await check_auth_rate_limit(http_request)

    email = request.email.lower()

    # Check if user exists, if not create one
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create user for demo purposes
        user = User(email=email)
        db.add(user)
        await db.commit()

    # Generate magic link token
    token = generate_magic_link_token()

    # Store token in Redis
    await RedisManager.store_magic_link(token, email)

    # Send email
    await email_service.send_magic_link(email, token)

    return MessageResponse(
        message="Magic link sent! Check your email to sign in.", success=True
    )


@router.post("/verify", response_model=TokenResponse)
async def verify_magic_link(
    verify_request: MagicLinkVerify,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Verify magic link token and return JWT access token.
    Sets httpOnly cookie with access token for security.
    """
    # Extract client info for logging
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]

    # Verify the magic link token
    email = await RedisManager.verify_magic_link(verify_request.token)

    if not email:
        # Log failed magic link attempt (no email to log)
        auth_attempt = AuthenticationAttempt(
            user_id=None,
            email="unknown",
            success=False,
            method=AuthMethod.MAGIC_LINK,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason="invalid_or_expired_token",
        )
        db.add(auth_attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link",
        )

    # Get user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        auth_attempt = AuthenticationAttempt(
            user_id=None,
            email=email,
            success=False,
            method=AuthMethod.MAGIC_LINK,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason="user_not_found",
        )
        db.add(auth_attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Log successful magic link auth
    auth_attempt = AuthenticationAttempt(
        user_id=user.id,
        email=email,
        success=True,
        method=AuthMethod.MAGIC_LINK,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(auth_attempt)

    # Update last login
    # Use naive UTC to match Column(DateTime) / TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create audit ticket for magic link login
    ticket = await TicketService.create_ticket(
        db=db,
        action_type="USER_LOGIN_MAGIC_LINK",
        entity_type="User",
        entity_id=user.id,
        status=TicketStatus.SUCCESS,
        user_id=user.id,
        request_payload={"email": email, "method": "magic_link"},
        response_data={"login_time": datetime.now(timezone.utc).isoformat()},
        ip_address=ip_address,
        user_agent=user_agent,
        tags=["auth", "login", "magic_link"],
    )

    await db.commit()

    logger.info(f"Magic link auth: email={email}, success=True, ip={ip_address}, ticket={ticket.ticket_id}")

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    # Set httpOnly cookie for secure token storage
    set_auth_cookie(response, access_token)

    return TokenResponse(
        access_token=access_token, user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def password_login(
    login_request: PasswordLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Login with email and password.
    Sets httpOnly cookie with access token for security.
    Rate limited to prevent brute force attacks.
    """
    # Check rate limit
    await check_auth_rate_limit(request)

    email = login_request.email.lower()

    # Extract client info for logging
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]

    # Helper function to log auth attempt
    async def log_auth_attempt(user_id, success: bool, failure_reason: str = None):
        auth_attempt = AuthenticationAttempt(
            user_id=user_id,
            email=email,
            success=success,
            method=AuthMethod.PASSWORD,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
        )
        db.add(auth_attempt)
        await db.commit()
        logger.info(
            f"Auth attempt: email={email}, success={success}, "
            f"ip={ip_address}, reason={failure_reason}"
        )

    # Find user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        await log_auth_attempt(
            user.id if user else None, False, "user_not_found_or_no_password"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not verify_password(login_request.password, user.password_hash):
        await log_auth_attempt(user.id, False, "invalid_password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not user.is_active:
        await log_auth_attempt(user.id, False, "account_disabled")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled"
        )

    # PREINTRODUCER with NDA not yet approved cannot log in (must use setup-password session until admin approves)
    if user.role == UserRole.PREINTRODUCER and not user.nda_signed:
        await log_auth_attempt(user.id, False, "preintroducer_nda_pending")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your NDA is pending approval. You cannot log in until an administrator approves your NDA.",
        )

    # Log successful authentication
    await log_auth_attempt(user.id, True)

    # Update last login
    # Use naive UTC to match Column(DateTime) / TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create audit ticket for login
    ticket = await TicketService.create_ticket(
        db=db,
        action_type="USER_LOGIN",
        entity_type="User",
        entity_id=user.id,
        status=TicketStatus.SUCCESS,
        user_id=user.id,
        request_payload={"email": email},
        response_data={"login_time": datetime.now(timezone.utc).isoformat()},
        ip_address=ip_address,
        user_agent=user_agent,
        tags=["auth", "login"],
    )

    await db.commit()

    logger.info(f"Login successful: email={email}, ticket={ticket.ticket_id}")

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    # Set httpOnly cookie for secure token storage
    set_auth_cookie(response, access_token)

    return TokenResponse(
        access_token=access_token, user=UserResponse.model_validate(user)
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Logout user by blacklisting their JWT token and clearing the auth cookie.
    The token will remain blacklisted until its original expiration time.
    """
    # Try to get token from cookie first, then fall back to Authorization header
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)

    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")

    # Always clear the auth cookie
    clear_auth_cookie(response)

    # Blacklist the token if we found one
    if token:
        payload = verify_token(token)
        if payload and "exp" in payload:
            # Calculate remaining time until token expiration
            exp_timestamp = payload["exp"]
            now_timestamp = datetime.now(timezone.utc).timestamp()
            remaining_seconds = max(int(exp_timestamp - now_timestamp), 0)

            # Blacklist the token until it expires
            if remaining_seconds > 0:
                await RedisManager.blacklist_token(token, remaining_seconds)

    return MessageResponse(message="Successfully logged out", success=True)


@router.get("/validate-invitation/{token}")
async def validate_invitation_token(token: str, db: AsyncSession = Depends(get_db)):  # noqa: B008
    """
    Check if invitation token is valid.
    Returns user info if valid for the setup password page.
    """
    result = await db.execute(select(User).where(User.invitation_token == token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Invalid invitation link")

    # Use naive UTC for comparison with DB timestamp
    if user.invitation_expires_at and user.invitation_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=410, detail="Invitation link has expired")

    return {
        "valid": True,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role.value if user.role else None,
    }


@router.post("/setup-password", response_model=TokenResponse)
async def setup_password_from_invitation(
    setup_request: SetupPasswordRequest,  # noqa: B008
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Set password from invitation link.
    Sets httpOnly cookie with access token for security.
    Password requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 special character
    """
    import re

    token = setup_request.token
    password = setup_request.password
    confirm_password = setup_request.confirm_password

    # Validate passwords match
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Validate password strength
    if len(password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=400, detail="Password must contain at least 1 uppercase letter"
        )
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
        raise HTTPException(
            status_code=400, detail="Password must contain at least 1 special character"
        )

    # Find user by invitation token
    result = await db.execute(select(User).where(User.invitation_token == token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=401, detail="Invalid or expired invitation link"
        )

    # Check expiration (use naive UTC for comparison with DB timestamp)
    if user.invitation_expires_at and user.invitation_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=401, detail="Invitation link has expired")

    # Set password and activate
    user.password_hash = hash_password(password)
    user.invitation_token = None  # Clear token
    user.invitation_expires_at = None
    user.must_change_password = False
    user.is_active = True
    # Use naive UTC to match Column(DateTime) / TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()
    await db.refresh(user)

    # Welcome email (fire-and-forget)
    try:
        from ...services.email_service import email_service as _email_svc
        await _email_svc.send_welcome_activated(user.email, user.first_name or "", role=user.role.value if user.role else "")
    except Exception:
        logger.debug("Welcome email failed for %s", user.email)

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    # Set httpOnly cookie for secure token storage
    set_auth_cookie(response, access_token)

    return TokenResponse(
        access_token=access_token, user=UserResponse.model_validate(user)
    )


# Note: get_current_user is defined in core/security.py
# Use: from app.core.security import get_current_user
