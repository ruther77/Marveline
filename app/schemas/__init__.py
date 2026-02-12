"""Schemas Pydantic pour validation des entrées/sorties de l'API."""
from app.schemas.base import (
    BaseSchema,
    TimestampSchema,
    TenantSchema,
    SoftDeleteSchema,
    IDSchema,
    EntityResponseSchema,
)
from app.schemas.common import (
    PaginationParams,
    PaginatedResponse,
    ErrorDetail,
    ErrorResponse,
    SuccessResponse,
)
from app.schemas.customer import (
    CustomerBase,
    CustomerCreate,
    CustomerUpdate,
    CustomerList,
    CustomerResponse,
)
from app.schemas.product import (
    ProductBase,
    ProductCreate,
    ProductUpdate,
    ProductList,
    ProductResponse,
)
from app.schemas.reservation import (
    ReservationLineBase,
    ReservationLineCreate,
    ReservationLineResponse,
    ReservationBase,
    ReservationCreate,
    ReservationUpdate,
    ReservationList,
    ReservationResponse,
)
from app.schemas.invoice import (
    InvoiceBase,
    InvoiceCreate,
    InvoiceUpdate,
    AddPaymentRequest,
    InvoiceList,
    InvoiceResponse,
)
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserInfo,
    ChangePasswordRequest,
)

__all__ = [
    # Base schemas
    "BaseSchema",
    "TimestampSchema",
    "TenantSchema",
    "SoftDeleteSchema",
    "IDSchema",
    "EntityResponseSchema",
    # Common schemas
    "PaginationParams",
    "PaginatedResponse",
    "ErrorDetail",
    "ErrorResponse",
    "SuccessResponse",
    # Customer schemas
    "CustomerBase",
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerList",
    "CustomerResponse",
    # Product schemas
    "ProductBase",
    "ProductCreate",
    "ProductUpdate",
    "ProductList",
    "ProductResponse",
    # Reservation schemas
    "ReservationLineBase",
    "ReservationLineCreate",
    "ReservationLineResponse",
    "ReservationBase",
    "ReservationCreate",
    "ReservationUpdate",
    "ReservationList",
    "ReservationResponse",
    # Invoice schemas
    "InvoiceBase",
    "InvoiceCreate",
    "InvoiceUpdate",
    "AddPaymentRequest",
    "InvoiceList",
    "InvoiceResponse",
    # Auth schemas
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "UserInfo",
    "ChangePasswordRequest",
]
