from datetime import datetime
from uuid import UUID

from app.domain import Task, TaskPriority, TaskStatus


class FakeRepo:
    def __init__(self) -> None:
        self._store: dict[UUID, Task] = {}

    async def create(self, task: Task) -> Task:
        self._store[task.id] = task
        return task

    async def get(self, task_id: UUID) -> Task | None:
        return self._store.get(task_id)

    async def list(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        items = list(self._store.values())
        if status:
            items = [t for t in items if t.status == status]
        if priority:
            items = [t for t in items if t.priority == priority]
        return items[offset : offset + limit], len(items)

    async def cancel_pending(self, task_id: UUID, completed_at: datetime) -> Task | None:
        task = self._store.get(task_id)
        if task is None or task.status not in (TaskStatus.NEW, TaskStatus.PENDING):
            return None
        task.status = TaskStatus.CANCELLED
        task.completed_at = completed_at
        return task

    async def mark_pending(self, task_id: UUID) -> Task | None:
        task = self._store.get(task_id)
        if task is None or task.status != TaskStatus.NEW:
            return None
        task.status = TaskStatus.PENDING
        return task

    # TODO
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass
