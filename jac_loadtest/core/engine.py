"""asyncio VU pool: ramp-up, duration/iteration control, graceful shutdown.

core/ has zero knowledge of jac-scale internals.
"""
from __future__ import annotations

import asyncio
import signal
import sys
from typing import TYPE_CHECKING

import aiohttp

from jac_loadtest.config import parse_duration
from jac_loadtest.core.metrics import RequestResult, normalize_path

if TYPE_CHECKING:
    from jac_loadtest.core.har_parser import HarEntry
    from jac_loadtest.core.metrics import MetricsCollector
    from jac_loadtest.config import LoadTestConfig


async def run_all_vus(
    entries: list[HarEntry],
    config: LoadTestConfig,
    metrics: MetricsCollector,
    topology: object | None = None,
    auth_provider: object | None = None,
) -> None:
    """Spawn N virtual user coroutines and run until duration/iterations/stop signal."""
    stop_requested = asyncio.Event()
    loop = asyncio.get_event_loop()

    original_sigint = signal.getsignal(signal.SIGINT)

    def _on_second_sigint(sig: int, frame: object) -> None:
        sys.exit(130)

    def _on_first_sigint(sig: int, frame: object) -> None:
        stop_requested.set()
        signal.signal(signal.SIGINT, _on_second_sigint)

    signal.signal(signal.SIGINT, _on_first_sigint)

    ramp_up_seconds = parse_duration(config.ramp_up)

    tasks = [
        asyncio.create_task(
            _run_vu(
                vu_id=i,
                delay=(i / config.vus) * ramp_up_seconds if config.vus > 1 else 0.0,
                entries=entries,
                config=config,
                metrics=metrics,
                stop_requested=stop_requested,
                loop=loop,
            )
        )
        for i in range(config.vus)
    ]

    try:
        await asyncio.gather(*tasks)
    finally:
        signal.signal(signal.SIGINT, original_sigint)


async def _run_vu(
    vu_id: int,
    delay: float,
    entries: list[HarEntry],
    config: LoadTestConfig,
    metrics: MetricsCollector,
    stop_requested: asyncio.Event,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Single virtual user: wait ramp delay, then replay HAR entries repeatedly."""
    if delay > 0:
        await asyncio.sleep(delay)

    timeout = aiohttp.ClientTimeout(total=parse_duration(config.timeout))
    duration_seconds = parse_duration(config.duration)
    t_start = loop.time()
    iteration = 0

    async with aiohttp.ClientSession(timeout=timeout) as session:
        while not stop_requested.is_set():
            if loop.time() - t_start >= duration_seconds:
                break
            if config.iterations is not None and iteration >= config.iterations:
                break

            for entry in entries:
                if stop_requested.is_set():
                    break
                result = await _send_request(
                    session=session,
                    entry=entry,
                    vu_id=vu_id,
                    config=config,
                    loop=loop,
                )
                metrics.record(result)

            iteration += 1


async def _send_request(
    session: aiohttp.ClientSession,
    entry: HarEntry,
    vu_id: int,
    config: LoadTestConfig,
    loop: asyncio.AbstractEventLoop,
) -> RequestResult:
    """Send one HTTP request and return a RequestResult."""
    headers = dict(entry.headers)
    t0 = loop.time()

    try:
        async with session.request(
            method=entry.method,
            url=entry.url,
            headers=headers,
            data=entry.body,
            allow_redirects=False,
        ) as resp:
            body = await resp.read()
            latency_ms = (loop.time() - t0) * 1000
            return RequestResult(
                endpoint=normalize_path(entry.url),
                service="monolith",
                status=resp.status,
                latency_ms=latency_ms,
                bytes_received=len(body),
                timestamp=t0,
                vu_id=vu_id,
                error_type=None,
            )

    except asyncio.TimeoutError:
        return RequestResult(
            endpoint=normalize_path(entry.url),
            service="monolith",
            status=0,
            latency_ms=parse_duration(config.timeout) * 1000,
            bytes_received=0,
            timestamp=t0,
            vu_id=vu_id,
            error_type="TIMEOUT",
        )

    except aiohttp.ClientConnectorError:
        return RequestResult(
            endpoint=normalize_path(entry.url),
            service="monolith",
            status=0,
            latency_ms=0.0,
            bytes_received=0,
            timestamp=t0,
            vu_id=vu_id,
            error_type="CONNECTION_REFUSED",
        )
