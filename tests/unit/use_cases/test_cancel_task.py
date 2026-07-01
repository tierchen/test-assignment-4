import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.domain import CancelError, Task, TaskNotFoundError, TaskPriority, TaskStatus
from app.service import TaskService


def make_task(status: TaskStatus) -> Task:
    return Task(
        id=uuid.uuid4(),
        name="T",
        description="",
        priority=TaskPriority.MEDIUM,
        status=status,
        created_at=datetime.now(UTC),
    )


class TestCancel:
    @pytest.fixture
    def svc(self, repo) -> TaskService:
        return TaskService(repo=repo, channel=AsyncMock(), queue_name="tasks")

    async def test_cancel__pending(self, svc, repo):
        task = make_task(TaskStatus.PENDING)
        await repo.create(task)

        result = await svc.cancel(task.id)

        assert result.status == TaskStatus.CANCELLED
        assert result.completed_at is not None

    async def test_cancel__not_found(self, svc):
        with pytest.raises(TaskNotFoundError):
            await svc.cancel(uuid.uuid4())

    @pytest.mark.parametrize(
        "status",
        [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED],
    )
    async def test_cancel__non_pending(self, svc, repo, status):
        task = make_task(status)
        await repo.create(task)

        with pytest.raises(CancelError):
            await svc.cancel(task.id)
