from pydantic import BaseModel, Field


class ListMeta(BaseModel):
    """Pagination / list envelope (extensible for cursor-based paging later)."""

    total: int = Field(ge=0, description="Total matching rows (before paging).")
    skip: int = Field(ge=0, description="Rows skipped.")
    limit: int = Field(ge=1, le=500, description="Max rows returned.")
