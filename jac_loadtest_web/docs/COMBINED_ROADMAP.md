# jac-loadtest Combined Roadmap

A unified delivery plan covering both `jac-loadtest-cli` (the engine) and `jac-loadtest-web`
(the visual frontend). Each phase lists what must be built at the CLI level and what must be
built at the web level, in dependency order.

---

## Architecture Principle

The CLI package (`jac_loadtest_cli`) is the engine — it owns all load generation, metric
collection, auth, topology routing, and report rendering. The web app is a shell that
configures the engine, invokes it via `sv` walkers, and visualises its output. **The engine
is never rewritten; it is only extended.**

```
Browser (cl codespace — Vite/React)        ←  web phases
  ↕ HTTP walker calls (jac-client fullstack)
jac-loadtest sv walkers (sv codespace)     ←  web phases (thin adapters)
  ↓ imports as Python module
jac-loadtest engine (jac_loadtest_cli)     ←  CLI phases
  ↓ extended by
Protocol Adapters                          ←  CLI phases (per protocol)
```

---

## Phase Status Overview

| Phase | Name | CLI | Web |
|-------|------|-----|-----|
| 0 | CLI Foundation | ✓ Done | — |
| 1 | CLI MVP | ✓ Done | — |
| 2 | CLI Auth + Think Time | ✓ Done | — |
| 3 | CLI Microservice Mode | ✓ Done | — |
| 4 | Production Hardening | In progress | — |
| 5 | Reporting & Polish | Mostly done | — |
| 6 | Web MVP | Minor extensions | Full UI shell |
| 7 | GraphQL & WebSocket | Engine adapters | Protocol UI |
| 8 | Advanced Personas | Core engine changes | Advanced persona UI |
| 9 | AI Flow Generation | None | LLM integration |
| 10 | gRPC & Databases | Protocol adapters | Schema editors |
| 11 | Distributed Testing | `--worker-nodes` flag | Worker management UI |
| 12 | Release & Ecosystem | PyPI + jac-scale | Docker + CI + public launch |

---

## Phase 0 — CLI Foundation ✓

> Repo skeleton and import tree wired before any logic is written.

### CLI
- [x] `jac_loadtest_cli/` package with `core/`, `bridge/`, `output/` layout
- [x] `jac.toml` with dependencies; plugin registered via `[entrypoints.jac]`
- [x] `plugin.jac` — `@registry.command(...)` entry point; `jac loadtest --help` works
- [x] Empty module stubs; full import tree resolves from day one
- [x] `tests/` directory with `tests/fixtures/` and JAC test blocks

### Web
None — CLI must be functional before web development begins.

**Exit criterion:** `jac loadtest --help` prints usage. ✓

---

## Phase 1 — CLI MVP (HAR replay + console report) ✓

> First working end-to-end path. No auth, no microservices.

### CLI
- [x] `core/har_parser.jac` — parse HAR 1.2, filter non-API entries, URL rewrite
- [x] `core/engine.jac` — asyncio VU coroutines, duration cap, `aiohttp.ClientSession`
- [x] `core/metrics.jac` — `RequestResult`, latency collection, p50/p95/p99
- [x] `output/reporter.jac` — Rich console table (per-endpoint rows + summary footer)
- [x] `config.jac` — `LoadTestConfig` dataclass + `parse_duration()`
- [x] `--url`, `--vus`, `--duration`, `--timeout` CLI flags
- [x] `tests/unit/test_har_parser.jac` (47 tests), `tests/unit/test_metrics.jac` (21 tests)
- [x] GitHub Actions CI

### Web
None — web depends on a working engine.

**Exit criterion:** `jac loadtest recording.har --url http://localhost:8000 --vus 10 --duration 30s` completes and prints a summary table. ✓

---

## Phase 2 — CLI Auth + Think Time ✓

> VUs log in independently and replay sessions realistically.

### CLI
- [x] `bridge/auth.jac` — detect login entry, JWT injection, identity type inference
- [x] Per-VU credentials via `--credentials-file credentials.csv` with wrap-around
- [x] Shared credential fallback: `--username` / `--password`
- [x] Think time: `--think-time none|real` with `--think-time-scale` multiplier
- [x] Ramp-up: `--ramp-up Ns` staggers VU startup
- [x] Three-layer config resolution (CLI → jac.toml → built-in defaults)
- [x] `tests/integration/test_auth.jac` (12 tests), `tests/unit/test_config.jac` (11 tests)

