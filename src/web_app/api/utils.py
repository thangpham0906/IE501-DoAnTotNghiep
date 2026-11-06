"""Hỗ trợ theo dõi client disconnect và ủy quyền thực thi sang InferenceRunner."""

import asyncio
from collections.abc import Callable
from typing import TypeVar
from fastapi import Request

from src.web_app.services.inference_runner import InferenceRunner, RunnerResult

T = TypeVar("T")


async def execute_with_disconnect_monitor(
    request: Request,
    runner: InferenceRunner,
    func: Callable[[], T],
    *,
    task_type: str,
    request_id: str,
    model_id: str | None = None,
    execution_timeout_sec: float | None = None,
) -> RunnerResult[T]:
    """Chạy tác vụ suy luận qua runner và chủ động giám sát client disconnect."""
    runner_task = asyncio.create_task(
        runner.run(
            func,
            task_type=task_type,
            request_id=request_id,
            model_id=model_id,
            execution_timeout_sec=execution_timeout_sec,
        )
    )

    async def watch_disconnect() -> None:
        try:
            while not runner_task.done():
                if await request.is_disconnected():
                    runner_task.cancel()
                    break
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    watch_task = asyncio.create_task(watch_disconnect())

    try:
        return await runner_task
    except asyncio.CancelledError:
        if not runner_task.done():
            runner_task.cancel()
            try:
                await runner_task
            except (asyncio.CancelledError, Exception):
                pass
        raise
    finally:
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass
