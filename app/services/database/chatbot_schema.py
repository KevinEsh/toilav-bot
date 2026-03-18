"""
Database schema for WhatsApp e-commerce chatbot.
Includes: Users (with address), Products (with details/variants), Orders, Messages, Reviews, FAQ, etc.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

# from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import (
    JSON,
    Column,
    Field,
    Numeric,
    Sequence,
    SQLModel,
    Text,
    UniqueConstraint,
)


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


class UserRole(str, Enum):
    ADMIN = "admin"
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    PENDING_VERIFICATION = "pending_verification"


# class ProductCategory(str, Enum):
#     FOOD = "food"
#     BEVERAGES = "beverages"
#     ELECTRONICS = "electronics"
#     CLOTHING = "clothing"
#     HOME = "home"
#     BEAUTY = "beauty"
#     HEALTH = "health"
#     SPORTS = "sports"
#     TOYS = "toys"
#     OTHER = "other"


class ProductUnit(str, Enum):
    UNIT = "unit"
    KG = "kg"
    GR = "gr"
    LITER = "liter"
    ML = "ml"
    METER = "meter"
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


class CancelReason(str, Enum):
    CUSTOMER_REQUEST = "customer_request"
    OUT_OF_STOCK = "out_of_stock"
    PAYMENT_FAILURE = "payment_failure"
    FRAUD_SUSPECTED = "fraud_suspected"
    OTHER = "other"


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
    INBOUND = "inbound"  # From customer to bot
    OUTBOUND = "outbound"  # From bot/store owner to customer


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
    ORDER = "order"  # like WhatsApp's catalog messages for products, we can use this type to send product information in a structured format that WhatsApp can render nicely in the chat interface. This would allow us to showcase products directly within the conversation, making it easier for customers to browse and make purchases without leaving the chat. We can include details like product name, image, price, and a button to view more or add to cart, all formatted according to WhatsApp's interactive message guidelines. This would enhance the shopping experience and drive more engagement and sales through the chatbot.


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
# USER MODEL (dashboard admin/staff)
# ============================================================================


class Users(SQLModel, table=True):
    """
    Users who access the store dashboard UI. These can be store owners,
    managers, or support staff who need access to the backend system to
    manage products, view orders, analytics, and assist customers.

    Args:
        u_id (int): User ID, auto-incremented.
        u_email (str): Email address (unique login identifier).
        u_username (str): Display name.
        u_password_hash (str): Hashed password (never store plaintext).
        u_role (UserRole): Role (owner, manager, staff).
        u_is_active (bool): Whether the account is active.
        u_last_login_at (Optional[datetime]): Last login timestamp.
        u_created_at (datetime): Account creation timestamp.
        u_updated_at (datetime): Last update timestamp.
    """

    u_id: int = id_field("users")
    u_email: str = Field(unique=True, index=True, max_length=255)
    u_username: str = Field(max_length=100)
    u_password_hash: str = Field(max_length=255)
    u_role: UserRole = Field(default=UserRole.STAFF)
    u_is_active: bool = Field(default=True)
    u_last_login_at: Optional[datetime] = Field(default=None)
    u_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    u_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# CUSTOMER MODEL (WhatsApp consumers)
# ============================================================================


class Customers(SQLModel, table=True):
    """
    Customer information for WhatsApp chatbot.
    Primary identifier is the WhatsApp phone number.
    Includes single address per customer.

    Args:
        c_id (int): Unique customer ID, auto-incremented.
        c_phone (str): WhatsApp phone number (unique, primary contact).
        c_whatsapp_id (str): WhatsApp Business API user ID.
        c_name (Optional[str]): Customer's full name.
        c_status (CustomerStatus): Account status.
        c_latitude (Optional[float]): GPS latitude for delivery.
        c_longitude (Optional[float]): GPS longitude for delivery.
        c_delivery_instructions (Optional[str]): Special delivery notes.
        c_created_at (datetime): Account creation timestamp.
        c_updated_at (datetime): Last update timestamp.
    """

    c_id: int = id_field("customers")
    c_phone: str = Field(unique=True, index=True, max_length=20)
    c_whatsapp_id: str = Field(default=None, max_length=50, unique=True)
    c_name: Optional[str] = Field(default=None, max_length=100)
    c_status: CustomerStatus = Field(default=CustomerStatus.ACTIVE)
    c_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    c_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    c_delivery_instructions: Optional[str] = Field(default=None, max_length=500)
    # Timestamps
    c_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    c_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# PRODUCT MODEL (enhanced with all details, category, variants)
# ============================================================================


class Products(SQLModel, table=True):
    """
    Products for the WhatsApp e-commerce chatbot.
    Includes pricing, images, and availability.

    Args:
        p_id (int): Product ID, auto-incremented.
        p_name (str): Name of the product.
        p_description (Optional[str]): Description of the product.
        p_price (float): Regular selling price.
        p_currency (str): Currency code (USD, EUR, etc.).
        p_quantity (int):
        p_unit (ProductUnit): Unit of measure (kg, piece, liter).
        p_image_url (Optional[str]): Public URL of the product image stored in MinIO.
        p_properties (Optional[dict]): JSON object for custom properties such as color, size, material, etc.
        p_is_available (bool): Whether product is available for sale. If false, hidden from customers.
        p_created_at (datetime): Creation timestamp.
        p_updated_at (datetime): Last update timestamp.
    """

    p_id: int = id_field("products")
    p_name: str = Field(unique=True)
    p_description: Optional[str] = Field(default=None, sa_column=Column(Text))
    p_sale_price: float = Field(default=0.0, ge=0.0, sa_column=Column(Numeric(10, 2)))
    p_currency: str = Field(default="MXN", max_length=3)
    p_net_content: float = Field(default=1.0, ge=0.0)
    p_unit: ProductUnit = Field(default=ProductUnit.UNIT)
    p_image_url: Optional[str] = Field(default=None)
    p_properties: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    p_rag_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    p_is_available: bool = Field(default=True)
    p_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    p_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Stores(SQLModel, table=True):
    """
    Stores for the WhatsApp e-commerce chatbot. Each store can have multiple products and sales records.
    This allows us to manage inventory and sales data for different store locations or brands within the chatbot.

    Args:
        s_id (Optional[int]): Store ID, auto-incremented.
        s_name (str): Name of the store.
        s_description (Optional[str]): Description of the store. Such as the type of products it sells, its history, or any other relevant information that can help customers understand what the store is about.
        s_properties (Optional[dict]): JSON object for custom properties such as city, state, contact information, website, social media links, etc.
        s_longitude (Optional[float]): GPS longitude for store location.
        s_latitude (Optional[float]): GPS latitude for store location.
    """

    s_id: Optional[int] = id_field("stores")
    s_name: str = Field(unique=True)
    s_description: Optional[str] = Field(default=None, sa_column=Column(Text))
    s_properties: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    s_rag_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    s_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    s_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    s_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    s_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Sales(SQLModel, table=True):
    """
    Sales records linking products and stores to display sales over history. This can be used for
    analytics, trends, and showcasing popular products in the chatbot.

    Args:
        sa_id (Optional[int]): Sale ID, auto-incremented.
        sa_p_id (int): Foreign key referencing the product.
        sa_s_id (int): Foreign key referencing the store.
        sa_date (date): Date of the sale.
        sa_units_sold (int): Number of units sold on this date, product, and store
    """

    __table_args__ = (UniqueConstraint("sa_p_id", "sa_s_id", "sa_date", name="unique_sale"),)

    sa_id: Optional[int] = id_field("sales")
    sa_p_id: int = Field(foreign_key="products.p_id")
    sa_s_id: int = Field(foreign_key="stores.s_id", index=True)
    sa_date: date = Field(default_factory=date.today)
    sa_units_sold: int = Field(ge=0)
    sa_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sa_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Stocks(SQLModel, table=True):
    """
    Stock levels for products in each store. This allows the chatbot to provide real-time availability
    information to customers when they inquire about products.

    Args:
        st_id (Optional[int]): Stock record ID, auto-incremented.
        st_p_id (int): Foreign key referencing the product.
        st_s_id (int): Foreign key referencing the store.
        st_units (int): Current stock units available for this product in this store.
        st_datetime (datetime): Timestamp of the stock record.
    """

    __table_args__ = (UniqueConstraint("st_p_id", "st_s_id", "st_datetime", name="unique_stock"),)

    st_id: Optional[int] = id_field("stocks")
    st_p_id: int = Field(foreign_key="products.p_id")
    st_s_id: int = Field(foreign_key="stores.s_id")
    st_datetime: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    st_units: int = Field(ge=0)
    st_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    st_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# ORDER MODELS
# ============================================================================


class Orders(SQLModel, table=True):
    """
    Customer orders.

    Args:
        o_id (int): Order ID, auto-incremented.
        o_code (str): Human-readable order code.
        o_u_id (int): Foreign key to users.
        o_s_id (Optional[int]): Foreign key to store.
        o_subtotal (float): Order subtotal before discounts.
        o_discount_amount (Optional[float]): Total discount applied.
        o_shipping_amount (Optional[float]): Shipping cost.
        o_total (float): Final order total.
        o_currency (str): Currency code.
        o_payment_method (Optional[PaymentMethod]): Payment method used.
        o_payment_status (Optional[PaymentStatus]): Payment status.
        o_notes (Optional[str]): Customer notes. Such as delivery instructions or special requests.
        o_internal_notes (Optional[str]): Internal staff notes.
        o_estimated_delivery (Optional[date]): Estimated delivery date.
        o_delivered_at (Optional[datetime]): Actual delivery timestamp.
        o_cancelled_at (Optional[datetime]): Cancellation timestamp.
        o_cancel_reason (Optional[CancelReason]): Reason for cancellation.
        o_created_at (datetime): Creation timestamp.
        o_updated_at (datetime): Last update timestamp.
    """

    o_id: int = id_field("orders")
    # o_code: str = Field(unique=True, max_length=30, index=True)
    o_c_id: int = Field(foreign_key="customers.c_id", index=True)
    o_s_id: int = Field(foreign_key="stores.s_id", index=True)
    o_status: OrderStatus = Field(default=OrderStatus.PENDING)
    # Amounts
    o_subtotal: float = Field(default=0.0, ge=0.0, sa_column=Column(Numeric(10, 2)))
    o_discount_amount: Optional[float] = Field(default=None, ge=0.0, sa_column=Column(Numeric(10, 2)))
    o_shipping_amount: Optional[float] = Field(default=None, ge=0.0, sa_column=Column(Numeric(10, 2)))
    o_total: float = Field(default=0.0, ge=0.0, sa_column=Column(Numeric(10, 2)))
    o_currency: str = Field(default="MXN", max_length=3)
    # Payment
    o_payment_method: Optional[PaymentMethod] = Field(default=None)
    o_payment_status: Optional[PaymentStatus] = Field(default=None)
    # Notes
    o_customer_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    o_internal_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    # Delivery
    o_estimated_delivery: Optional[datetime] = Field(default=None)
    o_delivered_at: Optional[datetime] = Field(default=None)
    # Cancellation
    o_cancelled_at: Optional[datetime] = Field(default=None)
    o_cancel_reason: Optional[CancelReason] = Field(default=None)
    # Timestamps
    o_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    o_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderItems(SQLModel, table=True):
    """
    Individual items within an order.

    Args:
        oi_id (int): Order item ID, auto-incremented.
        oi_o_id (int): Foreign key to order.
        oi_p_id (int): Foreign key to product.
        oi_units (int): Quantity ordered.
        oi_unit_price (float): Price per unit at time of purchase (snapshot).
        oi_discount_amount (Optional[float]): Discount applied to this item.
        oi_created_at (datetime): Creation timestamp.
        oi_updated_at (datetime): Last update timestamp.
    """

    oi_id: int = id_field("orderitems")
    oi_o_id: int = Field(foreign_key="orders.o_id", index=True)
    # index=True because we will often query items by order ID
    oi_p_id: int = Field(foreign_key="products.p_id")
    oi_units: int = Field(ge=1)
    oi_unit_price: float = Field(default=0.0, ge=0.0, sa_column=Column(Numeric(10, 2)))
    oi_discount_amount: Optional[float] = Field(default=None, ge=0.0, sa_column=Column(Numeric(10, 2)))
    oi_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    oi_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderStatusHistory(SQLModel, table=True):
    """
    Track order status changes over time.

    Args:
        osh_id (int): History entry ID, auto-incremented.
        osh_o_id (int): Foreign key to order.
        osh_status (OrderStatus): Order status.
        osh_created_at (datetime): Timestamp of change.
        osh_updated_at (datetime): Last update timestamp.
    """

    osh_id: int = id_field("orderstatushistory")
    osh_o_id: int = Field(foreign_key="orders.o_id", index=True)
    osh_status: OrderStatus = Field(default=OrderStatus.PENDING)
    osh_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    osh_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# CONVERSATION & MESSAGE MODELS
# ============================================================================

# TODO: internal note: interesting use but to much for MVP, we can add it later if we have time and resources to implement it properly. It would be a great way to maintain context in the chatbot conversations and provide a more personalized experience. We can track the conversation flow, user intent, and relevant information extracted from messages to enhance the bot's responses and make interactions more seamless for customers. For now, we can focus on getting the core messaging functionality working and then consider adding this conversation tracking feature in a future iteration.
# class Conversations(SQLModel, table=True):
#     """
#     WhatsApp conversation sessions.
#     Tracks conversation context and state.

