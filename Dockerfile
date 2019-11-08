FROM python:3-alpine

ARG SEARX_GID=1005
ARG SEARX_UID=1005

WORKDIR /usr/local/searxstats/

RUN addgroup -g ${SEARX_GID} searxstats && \
    adduser -u ${SEARX_UID} -D -h /usr/local/searxstats -s /bin/sh -G searxstats searxstats

COPY requirements.txt ./

RUN apk -U upgrade \
&& apk add -t build-dependencies \
    build-base \
    py3-setuptools \
    python3-dev \
    libffi-dev \
    libxslt-dev \
    libxml2-dev \
    openssl-dev \
 && apk add \
    ca-certificates \
    su-exec \
    libxslt \
    libxml2 \
    openssl \
    tini \
    firefox-esr \
 && pip3 install --upgrade pip \
 && pip3 install --no-cache -r requirements.txt \
 && apk del build-dependencies \
 && rm -Rf /var/cache/apk/

COPY utils/install_geckodriver.sh /usr/local/bin
RUN /usr/local/bin/install_geckodriver.sh /usr/local/bin

USER searxstats
COPY . /usr/local/searxstats
ENTRYPOINT [ "/sbin/tini", "--", "python3", "-msearxstats" ]
