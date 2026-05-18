"""Unit tests for core/metrics.py — no network, no I/O."""
from __future__ import annotations

import time
import pytest

from jac_loadtest.core.metrics import (
    RequestResult,
    MetricsCollector,
    percentile,
    normalize_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(
    endpoint: str = "POST /walker/search",
    status: int = 200,
    latency_ms: float = 50.0,
    error_type: str | None = None,
    vu_id: int = 0,
    service: str = "monolith",
) -> RequestResult:
    return RequestResult(
        endpoint=endpoint,
        service=service,
        status=status,
        latency_ms=latency_ms,
        bytes_received=100,
        timestamp=time.time(),
        vu_id=vu_id,
        error_type=error_type,
    )


# ---------------------------------------------------------------------------
# percentile()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_percentile_p50():
    assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0


@pytest.mark.unit
def test_percentile_p95_p99():
    data = [float(i) for i in range(1, 101)]  # 1..100
    p95 = percentile(data, 95)
    p99 = percentile(data, 99)
    assert p95 == 95.0
    assert p99 == 99.0


@pytest.mark.unit
def test_percentile_single_element():
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 95) == 42.0
    assert percentile([42.0], 99) == 42.0


@pytest.mark.unit
def test_percentile_empty():
    assert percentile([], 50) == 0.0
    assert percentile([], 99) == 0.0


# ---------------------------------------------------------------------------
# normalize_path()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_normalize_path_integer():
    assert normalize_path("http://host/walker/user/123") == "http://host/walker/user/{id}"


@pytest.mark.unit
def test_normalize_path_uuid_with_hyphens():
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    result = normalize_path(f"http://host/walker/order/{uuid}")
    assert result == "http://host/walker/order/{id}"


@pytest.mark.unit
def test_normalize_path_uuid_no_hyphens():
    uuid = "550e8400e29b41d4a716446655440000"
    result = normalize_path(f"http://host/walker/order/{uuid}")
    assert result == "http://host/walker/order/{id}"


@pytest.mark.unit
def test_normalize_path_unchanged():
    result = normalize_path("http://host/walker/search")
    assert result == "http://host/walker/search"


@pytest.mark.unit
def test_normalize_path_multiple_ids():
    result = normalize_path("http://host/a/123/b/456")
    assert result == "http://host/a/{id}/b/{id}"


# ---------------------------------------------------------------------------
# MetricsCollector — storage behaviour
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_total_count_never_drops():
    collector = MetricsCollector(max_samples=10)
    for _ in range(50):
        collector.record(_result())
    assert collector.total_count == 50
    assert len(collector._samples) == 10  # deque bounded


@pytest.mark.unit
def test_deque_bounded():
    collector = MetricsCollector(max_samples=5)
    for i in range(20):
        collector.record(_result(latency_ms=float(i)))
    assert collector.total_count == 20
    assert len(collector._samples) == 5
    # Oldest entries dropped — only last 5 remain
    latencies = [r.latency_ms for r in collector._samples]
    assert latencies == [15.0, 16.0, 17.0, 18.0, 19.0]


@pytest.mark.unit
def test_stats_snapshot_grows():
    collector = MetricsCollector()
    for _ in range(10):
        collector.record(_result())
    assert len(collector._snapshots) == 0
    collector.flush_snapshot(timestamp=time.time(), duration_seconds=5.0)
    assert len(collector._snapshots) == 1
    collector.flush_snapshot(timestamp=time.time(), duration_seconds=10.0)
    assert len(collector._snapshots) == 2


# ---------------------------------------------------------------------------
# MetricsCollector — compute_endpoint_stats()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_error_breakdown_http():
    collector = MetricsCollector()
    collector.record(_result(status=500, error_type=None))
    stats = collector.compute_endpoint_stats(duration_seconds=1.0)
    assert stats[0].error_breakdown == {"500": 1}


@pytest.mark.unit
def test_error_breakdown_network():
    collector = MetricsCollector()
    collector.record(_result(status=0, error_type="TIMEOUT"))
    stats = collector.compute_endpoint_stats(duration_seconds=1.0)
    assert stats[0].error_breakdown == {"TIMEOUT": 1}


@pytest.mark.unit
def test_success_rate_calculation():
    collector = MetricsCollector()
    for _ in range(9):
        collector.record(_result(status=200))
    collector.record(_result(status=500))
    stats = collector.compute_endpoint_stats(duration_seconds=1.0)
    assert stats[0].success_rate_pct == 90.0


@pytest.mark.unit
def test_error_type_http_vs_network():
    """4xx/5xx have error_type=None; network failures have error_type set."""
    collector = MetricsCollector()
    collector.record(_result(status=404, error_type=None))
    collector.record(_result(status=0, error_type="CONNECTION_REFUSED"))
    stats = collector.compute_endpoint_stats(duration_seconds=1.0)
    breakdown = stats[0].error_breakdown
    assert "404" in breakdown
    assert "CONNECTION_REFUSED" in breakdown
    assert breakdown["404"] == 1
    assert breakdown["CONNECTION_REFUSED"] == 1
