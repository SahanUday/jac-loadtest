# jac-loadtest Desktop — Product Roadmap

A cross-platform desktop application that brings the `jac-loadtest` engine to a visual,
no-CLI interface, then expands it into a full multi-protocol load testing tool competitive
with JMeter while being far more modern and approachable.

---

## Vision

The market gap this product targets: **there is no maintained, open-source, desktop-native
load testing tool with multi-protocol support and a good UX.** JMeter is the only
open-source desktop tool in this space and it is 20+ years old. Every modern alternative
(k6, Locust, Gatling, Artillery) is CLI-only. Enterprise tools (NeoLoad, LoadRunner) have
desktop clients but cost $50k+/year and target Fortune 1000 compliance teams.

This product positions as: **"the modern JMeter"** — a desktop-first, open-source load
tester that covers HTTP, GraphQL, WebSocket, gRPC, and database connections in a single
visual test builder.

---

## Architecture Principle

The existing `jac-loadtest` CLI engine (`core/`, `bridge/`, `output/`) is the backend.
The desktop UI is a frontend shell that configures the engine and visualises its output.
The engine is never rewritten — only extended with new protocol adapters.

```
Desktop UI (cl codespace — Vite/React)   ←  new work
  ↕ in-process walker calls (jac-desktop sv)
jac-loadtest engine (sv codespace)       ←  existing core, imported as Python module
  ↓ extended by
Protocol Adapters                        ←  new work per protocol
```

**Stack: `jac-desktop`** — the Jac-native desktop build target built into `jaclang` core.
`jac build --client desktop` produces a single relocatable binary that embeds CPython and
renders the `cl` Vite bundle via the OS-native webview (WebKitGTK on Linux, WKWebView on
macOS, WebView2 on Windows). There is no Electron, no Rust toolchain, and no separate
backend process — the `sv` codespace (Python) runs in-process inside the same embedded
interpreter that serves the frontend bundle.

The existing `jac_loadtest` Python package is imported directly inside the `sv` codespace.
The `cl` frontend calls `sv` walkers over the local jac-desktop IPC bridge; those walkers
invoke the engine, stream metrics events back to the UI, and write reports to disk. No
subprocess spawning and no HTTP server between the UI and the engine.

App identity and window geometry are configured in `jac.toml`:

```toml
[plugins.desktop]
name = "jac-loadtest"
identifier = "io.jaseci.jac-loadtest"
version = "0.1.0"

[plugins.desktop.window]
title = "jac-loadtest"
width = 1280
height = 800
min_width = 900
min_height = 600
resizable = true
```

Build and run:

```bash
jac build --client desktop      # → .jac/client/desktop/jac-loadtest  (binary + dist/)
jac start --client desktop      # build if needed, then open the native window
```

---

## Phase 0 — Desktop MVP

> **Goal:** Replace the command line entirely for the existing HTTP load testing feature.
> A user with no CLI experience should be able to run a load test — including recording
> traffic, generating test users, and running personas.

### Scope

This phase wraps the **existing** engine and adds foundational UX capabilities: HAR
recording, synthetic user generation, and a basic persona system. No new protocol support
beyond HTTP. The value is entirely in the UX shell and workflow automation.

### Features

**Project & Config**
- [ ] New test wizard: enter target URL, choose HAR file or record a session, set VU count,
      duration, ramp-up
- [ ] Save/load test configurations as `.jactest` project files (JSON)
- [ ] Three-layer config UI matching CLI: project defaults, per-run overrides, built-in defaults
- [ ] Thresholds panel: set `--fail-on-error-rate`, `--fail-on-p95`, `--fail-on-p99`

**HAR Management — Manual Upload**
- [ ] Drag-and-drop HAR file import onto the main workspace
- [ ] File picker button as a fallback for users unfamiliar with drag-and-drop
- [ ] HAR entry viewer: show all parsed requests with method, URL, status code, MIME type,
      and response time from the recording