### Web
None — auth and think-time features are surfaced in the Web MVP UI (Phase 6).

**Exit criterion:** `jac loadtest recording.har --credentials-file creds.csv` runs with 0 auth errors. 141 tests pass. ✓

---

## Phase 3 — CLI Microservice Mode ✓

> Route requests to the correct service process, report per-service breakdown.

### CLI
- [x] `bridge/topology.jac` — `TopologyRouter`, longest-prefix matching
- [x] `--mode microservice`, `--services-map JSON` flag
- [x] Auto-discovery from `./jac.toml` `[plugins.scale.microservices.routes]` + `JAC_SV_*_URL`
- [x] Fallback to `--url` (gateway) for unmatched paths
- [x] Per-service `RequestResult.service` field; per-service column in console reporter
- [x] `tests/unit/test_topology.jac` (18 tests), microservice-mode integration tests

### Web
None — microservice mode is surfaced in the Web MVP settings panel (Phase 6).

**Exit criterion:** `jac loadtest recording.har --mode microservice --services-map '{...}'` reports per-service latency. ✓

---

## Phase 4 — Production Hardening

> Reliable under pressure: clean shutdown, CI-compatible exit codes, error classification.

### CLI
- [x] Graceful shutdown — two-signal model (implemented in Phase 1)
- [ ] Exit codes: `0` = pass, `1` = threshold failed, `2` = config/tool error (flags parsed but enforcement not wired in `cli.jac`)
- [ ] Threshold enforcement: `--fail-on-error-rate N`, `--fail-on-p95 N`, `--fail-on-p99 N` (parsed, not enforced)
- [ ] `--abort-on-fail` — stop test immediately on first threshold breach (parsed, not enforced)
- [ ] `--threshold-start-delay Ns` — delay pass/fail evaluation (parsed, not enforced)
- [ ] RPS cap: `--rps N` via token bucket in `engine.jac` (`config.rps` stored but not checked)
- [ ] `--think-time scaled` — currently falls through to `none`; needs its own branch
- [ ] `--debug` flag: per-request lines to stderr (`config.debug` stored but never read)
- [x] `error_type` on `RequestResult`: `TIMEOUT`, `CONNECTION_REFUSED`, `DNS_ERROR`, etc.
- [x] Multi-process VU distribution: `--workers N` + `core/process_runner.jac`
- [ ] `tests/integration/test_engine.jac` — VU lifecycle, ramp-up, graceful shutdown, RPS cap, error types

### Web
None — these CLI fixes are prerequisites for the web's threshold UI and debug panel.

**Exit criterion:** interrupted test still generates a partial report; `$?` correctly signals threshold failures; `jac test tests/integration/` passes.

---

## Phase 5 — Reporting & Polish

> Machine-readable output for CI, charts for humans.

### CLI
- [x] `StatsSnapshot` written every 10s; live Rich progress bar
- [x] JSON report: `--report-format json` → stdout or `--report-out` file
- [x] HTML report: `--report-format html --report-out <path>` — Chart.js charts
- [ ] `--debug` flag: per-request lines to stderr (wiring only — `config.debug` is stored)
- [ ] **p99.9 latency** — add to `MetricsCollector`, `EndpointStats`, all three report formats
- [ ] **Per-endpoint RPS** — `sample_count / actual_duration_s` in `compute_endpoint_stats()`
- [ ] **Bytes received column** in console table (tracked, not rendered)
- [ ] **Apdex score** — `(satisfied + 0.5 × tolerating) / total` per endpoint; `--apdex-t N` flag
- [ ] **TTFB breakdown** — separate Time To First Byte from total latency via aiohttp trace API
- [ ] **Per-endpoint timeout override** — `--timeout` is currently global only
- [x] `tests/integration/test_reporter.jac` (21 tests)
- [ ] `tests/e2e/test_smoke.jac` — full pipeline: HAR → engine → JSON report, exit code 0

### Web
None — the reporting enhancements are surfaced in the web's results panel and dashboard (Phase 6).

**Exit criterion:** `jac loadtest ... --report-format html --report-out report.html` produces a self-contained HTML file with charts; `jac test tests/e2e/` passes.

---

## Phase 6 — Web MVP

> Replace the CLI entirely for standard HTTP load testing. A user with no CLI experience
> can run a complete test from a browser tab.

### CLI
These are small additions to make the engine web-callable. The engine core is not rewritten.

