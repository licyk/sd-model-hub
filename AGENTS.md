# SD Model Hub — working notes for agents

Everything needed to work on this repository is in this file. It is self-contained on purpose:
do not rely on anything outside it, and when you learn something durable, write it here.

## 1. What this is

A tool for downloading and managing Stable Diffusion models, with two ends over one core:

- **A command line** (`sd-model-hub`, Typer) that does everything, including starting the web UI.
- **A web UI** (Vue 3, served by the same Python process) with four screens: Browse, Hubs,
  Library, Settings.

What it does:

- **Browse and download** from Civitai, OpenModelDB and GitHub Releases over plain HTTP, with
  resume, SHA256 verification, preview images and metadata sidecars.
- **Hubs:** download files or whole repositories from Hugging Face (and mirrors such as
  hf-mirror) and ModelScope, through their own libraries.
- **Library:** manage ComfyUI and Stable Diffusion WebUI model folders — identify each model's
  kind and base architecture from the file header, browse with previews, and import, move,
  rename and delete models together with their companion files.

Package `sd_model_hub`, distribution and command `sd-model-hub`, Python 3.10 or newer. The web
UI is built into the wheel, so users never need Node.

## 2. Layout and the layer rule

```
sd_model_hub/
  core/        all logic. Imports no web or CLI framework.
    settings/  pydantic models + TOML file + env overrides
    auth/      Civitai credentials: manual token or OAuth (PKCE)
    db/        SQLite, numbered migrations
    detection/ header reading, kind rules, base-model rule tables (rules_data/*.json)
    library/   roots, layouts, browsing, path safety, file operations, sidecars, thumbnails
    sources/   Civitai, OpenModelDB, GitHub Releases (httpx)
    hubs/      Hugging Face, ModelScope metadata + the download worker
    downloads/ queue, HTTP downloader, hub runner
    net/       port binding, runtime file, shared httpx client
    context.py build_services(): builds everything once
  api/         FastAPI: routers/, security.py, sockets.py, static.py. Thin.
  cli/         Typer: app.py (the whole command tree), commands/, factory.py. Thin.
  webui/       the Vue project; dist/ is git-ignored and shipped as package data
scripts/       dev.py (task runner), build_wheel.py, generate_openapi.py, extract_header_fixture.py
tests/         core/, api/, cli/, fixtures/headers/
```

**The command line's shape.** `cli/app.py` has one `get_app()` that registers every command and
group, so the whole tree is readable in one place and a test can compare it with an expected
list. Command functions in `cli/commands/` are plain and undecorated — importable and testable
without Typer — and their name and help text are given at registration, not taken from the
function. `cli/factory.py` owns the shared settings and adds `--debug` at every level through
custom command and group classes; it is the only module that may import the private
`typer._click`; Typer upgrades must remain compatible with this integration. `main()` does
its own error handling so exit codes and messages are uniform. Heavy imports (FastAPI, uvicorn,
the hub libraries) go inside the command functions, which keeps `sd-model-hub version` fast.

**The layer rule, enforced by `tests/core/test_architecture.py`:** `core` may import the standard
library, `httpx`, `pydantic` and the hub libraries, and must not import `fastapi`, `starlette`,
`typer`, `click`, `socketio`, `uvicorn` or `rich`, nor anything from `sd_model_hub.api` or
`sd_model_hub.cli`. The API and the CLI are wrappers: parse input, call one core method, map a
domain error to a status or exit code, shape the output. No file access, HTTP calls or business
decisions in a route or a command.

Every operation exists once, as a core method taking and returning pydantic models, so the API's
JSON and the CLI's `--json` have the same shape.

**Pydantic compatibility:** the dependency has no version constraint. `core/record.py` supplies
the project's v2-style model methods and computed-property serialization on native v1 models;
v2 uses its native implementation. Keep nested events, `can_pause`, persistence exclusions and
hash validation working on both versions. Pydantic v1 needs Python 3.10–3.13 and FastAPI <0.126;
the release workflow tests it separately on Python 3.10 and 3.13, including ty. Run the full
`scripts/dev.py check` and generate the committed API types with v2: v1 has a different JSON
Schema format and cannot distinguish validation schemas from serialization schemas.

## 3. Commands

