"""API 路由聚合"""
from fastapi import APIRouter

from app.api.v1 import auth, chat, knowledge, sessions, files, votes

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["会话"])
api_router.include_router(files.router, prefix="/files", tags=["文件"])
api_router.include_router(votes.router, tags=["投票"])
api_router.include_router(knowledge.router, tags=["知识库"])

__all__ = ["api_router"]
