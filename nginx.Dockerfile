ARG NGINX_IMAGE=nginx:alpine
FROM ${NGINX_IMAGE}

ARG INTERFACE_STORE=/opt/interface

COPY ./interface/static ${INTERFACE_STORE}/static
COPY ./configs/nginx.conf /etc/nginx/nginx.conf
# Must be executable: the nginx entrypoint skips non-executable scripts
COPY ./configs/40-web-proxy.sh /docker-entrypoint.d/40-web-proxy.sh
RUN chmod 755 /docker-entrypoint.d/40-web-proxy.sh

