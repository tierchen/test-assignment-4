from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aio_pika
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings, load_settings
from app.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(settings.database_url)
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.declare_queue(
            settings.queue_name,
            durable=True,
            arguments={"x-max-priority": settings.queue_max_priority},
        )
        app.state.engine = engine
        app.state.channel = channel
        app.state.queue_name = settings.queue_name
        yield
        await connection.close()
        await engine.dispose()

    app = FastAPI(title="Task Service", version="0.1.0", lifespan=lifespan)
    app.include_router(router, prefix="/api/v1")
    return app
