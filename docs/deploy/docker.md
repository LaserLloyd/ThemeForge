# Running ThemeForge in Docker

ThemeForge is a CSS package, not an application: you install it into your own
app by copying the `ui-theme/` folder (see the README's Quick start). The
container exists for one job: **serve the specimen page**, which shows every
component in every theme, so you can look at it without installing anything.

```bash
git clone https://github.com/LaserLloyd/ThemeForge.git && cd ThemeForge        # scrub-ok: public repo URL  (or: git pull)
docker compose -f deploy/compose/compose.yml up -d
# open http://127.0.0.1:8185/   (redirects to /specimen/)
```

To use ThemeForge in an app, do **not** use this image: follow the Quick start
(`update.py --dest static/ui-theme`), or point an AI agent at `AGENTS.md`.

## Ports

| Port | Where | What |
|---|---|---|
| 8080 | inside the container | nginx (unprivileged, UID 101) |
| 8185 | host, `${BIND_ADDR:-127.0.0.1}:${HOST_PORT:-8185}` | the specimen preview |

Routes: `/` redirects to `/specimen/`; `/specimen/` is the page; `/ui-theme/` is
the package it loads; `/healthz` answers `ok` (used by the container
healthcheck).

## Configuration

Optional environment (for example in a `deploy/compose/.env` next to
`compose.yml`; there is nothing secret here):

| Variable | Default | Meaning |
|---|---|---|
| `HOST_PORT` | `8185` | host port |
| `BIND_ADDR` | `127.0.0.1` | host interface; `0.0.0.0` publishes to your network |
| `IMAGE` | `themeforge-preview:local` | image reference |
| `VERSION` | `dev` | version label baked into the image |
| `MEM_LIMIT` / `CPU_LIMIT` | `64m` / `0.5` | resource limits |

No volumes: the page is static and the image is stateless.

## Hardening

Non-root (UID 101), read-only root filesystem with a `tmpfs` at `/tmp`, all
capabilities dropped, `no-new-privileges`, bounded logs, memory and CPU
limits. The build context is an allow-list (`.dockerignore`): only
`specimen/` and `ui-theme/` enter the image.

## Your data

There is none to lose. The image is stateless and its root filesystem is
read-only; it declares no volume and no bind mount, so updating, recreating or
removing it (`down`, `down -v`) cannot touch anything of yours. The themes you
actually use live in your own apps' `ui-theme/` folders, not here. There is
therefore nothing to back up, no `PUID`/`PGID` setting, and the unprivileged
user (UID 101) never writes to a mounted path.

## Upgrading and removal

```bash
git pull && docker compose -f deploy/compose/compose.yml up -d --build
docker compose -f deploy/compose/compose.yml down
```

A theme edit needs a rebuild (`--build`); the files are copied into the image,
not mounted. For live editing while you work on ThemeForge itself, use
`python3 -m http.server` from the repository root and open `/specimen/`
instead.