- [ ] Toggle individual entries on/off before running (replaces the all-or-nothing MIME filter)
- [ ] HAR diff panel: when a new HAR is imported over an existing one, highlight added,
      removed, and changed entries
- [ ] HAR security warning: surfaced as a dismissible banner when `Authorization` or `Cookie`
      headers are detected in the imported file

**HAR Management — Automatic HAR Generation**
- [ ] Embedded session recorder: launches a Chromium instance (via Playwright, invoked
      from the `sv` codespace) with network capture enabled; the `cl` UI renders a
      Record / Stop toolbar panel communicating with the `sv` walker over the
      jac-desktop IPC bridge
- [ ] Record button in the toolbar: starts the Playwright browser process, intercepts all
      XHR/fetch network requests, and accumulates them into an in-memory HAR object inside
      the `sv` codespace
- [ ] Stop recording button: finalises the HAR, filters out static assets (images, fonts,
      CSS), and pushes the result to the `cl` frontend via a walker event — no file saved
      to disk unless the user explicitly exports it
- [ ] Optional proxy mode: for users who cannot use the embedded browser, the `sv` walker
      spins up a local HTTP proxy on a configurable port; the user points their own browser
      at it; captured traffic is parsed into HAR format when recording stops
- [ ] URL scope filter in the recorder: user enters a base URL (e.g. `https://myapp.com`)
      and only requests matching that origin are captured, ignoring third-party CDN and
      analytics noise
- [ ] Export recorded HAR to disk: save the captured session as a `.har` file for sharing
      or reuse in future test runs

**User Generation — Random & Synthetic Users**
- [ ] Random user generator panel: specify count, choose identity fields (username, email,
      password, custom fields), and generate a synthetic credentials list in memory
- [ ] Generation strategies:
  - *Random* — UUID-seeded random strings for each field
  - *Realistic* — human-like names and email addresses using a bundled name corpus
  - *Pattern* — user-defined template with a counter, e.g. `user_{{n}}@test.com`
- [ ] Preview table: show the first N generated rows before committing
- [ ] Export generated users to CSV (compatible with `--credentials-file` format)
- [ ] Import existing credentials CSV: file picker + drag-and-drop, shows a preview with
      row count and detected columns (`username`, `password`, custom fields)
- [ ] Credential assignment: generated or imported users are bound to a persona or
      distributed round-robin across all VUs if no persona is defined
- [ ] Wrap-around behaviour: when VU count exceeds user count, users are reused cyclically;
      a warning badge is shown indicating the reuse ratio

**Persona Builder (Basic)**

A **persona** is a named user type with its own request flow, VU count, and credential
assignment. This phase introduces the persona concept at the workflow level; advanced
per-persona metrics and weighted ramp-up are deferred to Phase 2.

- [ ] Persona manager panel: create, name, and colour-code up to 10 personas per test
- [ ] Per-persona flow editor: ordered list of request steps; steps can be reordered via
      drag-and-drop
- [ ] Assign HAR entries to a persona: drag entries from the HAR viewer onto a persona's
      flow, or use a bulk-assign dropdown ("assign all POST requests to Persona A")
- [ ] Per-persona VU count: absolute integer allocation (e.g. `vus: 20`)
- [ ] Credential binding: attach a generated user list or imported CSV to a specific persona;
      users are distributed round-robin across that persona's VUs
- [ ] Default persona: if no personas are defined, all HAR entries run as a single unnamed
      flow (backwards-compatible with the wizard path)
- [ ] Engine bridge: the `sv` walker serialises persona configs and passes them to the
      `jac_loadtest` engine imported in-process; the `PersonaConfig` dataclass in
      `core/engine.py` is the target format (full engine orchestration implemented in
      Phase 2, exposed at the UI level here)
- [ ] Per-persona run summary: after a test completes, the results panel shows a tab per
      persona with request count, error rate, and p95 latency — live per-persona streaming
      is deferred to Phase 2

**Credentials Panel**
- [ ] Username/password fields for a single shared credential (maps to `--username`/`--password`)
- [ ] Credentials CSV upload (maps to `--credentials-file`); displays row count and a
      preview of the first 5 rows
