FROM python:3.11-slim

WORKDIR /app

# System deps for satcfdi
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev gcc g++ base64 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Vault credentials directory
ENV VAULT_DIR=/app/credentials
RUN mkdir -p ${VAULT_DIR}

# Data directory for CFDI cache
ENV DATA_DIR=/app/data
RUN mkdir -p ${DATA_DIR}

# Railway PORT
ENV PORT=8080

EXPOSE 8080

# Entry point script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Longer timeout for SAT polling (60s)
CMD ["/app/start.sh"]