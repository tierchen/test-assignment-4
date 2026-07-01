from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.domain import Task, TaskPriority, TaskStatus
from app.infra.models import TaskModel


class TaskRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    @staticmethod
    def _to_task(row: Any) -> Task:
        return Task(
            id=row.id,
            name=row.name,
            description=row.description,
            priority=TaskPriority(row.priority),
            status=TaskStatus(row.status),
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            result=row.result,
            error=row.error,
        )

    async def create(self, task: Task) -> Task:
        row = (
            await self._conn.execute(
                sa.insert(TaskModel)
                .values(
                    id=task.id,
                    name=task.name,
                    description=task.description,
                    priority=task.priority,
                    status=task.status,
                    created_at=task.created_at,
                )
                .returning("*")
            )
        ).fetchone()
        if row is None:
            raise RuntimeError("Task was not created")
        return self._to_task(row)

    async def get(self, task_id: UUID) -> Task | None:
        row = (await self._conn.execute(sa.select(TaskModel).where(TaskModel.id == task_id))).fetchone()
        return self._to_task(row) if row else None

    async def list(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        query = sa.select(TaskModel)
        query_total = sa.select(sa.func.count()).select_from(TaskModel)

        if status:
            query = query.where(TaskModel.status == status)
            query_total = query_total.where(TaskModel.status == status)
        if priority:
            query = query.where(TaskModel.priority == priority)
            query_total = query_total.where(TaskModel.priority == priority)

        total = (await self._conn.execute(query_total)).scalar_one()
        rows = (
            await self._conn.execute(query.order_by(TaskModel.created_at.desc()).offset(offset).limit(limit))
        ).all()

        return [self._to_task(r) for r in rows], total

    # Оптимистичная блокировка: меняем статус только если его не успели сменить
    async def cancel_pending(self, task_id: UUID, completed_at: datetime) -> Task | None:
        row = (
            await self._conn.execute(
                sa.update(TaskModel)
                .where(
                    TaskModel.id == task_id,
                    TaskModel.status.in_([TaskStatus.NEW, TaskStatus.PENDING]),
                )
                .values(status=TaskStatus.CANCELLED, completed_at=completed_at)
                .returning("*")
            )
        ).fetchone()
        return self._to_task(row) if row else None

    async def mark_pending(self, task_id: UUID) -> Task | None:
        row = (
            await self._conn.execute(
                sa.update(TaskModel)
                .where(TaskModel.id == task_id, TaskModel.status == TaskStatus.NEW)
                .values(status=TaskStatus.PENDING)
                .returning("*")
            )
        ).fetchone()
        return self._to_task(row) if row else None

    async def start_pending(self, task_id: UUID, started_at: datetime) -> Task | None:
        row = (
            await self._conn.execute(
                sa.update(TaskModel)
                .where(
                    TaskModel.id == task_id,
                    TaskModel.status.in_([TaskStatus.NEW, TaskStatus.PENDING]),
                )
                .values(status=TaskStatus.IN_PROGRESS, started_at=started_at)
                .returning("*")
            )
        ).fetchone()
        return self._to_task(row) if row else None

    async def complete_in_progress(
        self,
        task_id: UUID,
        completed_at: datetime,
        result: str,
    ) -> Task | None:
        row = (
            await self._conn.execute(
                sa.update(TaskModel)
                .where(TaskModel.id == task_id, TaskModel.status == TaskStatus.IN_PROGRESS)
                .values(status=TaskStatus.COMPLETED, completed_at=completed_at, result=result)
                .returning("*")
            )
        ).fetchone()
        return self._to_task(row) if row else None

    async def fail_in_progress(
        self,
        task_id: UUID,
        completed_at: datetime,
        error: str,
    ) -> Task | None:
        row = (
            await self._conn.execute(
                sa.update(TaskModel)
                .where(TaskModel.id == task_id, TaskModel.status == TaskStatus.IN_PROGRESS)
                .values(status=TaskStatus.FAILED, completed_at=completed_at, error=error)
                .returning("*")
            )
        ).fetchone()
        return self._to_task(row) if row else None

    # TODO
    async def commit(self) -> None:
        await self._conn.commit()

    async def rollback(self) -> None:
        await self._conn.rollback()
