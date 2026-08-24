from ..extensions import db
from .base import _utcnow


class TaskHistory(db.Model):
    __tablename__ = "task_history"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False, index=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    field = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.String(500), nullable=True)
    new_value = db.Column(db.String(500), nullable=True)
    changed_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    task = db.relationship("Task", back_populates="history")
    changed_by = db.relationship("User", foreign_keys=[changed_by_id])
