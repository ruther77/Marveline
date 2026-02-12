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

    # ─────────────────────────────────────────────────────────────────────
    # CSRF Protection (403 FORBIDDEN)
    # ─────────────────────────────────────────────────────────────────────

    CSRF_TOKEN_MISSING = "CSRF token manquant"
    CSRF_TOKEN_INVALID = "CSRF token invalide"

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

    # ─────────────────────────────────────────────────────────────────────
    # Logique métier factures (400 BAD REQUEST)
    # ─────────────────────────────────────────────────────────────────────

    INVOICE_ALREADY_PAID = "Invoice is already paid"
    INVOICE_ALREADY_EXISTS = "Invoice already exists for this reservation"
    PAYMENT_EXCEEDS_TOTAL = "Payment amount exceeds invoice total"
    PAYMENT_AMOUNT_INVALID = "Payment amount must be positive"


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