```bash
python scripts/dev.py              # list the tasks
python scripts/dev.py dev          # API + Vite together, hot reload, Ctrl+C stops both
python scripts/dev.py check        # what CI runs: lint, ty, both test suites, generated types
python scripts/dev.py typecheck-py # ty for the Python package (Python 3.10 by default)
python scripts/dev.py test         # pytest + vitest + vue-tsc
python scripts/dev.py format       # ruff fixes and formatting
python scripts/dev.py typegen      # regenerate webui/src/api/schema.d.ts (commit the result)
python scripts/build_wheel.py      # web UI, then wheel and sdist
```

There is no Makefile on purpose: this project is developed on Windows as often as on Linux.
The web UI uses **bun**. Always finish a change with `python scripts/dev.py check`.

**Releasing** is `.github/workflows/release.yml`, on a push to `main` changing
`sd_model_hub/version.py`, a `v*` tag, or a manual run: tests and ty checks on Python 3.10–3.14, the
web tests and type-check, the generated-types check, then any tag is compared with
`sd_model_hub/version.py`, the wheel is built with the UI inside it and checked (UI present,
rules present, installs, runs), and only then published to PyPI by running Twine directly on the
runner, without Docker. Authentication uses `TWINE_USERNAME=__token__` and the GitHub Actions
secret `TWINE_PASSWORD` (a PyPI API token); no OIDC permission is needed. Uploads use
`--skip-existing --non-interactive`. All triggers publish to PyPI; only tag runs create a GitHub release.
For a version change, bump `VERSION`, commit and push to `main`. Python 3.10 is the floor, so `typing.Self`,
`tomllib` without the `tomli` fallback and other 3.11+ APIs are out.

## 4. Conventions

- **Python:** ruff with line length 180, indent 4, `E402` ignored (see `pyproject.toml`). Ruff's
  default rule set is kept clean; do not add blanket ignores to silence a finding.
- **Python types:** ty checks `sd_model_hub`, excluding the generated web UI and its dependencies.
  It targets Python 3.10 locally; CI overrides the target for each Python matrix entry.
  `typecheck-py` passes its own interpreter with `--python` so dependencies resolve consistently.
  The `dev` extra includes `keyring` for the optional credential-store import and `tomli` for
  checking the Python 3.10 fallback on newer hosts. Runtime dependencies keep their optional
  or version-specific behavior. Verify dependency fixes in an isolated environment, since a
  shared interpreter can hide undeclared packages.
- **Comments explain why, never what.** Do not narrate the diff or leave "changed X" notes.
- **Docstrings** on modules and non-obvious functions; one line where one line does.
- **Use the file tools to edit code.** A scripted mass rewrite (sed and friends) needs the user's
  agreement first; it was given once, for the `model_hub` → `sd_model_hub` rename.
- **TypeScript is pinned to 6.x.** `vue-tsc` and `openapi-typescript` need the JavaScript
  compiler API that TypeScript 7 removed; do not "upgrade" it without checking both.
- **Vue:** `<script setup lang="ts">`, strict TypeScript. Views and composite components import
  only from `src/ui/`; `src/ui/` is the only place that may import `@material/web` or
  `@lucide/vue`. No literal colours, radii or durations outside `src/theme/` — a test enforces
  the colours (`src/tokens.test.ts`).
- **Commit messages and PRs:** only when the user asks.

## 5. Settings, secrets and errors

Settings are a pydantic model saved as `settings.toml` in the data directory
(`~/.local/share/sd-model-hub`, `%APPDATA%` on Windows, or `SD_MODEL_HUB_DATA_DIR`). Groups:
`server`, `paths.model_roots`, `sources.<id>`, `auth.civitai`, `network`, `downloads`, `content`,
`library`.

Every setting can be overridden by an environment variable named `SD_MODEL_HUB_<GROUP>__<FIELD>`,
for example `SD_MODEL_HUB_SERVER__PORT=8000`. Overrides win over the file and are never written
back to it.

**Secrets never leave the server.** The settings API returns `token_configured: true` in place of
a token and accepts a new value or an explicit clear; OAuth tokens live in the credential store,
not in settings. A token is attached only to requests to its own source's host. Never log a
token, a code, a `state` value or a URL containing one, and never store credentials in download
records.

Domain errors live in `core/errors.py` and both wrappers translate them:

