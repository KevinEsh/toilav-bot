"""
Database schema for WhatsApp e-commerce chatbot.
Includes: Users (with address), Products (with details/variants), Orders, Messages, Reviews, FAQ, etc.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import CheckConstraint, Sequence, UniqueConstraint, Column, JSON, Text
from sqlmodel import Field, SQLModel


def id_field(table_name: str):
    """
    CREATE SEQUENCE IF NOT EXISTS table_name_id_seq START 1;
    """
    sequence = Sequence(f"{table_name}_id_seq")
    return Field(
        default=None,
        primary_key=True,
        unique=True,
        sa_column_args=[sequence],
        sa_column_kwargs={"server_default": sequence.next_value()},
    )


# ============================================================================
# ENUMS
# ============================================================================

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    PENDING_VERIFICATION = "pending_verification"


class ProductCategory(str, Enum):
    """Product categories as enum."""
    FOOD = "food"
    BEVERAGES = "beverages"
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    HOME = "home"
    BEAUTY = "beauty"
    HEALTH = "health"
    SPORTS = "sports"
    TOYS = "toys"
    OTHER = "other"

class ProductUnit(str, Enum):
    UNIT = "unit"
    KG = "kg"
    LITER = "liter"
    METER = "meter"
    SQUARE_METER = "square_meter"
    CUBIC_METER = "cubic_meter"
    HOUR = "hour"
    DAY = "day"
    OTHER = "other"

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CASH_ON_DELIVERY = "cash_on_delivery"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_PAYMENT = "mobile_payment"
    WALLET = "wallet"
    OTHER = "other"


class MessageDirection(str, Enum):
    INBOUND = "inbound"   # From customer to bot
    OUTBOUND = "outbound" # From bot to customer


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"
    REACTION = "reaction"
    ORDER = "order"


class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"
    ESCALATED = "escalated"


class FAQCategory(str, Enum):
    """FAQ categories as enum."""
    ORDERS = "orders"
    SHIPPING = "shipping"
    RETURNS = "returns"
    PAYMENTS = "payments"
    PRODUCTS = "products"
    ACCOUNT = "account"
    PROMOTIONS = "promotions"
    GENERAL = "general"
    OTHER = "other"


class NotificationType(str, Enum):
    ORDER_UPDATE = "order_update"
    PROMOTION = "promotion"
    REMINDER = "reminder"
    SYSTEM = "system"
    PAYMENT = "payment"
    DELIVERY = "delivery"


# ============================================================================
# USER MODEL (with address included)
# ============================================================================

class Users(SQLModel, table=True):
    """
    Customer/User information for WhatsApp chatbot.
    Primary identifier is the WhatsApp phone number.
    Includes single address per user.

    Args:
        u_id (Optional[int]): Unique user ID, auto-incremented.
        u_phone (str): WhatsApp phone number (unique, primary contact).
        u_whatsapp_id (Optional[str]): WhatsApp Business API user ID.
        u_name (Optional[str]): Customer's full name.
        u_email (Optional[str]): Email address.
        u_profile_name (Optional[str]): WhatsApp profile name.
        u_language (str): Preferred language code (e.g., 'es', 'en').
        u_status (UserStatus): Account status.
        u_is_verified (bool): Whether phone is verified.
        u_latitude (Optional[float]): GPS latitude for delivery.
        u_longitude (Optional[float]): GPS longitude for delivery.
        u_delivery_instructions (Optional[str]): Special delivery notes.
        u_last_interaction (Optional[datetime]): Last interaction timestamp.
        u_created_at (datetime): Account creation timestamp.
        u_updated_at (datetime): Last update timestamp.
    """

    u_id: Optional[int] = id_field("users")
    u_phone: str = Field(unique=True, index=True, max_length=20)
    u_whatsapp_id: Optional[str] = Field(default=None, max_length=50, unique=True)
    u_name: Optional[str] = Field(default=None, max_length=100)
    u_email: Optional[str] = Field(default=None, max_length=255) #TODO: realmente es necesario?
    u_status: UserStatus = Field(default=UserStatus.ACTIVE) 
    u_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    u_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    u_google_url: Optional[str] = Field(default=None, max_length=500)
    u_delivery_instructions: Optional[str] = Field(default=None, max_length=500)
    # Timestamps
    u_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    u_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# PRODUCT MODEL (enhanced with all details, category, variants)
# ============================================================================

class Products(SQLModel, table=True):
    """
    Products for the WhatsApp e-commerce chatbot.
    Includes pricing, category, images, variants, and availability.

    Args:
        p_id (Optional[int]): Product ID, auto-incremented.
        p_name (str): Name of the product.
        p_description (Optional[str]): Description of the product.
        p_category (ProductCategory): Product category.
        p_sku (Optional[str]): Stock Keeping Unit code.
        p_barcode (Optional[str]): Product barcode (EAN, UPC).
        p_price (float): Regular selling price.
        p_sale_price (Optional[float]): Discounted price. 
        p_cost_price (Optional[float]): Wholesale/cost price.
        p_currency (str): Currency code (USD, EUR, etc.).
        p_unit (str): Unit of measure (kg, piece, liter).
        p_weight (Optional[float]): Product weight in kg.
        p_image_url (Optional[str]): Primary product image URL.
        p_images (Optional[list]): JSON array of additional image URLs.
        p_variant_type (Optional[str]): Type of variants (size, color, weight, etc.).
        p_variants (Optional[list]): JSON array of variant options.
        p_is_available (bool): Whether product is available for sale.
        p_is_featured (bool): Whether product is featured/promoted.
        p_min_order_qty (int): Minimum order quantity.
        p_max_order_qty (Optional[int]): Maximum order quantity.
        p_stock_qty (int): Current stock quantity.
        p_created_at (datetime): Creation timestamp.
        p_updated_at (datetime): Last update timestamp.
    """

    __table_args__ = (
        CheckConstraint("p_price >= 0", name="check_p_price_positive"),
        CheckConstraint("p_sale_price IS NULL OR p_sale_price >= 0", name="check_p_sale_price_positive"),
        CheckConstraint("p_stock_qty >= 0", name="check_p_stock_positive"),
    )

    p_id: Optional[int] = id_field("products")
    p_name: str = Field(unique=True)
    p_description: Optional[str] = Field(default=None, sa_column=Column(Text))
    # Pricing
    p_price: float = Field(default=0.0, ge=0.0)
    p_cost_price: Optional[float] = Field(default=None, ge=0.0) #TODO
    p_currency: str = Field(default="MXN", max_length=3)
    p_unit: ProductUnit = Field(default=ProductUnit.UNIT) # 
    # Images
    p_image_uuid: Optional[str] = Field(default=None)
    # Variants (JSON for flexibility)
    p_fields: Optional[list] = Field(default=None, sa_column=Column(JSON))
    # Availability
    p_is_available: bool = Field(default=True)
    p_min_order_qty: int = Field(default=1, ge=1)
    p_max_order_qty: Optional[int] = Field(default=None, ge=1)
    p_stock_units: int = Field(default=0, ge=0)
    # Timestamps
    p_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    p_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# ORDER MODELS
# ============================================================================

class Orders(SQLModel, table=True):
    """
    Customer orders.

    Args:
        o_id (Optional[int]): Order ID, auto-incremented.
        o_number (str): Human-readable order number.
        o_u_id (int): Foreign key to users.
        o_s_id (Optional[int]): Foreign key to store.
        o_status (OrderStatus): Order status.
        o_subtotal (float): Order subtotal before discounts/tax.
        o_discount_amount (float): Total discount applied.
        o_tax_amount (float): Tax amount.
        o_shipping_amount (float): Shipping cost.
        o_total (float): Final order total.
        o_currency (str): Currency code.
        o_payment_method (Optional[PaymentMethod]): Payment method used.
        o_payment_status (PaymentStatus): Payment status.
        o_notes (Optional[str]): Customer notes.
        o_internal_notes (Optional[str]): Internal staff notes.
        o_estimated_delivery (Optional[date]): Estimated delivery date.
        o_delivered_at (Optional[datetime]): Actual delivery timestamp.
        o_cancelled_at (Optional[datetime]): Cancellation timestamp.
        o_cancel_reason (Optional[str]): Reason for cancellation.
        o_created_at (datetime): Creation timestamp.
        o_updated_at (datetime): Last update timestamp.
    """

    o_id: Optional[int] = id_field("orders")
    o_number: str = Field(unique=True, max_length=30, index=True)
    o_u_id: int = Field(foreign_key="users.u_id", index=True)
    o_s_id: Optional[int] = Field(default=None, foreign_key="stores.s_id")
    o_status: OrderStatus = Field(default=OrderStatus.PENDING)
    # Amounts
    o_subtotal: float = Field(default=0.0, ge=0.0)
    o_discount_amount: float = Field(default=0.0, ge=0.0)
    o_tax_amount: float = Field(default=0.0, ge=0.0)
    o_shipping_amount: float = Field(default=0.0, ge=0.0)
    o_total: float = Field(default=0.0, ge=0.0)
    o_currency: str = Field(default="USD", max_length=3)
    # Payment
    o_payment_method: Optional[PaymentMethod] = Field(default=None)
    o_payment_status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    # Notes
    o_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    o_internal_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    # Delivery
    o_estimated_delivery: Optional[date] = Field(default=None)
    o_delivered_at: Optional[datetime] = Field(default=None)
    # Cancellation
    o_cancelled_at: Optional[datetime] = Field(default=None)
    o_cancel_reason: Optional[str] = Field(default=None, max_length=500)
    # Timestamps
    o_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    o_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderItems(SQLModel, table=True):
    """
    Individual items within an order.

    Args:
        oi_id (Optional[int]): Order item ID, auto-incremented.
        oi_o_id (int): Foreign key to order.
        oi_p_id (int): Foreign key to product.
        oi_product_name (str): Product name at time of order (snapshot).
        oi_variant_name (Optional[str]): Variant name if applicable.
        oi_qty (int): Quantity ordered.
        oi_unit_price (float): Unit price at time of order.
        oi_discount (float): Discount applied to this item.
        oi_total (float): Total for this line item.
        oi_notes (Optional[str]): Special instructions.
        oi_created_at (datetime): Creation timestamp.
    """

    oi_id: Optional[int] = id_field("orderitems")
    oi_o_id: int = Field(foreign_key="orders.o_id", index=True)
    oi_p_id: int = Field(foreign_key="products.p_id")
    oi_product_name: str = Field(max_length=200)
    oi_variant_name: Optional[str] = Field(default=None, max_length=100)
    oi_qty: int = Field(ge=1)
    oi_unit_price: float = Field(ge=0.0)
    oi_discount: float = Field(default=0.0, ge=0.0)
    oi_total: float = Field(ge=0.0)
    oi_notes: Optional[str] = Field(default=None, max_length=500)
    oi_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderStatusHistory(SQLModel, table=True):
    """
    Track order status changes over time.

    Args:
        osh_id (Optional[int]): History entry ID, auto-incremented.
        osh_o_id (int): Foreign key to order.
        osh_from_status (Optional[OrderStatus]): Previous status.
        osh_to_status (OrderStatus): New status.
        osh_changed_by (Optional[str]): Who made the change.
        osh_notes (Optional[str]): Notes about the change.
        osh_created_at (datetime): Timestamp of change.
    """

    osh_id: Optional[int] = id_field("orderstatushistory")
    osh_o_id: int = Field(foreign_key="orders.o_id", index=True)
    osh_from_status: Optional[OrderStatus] = Field(default=None)
    osh_to_status: OrderStatus
    osh_changed_by: Optional[str] = Field(default=None, max_length=50)
    osh_notes: Optional[str] = Field(default=None, max_length=500)
    osh_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# CONVERSATION & MESSAGE MODELS
# ============================================================================

class Conversations(SQLModel, table=True):
    """
    WhatsApp conversation sessions.
    Tracks conversation context and state.

    Args:
        conv_id (Optional[int]): Conversation ID, auto-incremented.
        conv_u_id (int): Foreign key to user.
        conv_status (ConversationStatus): Conversation status.
        conv_intent (Optional[str]): Detected user intent.
        conv_context (Optional[dict]): JSON state for conversation flow.
        conv_started_at (datetime): When conversation started.
        conv_ended_at (Optional[datetime]): When conversation ended.
        conv_last_message_at (Optional[datetime]): Last message timestamp.
        conv_message_count (int): Total messages in conversation.
        conv_escalated_to (Optional[str]): Agent ID if escalated.
        conv_escalated_at (Optional[datetime]): Escalation timestamp.
    """

    conv_id: Optional[int] = id_field("conversations")
    conv_u_id: int = Field(foreign_key="users.u_id", index=True)
    conv_status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    conv_intent: Optional[str] = Field(default=None, max_length=50)
    conv_context: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    conv_started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    conv_ended_at: Optional[datetime] = Field(default=None)
    conv_last_message_at: Optional[datetime] = Field(default=None)
    conv_message_count: int = Field(default=0)
    conv_escalated_to: Optional[str] = Field(default=None, max_length=100)
    conv_escalated_at: Optional[datetime] = Field(default=None)


class Messages(SQLModel, table=True):
    """
    Individual WhatsApp messages.

    Args:
        m_id (Optional[int]): Message ID (internal), auto-incremented.
        m_conv_id (int): Foreign key to conversation.
        m_u_id (int): Foreign key to user.
        m_whatsapp_id (Optional[str]): WhatsApp message ID.
        m_direction (MessageDirection): Inbound or outbound.
        m_type (MessageType): Message type (text, image, etc.).
        m_content (Optional[str]): Message content/text.
        m_media_url (Optional[str]): URL for media messages.
        m_media_mime_type (Optional[str]): MIME type for media.
        m_status (MessageStatus): Delivery status.
        m_context_message_id (Optional[str]): ID of message being replied to.
        m_metadata (Optional[dict]): Additional message metadata.
        m_error_code (Optional[str]): Error code if failed.
        m_error_message (Optional[str]): Error message if failed.
        m_created_at (datetime): Creation timestamp.
        m_delivered_at (Optional[datetime]): Delivery timestamp.
        m_read_at (Optional[datetime]): Read timestamp.
    """

    m_id: Optional[int] = id_field("messages")
    m_conv_id: int = Field(foreign_key="conversations.conv_id", index=True)
    m_u_id: int = Field(foreign_key="users.u_id", index=True)
    # m_whatsapp_id: Optional[str] = Field(default=None, max_length=100, index=True)
    m_direction: MessageDirection
    m_type: MessageType = Field(default=MessageType.TEXT)
    m_content: Optional[str] = Field(default=None, sa_column=Column(Text))
    m_media_url: Optional[str] = Field(default=None, max_length=500)
    m_media_mime_type: Optional[str] = Field(default=None, max_length=100)
    m_status: MessageStatus = Field(default=MessageStatus.SENT)
    m_context_message_id: Optional[str] = Field(default=None, max_length=100)
    m_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    m_error_code: Optional[str] = Field(default=None, max_length=50)
    m_error_message: Optional[str] = Field(default=None, max_length=500)
    m_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    m_delivered_at: Optional[datetime] = Field(default=None)
    m_read_at: Optional[datetime] = Field(default=None)


class MessageTemplates(SQLModel, table=True):
    """
    WhatsApp message templates for outbound notifications.

    Args:
        mt_id (Optional[int]): Template ID, auto-incremented.
        mt_name (str): Template name (as registered with WhatsApp).
        mt_language (str): Language code.
        mt_category (Optional[str]): Template category.
        mt_content (str): Template content with placeholders.
        mt_header_type (Optional[str]): Header type (text, image, document).
        mt_header_content (Optional[str]): Header content.
        mt_has_buttons (bool): Whether template has buttons.
        mt_buttons (Optional[list]): JSON array of buttons.
        mt_status (str): Approval status.
        mt_whatsapp_template_id (Optional[str]): WhatsApp template ID.
        mt_created_at (datetime): Creation timestamp.
        mt_updated_at (datetime): Last update timestamp.
    """

    __table_args__ = (
        UniqueConstraint("mt_name", "mt_language", name="unique_template"),
    )

    mt_id: Optional[int] = id_field("messagetemplates")
    mt_name: str = Field(max_length=100)
    mt_language: str = Field(default="es", max_length=10)
    mt_category: Optional[str] = Field(default=None, max_length=50)
    mt_content: str = Field(sa_column=Column(Text))
    mt_header_type: Optional[str] = Field(default=None, max_length=20)
    mt_header_content: Optional[str] = Field(default=None, max_length=500)
    mt_has_buttons: bool = Field(default=False)
    mt_buttons: Optional[list] = Field(default=None, sa_column=Column(JSON))
    mt_status: str = Field(default="pending", max_length=20)
    mt_whatsapp_template_id: Optional[str] = Field(default=None, max_length=100)
    mt_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mt_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# REVIEW & FEEDBACK MODELS
# ============================================================================

class ProductReviews(SQLModel, table=True):
    """
    Product reviews from customers.

    Args:
        pr_id (Optional[int]): Review ID, auto-incremented.
        pr_p_id (int): Foreign key to product.
        pr_u_id (int): Foreign key to user.
        pr_o_id (Optional[int]): Foreign key to order (verify purchase).
        pr_rating (int): Rating (1-5).
        pr_title (Optional[str]): Review title.
        pr_comment (Optional[str]): Review comment.
        pr_images (Optional[list]): JSON list of image URLs.
        pr_is_verified_purchase (bool): Whether user purchased product.
        pr_is_approved (bool): Whether review is approved for display.
        pr_created_at (datetime): Creation timestamp.
    """

    __table_args__ = (
        CheckConstraint("pr_rating >= 1 AND pr_rating <= 5", name="check_rating_range"),
    )

    pr_id: Optional[int] = id_field("productreviews")
    pr_p_id: int = Field(foreign_key="products.p_id", index=True)
    pr_u_id: int = Field(foreign_key="users.u_id", index=True)
    pr_o_id: Optional[int] = Field(default=None, foreign_key="orders.o_id")
    pr_rating: int = Field(ge=1, le=5)
    pr_title: Optional[str] = Field(default=None, max_length=200)
    pr_comment: Optional[str] = Field(default=None, sa_column=Column(Text))
    pr_images: Optional[list] = Field(default=None, sa_column=Column(JSON))
    pr_is_verified_purchase: bool = Field(default=False)
    pr_is_approved: bool = Field(default=False)
    pr_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BotFeedback(SQLModel, table=True):
    """
    Feedback on bot responses for improvement.

    Args:
        bf_id (Optional[int]): Feedback ID, auto-incremented.
        bf_m_id (int): Foreign key to message.
        bf_u_id (int): Foreign key to user.
        bf_rating (Optional[int]): Rating (1-5).
        bf_comment (Optional[str]): User feedback comment.
        bf_was_helpful (Optional[bool]): Whether response was helpful.
        bf_created_at (datetime): Creation timestamp.
    """

    bf_id: Optional[int] = id_field("botfeedback")
    bf_m_id: int = Field(foreign_key="messages.m_id", index=True)
    bf_u_id: int = Field(foreign_key="users.u_id")
    bf_rating: Optional[int] = Field(default=None, ge=1, le=5)
    bf_comment: Optional[str] = Field(default=None, max_length=500)
    bf_was_helpful: Optional[bool] = Field(default=None)
    bf_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# FAQ MODEL (with category as enum)
# ============================================================================

class FAQItems(SQLModel, table=True):
    """
    Frequently Asked Questions for the chatbot.
    Used for RAG and quick responses.

    Args:
        faq_id (Optional[int]): FAQ ID, auto-incremented.
        faq_category (FAQCategory): FAQ category as enum.
        faq_question (str): The question.
        faq_answer (str): The answer.
        faq_keywords (Optional[list]): Keywords for matching.
        faq_display_order (int): Order within category.
        faq_view_count (int): How many times accessed.
        faq_is_active (bool): Whether FAQ is active.
        faq_created_at (datetime): Creation timestamp.
        faq_updated_at (datetime): Last update timestamp.
    """

    faq_id: Optional[int] = id_field("faqitems")
    faq_category: FAQCategory = Field(default=FAQCategory.GENERAL)
    faq_question: str = Field(sa_column=Column(Text))
    faq_answer: str = Field(sa_column=Column(Text))
    faq_keywords: Optional[list] = Field(default=None, sa_column=Column(JSON))
    faq_display_order: int = Field(default=0)
    faq_view_count: int = Field(default=0)
    faq_is_active: bool = Field(default=True)
    faq_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    faq_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# NOTIFICATION MODEL
# ============================================================================

class Notifications(SQLModel, table=True):
    """
    System notifications for users.
    Can be sent via WhatsApp or displayed in app.

    Args:
        n_id (Optional[int]): Notification ID, auto-incremented.
        n_u_id (int): Foreign key to user.
        n_type (NotificationType): Notification type.
        n_title (str): Short title.
        n_message (str): Full message content.
        n_data (Optional[dict]): Additional JSON data.
        n_is_read (bool): Whether user has read it.
        n_sent_via_whatsapp (bool): Whether sent via WhatsApp.
        n_whatsapp_message_id (Optional[str]): WhatsApp message ID if sent.
        n_scheduled_for (Optional[datetime]): Scheduled send time.
        n_sent_at (Optional[datetime]): Actual send time.
        n_created_at (datetime): Creation timestamp.
    """

    n_id: Optional[int] = id_field("notifications")
    n_u_id: int = Field(foreign_key="users.u_id", index=True)
    n_type: NotificationType = Field(default=NotificationType.SYSTEM)
    n_title: str = Field(max_length=200)
    n_message: str = Field(sa_column=Column(Text))
    n_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    n_is_read: bool = Field(default=False)
    n_sent_via_whatsapp: bool = Field(default=False)
    n_whatsapp_message_id: Optional[str] = Field(default=None, max_length=100)
    n_scheduled_for: Optional[datetime] = Field(default=None)
    n_sent_at: Optional[datetime] = Field(default=None)
    n_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# STORE SETTINGS & CONFIGURATION
# ============================================================================

class StoreSettings(SQLModel, table=True):
    """
    Key-value store settings and configuration.

    Args:
        ss_id (Optional[int]): Setting ID, auto-incremented.
        ss_s_id (Optional[int]): Foreign key to store (null = global).
        ss_key (str): Setting key.
        ss_value (Optional[str]): Setting value (text).
        ss_value_json (Optional[dict]): Setting value (JSON for complex values).
        ss_description (Optional[str]): What this setting does.
        ss_is_public (bool): Whether visible to customers.
        ss_updated_at (datetime): Last update timestamp.
    """

    __table_args__ = (
        UniqueConstraint("ss_s_id", "ss_key", name="unique_store_setting"),
    )

    ss_id: Optional[int] = id_field("storesettings")
    ss_s_id: Optional[int] = Field(default=None, foreign_key="stores.s_id")
    ss_key: str = Field(max_length=100, index=True)
    ss_value: Optional[str] = Field(default=None, sa_column=Column(Text))
    ss_value_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    ss_description: Optional[str] = Field(default=None, max_length=500)
    ss_is_public: bool = Field(default=False)
    ss_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BusinessHours(SQLModel, table=True):
    """
    Store business hours.

    Args:
        bh_id (Optional[int]): Business hours ID, auto-incremented.
        bh_s_id (int): Foreign key to store.
        bh_day_of_week (int): Day (0=Monday, 6=Sunday).
        bh_open_time (Optional[str]): Opening time (e.g., "09:00").
        bh_close_time (Optional[str]): Closing time (e.g., "18:00").
        bh_is_closed (bool): Whether closed this day.
    """

    __table_args__ = (
        UniqueConstraint("bh_s_id", "bh_day_of_week", name="unique_business_hours"),
        CheckConstraint("bh_day_of_week >= 0 AND bh_day_of_week <= 6", name="check_day_range"),
    )

    bh_id: Optional[int] = id_field("businesshours")
    bh_s_id: int = Field(foreign_key="stores.s_id", index=True)
    bh_day_of_week: int = Field(ge=0, le=6)
    bh_open_time: Optional[str] = Field(default=None, max_length=5)
    bh_close_time: Optional[str] = Field(default=None, max_length=5)
    bh_is_closed: bool = Field(default=False)


# ============================================================================
# DELIVERY & SHIPPING MODELS
# ============================================================================

class DeliveryZones(SQLModel, table=True):
    """
    Delivery zones/areas for a store.

    Args:
        dz_id (Optional[int]): Zone ID, auto-incremented.
        dz_s_id (int): Foreign key to store.
        dz_name (str): Zone name.
        dz_polygon (Optional[dict]): GeoJSON polygon defining the zone.
        dz_postal_codes (Optional[list]): JSON list of postal codes.
        dz_delivery_fee (float): Delivery fee for this zone.
        dz_min_order_amount (Optional[float]): Minimum order for delivery.
        dz_free_delivery_above (Optional[float]): Free delivery threshold.
        dz_estimated_time_minutes (Optional[int]): Estimated delivery time.
        dz_is_active (bool): Whether zone is serviced.
    """

    dz_id: Optional[int] = id_field("deliveryzones")
    dz_s_id: int = Field(foreign_key="stores.s_id", index=True)
    dz_name: str = Field(max_length=100)
    dz_polygon: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    dz_postal_codes: Optional[list] = Field(default=None, sa_column=Column(JSON))
    dz_delivery_fee: float = Field(default=0.0, ge=0.0)
    dz_min_order_amount: Optional[float] = Field(default=None, ge=0.0)
    dz_free_delivery_above: Optional[float] = Field(default=None, ge=0.0)
    dz_estimated_time_minutes: Optional[int] = Field(default=None, ge=0)
    dz_is_active: bool = Field(default=True)


class Deliveries(SQLModel, table=True):
    """
    Delivery tracking for orders.

    Args:
        d_id (Optional[int]): Delivery ID, auto-incremented.
        d_o_id (int): Foreign key to order.
        d_dz_id (Optional[int]): Foreign key to delivery zone.
        d_driver_name (Optional[str]): Delivery driver name.
        d_driver_phone (Optional[str]): Driver phone number.
        d_tracking_number (Optional[str]): External tracking number.
        d_status (str): Delivery status.
        d_scheduled_date (Optional[date]): Scheduled delivery date.
        d_scheduled_time_slot (Optional[str]): Time slot.
        d_picked_up_at (Optional[datetime]): When picked up for delivery.
        d_delivered_at (Optional[datetime]): Actual delivery time.
        d_delivery_notes (Optional[str]): Delivery notes.
        d_proof_of_delivery_url (Optional[str]): Photo proof URL.
        d_signature_url (Optional[str]): Signature image URL.
        d_latitude (Optional[float]): Delivery location latitude.
        d_longitude (Optional[float]): Delivery location longitude.
        d_created_at (datetime): Creation timestamp.
        d_updated_at (datetime): Last update timestamp.
    """

    d_id: Optional[int] = id_field("deliveries")
    d_o_id: int = Field(foreign_key="orders.o_id", unique=True, index=True)
    d_dz_id: Optional[int] = Field(default=None, foreign_key="deliveryzones.dz_id")
    d_driver_name: Optional[str] = Field(default=None, max_length=100)
    d_driver_phone: Optional[str] = Field(default=None, max_length=20)
    d_tracking_number: Optional[str] = Field(default=None, max_length=100)
    d_status: str = Field(default="pending", max_length=30)
    d_scheduled_date: Optional[date] = Field(default=None)
    d_scheduled_time_slot: Optional[str] = Field(default=None, max_length=50)
    d_picked_up_at: Optional[datetime] = Field(default=None)
    d_delivered_at: Optional[datetime] = Field(default=None)
    d_delivery_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    d_proof_of_delivery_url: Optional[str] = Field(default=None, max_length=500)
    d_signature_url: Optional[str] = Field(default=None, max_length=500)
    d_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    d_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    d_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    d_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# ANALYTICS & LOGGING MODELS
# ============================================================================

class BotAnalytics(SQLModel, table=True):
    """
    Daily analytics for bot performance.

    Args:
        ba_id (Optional[int]): Analytics ID, auto-incremented.
        ba_date (date): Date of metrics.
        ba_total_conversations (int): Total conversations started.
        ba_total_messages (int): Total messages exchanged.
        ba_inbound_messages (int): Messages from users.
        ba_outbound_messages (int): Messages from bot.
        ba_unique_users (int): Unique users interacting.
        ba_new_users (int): New users registered.
        ba_orders_placed (int): Orders placed via bot.
        ba_revenue (float): Total revenue from bot orders.
        ba_avg_response_time_ms (Optional[float]): Average response time.
        ba_escalation_rate (Optional[float]): Percentage escalated to human.
        ba_satisfaction_score (Optional[float]): Average satisfaction score.
        ba_created_at (datetime): Creation timestamp.
    """

    ba_id: Optional[int] = id_field("botanalytics")
    ba_date: date = Field(unique=True, index=True)
    ba_total_conversations: int = Field(default=0, ge=0)
    ba_total_messages: int = Field(default=0, ge=0)
    ba_inbound_messages: int = Field(default=0, ge=0)
    ba_outbound_messages: int = Field(default=0, ge=0)
    ba_unique_users: int = Field(default=0, ge=0)
    ba_new_users: int = Field(default=0, ge=0)
    ba_orders_placed: int = Field(default=0, ge=0)
    ba_revenue: float = Field(default=0.0, ge=0.0)
    ba_avg_response_time_ms: Optional[float] = Field(default=None, ge=0.0)
    ba_escalation_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    ba_satisfaction_score: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    ba_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(SQLModel, table=True):
    """
    Audit log for important system events.

    Args:
        al_id (Optional[int]): Log entry ID, auto-incremented.
        al_entity_type (str): Type of entity (user, order, product).
        al_entity_id (int): ID of the entity.
        al_action (str): Action performed (create, update, delete).
        al_actor_type (str): Who performed (user, system, admin).
        al_actor_id (Optional[str]): ID of the actor.
        al_old_values (Optional[dict]): Previous values (JSON).
        al_new_values (Optional[dict]): New values (JSON).
        al_ip_address (Optional[str]): IP address if applicable.
        al_user_agent (Optional[str]): User agent string.
        al_created_at (datetime): Timestamp of event.
    """

    al_id: Optional[int] = id_field("auditlog")
    al_entity_type: str = Field(max_length=50, index=True)
    al_entity_id: int
    al_action: str = Field(max_length=50)
    al_actor_type: str = Field(max_length=20)
    al_actor_id: Optional[str] = Field(default=None, max_length=50)
    al_old_values: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    al_new_values: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    al_ip_address: Optional[str] = Field(default=None, max_length=45)
    al_user_agent: Optional[str] = Field(default=None, max_length=500)
    al_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# EXPORT ALL MODELS
# ============================================================================

CHATBOT_MODELS = [
    # Users
    Users,
    # Products (enhanced)
    Products,
    # Orders
    Orders,
    OrderItems,
    OrderStatusHistory,
    # Conversations & Messages
    Conversations,
    Messages,
    MessageTemplates,
    # Reviews
    ProductReviews,
    BotFeedback,
    # FAQ
    FAQItems,
    # Notifications
    Notifications,
    # Settings
    StoreSettings,
    BusinessHours,
    # Delivery
    DeliveryZones,
    Deliveries,
    # Analytics
    BotAnalytics,
    AuditLog,
]
