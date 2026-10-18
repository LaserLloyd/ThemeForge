# syntax=docker/dockerfile:1.7
# =============================================================================
#  ThemeForge - specimen preview image
# =============================================================================
#  ThemeForge is a CSS package, not an app: it is installed into other apps by
#  copying the `ui-theme/` folder. This image only serves the specimen page
#  (every component in every theme) so "every repo runs in Docker" holds and
#  you can look at the themes without installing anything.
#
#  Build:   docker build -t themeforge-preview:dev .
#  Run:     docker compose -f deploy/compose/compose.yml up -d     -> http://127.0.0.1:8185/
#
#  No build step exists, so there is no builder stage (unlike the Python apps):
#  the image is the nginx base plus the two folders the page needs
#  (specimen/index.html loads ../ui-theme/*), in their relative layout; the
#  allow-list in .dockerignore keeps everything else in the repository out.
#
#  nginx-unprivileged runs as UID 101 and listens on 8080 inside the container
#  (no privileged port, no root). The root filesystem can be read-only (the
#  compose file does that); nginx writes only to /tmp.
# =============================================================================

FROM nginxinc/nginx-unprivileged:1.28-alpine-slim AS runtime

ARG VERSION=dev
ARG REVISION=unknown
ARG CREATED

LABEL org.opencontainers.image.title="ThemeForge specimen" \
      org.opencontainers.image.description="Static preview of every ThemeForge component in every theme" \
      org.opencontainers.image.source="https://github.com/LaserLloyd/ThemeForge" \
      org.opencontainers.image.documentation="https://github.com/LaserLloyd/ThemeForge/blob/main/docs/deploy/docker.md" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.created="${CREATED}"

# One server block, written inline so the repository needs no extra files:
#   /            -> redirect to /specimen/
#   /specimen/   the page          /ui-theme/   the package it loads
#   /healthz     200 "ok" (for HEALTHCHECK; never cached)
COPY --chown=101:101 <<'NGINX' /etc/nginx/conf.d/default.conf
server {
    listen 8080 default_server;
    listen [::]:8080 default_server;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    # Redirects stay relative: the container listens on 8080 but is usually published on another
    # host port, and an absolute Location would send the browser to :8080 (another service).
    absolute_redirect off;

    # The specimen is a development preview: always revalidate (cheap 304s) so
    # an edited theme shows on the next reload.
    add_header Cache-Control "no-cache" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;

    # Relative redirects: the container's port (8080) differs from the published one.
    absolute_redirect off;

    location = / { return 302 /specimen/; }
    location = /healthz { access_log off; default_type text/plain; return 200 "ok\n"; }
    location / { try_files $uri $uri/ =404; }
}
NGINX

# Copied as the unprivileged user's own files; the paths keep the relative
# layout specimen/index.html expects (../ui-theme/ui-theme.js, ...).
COPY --chown=101:101 specimen/ /usr/share/nginx/html/specimen/
COPY --chown=101:101 ui-theme/ /usr/share/nginx/html/ui-theme/

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]

STOPSIGNAL SIGQUIT