#     Example in the application: A customer initiates a conversation about an order. We create a Conversations entry with conv_u_id referencing the user, conv_status=ACTIVE, and conv_intent="order_inquiry". As the conversation progresses, we update conv_context with relevant information (e.g., order ID being discussed) and track timestamps. If the customer asks about a product, we might set conv_intent="product_inquiry" and store the product ID in conv_context. This allows us to maintain state across multiple messages and provide a more personalized experience.
#     A way to implement it using the chatbot powered by RAG could be: When a new message comes in, we check if there's an active conversation for that user. If not, we create a new Conversations entry. We then analyze the message to determine the user's intent (e.g., asking about an order, product, or requesting support) and update conv_intent accordingly. We can also store any relevant information extracted from the message (like order ID or product name) in conv_context as a JSON object. This way, when the next message comes in, we can refer back to conv_context to understand the context of the conversation and provide accurate responses. For example, if the user asks "Where is my order #123?", we set conv_intent="order_inquiry" and store {"order_id": 123} in conv_context. When they follow up with "Has it shipped?", we can check conv_context for the order_id and provide the current status of that specific order without needing them to repeat the information.

#     Args:
#         conv_id (Optional[int]): Conversation ID, auto-incremented.
#         conv_u_id (int): Foreign key to user.
#         conv_status (ConversationStatus): Conversation status.
#         conv_intent (Optional[str]): Detected user intent.
#         conv_context (Optional[dict]): JSON state for conversation flow.
#         conv_started_at (datetime): When conversation started.
#         conv_ended_at (Optional[datetime]): When conversation ended.
#         conv_last_message_at (Optional[datetime]): Last message timestamp.
#         conv_message_count (int): Total messages in conversation.
#         conv_escalated_to (Optional[str]): Agent ID if escalated.
#         conv_escalated_at (Optional[datetime]): Escalation timestamp.
#     """

