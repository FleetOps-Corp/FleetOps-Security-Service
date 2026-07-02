"""
Auth Service — API Schemas / DTOs (API Layer)
==============================================
SAD Reference: "DTOs · Validación de acceso" (pág. 5 diagram — Auth Service <<API>>)
Pattern: DTO (Data Transfer Object) — minimizes data exposure

These schemas define the public API contract for the Auth Service.
Pydantic performs automatic validation on deserialization (SAD: Validator tactic).
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """
    DTO for POST /register.
    SAD §3: new users register via this endpoint.
    """

    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
    )

    @field_validator("password")
    @classmethod
    def password_must_have_digit(cls, v: str) -> str:
        """
        SAD §7: Fiabilidad — Validator tactic.
        Ensures minimum password strength to protect user credentials.
        """
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class LoginRequest(BaseModel):
    """DTO for POST /login."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class TokenResponse(BaseModel):
    """
    DTO returned on successful login.
    SAD §3 flow step 6: "El token es devuelto al usuario."
    """

    access_token: str = Field(..., description="Signed JWT — include as Bearer token in subsequent requests")
    token_type: str = Field(default="bearer", description="Always 'bearer'")
    expires_in: int = Field(..., description="Token lifetime in seconds")


class UserResponse(BaseModel):
    """DTO returned on successful registration — excludes sensitive fields."""

    id: str
    email: str
    role: str
    is_active: bool


class ErrorResponse(BaseModel):
    """Standardized error response."""

    error: str
    detail: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str = "1.0.0"
