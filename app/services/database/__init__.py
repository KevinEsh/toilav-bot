"""
Database module for WhatsApp chatbot.
Contains all SQLModel schemas and database configuration.
"""

from .dbconfig import (
    engine,
    create_db_and_tables,
    get_session,
    SessionType,
    DATABASE_URL,
)

from .schema import (
    Stores,
    Sales,
    Promotions,
    Stocks,
)

from .chatbot_schema import (
    # Enums
    UserStatus,
    ProductCategory,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    MessageDirection,
    MessageType,
    MessageStatus,
    ConversationStatus,
    FAQCategory,
    NotificationType,
    # User model (with address)
    Users,
    # Product model (with details/variants)
    Products,
    # Order models
    Orders,
    OrderItems,
    OrderStatusHistory,
    # Conversation & Message models
    Conversations,
    Messages,
    MessageTemplates,
    # Review models
    ProductReviews, # Kevin
    BotFeedback, # Agustin
    # FAQ model
    FAQItems,
    # Notification
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
    # All models list
    CHATBOT_MODELS,
)

__all__ = [
    # Database config
    "engine",
    "create_db_and_tables",
    "get_session",
    "SessionType",
    "DATABASE_URL",
    # Supply chain models
    "Stores",
    "Sales",
    "Promotions",
    "Stocks",
    # Enums
    "UserStatus",
    "ProductCategory",
    "OrderStatus",
    "PaymentStatus",
    "PaymentMethod",
    "MessageDirection",
    "MessageType",
    "MessageStatus",
    "ConversationStatus",
    "FAQCategory",
    "NotificationType",
    # User model (with address)
    "Users",
    # Product model (with details/variants)
    "Products",
    # Order models
    "Orders",
    "OrderItems",
    "OrderStatusHistory",
    # Conversation & Message models
    "Conversations",
    "Messages",
    "MessageTemplates",
    # Review models
    "ProductReviews",
    "BotFeedback",
    # FAQ model
    "FAQItems",
    # Notification
    "Notifications",
    # Settings
    "StoreSettings",
    "BusinessHours",
    # Delivery
    "DeliveryZones",
    "Deliveries",
    # Analytics
    "BotAnalytics",
    "AuditLog",
    # All models list
    "CHATBOT_MODELS",
]
