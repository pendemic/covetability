from fastapi import APIRouter, Depends

from app.api.admin.aggregates import router as aggregates_router
from app.api.admin.deps import require_admin
from app.api.admin.ingestion import router as ingestion_router
from app.api.admin.labeling import router as labeling_router
from app.api.admin.review import router as review_router

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
router.include_router(aggregates_router)
router.include_router(ingestion_router)
router.include_router(labeling_router)
router.include_router(review_router)