| Exception | HTTP | Exit code |
| --- | --- | --- |
| `NotFoundError` | 404 | 2 |
| `ConflictError` | 409 | 3 |
| `InvalidPathError`, `ValidationError` | 400 | 4 |
| `AuthRequiredError` | 401 | 5 |
| `SourceError` / `RateLimitedError` | 502 / 429 | 6 |
| `ModelHubError` (base) | 500 | 1 |

The API's single error shape is `{"code", "message", "detail"}`.

## 6. Model detection

Detection reads **only the file header** — tensor names and shapes — never the weights, and never
unpickles anything.

- safetensors: an 8-byte little-endian length then that many bytes of JSON. The length is
  untrusted input: cap it (100 MB) and compare it with the file size.
- GGUF: the metadata and tensor table are parsed; shapes are reversed into PyTorch order.
- `.ckpt`, `.pt`, `.pth`, `.bin`, `.pkl` are **never** unpickled. They are `unknown` unless a
  sidecar or the folder says otherwise.

Two stages: `kinds.py` decides what kind of file it is, then `rules.py` matches data-driven rules
in `detection/rules_data/*.json` for the base architecture. Order matters, and every pattern is
anchored to an exact key or a prefix — loose substrings such as `blocks.0.` match the insides of
unrelated models. The kind tests, in order: LoRA (`.lora_up.`, `.lora_down.`, `.lora_A.`,
`.lora_B.`, `.hada_w1`, `.lokr_w1`, `.lora_mid.`), ControlNet, checkpoint
(`model.diffusion_model.` together with `first_stage_model.`/`cond_stage_model.`/
`conditioner.embedders.`), embedding, VAE (at least 90% of keys under `encoder`/`decoder`, at
least one under `decoder`, and no T5 marker), text encoder (exact marker keys such as
`encoder.block.0.layer.0.SelfAttention.q.weight`), bare diffusion model (marker keys under no
prefix, or under `model.diffusion_model.`, `model.` or `net.`), upscaler.

A rule carries `required_keys`, `absent_keys`, `any_key_prefixes`, `shapes`, `regex_shapes`,
`prediction`, `priority` and `confidence`. Adding an architecture means adding a rule, not code.
Results are cached in the `file_index` table by path, size and mtime, so deleting the database
only costs time. When the detected kind disagrees with the folder or a sidecar, the entry is
flagged rather than one of them winning.

These rules were run over 555 real files in local ComfyUI and Forge installs; the fixtures in
`tests/fixtures/headers/*.json.gz` are real headers (names and shapes only) from that set,
including two video/audio VAEs that naive substring rules misclassified. ControlNet, embedding
and upscaler rules are only covered by synthetic fixtures — no real samples were available.

**Licence note:** ComfyUI is GPL-3.0. The marker keys are facts about file formats and were
reimplemented; never copy code from it.

## 7. The library

A **root** is a folder plus a layout preset. Layout maps folder names to kinds and is a hint and a
default download destination, never an override of detection.

- `comfyui`: `checkpoints`, `loras`, `vae`, `text_encoders` (alias `clip`), `diffusion_models`
  (alias `unet`), `controlnet` (alias `t2i_adapter`), `clip_vision`, `upscale_models`,
  `embeddings`, `hypernetworks`, `style_models`, `vae_approx`, and more. Each also works under a
  `models/` prefix, so a root may be the install folder or its `models` folder.
- `sd-webui`: `models/Stable-diffusion`, `models/Lora`, `models/LyCORIS`, `models/VAE`,
  `models/VAE-approx`, `models/text_encoder`, `models/ControlNet`, `models/hypernetworks`, the
  upscaler folders (`ESRGAN`, `RealESRGAN`, `DAT`, `SwinIR`, `ScuNET`, `LDSR`, `BSRGAN`) — and
  `embeddings`, which sits **beside** `models/`, so a WebUI root is the installation folder.
- `custom`: no mapping.

**Companions.** A model's companions are the files sharing its stem, assigned to the longest
matching stem so `a.b.png` belongs to `a.b.safetensors` and not to `a.safetensors`. Every
operation — move, rename, delete, import — carries them along.

