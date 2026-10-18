from collections.abc import Generator

from sqlalchemy.orm import Session
from app.core.database import SessionLocal

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select

from app.models.student import Student

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_student(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Student:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise credentials_error
        student_id = UUID(subject)
    except (jwt.InvalidTokenError, ValueError):
        raise credentials_error from None

    student = db.scalars(
        select(Student).where(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
    ).first()

    if student is None:
        raise credentials_error

    return student