#     conv_id: int = id_field("conversations")
#     conv_u_id: int = Field(foreign_key="users.u_id", index=True)
#     conv_status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
#     conv_intent: Optional[str] = Field(default=None, max_length=50)
#     conv_context: Optional[dict] = Field(default=None, sa_column=Column(JSON))
#     conv_started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
#     conv_ended_at: Optional[datetime] = Field(default=None)
#     conv_last_message_at: Optional[datetime] = Field(default=None)
#     conv_message_count: int = Field(default=0)
#     conv_escalated_to: Optional[str] = Field(default=None, max_length=100)
#     conv_escalated_at: Optional[datetime] = Field(default=None)


class Messages(SQLModel, table=True):
    """
    Individual WhatsApp messages.

    Args:
        m_id (int): Message ID (internal), auto-incremented.
        m_u_id (int): Foreign key to user.
        m_direction (MessageDirection): Inbound or outbound.
        m_type (MessageType): Message type (text, image, etc.).
        m_content (Optional[str]): Message content/text.
        m_status (MessageStatus): Delivery status.
        m_context_message_id (Optional[str]): ID of message being replied to.
        m_error_code (Optional[str]): Error code if failed.
        m_error_message (Optional[str]): Error message if failed.
        m_created_at (datetime): Creation timestamp.
    """

    m_id: int = id_field("messages")
    # m_conv_id: int = Field(foreign_key="conversations.conv_id", index=True)
    m_c_id: int = Field(foreign_key="customers.c_id", index=True)
    m_direction: MessageDirection
    m_type: MessageType = Field(default=MessageType.TEXT)
    m_content: Optional[str] = Field(default=None, sa_column=Column(Text))
    # m_media_mime_type: Optional[str] = Field(default=None, max_length=100)
    m_status: MessageStatus = Field(default=MessageStatus.SENT)
    m_context_message_id: Optional[str] = Field(default=None, max_length=100)
    # m_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    m_error_code: Optional[str] = Field(default=None, max_length=50)
    m_error_message: Optional[str] = Field(default=None, max_length=500)
    m_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageTemplates(SQLModel, table=True):
    """
    WhatsApp message templates for outbound notifications. Example using the chatbot: We can create a MessageTemplates entry with mt_name="order_update" and mt_content containing the template text with placeholders (e.g., "Hola {{1}}, tu pedido {{2}} ha sido {{3}}."). When we want to send an order update notification, we can retrieve this template, replace the placeholders with actual values (customer name, order code, new status), and send the formatted message via WhatsApp. This allows us to maintain consistent messaging and easily manage templates for different types of notifications.

    Args:
        mt_id (int): Template ID, auto-incremented.
        mt_name (str): Template name (as registered with WhatsApp).
        mt_content (str): Template content with placeholders.
        mt_created_at (datetime): Creation timestamp.
        mt_updated_at (datetime): Last update timestamp.
    """

    # __table_args__ = (UniqueConstraint("mt_name", "mt_language", name="unique_template"),)

    mt_id: int = id_field("messagetemplates")
    mt_name: str = Field(unique=True, max_length=100)
    # mt_language: str = Field(default="es", max_length=10)
    # mt_category: Optional[str] = Field(default=None, max_length=50)
    mt_content: str = Field(sa_column=Column(Text))
    # mt_header_type: Optional[str] = Field(default=None, max_length=20)
    # mt_header_content: Optional[str] = Field(default=None, max_length=500)
    # mt_has_buttons: bool = Field(default=False)
    # mt_buttons: Optional[list] = Field(default=None, sa_column=Column(JSON))
    # mt_status: str = Field(default="pending", max_length=20)
    # mt_whatsapp_template_id: Optional[str] = Field(default=None, max_length=100)
    mt_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mt_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# REVIEW & FEEDBACK MODELS