**Previews** follow the WebUI's lookup: for each of `png`, `jpg`, `jpeg`, `webp`, `gif`, try
`<stem>.<ext>` then `<stem>.preview.<ext>`; first hit wins. Served through a thumbnail endpoint
that resizes with Pillow and caches in the data directory.

**Sidecars.** This project writes `<stem>.sdmodelhub.json`. `<stem>.json` belongs to the WebUI's
metadata editor: it is read for display and only ever created when `downloads.write_webui_metadata`
is on and no file exists. Also read: `<stem>.txt`, `<stem>.description.txt`, `<stem>.civitai.info`.

**Ignored** everywhere: dot entries, `*.incomplete`, `*.part`, `*.tmp`. A folder containing
`model_index.json` is one diffusers model, not a folder.

**Deleting** goes to the system trash through `send2trash`, which works on a headless machine: it
falls back to its own implementation of the FreeDesktop specification, moving the file to
`~/.local/share/Trash/files/` or to a `.Trash-<uid>` folder at the top of another filesystem.
Where it cannot (no permission to create that folder), a trash folder in the data directory is
used instead. On a server nobody empties the trash, so the settings page names the location and
offers permanent deletion.

**Path safety** is one function every operation calls (`library/safety.py`): components are
validated (no `..`, no separators, no control characters, no Windows-reserved names, no trailing
dot or space), and the result must stay inside the root. By default a symlink leaving the root is
refused and such folders are hidden from listings; `library.follow_symlinks` opens them, keeps the
path relative to the root, and walks a loop of links only once. Nothing is ever overwritten: a
clash raises `ConflictError`, and callers may ask for an automatic numeric suffix.

## 8. Downloads

One `DownloadManager` owns a queue and worker threads, shared by the CLI and the API. States:
`queued → running → completed`, plus `paused`, `failed`, `cancelled`. Jobs are persisted, and jobs
left `running` by a crash become `paused` (HTTP) or `failed` (hub) at the next start, so a restart
never silently repeats a download.

**HTTP downloads** (`downloads/http_downloader.py`):

The shared client in `core/net/http.py` inspects the HTTPX constructor to select `proxies`
for older releases such as 0.24.1 and `proxy` when supported (0.26+); 0.28 removed `proxies`.
Keep both parameter paths covered when changing proxy setup.

1. Resolve the URL immediately before each attempt — Civitai's links expire.
2. Stream into `<name>.part`, following redirects; take the name from `Content-Disposition` and
   sanitise it.
3. Resume with `Range`, sending `If-Range` when the source gives an `ETag`. Civitai sends none, so
   there a resume is only attempted when the total size still matches, with the SHA256 check as
   the backstop. A 200 answer to a range request restarts from zero.
4. Hash while streaming; a mismatch fails the job and removes the partial file.
5. Rename atomically; never overwrite unless the job says so.
6. Then write the preview and the sidecars, and fill the detection cache.
7. Retry transient failures with backoff, honouring 429 and `Retry-After`. A 401 gets one
   credential renewal and one retry.

Creating a download that matches a paused or failed HTTP job — same source file or URL, same
folder — resumes that job instead of making a second one, so re-running a command after Ctrl+C
continues from the `.part` file.

**Hub downloads** run in a **child process** (`core/hubs/worker.py`) because raising from either
library's progress hook does not stop the transfer: Hugging Face's default path ran to completion,
and ModelScope treated it as a network failure, retried, and then returned normally. Cancelling
means terminating that process. Consequences, all implemented:

- **No pause and no resume for hub jobs** — neither library resumes into `local_dir`. The UI
  offers cancel and restart and says a restart begins from zero. `can_pause` is false and pausing
  returns 409.
- After a cancel or a failure, delete the leftovers: `*.incomplete` under
  `<local_dir>/.cache/huggingface/download/` and `<name>.incomplete` beside the target.
- **Never trust a normal return:** check every expected file exists with its expected size.
  ModelScope returns cleanly even when a file failed.
- The worker removes its own directory from `sys.path` before importing, or `hubs/modelscope.py`
  shadows the real `modelscope` package.
- Progress comes from polling file sizes; the libraries' own hooks are too coarse.

Progress events are throttled to four per second per job. High-frequency values go to a Pinia
store, not the query cache.

## 9. Sources and hubs

Adapters normalise everything into `ModelSummary` / `ModelDetail` / `ModelVersion` / `ModelFile`,
and declare `capabilities` so the filter bar only offers filters that work.

