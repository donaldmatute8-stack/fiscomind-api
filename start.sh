#!/bin/bash
# Entry point para Railway - restaura vault key y arranca API

# Si existe VAULT_SYNC_KEY pero no existe .vault_key, crear el archivo
if [ -n "$VAULT_SYNC_KEY" ] && [ ! -f "/app/credentials/.vault_key" ]; then
    echo "🔐 Restaurando vault key..."
    echo "$VAULT_SYNC_KEY" | base64 -d > /app/credentials/.vault_key
    chmod 600 /app/credentials/.vault_key
    echo "✅ Vault key restaurado"
fi

# Asegurar que el directorio de datos existe
mkdir -p /app/data

# Arrancar la aplicación
exec gunicorn -w 2 -b 0.0.0.0:${PORT:-8080} --timeout 90 --keep-alive 5 app:app