- [ ] `run_test_headless(config_dict)` — public Python entry point that accepts a dict (not CLI args); returns a JSON-serialisable result dict; called by the `engine_bridge` sv walker
- [ ] `stream_metrics_callback` hook — optional callable passed to `run_all_vus()`; called with each `StatsSnapshot` so the sv walker can push it to SSE without polling a file or queue
- [ ] `PersonaConfig` dataclass stub in `core/engine.jac` (name, flow, vus, think_time, credentials) — consumed in Phase 8; stub added here so the sv walker can pass it through
- [ ] Verify `render_json()` and `render_html()` are importable as plain Python functions (no CLI context required)

### Web
Full UI shell — this is the primary delivery of this phase.

**Stack:**
```
jac_loadtest_web/
├── jac.toml                       ← kind = "fullstack"
├── main.jac
├── sv/
│   ├── engine_bridge.sv.jac       ← run_test(), stop_test(), stream_metrics()
│   ├── har_walkers.sv.jac         ← parse_har(), validate_har()
│   ├── recorder_walkers.sv.jac    ← start_proxy(), stop_proxy()
│   └── user_gen_walkers.sv.jac    ← generate_users(), export_csv()
└── cl/
    ├── App.cl.jac
    ├── pages/
    │   ├── TestBuilder.cl.jac
    │   ├── HarImport.cl.jac
    │   ├── UserGen.cl.jac
    │   ├── PersonaBuilder.cl.jac
    │   └── Results.cl.jac
    └── components/
        ├── RunControl.cl.jac
        ├── HarEntryTable.cl.jac
        ├── MetricsDashboard.cl.jac
        └── LatencyChart.cl.jac
```

**Project & Config:**
- [ ] New test wizard: target URL, HAR file or proxy record, VU count, duration, ramp-up
- [ ] Save/load test configurations as `.jactest` project files (server-side JSON)
- [ ] Three-layer config UI matching CLI: project defaults → per-run overrides → built-in
- [ ] Thresholds panel: `--fail-on-error-rate`, `--fail-on-p95`, `--fail-on-p99`
- [ ] Service map panel (microservice mode): enter JSON or auto-discover from `jac.toml`

**HAR Management — Manual Upload:**
- [ ] Drag-and-drop HAR upload → multipart POST to `parse_har` sv walker
- [ ] File picker button fallback
- [ ] HAR entry viewer: method, URL, status code, MIME type, response time
- [ ] Per-entry enable/disable toggle (replaces all-or-nothing MIME filter)
- [ ] HAR security warning banner when `Authorization` or `Cookie` headers detected
- [ ] HAR diff panel when a new HAR is imported over an existing one

**HAR Management — Proxy Recorder:**
- [ ] `start_proxy` sv walker: spins up local HTTP proxy on configurable port
- [ ] `stop_proxy` sv walker: stops proxy, returns parsed HAR entries to `cl`
- [ ] Record / Stop buttons in toolbar
- [ ] URL scope filter: capture only requests matching a base URL
- [ ] Export recorded HAR as `.har` file from browser
- [ ] Proxy port setting (default `8888`)

**User Generation:**
- [ ] Random user generator: count, identity fields (username, email, password, custom)
- [ ] Generation strategies: *Random* (UUID-seeded), *Realistic* (name corpus), *Pattern* (`user_{{n}}@test.com`)
- [ ] Preview table: first N generated rows before committing
- [ ] Export generated users as CSV (compatible with `--credentials-file`)
- [ ] Import existing credentials CSV; preview with row count and column detection
- [ ] Credential assignment: bind to a persona or distribute round-robin across all VUs
- [ ] Wrap-around warning badge showing reuse ratio

**Persona Builder (Basic):**
- [ ] Persona manager: create, name, colour-code up to 10 personas per test
- [ ] Per-persona flow editor: ordered list of request steps, drag-and-drop reorder
- [ ] Assign HAR entries to a persona: drag from HAR viewer or bulk-assign dropdown
- [ ] Per-persona VU count (absolute integer)
- [ ] Credential binding: attach generated list or CSV to a persona
- [ ] Default persona: all HAR entries run as a single flow when no personas are defined
- [ ] `engine_bridge` sv walker serialises persona configs and passes to `run_test_headless()`
- [ ] Per-persona post-run summary: request count, error rate, p95 latency

