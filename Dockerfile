ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

# image build step variables
ARG USER_NAME=cgan
ARG USER_ID=1000
ARG GROUP_ID=1000
ARG WORK_HOME=/opt/cgan
ARG API_WORKERS=32

# install system libraries
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends rsync ssh git curl gcc g++ pkg-config \
    ca-certificates libgdal-dev libgeos-dev libproj-dev gdal-bin libcgal-dev libxml2-dev   \
    libsqlite3-dev dvipng libfontconfig-dev libjpeg-dev libspng-dev libx11-dev libgbm-dev \
    libeccodes-dev libeccodes-tools && mkdir -p ${WORK_HOME}/.ssh ${WORK_HOME}/.local


RUN groupadd --gid ${GROUP_ID} ${USER_NAME} && \
    useradd --home-dir ${WORK_HOME} --uid ${USER_ID} --gid ${GROUP_ID} ${USER_NAME} && \
    chown -Rf ${USER_NAME}:${USER_NAME} ${WORK_HOME}

USER ${USER_NAME}
WORKDIR ${WORK_HOME}

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    python -m venv ${WORK_HOME}/.venv

COPY --chown=${USER_ID}:root . ${WORK_HOME}/
COPY --chown=${USER_ID}:root ./configs/forecast.yaml ${WORK_HOME}/6h_accumulations/cGAN/dsrnngan
COPY --chown=${USER_ID}:root ./configs/forecast.yaml ${WORK_HOME}/24h_accumulations/cGAN/dsrnngan

ENV PATH=${WORK_HOME}/.local/bin:${WORK_HOME}/.venv/bin:${PATH} VIRTUAL_ENV=${WORK_HOME}/.venv WORK_HOME=${WORK_HOME} API_WORKERS=${API_WORKERS}

RUN uv sync --all-extras

CMD ["sh", "-c", "fastapi run --proxy-headers --workers ${API_WORKERS}"]