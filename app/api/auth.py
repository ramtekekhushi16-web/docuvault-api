from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


def save_refresh_token(
    db: Session,
    user_id: int,
    refresh_token: str,
):
    payload = decode_refresh_token(refresh_token)

    expires_at = datetime.fromtimestamp(
        payload["exp"],
        tz=timezone.utc,
    )

    token_record = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at,
        is_revoked=False,
    )

    db.add(token_record)

    return token_record


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    save_refresh_token(
        db,
        user.id,
        refresh_token,
    )

    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    save_refresh_token(
        db,
        user.id,
        refresh_token,
    )

    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
def refresh_token(
    data: RefreshRequest,
    db: Session = Depends(get_db),
):
    try:
        payload = decode_refresh_token(
            data.refresh_token
        )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        token_hash = hash_refresh_token(
            data.refresh_token
        )

        stored_token = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash
            )
            .first()
        )

        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found",
            )

        if stored_token.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        now = datetime.now(timezone.utc)

        expires_at = stored_token.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        if expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )

        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
            )

        # Revoke old refresh token
        stored_token.is_revoked = True
        stored_token.revoked_at = now

        # Create new token pair
        new_access_token = create_access_token(
            user.id
        )

        new_refresh_token = create_refresh_token(
            user.id
        )

        save_refresh_token(
            db,
            user.id,
            new_refresh_token,
        )

        db.commit()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


@router.post("/logout")
def logout(
    data: LogoutRequest,
    db: Session = Depends(get_db),
):
    token_hash = hash_refresh_token(
        data.refresh_token
    )

    stored_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash
        )
        .first()
    )

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    if stored_token.is_revoked:
        return {
            "message": "Already logged out"
        }

    now = datetime.now(timezone.utc)

    stored_token.is_revoked = True
    stored_token.revoked_at = now

    db.commit()

    return {
        "message": "Logged out successfully"
    }


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
    }