**Credentials Panel:**
- [ ] Username/password fields for shared credential (maps to `--username`/`--password`)
- [ ] Credentials CSV upload; preview of first 5 rows
- [ ] "Generate Users" button links to user generator panel

**Run Control:**
- [ ] Run / Stop buttons → `run_test` and `stop_test` sv walkers
- [ ] Ramp-up progress ring: live VU count during ramp-up via SSE
- [ ] Live RPS counter and error rate badge via SSE

**Real-time Metrics Dashboard:**
- [ ] RPS-over-time line chart (live SSE streaming, not post-run)
- [ ] p50/p95/p99 latency-over-time chart (live SSE)
- [ ] Per-endpoint latency bar chart updating every 10s
- [ ] Error rate gauge with colour coding (green < 1%, yellow 1–5%, red > 5%)

**Reporting:**
- [ ] Inline results viewer: renders JSON report as Chart.js charts in-page
- [ ] Download as JSON (browser `Blob`)
- [ ] Download as HTML: sv walker calls `render_html()`, browser triggers file download
- [ ] Test run history: server-side list of past runs in `runs/`; list with summary stats

**Settings:**
- [ ] Worker process count selector (maps to `--workers`)
- [ ] Timeout, think-time, RPS cap controls
- [ ] Debug log panel: sv walker streams per-request lines via SSE when debug is on
- [ ] Proxy port setting
- [ ] Settings persisted to browser `localStorage`

**Exit criterion:** A non-technical user can open the app, upload a HAR or record via proxy,
generate synthetic users, assign them to a persona, click Run, watch live metrics, see a
per-persona result summary, and download an HTML report — without touching a terminal.

---

## Phase 7 — GraphQL & WebSocket

> First protocol expansion beyond HTTP.

### CLI
New engine adapter files — the existing HTTP engine is not changed.

- [ ] `core/ws_engine.jac` — WebSocket VU coroutine: connect, send message sequence, record event-to-first-message latency and throughput; supports `ws://` and `wss://`
- [ ] `core/graphql_engine.jac` — wraps `ws_engine` with `graphql-ws` handshake; sends subscription query, records events/second and time-to-first-event latency
- [ ] `RequestResult` gains `protocol: str` field (`"http"`, `"ws"`, `"graphql"`) for mixed-protocol metric breakdown
- [ ] `EndpointStats` grouped by `(protocol, endpoint)` in `MetricsCollector`
- [ ] `run_test_headless()` accepts protocol-specific config blocks alongside HTTP config

### Web
- [ ] Protocol selector tab on test builder: **HTTP | GraphQL | WebSocket**
- [ ] GraphQL request editor: query/mutation text area with syntax highlighting
- [ ] Variables panel: JSON editor with schema validation
- [ ] Schema introspection: `sv` walker fetches `{url}/graphql` schema; `cl` editor uses it for autocomplete
- [ ] Auto-detect GraphQL endpoints in imported HAR; render with dedicated GraphQL UI
- [ ] GraphQL subscription builder: enter subscription query, expected event schema
- [ ] Raw WebSocket scenario builder: connect, send message sequence, record response latencies
- [ ] Message templates with variable substitution (`{"user_id": "{{vu_id}}"}`)
- [ ] Metrics panel gains **Connections** tab for active WebSocket connection count
- [ ] Side-by-side scenario editor: define an HTTP flow + a WebSocket subscription in the same test run

**Exit criterion:** A user can run a test that simultaneously hammers a REST endpoint with 50 VUs and holds 20 concurrent GraphQL subscriptions, seeing unified metrics in one dashboard.

---

## Phase 8 — Advanced Persona-Based Testing

> Full persona system with weighted VU allocation, staggered ramp-up, and live per-persona metrics.

### CLI
These engine changes enable the web's advanced persona UI.

- [ ] `PersonaConfig` dataclass (full): `name`, `flow`, `vus`, `weight`, `think_time`, `ramp_up`, `credentials`
- [ ] `run_personas()` orchestrator: launches one `run_all_vus()` coroutine per persona concurrently; all share a single `MetricsCollector`
- [ ] `RequestResult.persona: str` field — populated from the running persona's name
- [ ] `EndpointStats` grouped by `(persona, endpoint)` — reports show per-persona rows
- [ ] JSON report gains `personas[]` section with per-persona summary
- [ ] HTML report gains a **Personas** section with individual persona summary cards

