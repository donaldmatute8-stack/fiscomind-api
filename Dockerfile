FROM python:3.11-slim

WORKDIR /app

# System deps for satcfdi (lxml, weasyprint)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Vault credentials - set env var so secure_vault finds them
ENV VAULT_DIR=/app/credentials

# Data directory for CFDI cache
ENV DATA_DIR=/app/data
RUN mkdir -p ${DATA_DIR}

# Railway asigna PORT automáticamente
ENV PORT=8080

EXPOSE 8080

CMD gunicorn -w 2 -b 0.0.0.0:${PORT} app:app