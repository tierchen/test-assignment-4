from unittest.mock import AsyncMock, patch

import pytest

from app.domain import TaskPriority, TaskStatus
from app.service import TaskService


class TestCreate:
    @pytest.fixture
    def svc(self, repo) -> TaskService:
        return TaskService(repo=repo, channel=AsyncMock(), queue_name="tasks")

    async def test_create__pending_status(self, svc):
        with patch("app.service.publish", new=AsyncMock()):
            task = await svc.create("Test", "desc", TaskPriority.HIGH)

        assert task.name == "Test"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.HIGH
        assert task.created_at is not None

    async def test_create__published(self, svc):
        with patch("app.service.publish", new=AsyncMock()) as mock_pub:
            task = await svc.create("Test", "", TaskPriority.LOW)

        args = mock_pub.call_args[0]
        assert args[2] == task.id
        assert args[3] == TaskPriority.LOW

    async def test_create__persisted(self, svc, repo):
        with patch("app.service.publish", new=AsyncMock()):
            task = await svc.create("Test", "", TaskPriority.MEDIUM)

        stored = await repo.get(task.id)
        assert stored is not None
        assert stored.status == TaskStatus.PENDING
