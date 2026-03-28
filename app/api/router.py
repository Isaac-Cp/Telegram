from fastapi import APIRouter

from app.api.routes import contacts, conversations, dashboard, health

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

