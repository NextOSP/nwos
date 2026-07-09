FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NWOS_CONFIG=/etc/nwos/nwos.conf

WORKDIR /opt/nwos

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        fonts-dejavu-core \
        git \
        libjpeg-dev \
        libldap2-dev \
        libpq-dev \
        libsasl2-dev \
        libxml2-dev \
        libxslt1-dev \
        node-less \
        npm \
        postgresql-client \
        wkhtmltopdf \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip wheel setuptools \
    && python -m pip install -r requirements.txt

COPY . .
RUN mkdir -p /etc/nwos /var/lib/nwos /var/log/nwos \
    && useradd --system --home /var/lib/nwos --shell /usr/sbin/nologin nwos \
    && chown -R nwos:nwos /var/lib/nwos /var/log/nwos /opt/nwos

COPY docker/nwos.conf /etc/nwos/nwos.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER nwos
EXPOSE 7073

ENTRYPOINT ["/entrypoint.sh"]
CMD ["server", "-c", "/etc/nwos/nwos.conf"]