# ============================================================================

# TODO: No for now, but we can include it in the future for gathering customer feedback and improving
# the chatbot experience. We can create a BotFeedback model to store user ratings and comments on the bot's
# responses. This would allow us to analyze feedback, identify areas for improvement, and track changes
# in customer satisfaction over time. For example, after a customer interacts with the bot, we can prompt
# them to rate their experience and provide comments. We can then store this feedback in the BotFeedback
# table with references to the specific messages or interactions it relates to. This data can be invaluable
# for continuously enhancing the chatbot's performance and ensuring it meets customer needs effectively.
# class ProductReviews(SQLModel, table=True):
#     """
#     Product reviews from customers.

#     Args:
#         pr_id (Optional[int]): Review ID, auto-incremented.
#         pr_p_id (int): Foreign key to product.
#         pr_u_id (int): Foreign key to user.
#         pr_o_id (Optional[int]): Foreign key to order (verify purchase).
#         pr_rating (int): Rating (1-5).
#         pr_title (Optional[str]): Review title.
#         pr_comment (Optional[str]): Review comment.
#         pr_images (Optional[list]): JSON list of image URLs.
#         pr_is_verified_purchase (bool): Whether user purchased product.
#         pr_is_approved (bool): Whether review is approved for display.
#         pr_created_at (datetime): Creation timestamp.
#     """

