import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import aio_pika
import orjson
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings
from app.domain import TaskPriority
from app.infra.db import TaskRepo

logger = logging.getLogger(__name__)

_PRIORITY = {TaskPriority.LOW: 1, TaskPriority.MEDIUM: 5, TaskPriority.HIGH: 10}
_DURATION = {TaskPriority.HIGH: 2.0, TaskPriority.MEDIUM: 5.0, TaskPriority.LOW: 10.0}


async def publish(
    channel: aio_pika.Channel,
    queue_name: str,
    task_id: UUID,
    priority: TaskPriority,
) -> None:
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=orjson.dumps({"task_id": str(task_id)}),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            priority=_PRIORITY[priority],
        ),
        routing_key=queue_name,
    )


async def fail(engine: AsyncEngine, task_id: UUID, error: str) -> None:
    async with engine.connect() as conn:
        repo = TaskRepo(conn)
        await repo.fail_in_progress(task_id, datetime.now(UTC), error)
        await conn.commit()


async def run_worker(settings: Settings) -> None:
    engine = create_async_engine(settings.database_url)
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=settings.worker_concurrency)
    queue = await channel.declare_queue(
        settings.queue_name,
        durable=True,
        arguments={"x-max-priority": settings.queue_max_priority},
    )

    async def handle(message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            data = orjson.loads(message.body)
            task_id = UUID(data["task_id"])
            try:
                await process(engine, task_id)
            except Exception as e:
                logger.error("task %s failed", task_id, exc_info=e)
                await fail(engine, task_id, str(e))

    await queue.consume(handle)
    logger.info("worker listening on '%s'", settings.queue_name)

    try:
        await asyncio.Future()
    finally:
        await connection.close()
        await engine.dispose()


async def process(engine: AsyncEngine, task_id: UUID) -> None:
    async with engine.connect() as conn:
        repo = TaskRepo(conn)
        task = await repo.start_pending(task_id, datetime.now(UTC))
        if task is None:
            return
        await conn.commit()

    duration = _DURATION[task.priority]
    await asyncio.sleep(duration)

    async with engine.connect() as conn:
        repo = TaskRepo(conn)
        result = f"Task '{task.name}' completed in {duration:.0f}s"
        await repo.complete_in_progress(task.id, datetime.now(UTC), result)
        await conn.commit()