- **Civitai** (`https://civitai.com/api/v1`): cursor pagination; `downloadUrl` answers 307 to a
  signed storage link; the token goes in `Authorization: Bearer`, never in a URL, and httpx drops
  it when the redirect leaves civitai.com; `GET /model-versions/by-hash/{sha256}` identifies a
  local file. Rate limits are undocumented, so honour 429 and `Retry-After`.
- **OpenModelDB:** one JSON file of upscalers, fetched once and cached, searched locally. Skip
  mega.nz and Google Drive links; verify the published SHA256.
- **GitHub Releases:** a curated repository list plus any `owner/repo` typed in; no search.
- **CivitAI Archive** is only a fallback for identifying a file Civitai no longer lists.
- All five HTTP sources answered byte-range requests when tested, so resume can be relied on;
  only Civitai sends no validator. Hugging Face states its limit in `ratelimit` headers (500
  requests per 300 seconds when measured). GitHub release assets carry no hash, so a download
  from there cannot be verified.
- **Do not try to add Tensor.Art, LibLib or SeaArt.** Their APIs run generation on their own
  servers; none offers model search or download, and an uploader can mark a model online-only.
  Unofficial direct-link tricks are not interfaces and must not be built on. Modelers, OpenXLab
  and WiseModel mainly host LLMs and each needs its own SDK: out of scope unless that changes.
- **Hugging Face and ModelScope** are repositories, not single files, so they have their own
  screen and adapter interface. Metadata goes over their REST APIs with the shared httpx client so
  the parent process never imports the heavy libraries; only the download worker does. ModelScope's
  default revision is `master`, and its list and file APIs live under different prefixes.

**Civitai authentication** has two methods that never replace each other:

- **manual**: a personal API token in settings or the environment. Works with no OAuth
  application; it is the default and must stay fully functional.
- **oauth**: Authorization Code with **PKCE (S256)** as a public client — no client secret is
  shipped or stored. `auth.civitai.oauth_client_id` must be set; without it the feature reports
  itself as unconfigured. The authorization service is `https://auth.civitai.com`, a fixed host
  kept apart from the model API, with `/api/auth/oauth/{authorize,token,userinfo,revoke}`. The
  scope is the bitmask `5` (`UserRead | ModelsRead`), which covers browsing and downloading; ask
  for more only when an actual call needs it. Access tokens last about an hour and refresh
  tokens about thirty days, but the values from the token response are what count. Device Flow
  exists as a later option for remote or CLI-only use; it is not implemented. Transactions are single-use, live five minutes, and are bound to the
  browser that started them by an HttpOnly, SameSite=Lax cookie. Tokens go to the OS credential
  store when available, else an owner-only file. They refresh a minute before expiry, once even
  across threads and processes (file lock), and the rotated pair is stored whole.

The method changes only when the user saves a manual token, completes an authorization, or asks
explicitly. **A failure, a disconnection or an expiry must never switch method** — the other
credential may belong to a different account. An environment override wins over both, and the UI
says so while it applies.

## 10. API

- One router per resource under `/api/v1`, explicit `operation_id`, pydantic models in and out.
- Routes that touch disk or database are plain `def` so they run in the thread pool.
- The OpenAPI schema also carries the socket event models, so the UI types push and REST from one
  file. `scripts/generate_openapi.py` prints it without starting a server; the generated
  `schema.d.ts` is committed and `dev.py typegen-check` fails when it is stale.
  FastAPI's built-in schemas also affect this file: 0.141.1 includes optional `input` and `ctx`
  fields on `ValidationError` that 0.117.1 omits. When CI reports a generated-type diff, match
  its FastAPI/Pydantic versions before regenerating; API code need not have changed.
- Records that cross the boundary inherit `core/record.py`, which marks defaulted fields as
  required in the output schema so generated types match what the server actually sends.
- **Uploads** (`PUT /api/v1/library/upload`) take the raw request body, not multipart, and stream
  straight into a `.part` file. Nothing is spooled to a temporary directory.
- **socket.io** is mounted at `/ws` (path `/ws/socket.io`); traffic is server to client only. REST
  stays the source of truth: events invalidate or patch the cache, and a reconnect refetches.
