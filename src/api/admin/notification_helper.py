from sqlalchemy.ext.asyncio import AsyncSession

from src.db.admin_models import Notification


async def create_notification(
    session: AsyncSession,
    *,
    title: str,
    message: str,
    link: str | None = None,
    icon: str | None = None,
) -> None:
    """Create an in-app notification.

    The caller is responsible for committing the transaction.
    """
    notification = Notification(
        title=title,
        message=message,
        link=link,
        icon=icon,
    )
    session.add(notification)