- [ ] Integration with the random user generator: "Generate Users" button opens the
      generator panel and imports the result directly into the credentials table

**Run Control**
- [ ] Run / Pause / Stop buttons wired to `sv` walkers that invoke the `jac_loadtest`
      engine in-process; stop maps to the engine's graceful two-signal shutdown model
- [ ] Ramp-up progress ring: shows live VU count during ramp-up phase, updated via
      walker events streamed to the `cl` frontend over the jac-desktop IPC bridge
- [ ] Live RPS counter and error rate badge updating every second

**Real-time Metrics Dashboard**
- [ ] RPS-over-time line chart (live, streaming — not post-run)
- [ ] p50/p95/p99 latency-over-time chart (live)
- [ ] Per-endpoint latency bar chart updating every 10 seconds
- [ ] Error rate gauge with colour coding (green < 1%, yellow 1–5%, red > 5%)

**Reporting**
- [ ] Embedded HTML report viewer rendered in the OS-native webview (no external browser
      needed — the jac-desktop window navigates to the report file via a loopback URL
      served by the embedded CPython `http.server`)
- [ ] Export to JSON, HTML, PDF
- [ ] Test history: list of past runs with summary stats; open any previous report

**Settings**
- [ ] Worker process count selector (maps to `--workers`)
- [ ] Timeout, think-time, RPS cap controls
- [ ] Debug log panel (maps to `--debug`)
- [ ] Recorder proxy port setting
- [ ] `[plugins.desktop]` window geometry remembered across sessions via `jac.toml`

### Exit Criterion

A non-technical user can: open the app, record a session using the embedded browser OR
import a HAR file manually, generate synthetic test users, assign them to a persona, click
Run, watch live metrics, see a per-persona result summary, and save an HTML report —
without touching a terminal.

### MVP Must-Have Checklist

**Must have:**
- [ ] jac-desktop app shell: `jac build --client desktop` produces a working binary;
      `cl` frontend calls `sv` walkers; `sv` walkers import `jac_loadtest` in-process
- [ ] Test configuration form: URL, VUs, duration, ramp-up
- [ ] Manual HAR import: drag-and-drop and file picker
- [ ] HAR entry viewer with per-entry enable/disable toggle
- [ ] Automatic HAR generation via embedded Playwright-based browser recorder
- [ ] Random user generator: pattern and realistic modes, CSV export
- [ ] Credentials panel: single credential and credentials CSV import
- [ ] Basic persona builder: create personas, assign HAR entries, set VU count,
      bind credentials
- [ ] Run / Stop buttons with graceful shutdown
- [ ] Live RPS and error rate counters during run
- [ ] Per-persona post-run summary (request count, error rate, p95)
- [ ] Embedded results viewer (renders existing HTML report output in the webview)
- [ ] Save/load `.jactest` project file

**Nice to have (defer to Phase 1):**
- Real-time latency charts during run (streaming metrics)
- Test run history
- Threshold configuration UI
- HAR diff panel
- Proxy-mode recorder

**Explicitly out of scope for MVP:**
- Any new protocol support
- Advanced persona features (weighted VU, staggered ramp-up, live per-persona charts)
- AI flow generation
- Distributed testing
- Plugin architecture

---

## Phase 1 — GraphQL & WebSocket Support

> **Goal:** First protocol expansion beyond HTTP. Both are high-value targets with poor
> tooling in the current market (GraphQL subscriptions via WebSocket are underserved by
> every major tool).

### GraphQL (HTTP)

- [ ] GraphQL request editor: query/mutation text area with syntax highlighting
- [ ] Variables panel (JSON editor with validation)
- [ ] Schema introspection: connect to `{url}/graphql` and pull schema, enable
      autocomplete and field validation in the query editor
- [ ] Auto-detect GraphQL endpoints in imported HAR files and render them with the
      dedicated GraphQL UI instead of the raw HTTP panel
- [ ] Per-query response time breakdown in metrics (keyed by `operationName` if set)