- **Security:** the default host is `127.0.0.1`. The `Host` header is checked against the bound
  host, which blocks DNS rebinding. A state-changing request whose `Origin` names another site, or
  whose `Sec-Fetch-Site` says cross-site, is refused; a request with neither header cannot come
  from a browser page and is allowed. A non-loopback host requires `server.access_token` on every
  request and on the socket handshake (bearer header, `sd_model_hub_token` cookie or `?token=`).
  The only exemption is the OAuth callback — exactly that path with GET — because the browser
  arrives from Civitai with no header; it is still validated against the transaction and the Host.
- **Serving the built UI:** the folder is found through `sd_model_hub.webui.__path__`, so a
  source checkout and an installed wheel both work with no configuration. The mount is
  registered last, after every API route and the socket. A missing `dist/` is a warning, not an
  error — that is the normal state while working on the back end. `index.html` is never cached,
  so a browser cannot pair an old UI with a new server, while hashed files under `assets/` are
  cached for a year. An unknown path falls back to `index.html` only when the request accepts
  HTML, so a mistyped asset or API path still gets a 404.
- The server binds the listening socket itself and hands it to uvicorn, so the port that was
  tested is the port that serves. It moves up on collision unless `server.strict_port`, prints
  `SERVER_READY url=…` on stdout, and writes `server.json` in the data directory.

## 11. Web UI

Vue 3 + Vite + TypeScript, Pinia, TanStack Vue Query, `openapi-fetch` with generated types,
socket.io-client, Lucide icons, `@material/web` wrapped inside `src/ui/`. Hash-history routing, so
one build works under any sub-path; the API base URL is derived from the running script's URL,
and Vite's `base` is `'./'` so assets resolve wherever the app is mounted. Fonts and icons are
bundled: nothing is fetched from a third-party origin at run time, except preview images, which
load straight from each source's CDN.

