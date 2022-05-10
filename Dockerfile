FROM debian:buster-slim AS build

ENV BUILD_POETRY_VERSION=1.1.13

RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes python3-venv python3-pip && \
    pip3 install --upgrade pip && \
    python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip

RUN pip3 install poetry==$BUILD_POETRY_VERSION

FROM build AS build-venv

COPY . /app
WORKDIR /app

RUN poetry build --no-interaction -f wheel
RUN /venv/bin/pip install --disable-pip-version-check dist/*.whl

FROM gcr.io/distroless/python3-debian10

ENV INSIDE_DOCKER_CONTAINER=1

LABEL   maintainer="vzhd1701 <vzhd1701@gmail.com>" \
        org.opencontainers.image.title="evernote-backup" \
        org.opencontainers.image.description="Backup & export Evernote notes and notebooks" \
        org.opencontainers.image.authors="vzhd1701 <vzhd1701@gmail.com>" \
        org.opencontainers.image.licenses="MIT" \
        org.opencontainers.image.documentation="https://github.com/vzhd1701/evernote-backup" \
        org.opencontainers.image.url="https://github.com/vzhd1701/evernote-backup" \
        org.opencontainers.image.source="https://github.com/vzhd1701/evernote-backup.git"

COPY --from=build-venv /venv /venv

WORKDIR /tmp

ENTRYPOINT ["/venv/bin/evernote-backup"]

EXPOSE 10500
