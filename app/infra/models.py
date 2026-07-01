import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain import TaskPriority, TaskStatus


class Base(DeclarativeBase):
    pass


metadata = Base.metadata


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        sa.Index("ix_tasks_status_priority", "status", "priority", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(255))
    description: Mapped[str] = mapped_column(sa.Text)
    priority: Mapped[TaskPriority] = mapped_column(sa.Enum(TaskPriority, name="task_priority"))
    status: Mapped[TaskStatus] = mapped_column(sa.Enum(TaskStatus, name="task_status"))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(sa.Text)
    error: Mapped[str | None] = mapped_column(sa.Text)
