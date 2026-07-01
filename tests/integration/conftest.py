import os
from unittest.mock import AsyncMock, patch

import pytest
from dotenv import load_dotenv
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.infra.db import TaskRepo
from app.infra.models import metadata
from app.routes import get_service, router
from app.service import TaskService

load_dotenv("local/etc/.env.test")
TEST_DB_URL = os.environ["TEST_DATABASE_URL"]


@pytest.fixture
async def engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(engine):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def override_service():
        async with engine.connect() as conn:
            repo = TaskRepo(conn)
            try:
                yield TaskService(repo=repo, channel=AsyncMock(), queue_name="tasks")
            except Exception:
                await repo.rollback()
                raise

    app.dependency_overrides[get_service] = override_service

    with patch("app.service.publish", new=AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
