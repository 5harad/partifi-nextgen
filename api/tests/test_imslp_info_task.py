import asyncio
import threading
import time

import pytest

from app.routers.v1 import _discard_imslp_lookup_task, _drain_imslp_lookup_task
from app.services.imslp import ImslpLookupCancelled


def _immediate_cancel(_cancel: threading.Event) -> None:
    raise ImslpLookupCancelled()


def _delayed_cancel(cancel: threading.Event) -> None:
    while not cancel.is_set():
        time.sleep(0.01)
    raise ImslpLookupCancelled()


@pytest.mark.parametrize("lookup", [_immediate_cancel, _delayed_cancel])
def test_drain_imslp_lookup_task_consumes_cancelled_lookup(lookup) -> None:
    async def run() -> None:
        cancel = threading.Event()
        task = asyncio.create_task(asyncio.to_thread(lookup, cancel))
        cancel.set()
        await _drain_imslp_lookup_task(task, cancel=cancel, timeout=5.0)
        assert task.done()

    asyncio.run(run())


def test_discard_imslp_lookup_task_consumes_orphaned_cancel() -> None:
    async def run() -> None:
        def slow_cancel() -> None:
            time.sleep(0.05)
            raise ImslpLookupCancelled()

        task = asyncio.create_task(asyncio.to_thread(slow_cancel))
        task.add_done_callback(_discard_imslp_lookup_task)
        await asyncio.sleep(0.2)
        assert task.done()
        assert isinstance(task.exception(), ImslpLookupCancelled)

    asyncio.run(run())


def test_drain_imslp_lookup_task_consumes_timeout_without_cancelling() -> None:
    async def run() -> None:
        def slow_timeout(_cancel: threading.Event) -> None:
            time.sleep(0.05)
            raise TimeoutError("IMSLP lookup timed out")

        cancel = threading.Event()
        task = asyncio.create_task(asyncio.to_thread(slow_timeout, cancel))
        await _drain_imslp_lookup_task(task, timeout=5.0)
        assert task.done()
        assert not cancel.is_set()

    asyncio.run(run())
