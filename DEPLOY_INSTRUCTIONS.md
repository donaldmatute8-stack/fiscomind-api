# FiscoMind Railway API v3.0 - Deploy Instructions

## Estado Actual
✅ API preparada para deploy
✅ Dockerfile configurado  
✅ Código listo
❌ Token Railway no autorizado (necesita ser regenerado)

## Qué token necesito

Necesito un **"User Access Token"** con permisos FULL ACCESS.

### Pasos para crearlo:

1. Ve a: https://railway.app/account/tokens
2. Click **"New Token"**
3. Selecciona **"User Access Token"** (no Project Token)
4. Marca **"Full Access"** (permite deploys)
5. Copia el token y envíamelo

### Alternativa: Deploy manual

Si prefieres, puedes hacer el deploy tú mismo:

```bash
cd /Users/bullslab/.openclaw/agents/fisco-workspace/railway-api

# Login (esto abre navegador)
railway login

# Link al proyecto
railway link

# Deploy
railway up
```

## Qué hace esta API

- `/dashboard` - Dashboard fiscal completo
- `/sync` - Sincronizar con SAT
- `/cfdis` - Lista CFDIs (recibidos/emitidos)
- `/cfdis/<uuid>` - Detalle completo de cada CFDI
- `/emitidos` - Solo facturas emitidas
- `/emitir` - Emitir nueva factura (integración SAT)
- `/cancelar` - Cancelar factura
- Descarga XML/PDF por cada CFDI

## Después del deploy

1. Railway te dará una URL tipo: `https://fiscomind-api.up.railway.app`
2. Actualizo la mini app para usar esa URL
3. El sync funcionará desde cualquier dispositivo
4. Podrás ver detalles completos de cada factura