### GraphQL Subscriptions (WebSocket)

- [ ] WebSocket engine adapter in `core/ws_engine.py` — connect, send `graphql-ws`
      protocol handshake, send subscription query, receive events, record
      event-to-first-message latency and message throughput
- [ ] Subscription test builder: enter subscription query, expected event schema
- [ ] Metrics: events/second, time-to-first-event p50/p95/p99, connection drop rate
- [ ] Load shape: N concurrent subscription connections, duration, ramp-up

### Raw WebSocket

- [ ] Generic WebSocket scenario builder: connect, send message sequence,
      record response latencies and message counts
- [ ] Message templates with variable substitution (e.g. `{"user_id": "{{vu_id}}"}`)
- [ ] Support both `ws://` and `wss://` with TLS certificate options

### UI Additions

- [ ] Protocol selector tab on the test builder: HTTP | GraphQL | WebSocket
- [ ] Metrics panel gains "Connections" tab for WebSocket active connection count
- [ ] Side-by-side scenario editor: define an HTTP flow + a WebSocket subscription
      in the same test run (mixed-protocol scenario)

### Exit Criterion

A user can run a load test that simultaneously hammers a REST endpoint with 50 VUs
and holds 20 concurrent GraphQL subscriptions, seeing unified metrics for both in one
dashboard.

---

## Phase 2 — Advanced Persona-Based Testing

> **Goal:** Extend the basic persona system introduced in Phase 0 with weighted VU
> allocation, staggered ramp-up, live per-persona metrics, and engine-level persona
> orchestration. This turns personas from a workflow organiser into a first-class load
> modelling primitive — no open-source tool does this in a GUI today.

### Engine Changes (core/engine.py extension)

- [ ] `PersonaConfig` dataclass: `name`, `flow`, `vus`, `think_time`, `ramp_up`, `weight`
- [ ] `run_personas()` orchestrator: launches one `run_all_vus` coroutine per persona
      concurrently, all sharing a single `MetricsCollector`
- [ ] `RequestResult` gains `persona: str` field for per-persona metric breakdown
- [ ] `EndpointStats` grouped by `(persona, endpoint)` — reports show per-persona rows

### Advanced Persona Builder

- [ ] Per-persona VU weight: percentage of total VUs (`weight: 0.4` → 40%) as an
      alternative to the absolute count set in Phase 0
- [ ] Per-persona ramp-up: stagger persona activation independently (e.g. "new users"
      ramp up over 30s, "power users" are always-on)
- [ ] Per-persona think time override: set a different think-time strategy per persona
      independent of the global setting
- [ ] Persona import/export: save a persona definition as a reusable `.jacpersona` file
      (JSON) that can be shared across test configurations

### Live Per-Persona Metrics

- [ ] Live RPS line chart broken down by persona colour during a run; streamed from
      the `sv` walker to the `cl` frontend via the jac-desktop IPC bridge
- [ ] Live error rate badge per persona in the run control bar

### Metrics & Reporting

- [ ] Persona comparison chart: side-by-side p95 latency per persona over time
- [ ] Per-persona error rate timeline
- [ ] Persona traffic mix chart: RPS contribution of each persona during the run
- [ ] HTML report gains a "Personas" section with individual persona summary cards

### Exit Criterion

