"""Multi-process coordinator: splits VUs across worker processes, merges metrics.

Each worker gets its own asyncio event loop and a contiguous slice of VU IDs.
Results are returned via a multiprocessing.Queue and merged into one MetricsCollector.
"""
from __future__ import annotations

import asyncio
import multiprocessing
import multiprocessing.process
import multiprocessing.queues

from jac_loadtest.core.har_parser import HarEntry
from jac_loadtest.core.metrics import MetricsCollector, RequestResult
from jac_loadtest.config import LoadTestConfig
from jac_loadtest.bridge.topology import TopologyRouter
from jac_loadtest.bridge.auth import AuthProvider, AuthenticationError

# Result payload sent from each worker: ("ok", samples) | ("auth_error", msg) | ("error", msg)
WorkerResult = tuple[str, list[RequestResult] | str]


def _worker_fn(
    vu_id_offset: int,
    worker_vus: int,
    entries: list[HarEntry],
    config: LoadTestConfig,
    topology: TopologyRouter | None,
    auth_provider: AuthProvider | None,
    queue: multiprocessing.queues.Queue[WorkerResult],
) -> None:
    """Entry point for each worker process. Must be a module-level function for pickling."""
    import dataclasses
    from jac_loadtest.core.engine import run_all_vus

    worker_config = dataclasses.replace(config, vus=worker_vus)
    metrics = MetricsCollector(max_samples=config.max_samples)
    try:
        asyncio.run(
            run_all_vus(
                entries,
                worker_config,
                metrics,
                topology=topology,
                auth_provider=auth_provider,
                vu_id_offset=vu_id_offset,
            )
        )
        queue.put(("ok", list(metrics._samples)))
    except AuthenticationError as exc:
        queue.put(("auth_error", str(exc)))
    except Exception:
        import traceback
        queue.put(("error", traceback.format_exc()))


def _compute_slices(total_vus: int, workers: int) -> list[tuple[int, int]]:
    """Return [(vu_id_offset, worker_vu_count), ...] distributing VUs as evenly as possible."""
    base = total_vus // workers
    remainder = total_vus % workers
    slices: list[tuple[int, int]] = []
    offset = 0
    for i in range(workers):
        count = base + (1 if i < remainder else 0)
        if count > 0:
            slices.append((offset, count))
            offset += count
    return slices


def run_multiprocess(
    entries: list[HarEntry],
    config: LoadTestConfig,
    topology: TopologyRouter | None,
    auth_provider: AuthProvider | None,
) -> MetricsCollector:
    """Spawn worker processes, collect their samples, and return a merged MetricsCollector.

    Worker count is capped at config.vus so we never spawn idle processes.
    Uses the 'spawn' start method for asyncio compatibility (no fork-inherited event loops).
    """
    workers = min(config.workers, config.vus)
    slices = _compute_slices(config.vus, workers)

    ctx = multiprocessing.get_context("spawn")
    queue: multiprocessing.queues.Queue[WorkerResult] = ctx.Queue()

    processes: list[multiprocessing.process.BaseProcess] = []
    try:
        for vu_id_offset, worker_vus in slices:
            p = ctx.Process(
                target=_worker_fn,
                args=(vu_id_offset, worker_vus, entries, config, topology, auth_provider, queue),
            )
            p.start()
            processes.append(p)

        # Collect exactly one result per worker.
        raw_results: list[WorkerResult] = [queue.get() for _ in processes]

        for p in processes:
            p.join()

    finally:
        # Terminate any workers still alive (e.g. after KeyboardInterrupt).
        for p in processes:
            if p.is_alive():
                p.terminate()

    # Surface the first error found across workers.
    for status, payload in raw_results:
        if status == "auth_error":
            assert isinstance(payload, str)
            raise AuthenticationError(payload)
        if status == "error":
            assert isinstance(payload, str)
            raise RuntimeError(f"Worker process failed: {payload}")

    merged = MetricsCollector(max_samples=config.max_samples)
    for _status, samples in raw_results:
        assert isinstance(samples, list)
        for result in samples:
            merged.record(result)

    return merged
