"""Console (Rich), JSON, and HTML report rendering.

stdout: machine-readable output (json).
stderr: all human-readable output (console table, progress bar, warnings).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jac_loadtest.core.metrics import EndpointStats
    from jac_loadtest.config import LoadTestConfig


def render_console(stats: list[EndpointStats], config: LoadTestConfig) -> None:
    """Print a Rich summary table to stderr."""
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from jac_loadtest.config import parse_duration

    console = Console(stderr=True, highlight=False)

    table = Table(box=box.SIMPLE_HEAVY, show_footer=False)
    table.add_column("Endpoint", style="cyan", no_wrap=True)
    table.add_column("Reqs", justify="right")
    table.add_column("OK%", justify="right")
    table.add_column("p50", justify="right")
    table.add_column("p95", justify="right")
    table.add_column("p99", justify="right")
    table.add_column("RPS", justify="right")
    table.add_column("Errs", justify="right")

    for s in stats:
        table.add_row(
            s.endpoint,
            str(s.total_requests),
            f"{s.success_rate_pct:.1f}",
            f"{s.p50_ms:.0f}ms",
            f"{s.p95_ms:.0f}ms",
            f"{s.p99_ms:.0f}ms",
            f"{s.rps:.1f}",
            str(s.error_count),
        )

    # TOTAL footer row aggregated across all endpoints
    if stats:
        total_reqs = sum(s.total_requests for s in stats)
        total_success = sum(s.success_count for s in stats)
        total_errors = sum(s.error_count for s in stats)
        overall_ok_pct = (total_success / total_reqs * 100.0) if total_reqs else 0.0

        all_latencies: list[float] = []
        for s in stats:
            # Approximate from p50/p95/p99 — real latencies live in MetricsCollector.
            # For the TOTAL row we compute a weighted mean of percentile values.
            all_latencies.extend([s.p50_ms] * s.total_requests)

        from jac_loadtest.core.metrics import percentile as pct
        all_p50 = pct(all_latencies, 50)
        all_p95 = pct(all_latencies, 95)
        all_p99 = pct(all_latencies, 99)
        total_rps = sum(s.rps for s in stats)

        table.add_section()
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{total_reqs}[/bold]",
            f"[bold]{overall_ok_pct:.1f}[/bold]",
            f"[bold]{all_p50:.0f}ms[/bold]",
            f"[bold]{all_p95:.0f}ms[/bold]",
            f"[bold]{all_p99:.0f}ms[/bold]",
            f"[bold]{total_rps:.1f}[/bold]",
            f"[bold]{total_errors}[/bold]",
        )

    console.print(table)

    duration_s = parse_duration(config.duration)
    console.print(
        f"Duration: {duration_s:.0f}s   VUs: {config.vus}   "
        f"Ramp-up: {config.ramp_up}   Mode: {config.mode}"
    )


def render_json(stats: list[EndpointStats], config: LoadTestConfig) -> str:
    raise NotImplementedError("JSON reporter is implemented in Phase 5.")


def render_html(stats: list[EndpointStats], config: LoadTestConfig) -> str:
    raise NotImplementedError("HTML reporter is implemented in Phase 5.")
