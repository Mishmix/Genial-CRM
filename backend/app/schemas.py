"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ============ Auth ============

class TelegramAuthRequest(BaseModel):
    init_data: str = Field(..., description="Telegram WebApp initData string")


class PasswordAuthRequest(BaseModel):
    password: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    success: bool
    user_id: Optional[int] = None
    username: Optional[str] = None
    message: Optional[str] = None


# ============ Tags ============

class TagBase(BaseModel):
    name: str
    color: Optional[str] = "#3b82f6"


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    id: int
    
    class Config:
        from_attributes = True


# ============ Messages ============

class MessageBase(BaseModel):
    text: Optional[str] = None
    direction: str


class MessageCreate(BaseModel):
    text: str


class MessageResponse(MessageBase):
    id: int
    client_id: int
    telegram_message_id: Optional[int] = None
    sent_at: datetime
    
    class Config:
        from_attributes = True


# ============ Clients ============

class ClientBase(BaseModel):
    telegram_user_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    language_code: Optional[str] = None


class ClientCreate(ClientBase):
    business_connection_id: Optional[str] = None


class ClientUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    tag_ids: Optional[List[int]] = None
    is_archived: Optional[bool] = None
    lost_reason: Optional[str] = None
    deadline: Optional[datetime] = None


class ClientListItem(BaseModel):
    id: int
    telegram_user_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    status: str
    unread_count: int
    last_message_at: Optional[datetime] = None
    avatar_local_path: Optional[str] = None
    tags: List[TagResponse] = []
    is_archived: bool = False
    deadline: Optional[datetime] = None
    lost_reason: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    message_count: int = 0
    
    class Config:
        from_attributes = True


class ClientDetail(ClientListItem):
    language_code: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    business_connection_id: Optional[str] = None
    messages: List[MessageResponse] = []
    merged_from: Optional[str] = None
    reminders: List["ReminderResponse"] = []
    
    class Config:
        from_attributes = True


class ClientsListResponse(BaseModel):
    items: List[ClientListItem]
    total: int
    page: int
    per_page: int


# ============ Templates ============

class TemplateBase(BaseModel):
    name: str
    language: str
    content: str
    is_auto_reply: bool = False
    is_active: bool = True


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    content: Optional[str] = None
    is_auto_reply: Optional[bool] = None
    is_active: Optional[bool] = None


class TemplateResponse(TemplateBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Settings ============

class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingsResponse(BaseModel):
    portfolio_url: Optional[str] = None
    auto_reply_enabled: bool = True
    social_proof: Optional[str] = None


class AdminResponse(BaseModel):
    id: int
    telegram_user_id: int
    username: Optional[str] = None
    role: str
    
    class Config:
        from_attributes = True


# ============ Search ============

class SearchQuery(BaseModel):
    q: str = Field(..., min_length=1)
    status: Optional[str] = None
    has_unread: Optional[bool] = None
    tag_ids: Optional[List[int]] = None


# ============ Reminders ============

class ReminderCreate(BaseModel):
    client_id: int
    reminder_type: str = Field(..., pattern="^(dm|sticky)$")
    text: str
    remind_at: datetime


class ReminderUpdate(BaseModel):
    text: Optional[str] = None
    remind_at: Optional[datetime] = None
    is_completed: Optional[bool] = None


class ReminderResponse(BaseModel):
    id: int
    client_id: int
    reminder_type: str
    text: str
    remind_at: datetime
    is_completed: bool
    completed_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Merge Clients ============

class MergeClientsRequest(BaseModel):
    source_client_ids: List[int]
    target_client_id: int


# ============ Manual Client Creation ============

class ManualClientCreate(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    source: str = Field(..., pattern="^(whatsapp|instagram|telegram|other)$")
    phone: Optional[str] = None
    notes: Optional[str] = None


# ============ Orders ============

class OrderCreate(BaseModel):
    client_id: int
    service_type: str = Field(..., pattern="^(thumbnail|banner|logo|channel_design|other)$")
    quantity: int = 1
    amount: Optional[int] = None  # in cents
    currency: str = "USD"
    has_ab_test: bool = False
    has_title: bool = False
    has_rush: bool = False
    deadline_type: Optional[str] = Field(None, pattern="^(exact|flexible)$")
    deadline_date: Optional[datetime] = None
    deadline_range: Optional[str] = None
    deadline_custom: Optional[str] = None
    notes: Optional[str] = None


class OrderUpdate(BaseModel):
    service_type: Optional[str] = None
    quantity: Optional[int] = None
    amount: Optional[int] = None
    has_ab_test: Optional[bool] = None
    has_title: Optional[bool] = None
    has_rush: Optional[bool] = None
    deadline_type: Optional[str] = None
    deadline_date: Optional[datetime] = None
    deadline_range: Optional[str] = None
    deadline_custom: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    client_id: int
    service_type: str
    quantity: int
    amount: Optional[float] = None
    currency: str
    has_ab_test: bool
    has_title: bool
    has_rush: bool
    deadline_type: Optional[str] = None
    deadline_date: Optional[datetime] = None
    deadline_range: Optional[str] = None
    deadline_custom: Optional[str] = None
    deadline_calculated: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    source: str = "manual"
    ai_confidence: Optional[float] = None
    todoist_task_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrderClientInfo(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    avatar_local_path: Optional[str] = None
    
    class Config:
        from_attributes = True


class OrderBoardResponse(BaseModel):
    id: int
    client_id: int
    service_type: str
    quantity: int
    amount: Optional[float] = None
    deadline_date: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    source: str = "manual"
    ai_confidence: Optional[float] = None
    created_at: datetime
    client: Optional[OrderClientInfo] = None
    
    class Config:
        from_attributes = True


# ============ Rejection Reasons ============

class RejectionReasonResponse(BaseModel):
    id: int
    code: str
    label: str
    emoji: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============ Conversations ============

class ConversationClientInfo(BaseModel):
    id: int
    telegram_user_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    avatar_local_path: Optional[str] = None
    status: str
    sticky_note: Optional[str] = None
    total_orders: int = 0
    total_spent: float = 0.0
    tags: List[TagResponse] = []


class ConversationCreate(BaseModel):
    client_id: int
    source: Optional[str] = "manual"
    category: Optional[str] = None


class ConversationUpdate(BaseModel):
    status: Optional[str] = None
    category: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejection_custom: Optional[str] = None


class ConversationResponse(BaseModel):
    id: int
    client_id: int
    source: Optional[str] = None
    category: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None
    rejection_custom: Optional[str] = None
    unread_count: int = 0
    auto_reply_sent: bool = False
    owner_replied: bool = False
    started_at: Optional[str] = None
    owner_replied_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    client: Optional[ConversationClientInfo] = None
    orders_count: int = 0
    total_amount: float = 0.0
    
    class Config:
        from_attributes = True


class ConversationMessageResponse(BaseModel):
    id: int
    direction: str
    text: Optional[str] = None
    message_type: str = "text"
    sent_at: Optional[str] = None


class ConversationDetailResponse(ConversationResponse):
    messages: List[ConversationMessageResponse] = []


class ConversationListResponse(BaseModel):
    items: List[ConversationResponse]
    total: int
