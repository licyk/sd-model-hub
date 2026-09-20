# SD Model Hub

Download and manage Stable Diffusion models, from the command line or a web UI.

- **Browse** Civitai, OpenModelDB and GitHub Releases, and download with resume, SHA256
  checks, preview images and metadata sidecars.
- **Hubs:** download files or whole repositories from Hugging Face (or a mirror such as
  hf-mirror) and ModelScope.
- **Library:** point SD Model Hub at your ComfyUI or Stable Diffusion WebUI model folders. It
  identifies each model's type and base model from the safetensors header (never unpickling
  anything), shows previews, and imports, moves, renames and deletes models together with
  their preview images and sidecar files. Drag files into the browser to upload them.

The design, the conventions and the known gaps are in [AGENTS.md](AGENTS.md).

## Install

```bash
pip install .            # from a checkout; see "Building" for the web UI
sd-model-hub --help
```

Python 3.10 or newer. The web UI is bundled into the package; users do not need Node.

## Command line

```text
sd-model-hub
├── webui                      start the server and open the web UI
├── version | env
├── config  show | get | set | path
├── source  list
├── auth    status | use <manual|oauth> | connect | disconnect
├── search <query>             --source --kind --base-model --sort --limit
├── info <source> <model-id>
├── download
│   ├── model <source> <model-id>    --version --file --root --dir --to
│   ├── url <url>                    --to --sha256 --name
│   ├── hf <repo-id>                 --revision --include --exclude --to
│   └── modelscope <repo-id>         --revision --include --exclude --to
└── library
    ├── root list | add | remove
    ├── list [path]            --root --recursive --kind
    ├── info <path>            --hash
    ├── identify <path>
    ├── scan                   --root
    ├── import <paths...>      --root --to --move --rename
    ├── move <src...> <dst>
    ├── rename <path> <new-name>
    └── delete <paths...>      --permanent --yes
```

Every listing command accepts `--json`, which prints the same records the API returns.
`--debug` works at every level. Errors exit with a code per kind: 2 not found, 3 conflict,
4 invalid path or input, 5 needs a token, 6 upstream failure.

Examples:

```bash
sd-model-hub library root add ~/ComfyUI/models --layout comfyui
sd-model-hub library list ~/ComfyUI/models/loras --recursive --kind lora
sd-model-hub search "detail tweaker" --kind lora --base-model "SDXL 1.0"
sd-model-hub download model civitai 122359           # into the layout's LoRA folder
sd-model-hub download hf stabilityai/sdxl-turbo --include "*.safetensors" --to ./sdxl-turbo
sd-model-hub config set sources.civitai.token <token>
sd-model-hub webui --port 7865
```

Ctrl+C during an HTTP download pauses it and keeps the `.part` file; running the same command
again resumes. Hub downloads cannot pause (neither library resumes), so Ctrl+C cancels them.

## Embedding in another application

```python
from sd_model_hub import ModelHubServer, ModelRoot

hub = ModelHubServer(
    data_dir="./hub-data",                   # database and caches
    settings_path="./my-app/model-hub.toml", # the settings file, wherever you want it
    model_roots=[ModelRoot("/srv/models", layout="comfyui", name="Models")],
    lock_model_roots=True,                 # the user cannot add, change or remove folders
    port=0,                                # any free port; a number asks for that one
    api_prefix="/tools/model-hub",         # keeps our routes clear of yours
)

url = hub.start()      # returns as soon as it is listening, e.g. http://127.0.0.1:54123/tools/model-hub
...
hub.stop()
```

| Option | Effect |
| --- | --- |
| `data_dir` | Where the database, caches and (by default) the settings file live |
| `settings_path` | The settings file on its own, apart from `data_dir` |
| `model_roots` | Folders of models, each with its own `layout`: `comfyui`, `sd-webui` or `custom` |
| `lock_model_roots` | Fixes them: the API refuses changes and the interface hides those actions |
| `port` | `0` any free port, a number for that one (moving up unless `strict_port`), `None` for the configured one |
| `api_prefix` | Serves the API, the socket and the web UI under one path |
| `settings` | Pins any other setting, e.g. `{"downloads": {"verify_hash": False}}`; pinned values cannot be changed in the UI |
| `host`, `access_token`, `open_browser`, `log_level` | As for the command line; a non-loopback host requires a token |

`hub.start()` is non-blocking and returns the URL; `hub.run()` serves in the foreground;
`with ModelHubServer(...) as hub:` does both ends. `hub.services` exposes the library, downloads
and settings for direct use, and `hub.url`, `hub.port` and `hub.running` describe the server.

The command line can also take the prefix: `sd-model-hub webui --api-prefix /tools/model-hub`.

## Settings

Settings live in `settings.toml` in the data directory (`sd-model-hub config path`). Any setting
can be overridden with an environment variable: `SD_MODEL_HUB_<GROUP>__<FIELD>`, for example
`SD_MODEL_HUB_SERVER__PORT=8000` or `SD_MODEL_HUB_NETWORK__PROXY=http://127.0.0.1:7890`.
`SD_MODEL_HUB_DATA_DIR` moves the data directory. Tokens are never returned by the API.

The server listens on `127.0.0.1` by default. To listen on another address, set
`server.access_token` first; every request then needs it.

### Civitai authentication

Two ways, side by side. Neither replaces the other, and nothing switches between them by itself.

**A personal API token** (the default, and all most people need):

```bash
sd-model-hub config set sources.civitai.token <token>       # or SD_MODEL_HUB_SOURCES__CIVITAI__TOKEN
```

