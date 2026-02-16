"""Messages d'erreur et de statut HTTP standardisés.

Ce module centralise tous les messages d'erreur utilisés dans l'application
pour garantir la cohérence et éviter les typos.
"""


class ErrorMessages:
    """Messages d'erreur HTTP standardisés.

    Usage :
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.PRODUCT_NOT_FOUND
        )
    """

    # ─────────────────────────────────────────────────────────────────────
    # Ressources non trouvées (404 NOT FOUND)
    # ─────────────────────────────────────────────────────────────────────

    PRODUCT_NOT_FOUND = "Product not found"
    RESERVATION_NOT_FOUND = "Reservation not found"
    INVOICE_NOT_FOUND = "Invoice not found"
    CUSTOMER_NOT_FOUND = "Customer not found"
    USER_NOT_FOUND = "User not found"
    SESSION_NOT_FOUND = "Session not found or access denied"

    # ─────────────────────────────────────────────────────────────────────
    # Validation métier (400 BAD REQUEST)
    # ─────────────────────────────────────────────────────────────────────

    INSUFFICIENT_STOCK = "Insufficient stock available"
    SKU_ALREADY_EXISTS = "Product with this SKU already exists"
    EMAIL_ALREADY_EXISTS = "Email already registered"
    AVAILABLE_EXCEEDS_STOCK = "available_quantity cannot exceed stock_quantity"

    # ─────────────────────────────────────────────────────────────────────
    # Authentification & Autorisation (401 UNAUTHORIZED / 403 FORBIDDEN)
    # ─────────────────────────────────────────────────────────────────────

    INVALID_CREDENTIALS = "Invalid email or password"
    ACCOUNT_INACTIVE = "Account is inactive"
    INVALID_TOKEN = "Could not validate credentials"
    TOKEN_EXPIRED = "Token has expired"
    INSUFFICIENT_PERMISSIONS = "Insufficient permissions for this action"
    INVALID_REFRESH_TOKEN = "Invalid refresh token"
    INVALID_REFRESH_TOKEN_TYPE = "Invalid token type (expected refresh token)"
    INVALID_TOKEN_PAYLOAD = "Invalid token payload"
    INVALID_TOKEN_TYPE = "Invalid token type"
    REFRESH_TOKEN_REVOKED = "Refresh token has been revoked"
    REFRESH_TOKEN_REPLAY = "Refresh token reuse detected — all sessions revoked"
    ACCESS_TOKEN_REVOKED = "Access token has been revoked"
    CURRENT_PASSWORD_INCORRECT = "Current password is incorrect"
    INVALID_ROLE = "Invalid role. Must be: admin, manager, or staff"

    # ─────────────────────────────────────────────────────────────────────
    # MFA (400 / 401)
    # ─────────────────────────────────────────────────────────────────────

    MFA_ALREADY_ENABLED = "MFA is already enabled for this user"
    MFA_NOT_ENABLED = "MFA is not enabled for this user"
    MFA_NO_PENDING_SETUP = "No pending MFA setup found"
    MFA_INVALID_TOTP_CODE = "Invalid TOTP code"
    MFA_CODE_ALREADY_USED = "TOTP code already used (anti-replay)"
    MFA_INVALID_RECOVERY_CODE = "Invalid recovery code"
    MFA_NO_RECOVERY_CODES = "No recovery codes available"
    MFA_SESSION_INVALID = "MFA session token is invalid or expired"
    MFA_MUST_PROVIDE_CODE = "Must provide either totp_code or recovery_code"
    MFA_BOTH_CODES_PROVIDED = "Provide either totp_code or recovery_code, not both"

    # ─────────────────────────────────────────────────────────────────────
    # Password Reset (400 / 401)
    # ─────────────────────────────────────────────────────────────────────

    PASSWORD_RESET_TOKEN_INVALID = "Invalid or expired password reset token"
    PASSWORD_RESET_TOKEN_EXPIRED = "Password reset token has expired"
    PASSWORD_RESET_RATE_LIMITED = "Too many password reset requests. Please try again later."

    # ─────────────────────────────────────────────────────────────────────
    # CSRF Protection (403 FORBIDDEN)
    # ─────────────────────────────────────────────────────────────────────

    CSRF_TOKEN_MISSING = "CSRF token manquant"
    CSRF_TOKEN_INVALID = "CSRF token invalide ou expiré"
    CSRF_TOKEN_GENERATION_FAILED = "Failed to generate CSRF token. Redis unavailable."

    # ─────────────────────────────────────────────────────────────────────
    # Rate Limiting (429 TOO MANY REQUESTS)
    # ─────────────────────────────────────────────────────────────────────

    TOO_MANY_REQUESTS = "Too many requests"

    # ─────────────────────────────────────────────────────────────────────
    # Logique métier réservations (400 BAD REQUEST)
    # ─────────────────────────────────────────────────────────────────────

    RESERVATION_NOT_DRAFT = "Reservation must be in draft status to be modified"
    RESERVATION_ALREADY_CONFIRMED = "Reservation is already confirmed"
    RESERVATION_ALREADY_CANCELLED = "Reservation is already cancelled"
    RESERVATION_REFERENCE_OVERFLOW = "Cannot generate unique reference (counter overflow)"

    # ─────────────────────────────────────────────────────────────────────
    # Logique métier factures (400 BAD REQUEST)
    # ─────────────────────────────────────────────────────────────────────

    INVOICE_ALREADY_PAID = "Invoice is already paid"
    INVOICE_ALREADY_EXISTS = "Invoice already exists for this reservation"
    PAYMENT_EXCEEDS_TOTAL = "Payment amount exceeds invoice total"
    PAYMENT_AMOUNT_INVALID = "Payment amount must be positive"
    STOCK_RESERVATION_FAILED = "Failed to reserve stock"
    INVOICE_CANCELLED_NO_PAYMENT = "Cannot add payment to cancelled invoice"
    INVOICE_PAID_NO_MODIFY = "Cannot modify paid invoice"
    INVOICE_PAID_NO_CANCEL = "Cannot cancel paid invoice"
    INVOICE_NUMBER_OVERFLOW = "Cannot generate unique invoice number (counter overflow)"

    # ─────────────────────────────────────────────────────────────────────
    # Categories (400 / 404)
    # ─────────────────────────────────────────────────────────────────────

    CATEGORY_NOT_FOUND = "Category not found"
    CATEGORY_HAS_CHILDREN = "Cannot delete category with active children"
    CATEGORY_SLUG_EXISTS = "Category with this slug already exists"
    CATEGORY_NAME_EXISTS = "Category with this name already exists"
    CATEGORY_PARENT_CYCLE = "Category cannot be its own parent"
    CATEGORY_PARENT_NOT_FOUND = "Parent category not found"

    # ─────────────────────────────────────────────────────────────────────
    # Bundles (400 / 404)
    # ─────────────────────────────────────────────────────────────────────

    BUNDLE_NOT_FOUND = "Bundle not found"
    BUNDLE_SLUG_EXISTS = "Bundle with this slug already exists"
    BUNDLE_NAME_EXISTS = "Bundle with this name already exists"
    BUNDLE_ITEM_NOT_FOUND = "Bundle item not found"
    BUNDLE_ITEM_DUPLICATE = "Product already exists in this bundle"
    BUNDLE_ITEM_PRODUCT_NOT_FOUND = "Product not found or inactive"


class HTTPStatusMessages:
    """Messages HTTP pour réponses structurées.

    Usage :
        return JSONResponse(
            status_code=200,
            content={"message": HTTPStatusMessages.SUCCESS}
        )
    """

    SUCCESS = "Operation successful"
    CREATED = "Resource created successfully"
    UPDATED = "Resource updated successfully"
    DELETED = "Resource deleted successfully"
    NO_CONTENT = "No content"


__all__ = [
    "ErrorMessages",
    "HTTPStatusMessages",
]
