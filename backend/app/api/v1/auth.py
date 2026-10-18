from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.student import Student
from app.schemas.auth import (
    StudentLogin,
    StudentRead,
    StudentRegister,
    TokenResponse,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=StudentRead,
    status_code=status.HTTP_201_CREATED,
)
def register_student(
    payload: StudentRegister,
    db: Annotated[Session, Depends(get_db)],
) -> Student:
    email = str(payload.email).strip().lower()

    existing_student = db.scalar(
        select(Student).where(Student.email == email)
    )
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    student = Student(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(student)

    try:
        db.commit()
        db.refresh(student)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None

    return student


@router.post("/login", response_model=TokenResponse)
def login_student(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    email = form.username.strip().lower()

    student = db.scalar(
        select(Student).where(Student.email == email)
    )

    if (
        student is None
        or student.password_hash is None
        or not verify_password(form.password, student.password_hash)
        or not student.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(str(student.id))
    )


@router.get("/me", response_model=StudentRead)
def get_my_profile(
    current_student: Annotated[Student, Depends(get_current_student)],
) -> Student:
    return current_student