### Web
- [ ] Per-persona VU weight: percentage of total VUs (`weight: 0.4` → 40%) as alternative to absolute count
- [ ] Per-persona ramp-up: independently staggered persona activation
- [ ] Per-persona think-time override: set a different think-time strategy per persona
- [ ] Persona import/export: download/upload `.jacpersona` files (JSON) for reuse across tests
- [ ] Live RPS line chart broken down by persona colour during a run (SSE)
- [ ] Live error rate badge per persona in the run control bar
- [ ] Persona comparison chart: side-by-side p95 latency per persona over time
- [ ] Per-persona error rate timeline
- [ ] Persona traffic mix chart: RPS contribution of each persona during the run

**Exit criterion:** A user defines two personas ("new visitor" and "returning user"), assigns weight-based VU allocation, sets independent ramp-ups, runs the test, and sees live per-persona RPS alongside separate p95 latency in the final report.

---

## Phase 9 — AI-Powered Flow Generation

> Make persona definition zero-effort: describe the user in plain English, get a ready-to-run flow.

### CLI
No engine changes required. The Claude API call lives in the `sv` codespace (server-side).

- [ ] Verify `jac_loadtest_cli` is importable as a plain Python module in the `sv` codespace without any CLI context (already true from Phase 6 headless entry point)

### Web
**API Surface Discovery:**
- [ ] OpenAPI/Swagger spec input: enter `{url}/openapi.json` or upload `.yaml`; `sv` walker fetches and parses all endpoints, methods, request/response schemas
- [ ] HAR-based discovery: use existing HAR import; parsed endpoints become the candidate step list
- [ ] Sitemap crawl: `sv` walker fetches `sitemap.xml` and crawls discovered URLs
- [ ] Discovered surface shown as a checklist of endpoints to include/exclude before generating flows

**LLM Flow Generation:**
- [ ] Persona description text input: plain-English description of the user type
- [ ] "Generate Flow" button: `generate_flow` sv walker calls Claude API (`anthropic` Python SDK)
  - Prompt includes: persona description, available endpoints (method + path), OpenAPI schema hints
  - Instruction to return ordered JSON array of steps: method, path, example body, suggested think time
- [ ] Generated flow shown in flow editor as editable draft steps
- [ ] Safety gate: destructive endpoints (DELETE, paths with `/delete`/`/destroy`/`/reset`) flagged with warning banner requiring explicit confirmation
- [ ] "Regenerate" button with feedback input for refinement
- [ ] Flow diff view: compare revised flow against previous version
- [ ] Save generated flows as reusable `.jacpersona` templates

**LLM Configuration:**
- [ ] API key management: entered in Settings panel; stored server-side in `.env` — never exposed to browser
- [ ] Model selector: default `claude-sonnet-4-6`, allow override
- [ ] Offline mode: AI generation disabled with clear explanation if no API key is set

**Exit criterion:** A user pastes an OpenAPI URL, writes a two-sentence persona description, clicks "Generate Flow", reviews the 8-step draft, approves it, and runs a 50-VU test — all without writing a line of code.

---

## Phase 10 — gRPC & Database Connections

> Match JMeter's multi-protocol coverage in a modern interface.

### CLI
New engine adapter files — the existing HTTP engine is not changed.

**gRPC:**
- [ ] `core/grpc_engine.jac` — VU coroutine: connect to gRPC endpoint, call method, record latency; supports unary, server-streaming, client-streaming, bidirectional
- [ ] `.proto` file parsing module: parses service definitions and methods; returns schema for `cl` editor
- [ ] Metrics: calls/second, message latency p50/p95/p99, stream duration, gRPC status code breakdown
- [ ] TLS configuration: CA cert, client cert, client key file paths

**Database (PostgreSQL, MySQL, MongoDB):**
- [ ] `core/db_engine.jac` — VU coroutine: acquire connection from pool, execute query, record acquisition time + execution time; release on iteration end
- [ ] Connection pool load testing: configurable pool size; metrics: pool utilisation (%), pool exhaustion events, failed connections
- [ ] Transaction scenario: multi-step SQL sequence that commits or rolls back as a unit
- [ ] Parameterised queries: `{{vu_id}}`, `{{iteration}}`, or CSV-column substitution to avoid cache-hit uniformity
- [ ] Metrics: queries/second, deadlock count, slow query count above configurable threshold

**Mixed Protocol:**
- [ ] `run_test_headless()` accepts a step list that interleaves protocol adapters
- [ ] Dependency chaining: extract a value from one step's response and inject into the next step's request body

