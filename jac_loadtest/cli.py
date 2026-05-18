# JacMetaImporter must be registered before any jac_scale import.
# jac-scale's microservice modules are compiled Jac; without this the import fails.
from jaclang.meta_importer import JacMetaImporter
import sys

if not any(isinstance(f, JacMetaImporter) for f in sys.meta_path):
    sys.meta_path.insert(0, JacMetaImporter())


def run(args: object) -> None:
    import asyncio
    import time

    from jac_loadtest.config import from_args
    from jac_loadtest.core.har_parser import parse_har
    from jac_loadtest.core.engine import run_all_vus
    from jac_loadtest.core.metrics import MetricsCollector
    from jac_loadtest.output.reporter import render_console

    config = from_args(args)

    if not config.url:
        print("Error: --url is required", file=sys.stderr)
        sys.exit(2)

    if not config.har_file:
        print("Error: har_file positional argument is required", file=sys.stderr)
        sys.exit(2)

    try:
        entries = parse_har(
            config.har_file,
            target_url=config.url,
            include_static=config.include_static,
            login_path=config.login_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    if not entries:
        print(
            "Error: no API entries found in HAR file after filtering. "
            "Use --include-static to include static assets.",
            file=sys.stderr,
        )
        sys.exit(2)

    metrics = MetricsCollector(max_samples=config.max_samples)
    t_start = time.time()

    asyncio.run(run_all_vus(entries, config, metrics))

    duration_s = time.time() - t_start
    stats = metrics.compute_endpoint_stats(duration_s)
    render_console(stats, config)