#     __table_args__ = (
#         CheckConstraint("pr_rating >= 1 AND pr_rating <= 5", name="check_rating_range"),
#     )

#     pr_id: int = id_field("productreviews")
#     pr_p_id: int = Field(foreign_key="products.p_id", index=True)
#     pr_u_id: int = Field(foreign_key="users.u_id", index=True)
#     pr_o_id: Optional[int] = Field(default=None, foreign_key="orders.o_id")
#     pr_rating: int = Field(ge=1, le=5)
#     pr_title: Optional[str] = Field(default=None, max_length=200)
#     pr_comment: Optional[str] = Field(default=None, sa_column=Column(Text))
#     pr_images: Optional[list] = Field(default=None, sa_column=Column(JSON))
#     pr_is_verified_purchase: bool = Field(default=False)
#     pr_is_approved: bool = Field(default=False)
#     pr_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# class BotFeedback(SQLModel, table=True):
#     """
#     Feedback on bot responses for improvement
#     la tabla entera no la veo necesaria, en primeras instancias deberiamos estar analizando el funcionamientos nosotros

#     Args:
#         bf_id (Optional[int]): Feedback ID, auto-incremented.
#         bf_m_id (int): Foreign key to message.
#         bf_u_id (int): Foreign key to user.
#         bf_rating (Optional[int]): Rating (1-5).
#         bf_comment (Optional[str]): User feedback comment.
#         bf_was_helpful (Optional[bool]): Whether response was helpful.
#         bf_created_at (datetime): Creation timestamp.
#     """