### Web
**gRPC:**
- [ ] gRPC scenario builder: upload `.proto` → `sv` walker parses it; browse services/methods in a tree view
- [ ] Request message editor: form-based editor from proto schema + raw JSON mode
- [ ] All streaming modes UI
- [ ] Metadata (header) editor for gRPC auth tokens and tracing headers
- [ ] TLS configuration panel: upload CA cert, client cert, client key (stored server-side)

**Database:**
- [ ] Database connection panel: host, port, database name, username, password, pool size, SSL mode
- [ ] Query editor per type: SQL (PostgreSQL/MySQL) with syntax highlighting; MongoDB JSON query document editor
- [ ] Result preview: run a query against the real DB before load testing
- [ ] Transaction scenario builder: multi-step SQL editor with commit/rollback toggle
- [ ] Parameterised query UI: bind CSV columns or VU variables to query parameters

**Mixed Protocol:**
- [ ] Scenario editor allows mixing steps across HTTP, WebSocket, gRPC, and database in a single persona flow
- [ ] Dependency chaining UI: visually wire an output field from one step into an input of the next

**Exit criterion:** A user runs a scenario that: logs in via HTTP, opens a WebSocket subscription, inserts a row into PostgreSQL, calls a gRPC method, and verifies the subscription received the expected event — measured end-to-end.

---

## Phase 11 — Distributed Testing

> Break the single-machine VU ceiling. Coordinate load across multiple machines.

### CLI
These additions enable the web's worker management UI. Mirrors CLI Phase 5b.

- [ ] `jac loadtest worker --port N` — lightweight `aiohttp` HTTP server that accepts `POST /start` (config JSON + HAR entries) and runs `run_multiprocess()` locally; returns `GET /results` on completion
- [ ] `--worker-nodes host:port,...` flag — POST serialised config + HAR to each node; wait; GET results; merge into a single `MetricsCollector`
- [ ] VU distribution across nodes — split `--vus` evenly; each node receives `vu_id_offset` for globally unique VU IDs
- [ ] Pre-authentication on controller — sends per-VU token slices to each worker (no auth burst at nodes)
- [ ] Worker health check: `GET /health` before test start; abort with clear error if any node is unreachable
- [ ] Result streaming: workers push `StatsSnapshot` updates to controller via long-poll during run

### Web
- [ ] Worker node manager UI: add remote worker nodes by IP/port; see status (connected, running, idle)
- [ ] VU distribution display: shows VU slice assigned to each node
- [ ] Metrics aggregation: results streamed from all workers → controller sv walker → SSE → `cl` frontend as single unified stream
- [ ] Geo distribution: label each worker node with a region; report latency breakdown by region
- [ ] Worker node auto-discovery: mDNS-based for nodes on the same LAN

**MQTT** (web-driven protocol, CLI adapter required):
- [ ] CLI: `core/mqtt_engine.jac` — connect to broker, publish/subscribe, measure delivery latency; supports MQTT 3.1.1 and 5, QoS 0/1/2
- [ ] Web: MQTT connection builder (broker URL, port, client ID, credentials, TLS); topic parameterisation (`sensors/{{vu_id}}/temperature`); metrics: messages/second, delivery latency p50/p95/p99, connection drops, message loss rate

**Exit criterion:** A user orchestrates a 5,000-VU test split across 3 worker nodes in different network segments, with unified per-region latency in the browser dashboard in real time.

---

## Phase 12 — Release & Ecosystem

> Production-ready release for both CLI and web. PyPI, jac-scale integration, Docker, CI plugin, public launch.

### CLI
- [ ] All `jac test tests/unit/`, `jac test tests/integration/`, `jac test tests/e2e/` pass cleanly
- [ ] Integration test: local jac-scale app + HAR capture → `jac loadtest` end-to-end (manual)
- [ ] Auth integration test: register test user, run with `--username`/`--password`, verify 0 auth errors (manual)
- [ ] `README.md` polished: install instructions, usage examples, all flags documented
- [ ] `jac.toml` polished: classifiers, description, license, version
- [ ] Publish to PyPI as `jac-loadtest-cli` via `jac bundle && twine upload dist/*`
- [ ] **jac-scale integration:** Move `jac_loadtest_cli/core/` and `output/` into `jac-scale/jac_scale/loadtest/`; swap HTTP auth for in-process `UserManager`; swap disk read for in-memory `ServiceRegistry`; register `jac loadtest` in `jac-scale/jac_scale/plugin.jac`; deprecate standalone package