**A connected account** (OAuth, Authorization Code with PKCE). It needs an OAuth application
registered with Civitai, because the client id identifies *this installation*:

```bash
sd-model-hub config set auth.civitai.oauth_client_id <client id>
sd-model-hub webui        # then Settings → Civitai authentication → Connect
sd-model-hub auth status  # which credential is in use, and where it is kept
```

Register the callback with Civitai exactly as the server uses it, by default
`http://127.0.0.1:7865/api/v1/auth/civitai/callback`. On another port or host, or when working
on the UI with the Vite dev server, list the exact URLs:

```bash
sd-model-hub config set auth.civitai.redirect_uris '["http://127.0.0.1:7865/api/v1/auth/civitai/callback", "http://localhost:5173/api/v1/auth/civitai/callback"]'
```

Tokens stay on the server: in the operating system's credential store when there is one, else a
file in the data directory readable only by you. They are never in `settings.toml`, never sent
to the browser, and never written into download records. Access tokens are refreshed about a
minute before they expire, once even if several downloads ask at the same time, and the rotated
pair is stored as a whole. `sd-model-hub auth disconnect` revokes the authorization and forgets
it locally, leaving any API token untouched.

An environment variable takes precedence over both, and the settings page says so while it does.

### Symbolic links

A model folder whose contents are symbolic links to another disk — as a WebUI install often has
for its LoRAs — needs one setting, because links that leave the model folder are refused by
default:

```bash
sd-model-hub config set library.follow_symlinks true
```

It is also in Settings, under Content & Library. With it on, linked folders open and keep the
path you navigate with; deleting, moving and renaming then act on the files where they really
are. Paths containing `..`, absolute paths and reserved names are still refused in either mode,
and a folder reached twice through a loop of links is walked once.

## Files SD Model Hub writes next to a model

| File | Purpose |
| --- | --- |
| `<name>.sdmodelhub.json` | Source metadata: model and version ids, base model, trigger words, SHA256 |
| `<name>.preview.<ext>` | Preview image, found by the WebUI's own lookup |
| `<name>.json` | Only when `downloads.write_webui_metadata` is on, and only if absent: the WebUI's user metadata |

## Development

```bash
pip install -e ".[dev]"
python scripts/dev.py              # list the developer tasks
python scripts/dev.py dev          # API server and web UI together, with hot reload
python scripts/dev.py check        # what CI runs: lint, tests, generated types
python scripts/dev.py test         # pytest, vitest and vue-tsc
python scripts/dev.py format       # ruff fixes and formatting
python scripts/dev.py typegen      # regenerate src/api/schema.d.ts from the OpenAPI schema
```

`dev` is the one to use while working on the UI: it starts the API server and the Vite dev
server together, tags each line of output with `api` or `web`, and stops both on Ctrl+C. Open
the address it prints (http://localhost:5173 by default); Vite proxies `/api` and `/ws` to the
API server, so one address serves both and the UI hot-reloads.

While the API server is restarting, the page's socket reconnects on its own and the proxy says
so once:

```text
[api proxy] http://127.0.0.1:7865 is not answering (ECONNREFUSED). Start it with: sd-model-hub webui --no-open
```

Data reappears by itself once the server is back; there is no need to reload the page.

```bash
python scripts/dev.py dev --api-port 8000 --web-port 3000 --data-dir ./dev-data
python scripts/dev.py web-dev      # only the UI, against an API server you started yourself
sd-model-hub webui --no-open       # only the API server
```

The tasks are a small Python script rather than a Makefile, so they work the same on Windows.
Each one prints the command it runs, so the underlying tools stay easy to call directly.

The web UI uses [bun](https://bun.sh). Layers: `sd_model_hub/core` holds all logic and imports
no web or CLI framework (a test enforces it); `sd_model_hub/api` (FastAPI) and `sd_model_hub/cli`
(Typer) are thin wrappers over it.

Detection rules are JSON files in `sd_model_hub/core/detection/rules_data/`. To add a test
fixture from a real file: `python scripts/extract_header_fixture.py <file> <name>`.

## Building

```bash
python scripts/build_wheel.py            # web UI with bun, then the wheel and sdist into dist/
python scripts/build_wheel.py --ci       # for CI: skips the type-check, keeps the built web UI
python scripts/build_wheel.py --outdir out --keep-web-dist
python scripts/dev.py wheel              # the same, through the task runner
```

A bare `python -m build` produces a wheel without the web UI, because setuptools packages only
the files that exist when it runs; the server then logs a warning and serves the API only.

## Releasing

`.github/workflows/release.yml` publishes to PyPI when a version tag is pushed:

```bash
python scripts/dev.py check                 # first, locally
# bump VERSION in sd_model_hub/version.py, commit
git tag v0.1.0 && git push origin v0.1.0
```

The workflow runs the tests on Python 3.10 to 3.13, the web UI tests and type-check, and the
generated-types check; then it verifies that the tag matches `sd_model_hub/version.py`, builds
the wheel **with the web UI in it**, checks the wheel really contains the UI and the detection
rules, installs it into a clean environment and runs `sd-model-hub version`. Only then does it
publish and create the GitHub release with the built files attached.

**Run workflow** in the Actions tab publishes to TestPyPI instead, so a release can be rehearsed.

Set-up, once: on PyPI add a *trusted publisher* for this repository with workflow
`release.yml` and environment `pypi` (and the same on TestPyPI with environment `testpypi`),
then create those two environments in the repository settings. No API token is stored anywhere;
the environments can also require an approval before a release goes out.
