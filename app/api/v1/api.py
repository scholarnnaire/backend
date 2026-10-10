from fastapi import APIRouter
from app.api.v1.endpoints import admin, user, analytics, scholarpedia, team, tournaments, arena, competition, payment

api_router = APIRouter()
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(scholarpedia.router, prefix="/scholarpedia", tags=["scholarpedia"])
api_router.include_router(team.router, prefix="/team", tags=["team"])
api_router.include_router(tournaments.router, prefix="/tournaments", tags=["tournaments"])
api_router.include_router(arena.router, prefix="/arena", tags=["arena"])
api_router.include_router(competition.router, prefix="/competition", tags=["competition"])
api_router.include_router(payment.router, prefix="/payment", tags=["payment"])
