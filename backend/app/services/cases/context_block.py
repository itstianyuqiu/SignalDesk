"""Build a deterministic case context block for the Copilot workflow."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case, CaseActionItem


async def build_case_context_block(
    session: AsyncSession,
    *,
    case_id: UUID,
) -> str | None:
    row = await session.get(Case, case_id)
    if row is None:
        return None
    stmt = (
        select(CaseActionItem)
        .where(CaseActionItem.case_id == case_id)
        .order_by(CaseActionItem.created_at.asc())
    )
    items = list((await session.execute(stmt)).scalars().all())
    lines = [
        f"Active case: {row.title} ({row.case_number})",
        f"Workflow status: {row.status}; priority: {row.priority}.",
    ]
    if row.category:
        lines.append(f"Category: {row.category}.")
    if row.summary.strip():
        lines.append(f"Case summary: {row.summary.strip()}")
    open_items = [i for i in items if i.status != "done"]
    if open_items:
        lines.append("Outstanding action items:")
        for it in open_items[:12]:
            lines.append(f"- [{it.status}] {it.title}")
    lines.append(
        "Stay aligned with this case when suggesting next steps; cite the knowledge base via tools when needed.",
    )
    return "\n".join(lines)
