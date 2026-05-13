#!/usr/bin/env python3
"""
FiscoMind Cron - Sincronización Automática
Se ejecuta cada día a las 6 AM para sincronizar CFDIs automaticamente.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fiscomind-cron")

# Constants
API_URL = os.environ.get(
    "FISCOMIND_API_URL", "https://fiscomind-api-production.up.railway.app"
)
USER_ID = os.environ.get("FISCOMIND_USER_ID", "marco_test")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data/users/marco_test"))


def run_sync():
    """Ejecuta sincronización automática"""
    try:
        import httpx

        logger.info("🔄 Iniciando sincronización automática...")

        # Sync recibidos (últimos 30 días)
        today = date.today()
        start_date = (today - timedelta(days=30)).isoformat()

        # Submit download request for received CFDIs
        resp = httpx.post(
            f"{API_URL}/sync",
            json={
                "date_start": start_date,
                "date_end": today.isoformat(),
                "tipo": "recibidos",
            },
            timeout=60,
        )

        if resp.status_code == 200:
            result = resp.json()
            request_id = result.get("id_solicitud")
            logger.info(f"✅ Sync recibidos submitida: {request_id}")

            # Wait for SAT processing (max 120s)
            for attempt in range(24):  # 24 attempts × 5s = 120s max
                time.sleep(5)
                check_resp = httpx.post(
                    f"{API_URL}/sync/check",
                    json={"id_solicitud": request_id},
                    timeout=30,
                )
                if check_resp.status_code == 200:
                    check_data = check_resp.json()
                    cfdis = check_data.get("cfdis", [])
                    if cfdis:
                        logger.info(f"✅ CFDIs recibidos descargados: {len(cfdis)}")
                        break
                    if check_data.get("error"):
                        logger.error(f"❌ Error sync: {check_data['error']}")
                        break

            # Sync emitidos
            resp_emitidos = httpx.post(
                f"{API_URL}/sync",
                json={
                    "date_start": start_date,
                    "date_end": today.isoformat(),
                    "tipo": "emitidos",
                },
                timeout=60,
            )

            if resp_emitidos.status_code == 200:
                result_emitidos = resp_emitidos.json()
                req_id_emit = result_emitidos.get("id_solicitud")
                logger.info(f"✅ Sync emitidos submitida: {req_id_emit}")

                for attempt in range(24):
                    time.sleep(5)
                    check_resp = httpx.post(
                        f"{API_URL}/sync/check",
                        json={"id_solicitud": req_id_emit},
                        timeout=30,
                    )
                    if check_resp.status_code == 200:
                        check_data = check_resp.json()
                        cfdis = check_data.get("cfdis", [])
                        if cfdis:
                            logger.info(f"✅ CFDIs emitidos descargados: {len(cfdis)}")
                            break

            # Log results
            log_result = {
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "details": "Sync automático completado",
            }
            log_file = DATA_DIR / "cron_log.json"
            with open(log_file, "w") as f:
                json.dump(log_result, f, indent=2)

            logger.info("✅ Sincronización automática completada")
            return True

        else:
            logger.error(f"❌ Error en sync: {resp.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ Error en cron: {e}", exc_info=True)
        return False


def check_alerts():
    """Verifica y genera alertas de cumplimiento"""
    try:
        import httpx

        # Get obligations
        resp = httpx.get(f"{API_URL}/obligaciones", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            obligations = data.get("obligaciones_pendientes", [])

            urgent = [o for o in obligations if o.get("dias_restantes", 999) <= 3]
            high = [o for o in obligations if 3 < o.get("dias_restantes", 999) <= 7]

            if urgent or high:
                alert_file = DATA_DIR / "alerts.json"
                with open(alert_file, "w") as f:
                    json.dump(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "urgentes": urgent,
                            "altas": high,
                        },
                        f,
                        indent=2,
                    )

                logger.info(
                    f"⚠️ Alertas generadas: {len(urgent)} urgentes, {len(high)} altas"
                )

        return True
    except Exception as e:
        logger.error(f"❌ Error en alertas: {e}")
        return False


def main():
    """Función principal del cron"""
    logger.info("=" * 60)
    logger.info("🚀 FiscoMind Cron iniciado")
    logger.info("=" * 60)

    # Create data directory if needed
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Run sync
    sync_result = run_sync()

    # Check alerts
    alert_result = check_alerts()

    if sync_result and alert_result:
        logger.info("✅ Tareas completadas exitosamente")
        sys.exit(0)
    else:
        logger.warning("⚠️ Algunas tareas fallaron")
        sys.exit(1)


if __name__ == "__main__":
    main()
