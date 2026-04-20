from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case


async def user_can_access_case(
    session: AsyncSession,
    *,
    case: Case,
    user_id: UUID,
) -> bool:
    if case.opened_by == user_id:
        return True
    if case.assignee_id == user_id:
        return True
    return False
