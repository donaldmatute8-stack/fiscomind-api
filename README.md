# FiscoMind Railway API

API completa para integración con SAT incluyendo:
- Sincronización de CFDIs
- Emisión de facturas (servicio gratuito SAT)
- Cancelación de facturas
- Descarga de XML/PDF

## Variables de Entorno Requeridas

```bash
# Credenciales del Bot
TELEGRAM_BOT_TOKEN=your_token

# Vault Master Key (para encriptación)
VAULT_MASTER_KEY=your_32_byte_hex_key

# Railway asigna PORT automáticamente
PORT=8000
```

## Despliegue

1. Login en Railway: `railway login`
2. Enlazar proyecto: `railway link`
3. Deploy: `railway up`

## Endpoints

- `GET /` - Info
- `GET /health` - Health check
- `POST /sync` - Sincronizar con SAT
- `GET /dashboard` - Dashboard fiscal
- `GET /cfdis` - Lista CFDIs
- `GET /cfdis/<uuid>/xml` - Descargar XML
- `GET /cfdis/<uuid>/pdf` - Descargar PDF
- `POST /sat-free/emitir` - Emitir factura (gratuito)
- `POST /sat-free/cancelar` - Cancelar factura
- `GET /sat-free/descargar/<uuid>` - Descargar vía SAT# Deploy triggered: Mon May 11 22:31:31 CST 2026
