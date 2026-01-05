"""API routes module."""
from fastapi import APIRouter

from app.api.routes_auth import router as auth_router
from app.api.routes_clients import router as clients_router
from app.api.routes_conversations import router as conversations_router
from app.api.routes_messages import router as messages_router
from app.api.routes_templates import router as templates_router
from app.api.routes_settings import router as settings_router
from app.api.routes_tags import router as tags_router
from app.api.routes_reminders import router as reminders_router
from app.api.routes_orders import router as orders_router
from app.api.routes_export import router as export_router
from app.api.routes_todoist import router as todoist_router
from app.api.routes_import import router as import_router
from app.api.routes_backup import router as backup_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(clients_router, prefix="/clients", tags=["clients"])
api_router.include_router(conversations_router, tags=["conversations"])
api_router.include_router(messages_router, prefix="/messages", tags=["messages"])
api_router.include_router(templates_router, prefix="/templates", tags=["templates"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(tags_router, prefix="/tags", tags=["tags"])
api_router.include_router(reminders_router, prefix="/reminders", tags=["reminders"])
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
api_router.include_router(export_router)
api_router.include_router(todoist_router, prefix="/todoist", tags=["todoist"])
api_router.include_router(import_router, prefix="/import", tags=["import"])
api_router.include_router(backup_router)
