#!/bin/sh
# Writes the `location /` block for configs/nginx.conf at container start (run by the
# nginx image's /docker-entrypoint.sh, like its other /docker-entrypoint.d scripts).
#
# WEB_UPSTREAM set (docker-compose: http://web:8000): proxy everything that isn't data or
# static files to the FastAPI interface (main.py).
# WEB_UPSTREAM unset (Cloud Run cgan-data-portal, which only serves data): `/` returns 404.
#
# A hardcoded `proxy_pass http://web:8000` would be resolved when nginx loads its config,
# so nginx would refuse to start anywhere a `web` host doesn't exist.
set -eu

SNIPPET_DIR=/etc/nginx/snippets
mkdir -p "$SNIPPET_DIR"

if [ -n "${WEB_UPSTREAM:-}" ]; then
  echo "$0: proxying / to ${WEB_UPSTREAM}"
  cat > "$SNIPPET_DIR/web-proxy.conf" <<EOF
location / {
    proxy_pass ${WEB_UPSTREAM%/}/;
    proxy_redirect off;
    proxy_set_header Host \$http_host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header X-Forwarded-Port \$server_port;
    proxy_pass_request_headers on;
}
EOF
else
  echo "$0: WEB_UPSTREAM not set; serving data only"
  cat > "$SNIPPET_DIR/web-proxy.conf" <<'EOF'
location / {
    return 404;
}
EOF
fi