A user defines two personas ("new visitor: browse + add to cart" and "returning user:
search + checkout"), assigns weight-based VU allocation, sets independent ramp-ups, runs
the test, and sees live per-persona RPS alongside separate p95 latency and error rate
per persona in the final report.

---

## Phase 3 — AI-Powered Flow Generation

> **Goal:** Make persona definition zero-effort for users who have an OpenAPI spec or
> can describe their app in plain English. This is the feature that has no equivalent
> in any existing tool.

### API Surface Discovery

Three input methods, offered as a wizard in the UI:

1. **OpenAPI/Swagger spec** — enter `{url}/openapi.json` or upload a `.yaml` file.
   The app parses all endpoints, methods, request schemas, and response schemas.
2. **HAR recording** — use the existing HAR import or recorder. Parsed endpoints become
   the candidate step list.
3. **Sitemap crawl** — enter the base URL. The app fetches `sitemap.xml` and
   crawls discovered URLs to identify API endpoints.

The discovered surface is shown as a checklist of endpoints the user can include or
exclude before generating flows.

### LLM Flow Generation

- [ ] Persona description text input: user writes a plain-English description of the
      user type (e.g. "A first-time visitor who browses product categories, views 3
      product pages, adds one item to cart, then abandons without purchasing")
- [ ] "Generate Flow" button: the `sv` walker calls the Claude API (`anthropic` SDK,
      invoked inside the embedded CPython). The prompt includes:
      - The persona description
      - The list of available endpoints with method and path
      - Schema hints from OpenAPI (request body shape, required fields)
      - Instruction to return an ordered JSON array of steps with method, path,
        example body, and suggested think time
- [ ] Generated flow is shown in the flow editor as editable draft steps — the user
      reviews, reorders, edits, or deletes steps before saving
- [ ] Safety gate: any step touching destructive endpoints (DELETE, paths containing
      `/delete`, `/destroy`, `/reset`) is flagged with a warning banner and requires
      explicit user confirmation before it is included

### Iteration & Refinement

- [ ] "Regenerate" button with feedback: user can tell the LLM "make the think times
      shorter" or "add more product views before checkout" and it revises the flow
- [ ] Flow diff view: compare the revised flow against the previous version
- [ ] Save generated flows as reusable persona templates (`.jacpersona` file format, JSON)

### LLM Configuration

- [ ] API key management panel (stored in OS keychain, never in project files)
- [ ] Model selector: default to `claude-sonnet-4-6`, allow override
- [ ] Offline mode: if no API key is set, AI generation is disabled with a clear
      explanation — the rest of the tool works without it

### Exit Criterion

A user pastes an OpenAPI URL, writes a two-sentence persona description, clicks
"Generate Flow", reviews the 8-step draft, approves it, and runs a 50-VU load test
against the generated flow — all without writing a single line of code or config.

---

## Phase 4 — gRPC & Database Connections

> **Goal:** Match JMeter's multi-protocol coverage in a modern interface. Database
> testing is the biggest gap in the open-source market and the highest-value addition
> for backend engineers.

### gRPC

- [ ] gRPC scenario builder: upload `.proto` file, browse service definitions and
      methods in a tree view, select a method to test
- [ ] Request message editor: form-based editor generated from the proto schema,
      plus raw JSON mode for advanced users
- [ ] All streaming modes: unary, server-streaming, client-streaming, bidirectional
- [ ] Metadata (header) editor for gRPC-specific headers (auth tokens, tracing)
- [ ] Metrics: calls/second, message latency p50/p95/p99, stream duration, error codes
      (gRPC status codes mapped to error breakdown)
- [ ] TLS configuration: upload CA cert, client cert, client key for mTLS environments

### Database Connections

Supported initially: **PostgreSQL**, **MySQL**, **MongoDB**.

- [ ] Database connection panel: host, port, database name, username, password,
      connection pool size, SSL mode
- [ ] Query editor per database type:
  - SQL (PostgreSQL/MySQL): raw SQL with syntax highlighting, result preview
  - MongoDB: JSON query document editor (find, aggregate, insert, update)
- [ ] Connection pool load testing: define a pool size, run N concurrent queries,
      measure: connection acquisition time, query execution time p50/p95/p99,
      pool exhaustion events, failed connections
- [ ] Transaction scenario: multi-step SQL sequence that commits or rolls back as a
      unit — measures total transaction time
- [ ] Parameterised queries: substitute `{{vu_id}}`, `{{iteration}}`, or values from
      a CSV column into query parameters to avoid cache-hit uniformity
- [ ] Metrics: queries/second, connection pool utilisation (%), deadlock count,
      slow query count (above configurable threshold)

### Mixed-Protocol Scenarios

- [ ] Scenario editor allows mixing steps across protocols in a single persona flow:
      e.g. POST HTTP → open WebSocket subscription → run 3 SQL queries → close WebSocket
- [ ] Dependency chaining: extract a value from one step's response and use it in the
      next step's request body (e.g. extract `order_id` from HTTP response, pass to
      the next SQL query)
- [ ] Think times and ramp-up apply uniformly across mixed steps

### Exit Criterion

A user runs a scenario that: (1) logs in via HTTP, (2) opens a WebSocket subscription,
(3) inserts a row into PostgreSQL, (4) calls a gRPC method, (5) verifies the subscription
received the expected event — all in a single persona flow measured end-to-end.

---

## Phase 5 — MQTT & Distributed Testing

> **Goal:** Enter the IoT load testing vertical and break the single-machine VU ceiling.

### MQTT

- [ ] MQTT connection builder: broker URL (`mqtt://`, `mqtts://`), port, client ID,
      username/password, TLS options, keep-alive interval
- [ ] Protocol versions: MQTT 3.1.1 and MQTT 5
- [ ] QoS levels: 0 (at most once), 1 (at least once), 2 (exactly once)
- [ ] Scenario builder: publish messages to topics on a schedule, subscribe to topics
      and measure message delivery latency (publish timestamp → receive timestamp)
- [ ] Topic parameterisation: `sensors/{{vu_id}}/temperature` for per-VU topics
- [ ] Metrics: messages/second, delivery latency p50/p95/p99, connection drops,
      reconnect count, message loss rate (for QoS 0)
- [ ] Load simulation: N concurrent MQTT clients (VUs), each publishing at a
      configurable rate

### Distributed Load Generation

- [ ] Worker node agent: a lightweight `jac-loadtest-agent` process that runs on
      remote machines and accepts work from the desktop controller
- [ ] Controller UI: add remote worker nodes by IP/port, see their status (connected,
      running, idle)
- [ ] VU distribution: total VUs split across all worker nodes (local + remote)
- [ ] Metrics aggregation: results streamed back to the controller in real time,
      merged into a single unified dashboard
- [ ] Geo distribution: label each worker node with a region; report latency
      breakdown by region in the HTML report
- [ ] Worker node discovery: mDNS-based auto-discovery for nodes on the same LAN

### Exit Criterion

A user orchestrates a 10,000-VU MQTT load test against an IoT broker, split across
3 worker nodes in different network segments, and sees unified per-region latency
in the report.

---

## Phase 6 — Polish & Ecosystem

> **Goal:** Production-ready release. CI integration, plugin ecosystem, public launch.

### CI/CD Integration

- [ ] Headless mode: `jac-loadtest --headless --config test.jactest` runs a saved
      `.jactest` configuration without opening the desktop window — same exit codes as
      the CLI engine (0 = pass, 1 = threshold fail, 2 = tool error); implemented by
      setting `JAC_BUILD=1` and invoking the engine walker directly from the `sv`
      codespace without the `cl` frontend
- [ ] GitHub Actions plugin: `jaseci-labs/jac-loadtest-action@v1` that runs a
      `.jactest` file and posts a summary comment on the PR with pass/fail and key metrics
- [ ] JUnit XML output: `--report-format junit` for CI systems that consume XML
      test results (Jenkins, Azure DevOps, GitLab)

### Plugin Architecture

- [ ] Protocol plugin interface: a defined Python ABC (`ProtocolAdapter`) that
      third-party authors can implement to add new protocols without modifying the core
- [ ] Plugin registry: install plugins from a URL or local path; the UI auto-discovers
      installed plugins and adds their protocol tab to the test builder
- [ ] Official plugin list: maintained index of community protocol adapters
- [ ] Example plugins: Redis, Kafka, AMQP (RabbitMQ) as reference implementations

### UX Polish

- [ ] Onboarding tour: step-by-step walkthrough for first-time users
- [ ] Test templates library: pre-built test configs for common patterns
      (REST API stress test, WebSocket broadcast, DB connection pool test)
- [ ] Dark / light theme toggle
- [ ] Keyboard shortcuts for all primary actions
- [ ] Accessibility audit (WCAG 2.1 AA)

### Distribution

The jac-desktop binary output (`.jac/client/desktop/`) is already a relocatable
self-contained directory. Packaging per platform:

- [ ] macOS: wrap `.jac/client/desktop/` in a `.app` bundle, code-sign with Apple
      Developer ID, notarise via `notarytool`; distribute as `.dmg`
- [ ] Windows: bundle the directory into a `.exe` installer (NSIS or WiX); sign with
      an Authenticode certificate
- [ ] Linux: package as `.AppImage` (single-file portable) and `.deb`/`.rpm` for
      distro package managers
- [ ] Auto-update mechanism: check a release endpoint on startup, download delta
      updates and replace the binary in-place
- [ ] Public website with docs, changelog, and download links

---

## Milestone Summary

| Phase | Name | Key Deliverable | Market Position |
|---|---|---|---|
| **0 — MVP** | Desktop Shell | HAR import, session recorder, user generation, basic personas | Better JMeter UX for HTTP |
| **1** | GraphQL & WebSocket | First non-HTTP protocols | Ahead of Artillery, matches k6 |
| **2** | Advanced Personas | Weighted VUs, staggered ramp-up, live per-persona charts | Unique in open-source market |
| **3** | AI Flow Generation | LLM-generated flows from persona descriptions | No equivalent exists |
| **4** | gRPC & Databases | PostgreSQL, MySQL, MongoDB, gRPC | Matches JMeter's protocol breadth |
| **5** | MQTT & Distributed | IoT testing, multi-machine VU distribution | Surpasses JMeter |
| **6** | Polish & Ecosystem | Plugin system, CI integration, public launch | Full product release |

---

## Protocol Support Target (Final Product)

| Protocol | Phase | Notes |
|---|---|---|
| HTTP/HTTPS | 0 (MVP) | Existing engine |
| GraphQL (query/mutation) | 1 | HTTP POST, operation name keying |
| GraphQL subscriptions | 1 | WebSocket transport, `graphql-ws` protocol |
| WebSocket (raw) | 1 | Generic message sequences |
| gRPC | 4 | All streaming modes, mTLS |
| PostgreSQL | 4 | Native driver, connection pool testing |
| MySQL | 4 | Native driver, transaction scenarios |
| MongoDB | 4 | Driver-based, aggregation pipeline support |
| MQTT | 5 | 3.1.1 + 5, QoS 0/1/2, TLS |
| Redis | 6 (plugin) | Community plugin reference implementation |
| Kafka | 6 (plugin) | Community plugin reference implementation |
| AMQP (RabbitMQ) | 6 (plugin) | Community plugin reference implementation |

---

## Competitive Positioning

| Capability | jac-loadtest Desktop | JMeter | k6 | Gatling | NeoLoad |
|---|---|---|---|---|---|
| Desktop GUI | Yes (Jac-native, OS webview) | Yes (Java Swing, dated) | No | No | Yes (enterprise) |
| HTTP | Yes | Yes | Yes | Yes | Yes |
| Session recorder (auto HAR) | Yes (embedded Playwright) | Yes (HTTP proxy) | No | No | Yes |
| Random user generation | Yes (built-in) | Via CSV Dataset | Via scripts | Via scripts | Yes |
| Persona-based testing | Yes (visual, Phase 0) | Manual | Manual code | Manual code | Manual |
| GraphQL subscriptions | Yes | Via plugin | Manual WS | No | Yes |
| gRPC | Yes | Via plugin | Yes | Yes | Yes |
| Database load testing | Yes (built-in) | Yes (JDBC) | Via extension | No | Unclear |
| MQTT | Yes | No | Via extension | Yes | Yes |
| AI flow generation | Yes | No | No | No | Partial |
| Open source | Yes | Yes | Yes | Partial | No |
| Price | Free | Free | Free | Free/paid | Enterprise |
