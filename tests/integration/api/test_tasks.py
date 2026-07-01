from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain import TaskStatus
from app.infra.models import TaskModel


async def _set_status(engine: AsyncEngine, task_id: UUID, status: TaskStatus) -> None:
    async with engine.connect() as conn:
        await conn.execute(
            sa.update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(status=status, completed_at=datetime.now(UTC))
        )
        await conn.commit()


class TestCreate:
    async def test_create__ok(self, client: AsyncClient):
        r = await client.post("/api/v1/tasks", json={"name": "My task", "priority": "HIGH"})

        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "My task"
        assert data["status"] == "PENDING"
        assert data["priority"] == "HIGH"
        assert data["id"] is not None

    async def test_create__persisted(self, client: AsyncClient, engine: AsyncEngine):
        r = await client.post("/api/v1/tasks", json={"name": "Persisted", "priority": "LOW"})

        task_id = UUID(r.json()["id"])
        async with engine.connect() as conn:
            row = (
                await conn.execute(sa.select(TaskModel).where(TaskModel.id == task_id))
            ).fetchone()

        assert row is not None
        assert row.name == "Persisted"
        assert row.status == TaskStatus.PENDING
        assert row.priority == "LOW"

    async def test_create__default_priority(self, client: AsyncClient):
        r = await client.post("/api/v1/tasks", json={"name": "T"})

        assert r.status_code == 201
        assert r.json()["priority"] == "MEDIUM"

    async def test_create__empty_name_invalid(self, client: AsyncClient):
        r = await client.post("/api/v1/tasks", json={"name": ""})

        assert r.status_code == 422


class TestGet:
    async def test_get__ok(self, client: AsyncClient):
        created = (await client.post("/api/v1/tasks", json={"name": "T"})).json()

        r = await client.get(f"/api/v1/tasks/{created['id']}")

        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    async def test_get__not_found(self, client: AsyncClient):
        r = await client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000")

        assert r.status_code == 404


class TestList:
    async def test_list__ok(self, client: AsyncClient):
        await client.post("/api/v1/tasks", json={"name": "A"})
        await client.post("/api/v1/tasks", json={"name": "B"})

        r = await client.get("/api/v1/tasks")

        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list__filter_by_status(self, client: AsyncClient):
        await client.post("/api/v1/tasks", json={"name": "A"})

        r = await client.get("/api/v1/tasks", params={"status": "COMPLETED"})

        assert r.json()["total"] == 0

    async def test_list__filter_by_priority(self, client: AsyncClient):
        await client.post("/api/v1/tasks", json={"name": "A", "priority": "HIGH"})
        await client.post("/api/v1/tasks", json={"name": "B", "priority": "LOW"})

        r = await client.get("/api/v1/tasks", params={"priority": "HIGH"})

        assert r.json()["total"] == 1

    async def test_list__pagination(self, client: AsyncClient):
        for i in range(5):
            await client.post("/api/v1/tasks", json={"name": f"T{i}"})

        r = await client.get("/api/v1/tasks", params={"offset": 2, "limit": 2})

        data = r.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2


class TestCancel:
    async def test_cancel__ok(self, client: AsyncClient):
        created = (await client.post("/api/v1/tasks", json={"name": "T"})).json()

        r = await client.delete(f"/api/v1/tasks/{created['id']}")

        assert r.status_code == 204

    async def test_cancel__not_found(self, client: AsyncClient):
        r = await client.delete("/api/v1/tasks/00000000-0000-0000-0000-000000000000")

        assert r.status_code == 404

    async def test_cancel__completed_conflict(self, client: AsyncClient, engine: AsyncEngine):
        created = (await client.post("/api/v1/tasks", json={"name": "T"})).json()
        await _set_status(engine, UUID(created["id"]), TaskStatus.COMPLETED)

        r = await client.delete(f"/api/v1/tasks/{created['id']}")

        assert r.status_code == 409