#     bf_id: Optional[int] = id_field("botfeedback")
#     bf_m_id: int = Field(foreign_key="messages.m_id", index=True)
#     bf_u_id: int = Field(foreign_key="users.u_id")
#     bf_was_helpful: Optional[bool] = Field(default=None)
#     bf_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# FAQ MODEL (with category as enum)
# ============================================================================


class FAQItems(SQLModel, table=True):
    """
    Frequently Asked Questions for the chatbot.
    Used for RAG and quick responses.

    Args:
        faq_id (int): FAQ ID, auto-incremented.
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

    faq_id: int = id_field("faqitems")
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

# class Notifications(SQLModel, table=True):
#     """
#     System notifications for users.
#     Can be sent via WhatsApp or displayed in app.

#     Args:
#         n_id (Optional[int]): Notification ID, auto-incremented.
#         n_u_id (int): Foreign key to user.
#         n_type (NotificationType): Notification type.
#         n_title (str): Short title.
#         n_message (str): Full message content.
#         n_data (Optional[dict]): Additional JSON data.
#         n_is_read (bool): Whether user has read it.
#         n_sent_via_whatsapp (bool): Whether sent via WhatsApp.
#         n_whatsapp_message_id (Optional[str]): WhatsApp message ID if sent.
#         n_scheduled_for (Optional[datetime]): Scheduled send time.
#         n_sent_at (Optional[datetime]): Actual send time.
#         n_created_at (datetime): Creation timestamp.
#     """

# n_id: Optional[int] = id_field("notifications")
# n_u_id: int = Field(foreign_key="users.u_id", index=True)
# n_type: NotificationType = Field(default=NotificationType.SYSTEM)
# n_message: str = Field(sa_column=Column(Text))
# n_sent_via_whatsapp: bool = Field(default=False)
# n_whatsapp_message_id: Optional[str] = Field(default=None, max_length=100)
# n_sent_at: Optional[datetime] = Field(default=None)
# n_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# STORE SETTINGS & CONFIGURATION
# ============================================================================

# class StoreSettings(SQLModel, table=True):
#     """
#     Key-value store settings and configuration.

#     Args:
#         ss_id (Optional[int]): Setting ID, auto-incremented.
#         ss_s_id (Optional[int]): Foreign key to store (null = global).
#         ss_key (str): Setting key.
#         ss_value (Optional[str]): Setting value (text).
#         ss_value_json (Optional[dict]): Setting value (JSON for complex values).
#         ss_description (Optional[str]): What this setting does.
#         ss_is_public (bool): Whether visible to customers.
#         ss_updated_at (datetime): Last update timestamp.
#     """

#     __table_args__ = (
#         UniqueConstraint("ss_s_id", "ss_key", name="unique_store_setting"),
#     )

#     ss_id: Optional[int] = id_field("storesettings")
#     ss_s_id: Optional[int] = Field(default=None, foreign_key="stores.s_id")
#     ss_key: str = Field(max_length=100, index=True) #cual es la diferencia con key?
#     ss_value: Optional[str] = Field(default=None, sa_column=Column(Text))
#     ss_description: Optional[str] = Field(default=None, max_length=500)
#     ss_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# class BusinessHours(SQLModel, table=True):
#     """
#     Store business hours.

#     Args:
#         bh_id (Optional[int]): Business hours ID, auto-incremented.
#         bh_s_id (int): Foreign key to store.
#         bh_day_of_week (int): Day (0=Monday, 6=Sunday).
#         bh_open_time (Optional[str]): Opening time (e.g., "09:00").
#         bh_close_time (Optional[str]): Closing time (e.g., "18:00").
#         bh_is_closed (bool): Whether closed this day.
#     """