Material Design 3 in two layers. Colour roles are generated from one source colour with
`@material/material-color-utilities` (Tonal Spot, light and dark, contrast level) and written to
`:root` as `--md-sys-color-*`. Static tokens live in `src/theme/tokens.css`: the 15 type styles,
shape radii (4, 8, 12, 16, 28, full), elevation by surface tone first, motion durations
(short 50–200, medium 250–400, long 450–600 ms) and easings (emphasized
`cubic-bezier(0.2, 0, 0, 1)`, decelerate `cubic-bezier(0.05, 0.7, 0.1, 1)`, accelerate
`cubic-bezier(0.3, 0, 0.8, 0.15)`), and state layers — **hover 8%, focus 12%, pressed 12%,
dragged 16%** (Google's token files say 12%, not the 10% some pages show). Spacing is a 4px base
unit, mostly in steps of 8.

One motion system in `src/ui/motion/`: `fade-through` between screens, `shared-axis-x` for folders
and tabs, `container` for card-to-dialog, `sheet` for drawers, `list` for grids (20 ms stagger,
capped), `collapse`, `snackbar`. Under `prefers-reduced-motion` everything becomes a short fade and
ripples are off. Navigation follows the window size classes: bottom bar below 600 px, rail above.

Preferences (theme, source colour, contrast, language, last source and root, view mode) are client
state: `localStorage` plus the server's client-state endpoint, with an early script in
`index.html` applying the theme before the bundle loads to avoid a flash.

In development, Vite proxies `/api`, `/openapi.json` and `/ws`. Proxy failures that mean "the API
server is restarting" (ECONNRESET, ECONNREFUSED, EPIPE…) are collapsed into one throttled line by
a custom logger; everything else is still printed in full.

## 12. Embedding in another application

`sd_model_hub/embed.py` is the public façade, re-exported lazily from the package so
`sd-model-hub version` does not pay for FastAPI:

```python
from sd_model_hub import ModelHubServer, ModelRoot

hub = ModelHubServer(data_dir=..., settings_path=..., model_roots=[ModelRoot(path, layout="comfyui")],
                     lock_model_roots=True, port=0, api_prefix="/tools/model-hub", settings={...})
url = hub.start()   # non-blocking, returns the URL; hub.run() blocks; it is a context manager too
hub.stop()
```

How each part works, so it stays that way:

- **Pinned settings.** `SettingsService(overrides=…)` holds a layer above the file and the
  environment that is never written back, so `settings={...}` and locked `model_roots` cannot be
  changed through the API. `build_services(settings_overrides=…, roots_locked=…)` passes them on.
- **Locked roots.** `LibraryService.roots_locked` makes add, update and remove raise
  `ConflictError`; `GET /app/meta` reports `roots_locked` and the interface hides the actions.
  Unlocked roots are merely seeded at start-up, so the user may add their own.
- **Ports.** `port=0` binds any free port; a number moves up on collision unless `strict_port`.
  The socket is bound before the app starts, so the port that was tested is the one served.
- **Prefix.** `create_app(api_prefix=…)` moves the API, the socket and the static UI under one
  path. The web UI needs no change: it derives its base URL from its own script's URL. Security
  paths (public health, the OAuth callback exemption, protected prefixes) are built from the
  prefix, and the OAuth redirect and callback URL include it.
- **Lifecycle.** `start()` runs uvicorn in a thread and waits for `server.started`; `stop()` sets
  `should_exit`, joins, closes the socket and the services, and is safe to call twice.

## 13. Testing

Both suites run offline. `python scripts/dev.py check` must pass before you call a change done.

- **Python (pytest):** detection against real saved headers plus synthetic ones; path safety
  (traversal, absolute paths, symlink escapes, reserved names, clashes); library operations in a
  temporary directory (companions follow, nothing is overwritten); the download manager against
  `httpx.MockTransport` (redirects, `Content-Disposition`, range resume, hash mismatch, 429,
  cancel mid-stream, pause and resume, crash recovery); source and hub parsing from recorded
  responses; the five port cases; OAuth (PKCE, every refusal, refresh, rotation, concurrency,
  revocation, the manual/OAuth matrix, no credential in any response); the API with `TestClient`;
  the CLI with `CliRunner`, including a snapshot of the whole command tree; the architecture rule.
- **Web (vitest + vue-tsc):** the base-URL helper, `ui/` components, theme generation, i18n,
  formatting, the no-literal-colours rule, the dev proxy filter.
- Tests that need the network are marked `live` and deselected by default.
- When you fix a bug, add the test that would have caught it.

## 14. Invariants worth keeping

- `core` imports no web or CLI framework; the API and CLI stay thin.
- Never unpickle a model file. Never copy code from ComfyUI (GPL-3.0).
- Never overwrite a user's file silently; never delete outside a root.
- A credential is never returned to a client, written into a job record, logged, or sent to a host
  other than the one it belongs to.
- Text from a source (a model description, a README) is rendered as text, never as HTML.
- `websockets` stays a declared dependency: uvicorn speaks WebSocket only with it or `wsproto`,
  and without one the socket silently drops to long polling.
- Manual API tokens keep working with no OAuth configured, and nothing switches authentication
  method by itself.
- Hub downloads cannot pause; do not add a pause button that promises otherwise.
- The generated `schema.d.ts` is committed and regenerated whenever the API changes.
- A host application's pinned settings and locked model folders cannot be overridden from the UI,
  the API or the command line.
- An anchored menu renders at the end of the document, never inside a card or row that clips it.

## 15. Known gaps

- No Civitai OAuth application is registered, so OAuth is unconfigured by default and the real
  authorization, refresh, revocation and authenticated download paths are untested. Device Flow is
  not implemented.
- Civitai downloads of login-gated files were never tried with a real token, and no complete
  Civitai file was ever downloaded end to end (they run to hundreds of megabytes). The flow is
  covered by a mock test, including the token being dropped on the redirect to storage.
- ControlNet, embedding and upscaler detection rules have only synthetic fixtures.
- hf-mirror and Gitee AI endpoints were never tested from a network that needs them.
- Drag-and-drop upload is covered at the API level, not by dropping a file in a real browser.
- The Windows credential store, and the app on Windows generally, is untested.
- The root `LICENSE` is the GPLv3 text copied from `sd-webui-all-in-one`.
- **Before the first release:** the project has no `license` or `urls` metadata, and publishing
  needs the `TWINE_PASSWORD` secret plus the `pypi` environment. The
  name `sd-model-hub` was free on PyPI when last checked.
- "Select similar models" from the original plan is implemented as filters for kind and base
  model; nobody has confirmed that is what was meant.
