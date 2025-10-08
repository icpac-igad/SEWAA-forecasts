ARG PYTHON_VERSION=3.11

FROM alpine/git AS builder
ARG GAN_REPO=https://github.com/jaysnm/SEWAA-forecasts.git

RUN git clone --depth 1 ${GAN_REPO} /tmp/cgan


FROM python:${PYTHON_VERSION}-slim AS runner

# image build step variables
ARG USER_NAME=cgan
ARG USER_ID=1000
ARG GROUP_ID=1000
ARG WORK_HOME=/opt/cgan
ARG API_WORKERS=24



# install system libraries
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends git rsync ssh ca-certificates pkg-config \
    libgdal-dev libgeos-dev libproj-dev gdal-bin libcgal-dev libxml2-dev libsqlite3-dev  \
    gcc g++ dvipng libfontconfig-dev libjpeg-dev libspng-dev libx11-dev libgbm-dev \
    libeccodes-dev libeccodes-tools curl && mkdir -p ${WORK_HOME}/.ssh ${WORK_HOME}/.local


RUN groupadd --gid ${GROUP_ID} ${USER_NAME} && \
    useradd --home-dir ${WORK_HOME} --uid ${USER_ID} --gid ${GROUP_ID} ${USER_NAME} && \
    chown -Rf ${USER_NAME}:${USER_NAME} ${WORK_HOME}

USER ${USER_NAME}
WORKDIR ${WORK_HOME}

COPY --from=builder --chown=${USER_ID}:root /tmp/cgan ${WORK_HOME}

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    python -m venv ${WORK_HOME}/.venv

ENV PATH=${WORK_HOME}/.local/bin:${WORK_HOME}/.venv/bin:${PATH} VIRTUAL_ENV=${WORK_HOME}/.venv WORK_HOME=${WORK_HOME} API_WORKERS=${API_WORKERS}

RUN uv sync

CMD ["fastapi", "run", "--proxy-headers", "--workers", ${API_WORKERS}]