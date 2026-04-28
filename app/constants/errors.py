"""Standardized error and HTTP status messages.

This module centralizes ALL error messages used across the application.
All messages are in English. Frontend handles i18n/translation to French.
"""


class ErrorMessages:
    """Standardized HTTP error messages.

    Usage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.PRODUCT_NOT_FOUND
        )
    """

    # -----------------------------------------------------------------
    # Resources not found (404 NOT FOUND)
    # -----------------------------------------------------------------

    PRODUCT_NOT_FOUND = "Product not found"
    RESERVATION_NOT_FOUND = "Reservation not found"
    INVOICE_NOT_FOUND = "Invoice not found"
    CUSTOMER_NOT_FOUND = "Customer not found"
    USER_NOT_FOUND = "User not found"
    SESSION_NOT_FOUND = "Session not found or access denied"
    CATEGORY_NOT_FOUND = "Category not found"
    BUNDLE_NOT_FOUND = "Bundle not found"
    BUNDLE_ITEM_NOT_FOUND = "Bundle item not found"
    VARIANT_NOT_FOUND = "Product variant not found"
    MOVEMENT_NOT_FOUND = "Inventory movement not found"
    MOVEMENT_ITEM_NOT_FOUND = "Movement item not found"
    DEVIS_NOT_FOUND = "Quote not found"
    DEVIS_LINE_NOT_FOUND = "Quote line not found"
    DEVIS_VERSION_NOT_FOUND = "Quote version not found"
    EVENT_NOT_FOUND = "Event not found"
    INCIDENT_NOT_FOUND = "Incident not found"
    ACTION_PLAN_NOT_FOUND = "Action plan not found"
    SUPPLIER_NOT_FOUND = "Supplier not found"
    SUPPLIER_ORDER_NOT_FOUND = "Supplier order not found"
    SUPPLIER_ORDER_LINE_NOT_FOUND = "Supplier order line not found"
    STOCK_ITEM_NOT_FOUND = "Stock item not found"
    DAMAGE_TYPE_NOT_FOUND = "Damage type not found"
    COLLECTION_NOT_FOUND = "Collection not found"
    DELIVERY_ZONE_NOT_FOUND = "Delivery zone not found"
    FORMULA_NOT_FOUND = "Formula not found"
    PRICING_RULE_NOT_FOUND = "Pricing rule not found"
    NOTIFICATION_NOT_FOUND = "Notification not found"
    PAYMENT_NOT_FOUND = "Payment not found"
    DEPOSIT_NOT_FOUND = "Deposit not found"
    CREDIT_NOTE_NOT_FOUND = "Credit note not found"
    INVOICE_CHARGE_NOT_FOUND = "Invoice charge not found"
    API_KEY_NOT_FOUND = "API key not found"
    FEATURE_FLAG_NOT_FOUND = "Feature flag not found"
    TENANT_NOT_FOUND = "Tenant not found"
    PASSWORD_RESET_TOKEN_NOT_FOUND = "Password reset token not found"
    IMAGE_NOT_FOUND = "Image not found"
    MAINTENANCE_NOT_FOUND = "Maintenance record not found"
    RELANCE_NOT_FOUND = "Follow-up not found"
    RESERVATION_LINE_NOT_FOUND = "Reservation line not found"
    DEPARTURE_LINE_NOT_FOUND = "Ligne de départ inconnue"
    VENTE_NOT_FOUND = "Sale not found"
    # IAM v2
    MEMBERSHIP_NOT_FOUND = "Membership not found"
    ACCOUNT_NOT_FOUND = "Account not found"
    NOT_FOUND = "Resource not found"

    # -----------------------------------------------------------------
    # Authorization (403 FORBIDDEN) — IAM v2
    # -----------------------------------------------------------------

    ACCESS_DENIED = "Access denied"
    MEMBERSHIP_SUSPENDED = "Membership is suspended"
    MEMBERSHIP_REVOKED = "Membership has been revoked"

    # -----------------------------------------------------------------
    # Validation / Business rules (400 BAD REQUEST)
    # -----------------------------------------------------------------

    INSUFFICIENT_STOCK = "Insufficient stock available"
    SKU_ALREADY_EXISTS = "Product with this SKU already exists"
    EMAIL_ALREADY_EXISTS = "Email already registered"
    AVAILABLE_EXCEEDS_STOCK = "available_quantity cannot exceed stock_quantity"

    # Products
    PRODUCT_INACTIVE = "Product is inactive"
    PRODUCT_HAS_RESERVATIONS = "Cannot delete product with active reservations"
    PRODUCT_HAS_VARIANTS = "Cannot delete product with existing variants"
    PRODUCT_NAME_EXISTS = "Product with this name already exists"

    # Categories
    CATEGORY_HAS_CHILDREN = "Cannot delete category with active children"
    CATEGORY_SLUG_EXISTS = "Category with this slug already exists"
    CATEGORY_NAME_EXISTS = "Category with this name already exists"
    CATEGORY_PARENT_CYCLE = "Category cannot be its own parent"
    CATEGORY_PARENT_NOT_FOUND = "Parent category not found"
    CATEGORY_HAS_PRODUCTS = "Cannot delete category with assigned products"

    # Bundles
    BUNDLE_SLUG_EXISTS = "Bundle with this slug already exists"
    BUNDLE_NAME_EXISTS = "Bundle with this name already exists"
    BUNDLE_ITEM_DUPLICATE = "Product already exists in this bundle"
    BUNDLE_ITEM_PRODUCT_NOT_FOUND = "Product not found or inactive"
    BUNDLE_ITEM_VARIANT_REQUIRED = "variant_id is required for products with active variants"
    BUNDLE_ITEM_VARIANT_MISMATCH = "variant_id does not belong to the specified product"

    # Variants
    VARIANT_LABEL_EXISTS = "Variant with this label already exists for this product"
    VARIANT_COLOR_EXISTS = "Variant with this color already exists for this product"
    VARIANT_HAS_STOCK = "Cannot delete variant with existing stock items"

    # Reservations
    RESERVATION_NOT_DRAFT = "Reservation cannot be modified in its current status"
    RESERVATION_ALREADY_CONFIRMED = "Reservation is already confirmed"
    RESERVATION_ALREADY_CANCELLED = "Reservation is already cancelled"
    RESERVATION_REFERENCE_OVERFLOW = "Cannot generate unique reference (counter overflow)"
    RESERVATION_INVALID_STATUS_TRANSITION = "Invalid reservation status transition"
    RESERVATION_DATES_INVALID = "End date must be after start date"
    RESERVATION_NO_LINES = "Reservation must have at least one line"
    RESERVATION_LINE_QUANTITY_INVALID = "Line quantity must be positive"
    RESERVATION_LOCKED_BY_DEVIS = (
        "Reservation linked to a quote — perimeter changes require an amendment "
        "(POST /reservations/{id}/amend)"
    )
    RESERVATION_CANNOT_CONFIRM = "Reservation cannot be confirmed in its current state"
    RESERVATION_CANNOT_CANCEL = "Reservation cannot be cancelled in its current state"
    RESERVATION_CANNOT_COMPLETE = "Reservation cannot be completed in its current state"
    RESERVATION_PRE_CHECK_INCOMPLETE = "Pre-check must be completed before departure"
    RESERVATION_DEPOSIT_REQUIRED = "Deposit must be paid before departure"
    RESERVATION_ADVANCE_NOT_PAID = (
        "Acompte non encaissé — impossible de livrer. "
        "Encaissez l'acompte (paiement partiel ou total de la facture) avant le départ matériel."
    )
    RESERVATION_SIGNATURE_REQUIRED = (
        "Signature contractuelle manquante — impossible de livrer. "
        "Faites signer le contrat de location avant le départ matériel."
    )
    RESERVATION_ALREADY_COMPLETED = "Reservation is already completed"
    RESERVATION_HAS_INVOICE = "Reservation already has an associated invoice"
    RESERVATION_DISPUTE_NOT_OPEN = "No open dispute on this reservation"

    # Invoices
    INVOICE_ALREADY_PAID = "Invoice is already paid"
    INVOICE_ALREADY_EXISTS = "Invoice already exists for this reservation"
    PAYMENT_EXCEEDS_TOTAL = "Payment amount exceeds invoice total"
    PAYMENT_AMOUNT_INVALID = "Payment amount must be positive"
    STOCK_RESERVATION_FAILED = "Failed to reserve stock"
    INVOICE_CANCELLED_NO_PAYMENT = "Cannot add payment to cancelled invoice"
    INVOICE_PAID_NO_MODIFY = "Cannot modify paid invoice"
    INVOICE_PAID_NO_CANCEL = "Cannot cancel paid invoice"
    INVOICE_NUMBER_OVERFLOW = "Cannot generate unique invoice number (counter overflow)"
    INVOICE_INVALID_STATUS_TRANSITION = "Invalid invoice status transition"
    INVOICE_ALREADY_CANCELLED = "Invoice is already cancelled"
    INVOICE_ALREADY_SENT = "Invoice is already sent"
    INVOICE_HAS_PAYMENTS = "Cannot cancel invoice with recorded payments. Create a credit note first"
    INVOICE_NOT_SENT = "Invoice must be sent before recording payment"
    INVOICE_PDF_GENERATION_FAILED = "Failed to generate invoice PDF"

    # Credit notes
    CREDIT_NOTE_EXCEEDS_TOTAL = "Credit note amount exceeds invoice total"
    CREDIT_NOTE_ALREADY_REFUNDED = "Credit note is already refunded"
    CREDIT_NOTE_INVALID_STATUS = "Invalid credit note status transition"

    # Payments
    PAYMENT_METHOD_REQUIRED = "Payment method is required"
    PAYMENT_ALREADY_PROCESSED = "Payment has already been processed"

    # Deposits
    DEPOSIT_AMOUNT_INVALID = "Deposit amount must be positive"
    DEPOSIT_EXCEEDS_TOTAL = "Deposit amount exceeds reservation total"
    DEPOSIT_ALREADY_RETURNED = "Deposit has already been returned"
    DEPOSIT_ALREADY_RETAINED = "Deposit has already been retained"

    # Devis (Quotes)
    DEVIS_NOT_DRAFT = "Quote cannot be modified in its current status"
    DEVIS_ALREADY_SENT = "Quote has already been sent"
    DEVIS_ALREADY_ACCEPTED = "Quote has already been accepted"
    DEVIS_ALREADY_REFUSED = "Quote has already been refused"
    DEVIS_ALREADY_CONVERTED = "Quote has already been converted to reservation"
    DEVIS_INVALID_STATUS_TRANSITION = "Invalid quote status transition"
    DEVIS_NO_LINES = "Quote must have at least one line"
    DEVIS_CANNOT_CONVERT = "Quote must be accepted before conversion to reservation"
    DEVIS_NO_CONVERTIBLE_LINES = "No lines with valid product references to convert"
    DEVIS_EXPIRED = "Quote has expired"
    DEVIS_SIGNATURE_REQUIRED = "Quote must be signed before acceptance"

    # Ventes (Sales)
    VENTE_INVALID_STATUS_TRANSITION = "Invalid sale status transition"
    VENTE_ALREADY_COMPLETED = "Sale is already completed"
    VENTE_ALREADY_CANCELLED = "Sale is already cancelled"

    # Inventory movements
    MOVEMENT_NOT_DRAFT = "Movement cannot be modified in its current status"
    MOVEMENT_ALREADY_COMPLETED = "Movement is already completed"
    MOVEMENT_ALREADY_CANCELLED = "Movement is already cancelled"
    MOVEMENT_INVALID_TYPE = "Invalid movement type"
    MOVEMENT_QUANTITY_MISMATCH = "Returned quantity does not match expected"
    MOVEMENT_ITEM_ALREADY_CHECKED = "Movement item has already been checked"
    MOVEMENT_CANNOT_COMPLETE = "Movement cannot be completed in its current state"

    # Stock
    STOCK_ITEM_ALREADY_EXISTS = "Stock item already exists for this variant"
    STOCK_ITEM_NOT_AVAILABLE = "Stock item is not available"
    STOCK_ADJUSTMENT_INVALID = "Stock adjustment quantity must be non-zero"
    STOCK_QUANTITY_NEGATIVE = "Stock quantity cannot be negative"

    # Damages
    DAMAGE_TYPE_NAME_EXISTS = "Damage type with this name already exists"
    DAMAGE_TYPE_HAS_RECORDS = "Cannot delete damage type with existing damage records"
    DAMAGE_FEE_NEGATIVE = "Damage fee must be non-negative"

    # Events
    EVENT_DATES_INVALID = "Event end date must be after start date"
    EVENT_ALREADY_CLOSED = "Event is already closed"
    EVENT_OVERLAP = "Event dates overlap with an existing event"
    INCIDENT_ALREADY_RESOLVED = "Incident is already resolved"

    # Suppliers
    SUPPLIER_NAME_EXISTS = "Supplier with this name already exists"
    SUPPLIER_HAS_ORDERS = "Cannot delete supplier with existing orders"
    SUPPLIER_ORDER_ALREADY_RECEIVED = "Supplier order has already been received"
    SUPPLIER_ORDER_ALREADY_CANCELLED = "Supplier order is already cancelled"
    SUPPLIER_ORDER_INVALID_STATUS = "Invalid supplier order status transition"

    # Collections
    COLLECTION_NAME_EXISTS = "Collection with this name already exists"
    COLLECTION_SLUG_EXISTS = "Collection with this slug already exists"

    # Delivery zones
    DELIVERY_ZONE_NAME_EXISTS = "Delivery zone with this name already exists"

    # Formulas
    FORMULA_NAME_EXISTS = "Formula with this name already exists"
    FORMULA_EXPRESSION_INVALID = "Formula expression is invalid"

    # Pricing
    PRICING_RULE_OVERLAP = "Pricing rule overlaps with existing rule"
    PRICING_RULE_INVALID = "Pricing rule configuration is invalid"

    # Customers
    CUSTOMER_EMAIL_EXISTS = "Customer with this email already exists"
    CUSTOMER_HAS_RESERVATIONS = "Cannot delete customer with active reservations"
    CUSTOMER_INACTIVE = "Customer account is inactive"

    # Relances (follow-ups)
    RELANCE_ALREADY_SENT = "Follow-up has already been sent"
    RELANCE_CANCELLED = "Follow-up has been cancelled"

    # Images
    IMAGE_UPLOAD_FAILED = "Image upload failed"
    IMAGE_FORMAT_INVALID = "Invalid image format. Supported: JPEG, PNG, WebP"
    IMAGE_SIZE_EXCEEDED = "Image size exceeds maximum allowed"
    IMAGE_LIMIT_REACHED = "Maximum number of images reached for this product"

    # Maintenance
    MAINTENANCE_DATES_INVALID = "Maintenance end date must be after start date"
    MAINTENANCE_OVERLAP = "Maintenance dates overlap with existing record"

    # Notifications
    NOTIFICATION_ALREADY_READ = "Notification is already marked as read"

    # Generic validation
    INVALID_SORT_FIELD = "Invalid sort field"
    INVALID_FILTER_VALUE = "Invalid filter value"
    INVALID_DATE_RANGE = "Invalid date range"
    INVALID_PAGINATION = "Invalid pagination parameters"
    FILE_TOO_LARGE = "File size exceeds maximum allowed"
    INVALID_FILE_TYPE = "Invalid file type"

    # -----------------------------------------------------------------
    # Authentication & Authorization (401 UNAUTHORIZED / 403 FORBIDDEN)
    # -----------------------------------------------------------------

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
    DEVICE_REVOKED = "Device has been revoked"
    CURRENT_PASSWORD_INCORRECT = "Current password is incorrect"
    PASSWORD_SAME_AS_CURRENT = "New password must be different from current password"
    PASSWORD_CHANGE_RATE_LIMITED = "Too many failed attempts. Please try again later."
    INVALID_ROLE = "Invalid role. Must be: admin, manager, or staff"
    SELF_ROLE_CHANGE = "Cannot change your own role"
    SELF_DEACTIVATE = "Cannot deactivate your own account"
    ADMIN_REQUIRED = "Admin privileges required"
    SCOPE_REQUIRED = "Required scope: {scope}"
    OAUTH_STATE_INVALID = "Invalid or expired OAuth state"
    OAUTH_PROVIDER_ERROR = "OAuth provider returned an error"
    OAUTH_EMAIL_NOT_FOUND = "No account found with this OAuth email"
    OAUTH_ACCOUNT_LINKED = "OAuth account is already linked"
    PASSWORD_CHANGE_REQUIRED = "Password change is required"

    # -----------------------------------------------------------------
    # MFA (400 / 401)
    # -----------------------------------------------------------------

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
    MFA_STEP_UP_REQUIRED = "Step-up authentication required for this action"
    MFA_STEP_UP_EXPIRED = "Step-up authentication has expired"

    # -----------------------------------------------------------------
    # Password Reset (400 / 401)
    # -----------------------------------------------------------------

    PASSWORD_RESET_TOKEN_INVALID = "Invalid or expired password reset token"
    PASSWORD_RESET_TOKEN_EXPIRED = "Password reset token has expired"
    PASSWORD_RESET_RATE_LIMITED = "Too many password reset requests. Please try again later."
    PASSWORD_TOO_WEAK = "Password does not meet security requirements"

    # -----------------------------------------------------------------
    # CSRF Protection (403 FORBIDDEN)
    # -----------------------------------------------------------------

    CSRF_TOKEN_MISSING = "CSRF token missing"
    CSRF_TOKEN_INVALID = "CSRF token invalid or expired"
    CSRF_TOKEN_GENERATION_FAILED = "Failed to generate CSRF token. Redis unavailable."

    # -----------------------------------------------------------------
    # Brute Force & Credential Stuffing (429 / 400)
    # -----------------------------------------------------------------

    LOGIN_GLOBALLY_BLOCKED = (
        "Login temporarily blocked due to excessive failed attempts. "
        "Please try again later."
    )
    CAPTCHA_REQUIRED = "CAPTCHA verification required"
    PASSWORD_COMPROMISED = (
        "This password has been found in known data breaches. "
        "Please choose a different one."
    )

    # -----------------------------------------------------------------
    # Rate Limiting (429 TOO MANY REQUESTS)
    # -----------------------------------------------------------------

    TOO_MANY_REQUESTS = "Too many requests"

    # -----------------------------------------------------------------
    # Service / Internal errors (500 / 503)
    # -----------------------------------------------------------------

    INTERNAL_ERROR = "An internal error occurred"
    DATABASE_ERROR = "A database error occurred"
    REDIS_UNAVAILABLE = "Cache service temporarily unavailable"
    EMAIL_SEND_FAILED = "Failed to send email"
    CELERY_TASK_FAILED = "Background task failed"

    # -----------------------------------------------------------------
    # Tenant (400 / 403)
    # -----------------------------------------------------------------

    TENANT_MISMATCH = "Resource does not belong to your tenant"
    TENANT_INACTIVE = "Tenant account is inactive"
    TENANT_LIMIT_REACHED = "Tenant resource limit reached"

    # -----------------------------------------------------------------
    # API Keys (400 / 401)
    # -----------------------------------------------------------------

    API_KEY_INVALID = "Invalid API key"
    API_KEY_EXPIRED = "API key has expired"
    API_KEY_NAME_EXISTS = "API key with this name already exists"
    API_KEY_LIMIT_REACHED = "Maximum number of API keys reached"

    # -----------------------------------------------------------------
    # Feature Flags
    # -----------------------------------------------------------------

    FEATURE_FLAG_KEY_EXISTS = "Feature flag with this key already exists"
    FEATURE_DISABLED = "This feature is currently disabled"

    # -----------------------------------------------------------------
    # Sessions
    # -----------------------------------------------------------------

    SESSION_EXPIRED = "Session has expired"
    SESSION_REVOKED = "Session has been revoked"
    MAX_SESSIONS_REACHED = "Maximum number of active sessions reached"

    # -----------------------------------------------------------------
    # Users
    # -----------------------------------------------------------------

    USER_EMAIL_EXISTS = "User with this email already exists"
    USER_INACTIVE = "User account is inactive"
    USER_HAS_ACTIVE_SESSIONS = "Cannot delete user with active sessions"

    # -----------------------------------------------------------------
    # Loyalty
    # -----------------------------------------------------------------

    LOYALTY_MEMBER_NOT_FOUND = "Loyalty member not found"
    LOYALTY_MEMBER_ALREADY_EXISTS = "A loyalty member with this phone number already exists"
    LOYALTY_PROGRAM_NOT_FOUND = "Loyalty program not found"
    LOYALTY_INSUFFICIENT_POINTS = "Insufficient points for this reward"
    LOYALTY_REWARD_NOT_FOUND = "Reward not found in catalog"
    LOYALTY_REWARD_NOT_AVAILABLE = "This reward is not currently available"
    LOYALTY_REWARD_NOT_ELIGIBLE = "Member is not eligible for this reward tier"
    LOYALTY_REFERRAL_LIMIT_REACHED = "Maximum number of referrals reached"
    LOYALTY_REFERRAL_CODE_NOT_FOUND = "Referral code not found"
    LOYALTY_REFERRAL_SELF = "Cannot use your own referral code"
    LOYALTY_DOUBLE_SCAN = "This transaction already has a loyalty scan"
    LOYALTY_BARCODE_INVALID = "Invalid loyalty barcode"
    LOYALTY_FLASH_OFFER_NOT_FOUND = "Flash offer not found"
    LOYALTY_WELCOME_ALREADY_USED = "Welcome reward already used"


class HTTPStatusMessages:
    """HTTP messages for structured responses.

    Usage:
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
