FROM debian:bullseye-slim

ARG SEARX_GID=1005
ARG SEARX_UID=1005

ENV INITRD=no
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /usr/local/searxstats/

RUN addgroup --gid ${SEARX_GID} searxstats \
 && adduser --system -u ${SEARX_UID} --home /usr/local/searxstats --shell /bin/sh --gid ${SEARX_GID} searxstats \
 && chown searxstats:searxstats /usr/local/searxstats

COPY requirements.txt ./

RUN apt-get update \
 && apt-get -y --no-install-recommends install \
    wget git build-essential \
    python3 python3-pip python3-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev libyaml-dev python3-ldns \
    tor tini bzip2 firefox-esr \
 && pip install --upgrade pip setuptools wheel \
 && pip install --no-cache -r requirements.txt \
 && apt-get -y purge build-essential python3-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev libyaml-dev \
 && apt-get -y --no-install-recommends install libxslt1.1 libxml2 zlib1g libffi7 libssl1.1 \
 && apt-get -y autoremove \
 && apt-get -y clean \
 && mkdir /usr/local/searxstats/cache

COPY --chown=searxstats:searxstats . /usr/local/searxstats

RUN /usr/local/searxstats/utils/install-geckodriver /usr/local/bin

USER searxstats
ENTRYPOINT [ "/usr/bin/tini", "--", "/usr/local/searxstats/docker-entrypoint.sh" ]
