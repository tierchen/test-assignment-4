import uuid
from datetime import UTC, datetime

import aio_pika

from app.domain import CancelError, Task, TaskNotFoundError, TaskPriority, TaskStatus
from app.infra.db import TaskRepo
from app.infra.queue import publish


class TaskService:
    def __init__(self, repo: TaskRepo, channel: aio_pika.Channel, queue_name: str) -> None:
        self._repo = repo
        self._channel = channel
        self._queue_name = queue_name

    async def create(self, name: str, description: str, priority: TaskPriority) -> Task:
        task = Task(
            id=uuid.uuid4(),
            name=name,
            description=description,
            priority=priority,
            status=TaskStatus.NEW,
            created_at=datetime.now(UTC),
        )
        task = await self._repo.create(task)
        await self._repo.commit()

        await publish(self._channel, self._queue_name, task.id, task.priority)

        queued = await self._repo.mark_pending(task.id)
        await self._repo.commit()
        return queued or await self._repo.get(task.id) or task

    async def get(self, task_id: uuid.UUID) -> Task:
        task = await self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def list(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        return await self._repo.list(status, priority, offset, limit)

    async def cancel(self, task_id: uuid.UUID) -> Task:
        task = await self._repo.cancel_pending(task_id, datetime.now(UTC))
        if task is not None:
            await self._repo.commit()
            return task
        existing = await self._repo.get(task_id)
        if existing is None:
            raise TaskNotFoundError(task_id)
        raise CancelError(f"Cannot cancel task in status {existing.status}")
