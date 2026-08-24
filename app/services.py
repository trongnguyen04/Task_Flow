from datetime import datetime

from markupsafe import escape

from .extensions import db
from .models import Notification


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def notify_assignment(task):
    if not task.assignee_id:
        return

    db.session.add(
        Notification(
            user_id=task.assignee_id,
            task_id=task.id,
            message=f"Bạn được giao công việc: {escape(task.title)}",
        )
    )
