from fastapi import APIRouter

router = APIRouter(prefix="/items")


@router.get("/")
def list_items():
    return []


@router.post("/")
def create_item():
    return {}