#     __table_args__ = (
#         UniqueConstraint("bh_s_id", "bh_day_of_week", name="unique_business_hours"),
#         CheckConstraint("bh_day_of_week >= 0 AND bh_day_of_week <= 6", name="check_day_range"),
#     )

#     bh_id: Optional[int] = id_field("businesshours")
#     bh_s_id: int = Field(foreign_key="stores.s_id", index=True)
#     bh_day_of_week: int = Field(ge=0, le=6)
#     bh_open_time: Optional[str] = Field(default=None, max_length=5)
#     bh_close_time: Optional[str] = Field(default=None, max_length=5)


# ============================================================================
# DELIVERY & SHIPPING MODELS
# ============================================================================

# class DeliveryZones(SQLModel, table=True):
#     """
#     Delivery zones/areas for a store.

#     Args:
#         dz_id (Optional[int]): Zone ID, auto-incremented.
#         dz_s_id (int): Foreign key to store.
#         dz_name (str): Zone name.
#         dz_polygon (Optional[dict]): GeoJSON polygon defining the zone.
#         dz_postal_codes (Optional[list]): JSON list of postal codes.
#         dz_delivery_fee (float): Delivery fee for this zone.
#         dz_min_order_amount (Optional[float]): Minimum order for delivery.
#         dz_free_delivery_above (Optional[float]): Free delivery threshold.
#         dz_estimated_time_minutes (Optional[int]): Estimated delivery time.
#         dz_is_active (bool): Whether zone is serviced.
#     """

#     dz_id: Optional[int] = id_field("deliveryzones")
#     dz_s_id: int = Field(foreign_key="stores.s_id", index=True)
#     dz_name: str = Field(max_length=100)
#     dz_polygon: Optional[dict] = Field(default=None, sa_column=Column(JSON))
#     dz_postal_codes: Optional[list] = Field(default=None, sa_column=Column(JSON))
#     dz_delivery_fee: float = Field(default=0.0, ge=0.0)
#     dz_min_order_amount: Optional[float] = Field(default=None, ge=0.0)
#     dz_free_delivery_above: Optional[float] = Field(default=None, ge=0.0)
#     dz_estimated_time_minutes: Optional[int] = Field(default=None, ge=0)
#     dz_is_active: bool = Field(default=True)


# class Deliveries(SQLModel, table=True):
#     """
#     Delivery tracking for orders.

#     Args:
#         d_id (Optional[int]): Delivery ID, auto-incremented.
#         d_o_id (int): Foreign key to order.
#         d_dz_id (Optional[int]): Foreign key to delivery zone.
#         d_driver_name (Optional[str]): Delivery driver name.
#         d_driver_phone (Optional[str]): Driver phone number.
#         d_tracking_number (Optional[str]): External tracking number.
#         d_status (str): Delivery status.
#         d_scheduled_date (Optional[date]): Scheduled delivery date.
#         d_scheduled_time_slot (Optional[str]): Time slot.
#         d_picked_up_at (Optional[datetime]): When picked up for delivery.
#         d_delivered_at (Optional[datetime]): Actual delivery time.
#         d_delivery_notes (Optional[str]): Delivery notes.
#         d_proof_of_delivery_url (Optional[str]): Photo proof URL.
#         d_signature_url (Optional[str]): Signature image URL.
#         d_latitude (Optional[float]): Delivery location latitude.
#         d_longitude (Optional[float]): Delivery location longitude.
#         d_created_at (datetime): Creation timestamp.
#         d_updated_at (datetime): Last update timestamp.
#     """

#     d_id: Optional[int] = id_field("deliveries")
#     d_o_id: int = Field(foreign_key="orders.o_id", unique=True, index=True)
#     d_dz_id: Optional[int] = Field(default=None, foreign_key="deliveryzones.dz_id")
#     d_driver_name: Optional[str] = Field(default=None, max_length=100)
#     d_driver_phone: Optional[str] = Field(default=None, max_length=20)
#     d_tracking_number: Optional[str] = Field(default=None, max_length=100)
#     d_status: str = Field(default="pending", max_length=30)
#     d_scheduled_date: Optional[date] = Field(default=None)
#     d_scheduled_time_slot: Optional[str] = Field(default=None, max_length=50)
#     d_picked_up_at: Optional[datetime] = Field(default=None)
#     d_delivered_at: Optional[datetime] = Field(default=None)
#     d_delivery_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
#     d_proof_of_delivery_url: Optional[str] = Field(default=None, max_length=500)
#     d_signature_url: Optional[str] = Field(default=None, max_length=500)
#     d_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
#     d_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
#     d_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
#     d_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# ANALYTICS & LOGGING MODELS
# ============================================================================

