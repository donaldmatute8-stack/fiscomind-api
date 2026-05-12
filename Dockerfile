FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway asigna PORT automáticamente
ENV PORT=8080

EXPOSE 8080

# Usar el PORT de Railway
CMD gunicorn -w 2 -b 0.0.0.0:${PORT} app:app