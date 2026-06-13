"""Run CPU work in child processes; propagate worker death as exceptions."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def run_in_parallel(
    fn: Callable[[T], None],
    jobs: list[T],
    *,
    workers: int,
    on_done: Callable[[], None] | None = None,
) -> None:
    """Run fn on each job; call on_done after each job finishes (any order)."""
    if not jobs:
        return
    if workers <= 1:
        for job in jobs:
            fn(job)
            if on_done:
                on_done()
        return

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fn, job) for job in jobs]
        for future in as_completed(futures):
            future.result()
            if on_done:
                on_done()


def map_in_parallel(
    fn: Callable[[T], R],
    jobs: list[T],
    *,
    workers: int,
) -> list[R]:
    """Run fn on each job; return results in input order."""
    if not jobs:
        return []
    if workers <= 1:
        return [fn(job) for job in jobs]

    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(fn, jobs))
