from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID

from aio_pika.exceptions import AMQPException, ChannelInvalidStateError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.domain import CancelError, TaskNotFoundError, TaskPriority, TaskStatus
from app.infra.db import TaskRepo
from app.service import TaskService


class CreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result: str | None
    error: str | None


class TaskList(BaseModel):
    items: list[TaskResponse]
    total: int
    offset: int
    limit: int


class TaskStatusResponse(BaseModel):
    id: UUID
    status: TaskStatus


async def get_service(request: Request) -> AsyncGenerator[TaskService]:
    async with request.app.state.engine.connect() as conn:
        repo = TaskRepo(conn)
        try:
            yield TaskService(
                repo=repo,
                channel=request.app.state.channel,
                queue_name=request.app.state.queue_name,
            )
        except Exception:
            await repo.rollback()
            raise


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Create task")
async def create_task(body: CreateRequest, service: TaskService = Depends(get_service)) -> TaskResponse:
    try:
        task = await service.create(body.name, body.description, body.priority)
    except (AMQPException, ChannelInvalidStateError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue is unavailable",
        ) from None
    return TaskResponse.model_validate(task)


@router.get("", response_model=TaskList, summary="List tasks")
async def list_tasks(
    service: TaskService = Depends(get_service),
    task_status: TaskStatus | None = Query(None, alias="status"),
    priority: TaskPriority | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TaskList:
    items, total = await service.list(task_status, priority, offset, limit)
    return TaskList(items=[TaskResponse.model_validate(t) for t in items], total=total, offset=offset, limit=limit)


@router.get("/{task_id}", response_model=TaskResponse, summary="Get task")
async def get_task(task_id: UUID, service: TaskService = Depends(get_service)) -> TaskResponse:
    try:
        task = await service.get(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from None
    return TaskResponse.model_validate(task)


@router.get("/{task_id}/status", response_model=TaskStatusResponse, summary="Get task status")
async def get_task_status(task_id: UUID, service: TaskService = Depends(get_service)) -> TaskStatusResponse:
    try:
        task = await service.get(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from None
    return TaskStatusResponse(id=task.id, status=task.status)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel task")
async def cancel_task(task_id: UUID, service: TaskService = Depends(get_service)) -> None:
    try:
        await service.cancel(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from None
    except CancelError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None
