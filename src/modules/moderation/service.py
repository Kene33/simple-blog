from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import AppError
from src.db.models import Report, User
from src.modules.comments.service import get_comment
from src.modules.moderation.schemas import ReportCreateRequest
from src.modules.posts.service import get_post


async def create_report(session: AsyncSession, reporter: User, payload: ReportCreateRequest) -> Report:
    if payload.post_id is not None:
        await get_post(session, payload.post_id)
    else:
        await get_comment(session, payload.comment_id)
    target_filter = Report.post_id == payload.post_id if payload.post_id is not None else Report.comment_id == payload.comment_id
    duplicate = await session.scalar(select(Report.id).where(Report.reporter_id == reporter.id, Report.status == "open", target_filter))
    if duplicate is not None:
        raise AppError("RESOURCE_CONFLICT", "An open report already exists for this target", 409)
    report = Report(reporter_id=reporter.id, post_id=payload.post_id, comment_id=payload.comment_id, reason=payload.reason, details=payload.details)
    session.add(report)
    await session.flush()
    return report
