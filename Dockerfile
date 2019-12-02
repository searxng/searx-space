FROM python:3.7-slim-buster

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
    firefox-esr wget git build-essential python3-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev \
    tini \
 && pip3 install --upgrade pip \
 && pip3 install --no-cache -r requirements.txt \
 && apt-get -y purge build-essential python3-dev libxslt1-dev zlib1g-dev \
 && apt-get -y --no-install-recommends install libxslt1.1 libxml2 zlib1g libffi6 libssl1.1 \
 && apt-get -y autoremove \
 && apt-get -y clean

COPY --chown=searxstats:searxstats . /usr/local/searxstats

RUN /usr/local/searxstats/utils/install-geckodriver /usr/local/bin \
 && mkdir /usr/local/searxstats/cache \
 && chown searxstats:searxstats /usr/local/searxstats/cache

USER searxstats
ENTRYPOINT [ "/usr/bin/tini", "--", "python3", "-msearxstats" ]
