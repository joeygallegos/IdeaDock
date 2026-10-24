from app.api.routes import router
from app.api.boards import router as boards_router

router.include_router(boards_router)

__all__ = ["router"]