# class BotAnalytics(SQLModel, table=True):
#     """
#     Daily analytics for bot performance.

#     Args:
#         ba_id (Optional[int]): Analytics ID, auto-incremented.
#         ba_date (date): Date of metrics.
#         ba_total_conversations (int): Total conversations started.
#         ba_total_messages (int): Total messages exchanged.
#         ba_inbound_messages (int): Messages from users.
#         ba_outbound_messages (int): Messages from bot.
#         ba_unique_users (int): Unique users interacting.
#         ba_new_users (int): New users registered.
#         ba_orders_placed (int): Orders placed via bot.
#         ba_revenue (float): Total revenue from bot orders.
#         ba_avg_response_time_ms (Optional[float]): Average response time.
#         ba_escalation_rate (Optional[float]): Percentage escalated to human.
#         ba_satisfaction_score (Optional[float]): Average satisfaction score.
#         ba_created_at (datetime): Creation timestamp.
#     """

#     ba_id: Optional[int] = id_field("botanalytics")
#     ba_date: date = Field(unique=True, index=True)
#     ba_total_conversations: int = Field(default=0, ge=0)
#     ba_total_messages: int = Field(default=0, ge=0)
#     ba_inbound_messages: int = Field(default=0, ge=0)
#     ba_outbound_messages: int = Field(default=0, ge=0)
#     ba_unique_users: int = Field(default=0, ge=0)
#     ba_new_users: int = Field(default=0, ge=0)
#     ba_orders_placed: int = Field(default=0, ge=0)
#     ba_revenue: float = Field(default=0.0, ge=0.0)
#     ba_avg_response_time_ms: Optional[float] = Field(default=None, ge=0.0)
#     ba_escalation_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
#     ba_satisfaction_score: Optional[float] = Field(default=None, ge=0.0, le=5.0)
#     ba_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# class AuditLog(SQLModel, table=True):
#     """
#     Audit log for important system events.

#     Args:
#         al_id (Optional[int]): Log entry ID, auto-incremented.
#         al_entity_type (str): Type of entity (user, order, product).
#         al_entity_id (int): ID of the entity.
#         al_action (str): Action performed (create, update, delete).
#         al_actor_type (str): Who performed (user, system, admin).
#         al_actor_id (Optional[str]): ID of the actor.
#         al_old_values (Optional[dict]): Previous values (JSON).
#         al_new_values (Optional[dict]): New values (JSON).
#         al_ip_address (Optional[str]): IP address if applicable.
#         al_user_agent (Optional[str]): User agent string.
#         al_created_at (datetime): Timestamp of event.
#     """

#     al_id: Optional[int] = id_field("auditlog")
#     al_entity_type: str = Field(max_length=50, index=True)
#     al_entity_id: int
#     al_action: str = Field(max_length=50)
#     al_actor_type: str = Field(max_length=20)
#     al_actor_id: Optional[str] = Field(default=None, max_length=50)
#     al_ip_address: Optional[str] = Field(default=None, max_length=45)
#     al_user_agent: Optional[str] = Field(default=None, max_length=500)
#     al_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# EXPORT ALL MODELS
# ============================================================================

CHATBOT_MODELS = [
    # Users & Customers
    Users,
    Customers,
    # Products & Inventory
    Products,
    Stores,
    Sales,
    Stocks,
    # Orders
    Orders,
    OrderItems,
    OrderStatusHistory,
    # Messages
    Messages,
    MessageTemplates,
    # Feedback
    # BotFeedback,
    # # FAQ
    FAQItems,
    # # Notifications
    # Notifications,
    # # Settings
    # StoreSettings,
    # BusinessHours,
    # # Delivery
    # DeliveryZones,
    # Deliveries,
    # # Analytics
    # BotAnalytics,
    # AuditLog,
]