### Web
**Headless CI API:**
- [ ] `POST /api/run` — accepts `.jactest` config JSON, returns results as JSON (no browser required); same exit-code semantics as CLI
- [ ] `GET /api/run?format=junit` — JUnit XML output for Jenkins, Azure DevOps, GitLab
- [ ] GitHub Actions plugin: `jaseci-labs/jac-loadtest-action@v1` posts to headless API; comments pass/fail + key metrics on the PR

**Plugin Architecture:**
- [ ] `ProtocolAdapter` ABC: defined Python interface for third-party protocol plugins
- [ ] Plugin registry: install server-side; UI auto-discovers installed plugins and adds protocol tab on next page load
- [ ] Official plugin list: maintained index of community adapters
- [ ] Example plugins: Redis, Kafka, AMQP (RabbitMQ) as reference implementations

**UX Polish:**
- [ ] Onboarding tour: step-by-step walkthrough for first-time users
- [ ] Test templates library: pre-built configs (REST API stress test, WebSocket broadcast, DB connection pool test)
- [ ] Dark / light theme toggle (persisted to `localStorage`)
- [ ] Keyboard shortcuts for all primary actions
- [ ] Accessibility audit (WCAG 2.1 AA)

**Deployment:**
- [ ] Docker image: single container running `jac serve`
- [ ] `docker-compose.yml` example: web app + optional worker node agents
- [ ] Auth layer (optional): toggle-able login wall for team deployments; API token for headless CI
- [ ] Public website with docs, changelog, and hosted demo instance

**Exit criterion:** `jac install jac-loadtest-cli && jac loadtest --help` works from PyPI; `docker run jaseci/jac-loadtest` serves the web app; GitHub Actions CI plugin is published.

---

## Milestone Summary

| Milestone | Phase | CLI Deliverable | Web Deliverable |
|-----------|-------|-----------------|-----------------|
| M1 | 0 | `jac loadtest --help` works | — |
| M2 | 1 | HAR replay + console report | — |
| M3 | 2 | Per-VU JWT injection + credentials file | — |
| M4 | 3 | Per-service routing + breakdown | — |
| M5 | 4 | Graceful shutdown, thresholds, exit codes, RPS cap | — |
| M6 | 5 | JSON + HTML reports, p99.9, Apdex, TTFB | — |
| M7 | 6 | Headless `run_test_headless()` entry point | Full HTTP web app: HAR upload, proxy recorder, user gen, personas, live metrics |
| M8 | 7 | `ws_engine.jac`, `graphql_engine.jac` | GraphQL + WebSocket protocol UI |
| M9 | 8 | `PersonaConfig`, `run_personas()`, `RequestResult.persona` | Weighted VUs, per-persona live charts |
| M10 | 9 | — | AI flow generation from persona descriptions |
| M11 | 10 | `grpc_engine.jac`, `db_engine.jac` (Postgres/MySQL/MongoDB) | gRPC builder, SQL/Mongo query editors |
| M12 | 11 | `--worker-nodes` flag, `jac loadtest worker` server mode | Worker management UI, geo region reporting |
| M13 | 12 | PyPI release + jac-scale integration | Docker image, CI plugin, public launch |

---

## Protocol Support Target

| Protocol | Phase | CLI Adapter | Web UI |
|----------|-------|-------------|--------|
| HTTP/HTTPS | 0–5 (existing) | `core/engine.jac` | Phase 6 |
| GraphQL (query/mutation) | 7 | `core/graphql_engine.jac` | Phase 7 |
| GraphQL subscriptions | 7 | `core/ws_engine.jac` (graphql-ws) | Phase 7 |
| WebSocket (raw) | 7 | `core/ws_engine.jac` | Phase 7 |
| gRPC | 10 | `core/grpc_engine.jac` | Phase 10 |
| PostgreSQL | 10 | `core/db_engine.jac` | Phase 10 |
| MySQL | 10 | `core/db_engine.jac` | Phase 10 |
| MongoDB | 10 | `core/db_engine.jac` | Phase 10 |
| MQTT | 11 | `core/mqtt_engine.jac` | Phase 11 |
| Redis | 12 (plugin) | Community plugin | Phase 12 |
| Kafka | 12 (plugin) | Community plugin | Phase 12 |
| AMQP (RabbitMQ) | 12 (plugin) | Community plugin | Phase 12 |
