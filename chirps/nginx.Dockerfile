ARG NGINX_IMAGE=nginx:alpine
FROM ${NGINX_IMAGE}

ARG INTERFACE_STORE=/opt/interface

COPY ./interface/static ${INTERFACE_STORE}/static
COPY ./configs/nginx.conf /etc/nginx/nginx.conf

