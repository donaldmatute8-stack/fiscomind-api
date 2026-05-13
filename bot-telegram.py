"""
FiscoMind Bot v3.0 - Railway API + HTML safe
Fix: can't parse entities error (escape all dynamic HTML)
"""

import os, json, logging, httpx
from datetime import date, timedelta, datetime
from html import escape as h

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    JobQueue,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
API = os.environ.get(
    "FISCOMIND_API_URL", "https://fiscomind-api-production.up.railway.app"
)
WEBAPP = os.environ.get("FISCOMIND_WEBAPP_URL", "https://fiscomind.vercel.app")

client = httpx.Client(base_url=API, timeout=30)


def api_get(path, **kw):
    try:
        return client.get(path, params=kw).json()
    except Exception as e:
        return {"error": str(e)}


def api_post(path, data=None):
    try:
        return client.post(path, json=data or {}).json()
    except Exception as e:
        return {"error": str(e)}


# ⏰ Morning Job - Pregunta cada mañana
async def morning_sync_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Envía recordatorio diario a las 7 AM"""
    job_data = context.job.data
    chat_id = job_data.get("chat_id")

    if not chat_id:
        return

    keyboard = [
        [InlineKeyboardButton("🔄 Sincronizar ahora", callback_data="morning_sync")],
        [InlineKeyboardButton("📊 Ver mi panorama", callback_data="panorama")],
        [InlineKeyboardButton("⏰ Recordar más tarde", callback_data="snooze")],
    ]

    await context.bot.send_message(
        chat_id=chat_id,
        text="☀️*¡Buenos días Marco!*\n\n"
        "¿Quieres sincronizar tus CFDIs del SAT ahora?\n\n"
        "_Última sincronización: Revisando..._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def setup_morning_jobs(application: Application):
    """Configura jobs automáticos"""
    # Buscar chat_id del usuario principal - asumimos marco_test por ahora
    # En producción esto debería leer de base de datos
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", None)

    if chat_id:
        # Recordatorio diario 7 AM
        job_queue = application.job_queue
        job_queue.run_daily(
            morning_sync_reminder,
            time=datetime.time(hour=7, minute=0),
            days=(0, 1, 2, 3, 4, 5, 6),  # Todos los días
            data={"chat_id": int(chat_id)},
            name="morning_sync",
        )

        # Alerta de vencimientos - 9 AM
        job_queue.run_daily(
            check_obligations_alert,
            time=datetime.time(hour=9, minute=0),
            days=(0, 1, 2, 3, 4, 5, 6),
            data={"chat_id": int(chat_id)},
            name="obligations_alert",
        )

        # Alerta urgente - 3 PM
        job_queue.run_daily(
            urgent_obligations_alert,
            time=datetime.time(hour=15, minute=0),
            days=(0, 1, 2, 3, 4, 5, 6),
            data={"chat_id": int(chat_id)},
            name="urgent_alert",
        )

        logger.info(f"✅ Jobs configurados para chat_id: {chat_id}")


async def check_obligations_alert(context: ContextTypes.DEFAULT_TYPE):
    """Alerta diaria de obligaciones fiscales"""
    job_data = context.job.data
    chat_id = job_data.get("chat_id")

    if not chat_id:
        return

    try:
        r = api_get("/obligaciones")
        obligations = r.get("obligaciones_pendientes", [])

        urgent = [o for o in obligations if o.get("dias_restantes", 999) <= 3]
        high = [o for o in obligations if 3 < o.get("dias_restantes", 999) <= 7]

        if urgent or high:
            text = "🔴 *ALERTAS FISCALES* 🔴\n\n"

            if urgent:
                text += "*🚨 URGENTE (≤3 días):*\n"
                for o in urgent:
                    text += f"• {h(o.get('titulo', ''))} - {o.get('dias_restantes', '?')} días restantes\n"
                text += "\n"

            if high:
                text += "*⚠️ PRÓXIMOS (4-7 días):*\n"
                for o in high:
                    text += f"• {h(o.get('titulo', ''))} - {o.get('dias_restantes', '?')} días restantes\n"
                text += "\n"

            text += "_Usa /obligaciones para ver detalles o /help para más opciones._"

            await context.bot.send_message(
                chat_id=chat_id, text=text, parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error en alerta: {e}")


async def urgent_obligations_alert(context: ContextTypes.DEFAULT_TYPE):
    """Alerta urgente de última hora (3 PM)"""
    job_data = context.job.data
    chat_id = job_data.get("chat_id")

    if not chat_id:
        return

    try:
        r = api_get("/obligaciones")
        obligations = r.get("obligaciones_pendientes", [])
        critical = [o for o in obligations if o.get("dias_restantes", 999) <= 1]

        if critical:
            text = f"⏰ *URGENTE - VENCE MAÑANA O HOY* ⏰\n\n"
            for o in critical:
                text += f"• {h(o.get('titulo', ''))}\n"
                text += f"  Vence: {o.get('vence', '')}\n"
                text += f"  Acción: {h(o.get('accion', ''))}\n\n"

            text += (
                "⚠️ *No olvides presentar tu declaración para evitar multas y recargos.*"
            )

            await context.bot.send_message(
                chat_id=chat_id, text=text, parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error en alerta urgente: {e}")


async def start(update: Update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🤖 \u003cb\u003eHola, soy FiscoMind\u003c/b\u003e 📊💰\n\n"
        "Tu contador AI inteligente para el SAT (desde 2022).\n\n"
        "\u003cb\u003e📌 Principales comandos:\u003c/b\u003e\n"
        "• /panorama - Tu situación fiscal completa\n"
        "• /declarar - Ayuda para declarar (ceros, normal, regularizar)\n"
        "• /baja - Suspensión temporal o definitiva\n"
        "• /sync - Sincronizar CFDIs con el SAT\n"
        "• /optimizar - Recomendaciones de ahorro fiscal\n"
        "• /proyeccion - ISR proyectado anual\n"
        "• /obligaciones - Ver obligaciones pendientes\n"
        "• /export - Exportar datos (CSV/PDF)\n"
        "\n"
        "\u003cb\u003e💡 Novedades 2026:\u003c/b\u003e\n"
        "• Alertas automáticas de vencimientos\n"
        "• Consultoría SAT 2026 legal\n"
        "• Detección de rezago de declaraciones\n"
        "\n"
        "\u003cb\u003e📱 Mini App:\u003c/b\u003e \u003ca href='"
        + WEBAPP
        + "'\u003eAbrir\u003c/a\u003e\n\n"
        "_Soy más inteligente que Konta. Me conecto al SAT en tiempo real._"
    )
    kb = [
        [InlineKeyboardButton("📊 Panorama", callback_data="panorama")],
        [InlineKeyboardButton("📋 Declarar", callback_data="declarar")],
        [InlineKeyboardButton("🔗 Suspender Baja", callback_data="baja")],
        [InlineKeyboardButton("🌐 Mini App", web_app=WebAppInfo(url=WEBAPP))],
    ]
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    kb = [
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="dash"),
            InlineKeyboardButton("📄 CFDIs", callback_data="cfdis"),
        ],
        [
            InlineKeyboardButton("📝 Factura", callback_data="factura"),
            InlineKeyboardButton("💡 Estrategia", callback_data="estrategia"),
        ],
        [
            InlineKeyboardButton("📅 Obligaciones", callback_data="oblig"),
            InlineKeyboardButton("🔒 Opinión SAT", callback_data="opinion"),
        ],
        [
            InlineKeyboardButton("📥 Sincronizar", callback_data="sync"),
            InlineKeyboardButton("🌐 Mini App", web_app=WebAppInfo(url=WEBAPP)),
        ],
    ]
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )


async def dashboard(update: Update, context):
    d = api_get("/dashboard")
    s = d.get("summary", {})
    text = (
        f"📊 <b>Dashboard Fiscal</b>\n\n"
        f"📥 Recibidos: {s.get('total_recibidos', 0)}\n"
        f"📤 Emitidos: {s.get('total_emitidos', 0)}\n"
        f"💰 Ingresos: ${s.get('total_ingresos', 0):,.2f}\n"
        f"💸 Egresos: ${s.get('total_egresos', 0):,.2f}\n"
        f"✅ Deducible: ${s.get('total_deducible', 0):,.2f}\n"
        f"💡 Ahorro ISR: ${s.get('ahorro_isr_estimado', 0):,.2f}\n\n"
        f"<i>Sync: {h(d.get('last_sync', 'Nunca'))}</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cfdis(update: Update, context):
    d = api_get("/cfdis")
    c = d.get("cfdis", [])
    if not c:
        await update.message.reply_text(
            "❌ No hay CFDIs. Sincroniza con SAT primero.", parse_mode="HTML"
        )
        return
    text = f"📄 <b>CFDIs ({len(c)})</b>\n\n"
    for x in c[:15]:
        icon = {"I": "📥", "E": "📤", "P": "💳"}.get(x.get("efecto", ""), "📄")
        st = "✅" if x.get("estatus") == "1" else "❌"
        text += f"{icon}{st} <b>${x.get('monto', 0):,.2f}</b> - {h(x.get('nombre_emisor', x.get('emisor', ''))[:30])}\n"
        text += f"   📅 {x.get('fecha_emision', '')}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def obligaciones(update: Update, context):
    d = api_get("/obligaciones")
    o = d.get("obligaciones_pendientes", [])
    r = d.get("resumen", {})
    if not o:
        await update.message.reply_text(
            "✅ Sin obligaciones pendientes.", parse_mode="HTML"
        )
        return
    text = "📅 <b>Obligaciones Fiscales</b>\n\n"
    for x in o:
        e = {
            "critical": "🔴",
            "high": "🟡",
            "overdue": "⛔",
            "normal": "🟢",
            "low": "⚪",
        }.get(x.get("urgencia", ""), "⚪")
        text += f"{e} <b>{h(x.get('titulo', ''))}</b>\n   Vence: {x.get('vence', '')} · {x.get('dias_restantes', '?')} días\n\n"
    text += f"Resumen: 🔴{r.get('criticas', 0)} 🟡{r.get('altas', 0)} 🟢{r.get('normales', 0)}"
    await update.message.reply_text(text, parse_mode="HTML")


async def opinion(update: Update, context):
    d = api_get("/opinion")
    if d.get("status") == "Positiva":
        await update.message.reply_text(
            "✅ <b>Opinión de Cumplimiento: POSITIVA</b>\nEstás al corriente con el SAT.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"📋 Opinión: {h(str(d.get('status', 'Error')))}\nPendientes: {d.get('pending_obligations', '?')}",
            parse_mode="HTML",
        )


async def estrategia(update: Update, context):
    d = api_get("/dashboard")
    s = d.get("summary", {})
    o = api_get("/obligaciones").get("obligaciones_pendientes", [])
    ing = s.get("total_ingresos", 0)
    egr = s.get("total_egresos", 0)
    ded = s.get("total_deducible", 0)
    ah = s.get("ahorro_isr_estimado", 0)
    text = (
        f"💡 <b>Estrategia Fiscal</b>\n\n"
        f"💰 Ingresos: ${ing:,.2f}\n"
        f"💸 Egresos: ${egr:,.2f}\n"
        f"✅ Deducible: ${ded:,.2f}\n"
        f"💡 Ahorro ISR: ${ah:,.2f}\n\n"
        f"<b>🎯 Recomendaciones:</b>\n\n"
    )
    if ded < ing * 0.10:
        text += "1. ⚠️ Deducciones bajas - revisa transporte, oficina, software\n\n"
    if ing > 0:
        text += f"2. IVA a cargo: ${ing * 0.16:,.2f}\n\n"
    text += "3. Evalúa Régimen Simplificado de Confianza (626)\n\n"
    crit = [x for x in o if x.get("urgencia") == "critical"]
    if crit:
        text += f"<b>🚨 Urgente:</b>\n"
        for x in crit:
            text += (
                f"• {h(x.get('titulo', ''))} - {x.get('dias_restantes', '?')} días\n"
            )
    await update.message.reply_text(text, parse_mode="HTML")


from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    InputFile,
)

# ─── Generación de factura inline (flujo conversacional) ───
EMITIR_FLOW = {}


async def cmd_export(update: Update, context):
    """Exporta datos reales como archivo descargable"""
    args = context.args or ["csv"]
    fmt = args[0].lower()
    if fmt not in ("csv", "pdf", "xlsx"):
        fmt = "csv"
    filters = {}
    if len(args) > 1:
        # /export csv 2026-05  -> mes
        filters["mes"] = args[1]
    if len(args) > 2:
        filters["anio"] = args[2]

    url = f"/export/{fmt}?"
    url += "&".join(f"{k}={v}" for k, v in filters.items())

    await update.message.reply_text(f"📤 Generando {fmt.upper()}...", parse_mode="HTML")

    try:
        r = client.get(url)
        if r.status_code == 200:
            filename = f"fiscomind_{fmt}_{date.today().strftime('%Y%m%d')}.{fmt if fmt != 'xlsx' else 'xlsx'}"
            buffer = io.BytesIO(r.content)
            buffer.name = filename
            if fmt == "csv":
                await update.message.reply_document(
                    document=InputFile(buffer, filename=filename),
                    caption="📄 CFDIs exportados",
                )
            elif fmt == "pdf":
                await update.message.reply_document(
                    document=InputFile(buffer, filename=filename),
                    caption="📊 Reporte fiscal",
                )
            else:
                await update.message.reply_document(
                    document=InputFile(buffer, filename=filename),
                    caption="📈 Resumen fiscal",
                )
        else:
            error = r.json().get("message", "Error")
            await update.message.reply_text(f"❌ Error: {error}", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error de conexión: {str(e)}", parse_mode="HTML"
        )


async def cmd_declarar(update: Update, context):
    """
    Genera borrador de declaración LISTO como archivo descargable.
    No solo instrucciones — el bot genera el PDF con tus datos reales.
    """
    args = context.args or []
    if not args:
        text = (
            "📋 <b>DECLARACIONES — BORRADOR REAL</b>\n\n"
            "Te genero un borrador con TUS DATOS del SAT:\n\n"
            "• /declarar ceros \u003e PDF listo para presentar en ceros\n"
            "• /declarar normal \u003e PDF con tus ingresos reales\n"
            "• /declarar regularizar \u003e Plan de regularización\n\n"
            "📎 El bot te envía el archivo, tú solo lo subes al SAT."
        )
        await update.message.reply_text(text, parse_mode="HTML")
        return

    tipo = args[0].lower()
    mes = (
        args[1]
        if len(args) > 1
        else (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    )

    await update.message.reply_text(
        f"📄 Generando borrador de {tipo} para {mes}...", parse_mode="HTML"
    )

    try:
        r = client.get(f"/declaracion/borrador/{tipo}?periodo={mes}")
        if r.status_code == 200:
            filename = f"borrador_{tipo}_{mes}.pdf"
            buffer = io.BytesIO(r.content)
            buffer.name = filename
            await update.message.reply_document(
                document=InputFile(buffer, filename=filename),
                caption=f"📎 Borrador de declaración {tipo}\nPeriodo: {mes}\n\n"
                f"<i>Presenta este borrador en el SAT con los datos aquí indicados.</i>",
                parse_mode="HTML",
            )
        else:
            error = r.json().get("message", "Error")
            await update.message.reply_text(f"❌ Error: {error}", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


async def emitir_start(update: Update, context):
    """Inicia flujo de emisión de factura"""
    chat_id = update.effective_chat.id
    EMITIR_FLOW[chat_id] = {"step": "rfc_receptor"}
    await update.message.reply_text(
        "📝 <b>CREAR FACTURA CFDI 4.0</b>\n\nPaso 1/5: Envíame el RFC del receptor:",
        parse_mode="HTML",
    )


async def emitir_handler(update: Update, context):
    """Maneja las respuestas del flujo de emisión"""
    chat_id = update.effective_chat.id
    flow = EMITIR_FLOW.get(chat_id)
    if not flow:
        return  # No está en flujo

    text = update.message.text
    step = flow.get("step")

    if step == "rfc_receptor":
        flow["rfc_receptor"] = text.strip().upper()
        flow["step"] = "nombre_receptor"
        await update.message.reply_text("Paso 2/5: Nombre del receptor:")
    elif step == "nombre_receptor":
        flow["nombre_receptor"] = text.strip()
        flow["step"] = "concepto"
        await update.message.reply_text("Paso 3/5: Concepto del servicio/producto:")
    elif step == "concepto":
        flow["concepto"] = text.strip()
        flow["step"] = "monto"
        await update.message.reply_text("Paso 4/5: Monto total (sin IVA):")
    elif step == "monto":
        try:
            flow["monto"] = float(text.replace(",", "").replace("$", ""))
            flow["step"] = "confirmar"

            # Preview
            preview = (
                f"📋 <b>Resumen de la factura:</b>\n\n"
                f"Receptor: {flow['nombre_receptor']}\n"
                f"RFC: {flow['rfc_receptor']}\n"
                f"Concepto: {flow['concepto']}\n"
                f"Monto: ${flow['monto']:,.2f}\n"
                f"IVA (16%): ${flow['monto'] * 0.16:,.2f}\n"
                f"Total: ${flow['monto'] * 1.16:,.2f}\n\n"
                f"¿Confirmar y timbrar? Responde: <b>SI</b> o <b>NO</b>"
            )
            await update.message.reply_text(preview, parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Monto inválido. Envía solo números:")
    elif step == "confirmar":
        if text.upper() == "SI":
            # Timbrar real
            await update.message.reply_text("⏳ Conectando con SAT para timbrar...")
            try:
                resp = api_post(
                    "/timbrar",
                    {
                        "emisor": {
                            "rfc": "MUTM8610091NA",
                            "nombre": "MARCO ARTURO MUÑOZ DEL TORO",
                            "regimen_fiscal": "612",
                        },
                        "receptor": {
                            "rfc": flow["rfc_receptor"],
                            "nombre": flow["nombre_receptor"],
                            "uso_cfdi": "G03",
                        },
                        "conceptos": [
                            {
                                "descripcion": flow["concepto"],
                                "cantidad": 1,
                                "precio_unitario": flow["monto"],
                                "impuestos": {
                                    "traslados": [
                                        {
                                            "base": flow["monto"],
                                            "impuesto": "002",
                                            "tipo_factor": "Tasa",
                                            "tasa": "0.16",
                                        }
                                    ]
                                },
                            }
                        ],
                        "total": flow["monto"] * 1.16,
                        "forma_pago": "03",
                        "metodo_pago": "PUE",
                    },
                )
                if resp.get("status") == "success":
                    uuid = resp.get("uuid", "")
                    xml = resp.get("xml", "")
                    if xml:
                        xml_bytes = (
                            base64.b64decode(xml) if "," not in xml else xml.encode()
                        )
                        buffer = io.BytesIO(xml_bytes)
                        buffer.name = f"CFDI_{uuid}.xml"
                        await update.message.reply_document(
                            document=InputFile(buffer, filename=f"CFDI_{uuid}.xml"),
                            caption=f"✅ <b>Factura timbrada</b>\nUUID: <code>{uuid}</code>",
                        )
                    else:
                        await update.message.reply_text(f"✅ Timbrada: {uuid}")
                else:
                    await update.message.reply_text(
                        f"❌ Error SAT: {resp.get('message', '')}"
                    )
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")
            finally:
                EMITIR_FLOW.pop(chat_id, None)
        else:
            await update.message.reply_text("❌ Cancelado.")
            EMITIR_FLOW.pop(chat_id, None)


# ─── Bot entrypoint ───


async def timbrar(update: Update, context):
    """Comando /timbrar - Muestra cómo timbrar una factura"""
    text = (
        "📋 <b>Timbrar Factura CFDI 4.0</b>\n\n"
        "Para timbrar una factura (generar CFDI oficial), usa la Mini App:\n\n"
        f"<a href='{WEBAPP}'>🌐 Abrir FiscoMind Mini App</a>\n\n"
        "<b>Flujo:</b>\n"
        "1. Captura tus datos del emisor\n"
        "2. Captura datos del receptor\n"
        "3. Agrega conceptos\n"
        "4. ¡Listo! Tu CFDI se timbra automáticamente\n\n"
        "<i>El timbrado es gratuito vía SAT.</i>"
    )
    kb = [[InlineKeyboardButton("🌐 Mini App", web_app=WebAppInfo(url=WEBAPP))]]
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )


async def cmd_cancelar(update: Update, context):
    """Comando /cancelar - Cancela una factura"""
    args = context.args
    if not args:
        text = (
            "❌ <b>Cancelar Factura</b>\n\n"
            "Sintaxis: <code>/cancelar UUID</code>\n\n"
            "Ejemplo:\n<code>/cancelar ABC123</code>\n\n"
            "⚠️ Solo puedes cancelar facturas que:\n"
            "- Tengan buzón tributario del receptor\n"
            "- Estén dentro del plazo permitido\n"
            "- No hayan sido pagadas"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        return

    uuid = args[0].upper()
    r = api_post("/cancelar", {"uuid": uuid})

    if r.get("status") == "success":
        await update.message.reply_text(
            f"✅ <b>CFDI Cancelado</b>\n\nUUID: <code>{h(uuid)}</code>\n\nLa cancelación se registró.",
            parse_mode="HTML",
        )
    elif r.get("status") == "pending":
        await update.message.reply_text(
            f"⏳ <b>Solicitud Enviada</b>\n\n"
            f"UUID: <code>{h(uuid)}</code>\n\n"
            "La cancelación requiere aceptación del receptor según las reglas SAT.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"❌ {h(str(r.get('message', 'Error')))}", parse_mode="HTML"
        )


async def cmd_estado(update: Update, context):
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Sintaxis: <code>/estado UUID</code>", parse_mode="HTML"
        )
        return
    uuid = args[0].upper()
    r = api_get(f"/estado-cfdi/{uuid}")
    if r.get("status") == "success":
        estado = r.get("estado", "desconocido")
        valido = r.get("valido", False)
        emoji = "✅" if valido else "❌"
        await update.message.reply_text(
            f"{emoji} <b>Estado CFDI</b>\n\nUUID: <code>{h(uuid)}</code>\nEstado: {estado}",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"❌ {h(str(r.get('message', 'Error')))}", parse_mode="HTML"
        )


async def cmd_obligaciones(update: Update, context):
    r = api_get("/obligaciones")
    obl = r.get("obligaciones_pendientes", [])
    text = "📅 <b>Obligaciones Fiscales</b>\n\n"
    for o in obl[:5]:
        dias = o.get("dias_restantes", "?")
        emoji = "🔴" if dias <= 3 else ("🟡" if dias <= 7 else "🟢")
        text += f"{emoji} {h(o.get('titulo', ''))} - {dias}d\n"
    if not obl:
        text = "✅ Todo al día. No hay obligaciones pendientes."
    await update.message.reply_text(text, parse_mode="HTML")


async def factura(update: Update, context):
    text = (
        "📝 <b>Crear Factura CFDI 4.0</b>\n\n"
        "Para crear una factura completa con múltiples conceptos, usa la Mini App:\n\n"
        f"<a href='{WEBAPP}'>🌐 Abrir FiscoMind Mini App</a>\n\n"
        "O mándame los datos así:\n\n"
        "<code>/hacerfactura</code>\n"
        "RFC: XAXX010101000\n"
        "Nombre: Cliente SA\n"
        "Concepto: Servicio de consultoría\n"
        "Cantidad: 1\n"
        "Precio: 5000\n"
        "IVA: 16\n"
        "Forma pago: 03\n"
        "Método: PUE"
    )
    kb = [
        [
            InlineKeyboardButton(
                "🌐 Mini App (recomendado)", web_app=WebAppInfo(url=WEBAPP)
            )
        ]
    ]
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )


async def cmd_optimize(update: Update, context):
    """Comando /optimizar - Sugerencias de optimización fiscal"""
    r = api_get("/optimize/suggestions")
    if r.get("status") == "error":
        await update.message.reply_text(
            f"❌ {h(str(r.get('message', 'Error')))}", parse_mode="HTML"
        )
        return

    sugerencias = r.get("sugerencias", [])
    total = r.get("total_gastos", 0)

    text = "📊 <b>Optimización Fiscal</b>\n\n"
    text += f"Gastos registrados: ${total:,.2f}\n\n"

    for s in sugerencias:
        emoji = {"info": "ℹ️", "warning": "⚠️", "alert": "🔴"}.get(
            s.get("tipo", ""), "📌"
        )
        text += f"{emoji} <b>{s.get('titulo', '')}</b>\n{h(s.get('mensaje', ''))}\n\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_proyeccion(update: Update, context):
    """Comando /proyeccion - Proyección de ISR"""
    r = api_get("/optimize/projection")
    if r.get("status") == "error":
        await update.message.reply_text(
            f"❌ {h(str(r.get('message', 'Error')))}", parse_mode="HTML"
        )
        return

    proy = r.get("proyeccion", {})
    actual = r.get("actual", {})

    text = "📈 <b>Proyección ISR</b>\n\n"
    text += f"<b>Trimestre Actual:</b>\n"
    text += f"Ingresos: ${actual.get('ingresos', 0):,.2f}\n"
    text += f"Egresos: ${actual.get('egresos', 0):,.2f}\n"
    text += f"ISR estimado: ${actual.get('isr_estimado', 0):,.2f}\n\n"
    text += f"<b>Proyección Anual:</b>\n"
    text += f"ISR proyectado: ${proy.get('isr_proyectado', 0):,.2f}\n"
    text += f"Pago trimestral: ${proy.get('pago_trimestral_estimado', 0):,.2f}"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_sugerir(update: Update, context):
    """Comando /sugerir - Consejo rápido de ahorro"""
    r = api_get("/optimize/suggestions")
    sugerencias = r.get("sugerencias", [])

    if sugerencias:
        s = sugerencias[0]
        emoji = {"info": "ℹ️", "warning": "⚠️", "alert": "🔴"}.get(
            s.get("tipo", ""), "📌"
        )
        await update.message.reply_text(
            f"{emoji} <b>{s.get('titulo', '')}</b>\n{h(s.get('mensaje', ''))}",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "📭 No hay sugerencias por ahora. Sincroniza tus CFDIs primero.",
            parse_mode="HTML",
        )


# Conversational AI
async def handle_message(update: Update, context):
    text = update.message.text.lower()
    if any(w in text for w in ["isr", "impuesto", "renta"]):
        d = api_get("/dashboard")
        s = d.get("summary", {})
        await update.message.reply_text(
            f"💰 <b>ISR Estimado</b>\n\nIngresos: ${s.get('total_ingresos', 0):,.2f}\nISR ~30%: ${s.get('total_ingresos', 0) * 0.30:,.2f}\nDeducciones: ${s.get('total_deducible', 0):,.2f}\nAhorro: ${s.get('ahorro_isr_estimado', 0):,.2f}",
            parse_mode="HTML",
        )
    elif "iva" in text:
        d = api_get("/dashboard")
        s = d.get("summary", {})
        await update.message.reply_text(
            f"📊 <b>IVA</b>\n\nA cargo: ${s.get('total_ingresos', 0) * 0.16:,.2f}\nA acreditar: ${s.get('total_egresos', 0) * 0.16:,.2f}\nPor pagar: ${(s.get('total_ingresos', 0) - s.get('total_egresos', 0)) * 0.16:,.2f}",
            parse_mode="HTML",
        )
    elif any(w in text for w in ["deduc", "gasto"]):
        d = api_get("/dashboard")
        s = d.get("summary", {})
        await update.message.reply_text(
            f"📝 <b>Deducciones</b>\n\nTotal: ${s.get('total_deducible', 0):,.2f}\nAhorro: ${s.get('ahorro_isr_estimado', 0):,.2f}\n\n💡 Agrega: médicos, transporte, software, donativos",
            parse_mode="HTML",
        )
    elif any(w in text for w in ["estrategia", "optim", "ahorr"]):
        await estrategia(update, context)
    elif any(w in text for w in ["oblig", "calendario", "venc"]):
        await obligaciones(update, context)
    elif any(w in text for w in ["opinión", "cumpl"]):
        await opinion(update, context)
    elif any(w in text for w in ["sincron", "descarg", "sync"]):
        await sync_sat(update, context)
    elif any(w in text for w in ["factura", "emitir", "crear"]):
        await factura(update, context)
    elif any(w in text for w in ["hola", "hi", "hello", "buenas"]):
        await start(update, context)
    else:
        await update.message.reply_text(
            "Puedo ayudarte con:\n• ISR, IVA, deducciones\n• Estrategia fiscal\n• Obligaciones\n• Sincronizar SAT\n• Crear factura\n\nPregúntame algo 😊",
            parse_mode="HTML",
        )


async def button(update: Update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d == "dash":
        s = api_get("/dashboard").get("summary", {})
        await q.message.edit_text(
            f"📊 <b>Dashboard</b>\n\nIngresos: ${s.get('total_ingresos', 0):,.2f}\nEgresos: ${s.get('total_egresos', 0):,.2f}\nDeducible: ${s.get('total_deducible', 0):,.2f}\nAhorro ISR: ${s.get('ahorro_isr_estimado', 0):,.2f}",
            parse_mode="HTML",
        )
    elif d == "cfdis":
        c = api_get("/cfdis").get("cfdis", [])
        t = f"📄 <b>CFDIs: {len(c)}</b>\n\n"
        for x in c[:10]:
            t += f"• ${x.get('monto', 0):,.2f} - {h(x.get('nombre_emisor', x.get('emisor', ''))[:25])}\n"
        await q.message.edit_text(t, parse_mode="HTML")
    elif d == "factura":
        kb = [
            [InlineKeyboardButton("🌐 Abrir Mini App", web_app=WebAppInfo(url=WEBAPP))]
        ]
        await q.message.edit_text(
            "📝 <b>Crear Factura</b>\n\nUsa la Mini App para facturas completas con múltiples conceptos:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML",
        )
    elif d == "estrategia":
        s = api_get("/dashboard").get("summary", {})
        await q.message.edit_text(
            f"💡 <b>Estrategia</b>\n\nIngresos: ${s.get('total_ingresos', 0):,.2f}\nDeducciones: ${s.get('total_deducible', 0):,.2f}\nAhorro ISR: ${s.get('ahorro_isr_estimado', 0):,.2f}\n\n1. Maximiza deducciones\n2. Acredita IVA\n3. Evalúa Régimen 626",
            parse_mode="HTML",
        )
    elif d == "oblig":
        o = api_get("/obligaciones").get("obligaciones_pendientes", [])
        t = "📅 <b>Obligaciones</b>\n\n"
        for x in o[:5]:
            e = {"critical": "🔴", "high": "🟡", "normal": "🟢"}.get(
                x.get("urgencia", ""), "⚪"
            )
            t += f"{e} {h(x.get('titulo', ''))} - {x.get('dias_restantes', '?')}d\n"
        await q.message.edit_text(t or "✅ Todo al día", parse_mode="HTML")
    elif d == "opinion":
        o = api_get("/opinion")
        await q.message.edit_text(
            f"🔒 <b>Opinión SAT:</b> {h(str(o.get('status', 'Error')))}",
            parse_mode="HTML",
        )
    elif d == "panorama":
        await cmd_panorama(update, context)
    elif d == "declarar":
        await cmd_declarar(update, context)
    elif d == "baja":
        await cmd_baja(update, context)
    elif d == "morning_sync":
        await sync_sat(update, context)
    elif d == "snooze":
        await q.message.edit_text(
            "⏰ Se pospuso la sincronización. Usa /sync cuando estés listo.",
            parse_mode="HTML",
        )
    elif d == "export":
        text = (
            "📤 \u003cb\u003eExportar Datos\u003c/b\u003e\n\n"
            "Tus datos están en FiscoMind. Puedes exportar:\n\n"
            "• \u003cb\u003eCSV\u003c/b\u003e - Facturas para Excel\n"
            "• \u003cb\u003ePDF\u003c/b\u003e - Reporte fiscal\n\n"
            "\u003cb\u003eComandos:\u003c/b\u003e\n"
            "• /export csv\n"
            "• /export pdf"
        )
        await q.message.edit_text(text, parse_mode="HTML")
    elif d == "sync":
        today = date.today()
        r = api_post(
            "/sync",
            {
                "date_start": (today - timedelta(days=30)).isoformat(),
                "date_end": today.isoformat(),
                "tipo": "recibidos",
            },
        )
        if r.get("status") == "submitted":
            await q.message.edit_text(
                f"📥 Sync iniciada ✅\n\nID: <code>{h(r['id_solicitud'])}</code>\nEspera ~60s.",
                parse_mode="HTML",
            )
        else:
            await q.message.edit_text(
                f"❌ {h(str(r.get('message', r)))}", parse_mode="HTML"
            )


async def cmd_panorama(update: Update, context):
    """Comando /panorama - Visión completa de tu situación fiscal"""
    await update.message.reply_text(
        "📊 Generando tu panorama fiscal...", parse_mode="HTML"
    )

    # Obtener datos del dashboard y obligaciones
    dash = api_get("/dashboard")
    summary = dash.get("summary", {})
    ult_sync = dash.get("last_sync", "Nunca")

    # Get obligations
    obl = api_get("/obligaciones")
    obligaciones = obl.get("obligaciones_pendientes", [])

    # Get optimization
    opt = api_get("/optimize/suggestions")
    sugerencias = opt.get("sugerencias", [])

    # Get projection
    proy = api_get("/optimize/projection")
    isr_proy = proy.get("proyeccion_anual", {}).get("isr_anual_estimado", 0)

    text = "🎯 <b>TU PANORAMA FISCAL</b>\n\n"

    # Resumen
    text += f"📥 Última sync: {ult_sync[:10] if ult_sync else 'Nunca'}\n"
    text += f"📄 CFDIs: {summary.get('total_recibidos', 0)} recibidos | {summary.get('total_emitidos', 0)} emitidos\n"
    text += f"💰 Ingresos: ${summary.get('total_ingresos', 0):,.2f}\n"
    text += f"💸 Egresos: ${summary.get('total_egresos', 0):,.2f}\n"
    text += f"📉 Deducible: ${summary.get('total_deducible', 0):,.2f}\n"
    text += f"🔴 ISR Estimado Anual: ${isr_proy:,.2f}\n\n"

    # Obligaciones
    if obligaciones:
        urgentes = [o for o in obligaciones if o.get("dias_restantes", 999) <= 3]
        if urgentes:
            text += "🚨 <b>OBLIGACIONES URGENTES:</b>\n"
            for o in urgentes[:3]:
                text += f"• {h(o.get('titulo', ''))} ({o.get('dias_restantes', '?')} días)\n"
            text += "\n"

    # Sugerencias principales
    if sugerencias:
        text += "💡 <b>SUGERENCIAS:</b>\n"
        for s in sugerencias[:3]:
            text += f"• {h(s.get('titulo', ''))}\n"
        text += "\n"

    # Opciones
    text += "<b>Opciones:</b>\n"
    text += "• /declarar - Ayuda para declarar en ceros\n"
    text += "• /baja - Suspender temporalmente\n"
    text += "• /optimizar - Ver todas las sugerencias\n"
    text += "• /proyeccion - Ver ISR proyectado\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_baja(update: Update, context):
    """Comando /baja - Suspensión temporal o baja definitiva"""
    args = context.args

    if not args or args[0].lower() not in ["temporal", "definitiva"]:
        text = (
            "🔒 <b>BAJA DE ACTIVIDADES</b>\n\n"
            "¿Quieres Suspensión Temporal o Baja Definitiva?\n\n"
            "1️⃣ <b>Suspensión Temporal</b>\n"
            "   • No pagas ISR durante la suspensión\n"
            "   • No presentas declaraciones\n"
            "   • Mantienes RFC activo\n"
            "   • Puedes reactivarte cuando quieras\n"
            "   • Ideal: 6+ meses sin actividad\n\n"
            "2️⃣ <b>Baja Definitiva</b>\n"
            "   • Cancelas RFC como contribuyente\n"
            "   • No puedes facturar más\n"
            "   • Si trabajas como empleado, no necesitas RFC\n"
            "   • Ideal: Cambio permanente a empleado\n\n"
            "💡 <b>Recomendación:</b>\n"
            "Si no vas a facturar por 6+ meses pero piensas volver → <b>SUSPENSIÓN</b>\n"
            "Si vas a trabajar solo como empleado → <b>BAJA</b>\n\n"
            "<b>Usa:</b> /baja temporal o /baja definitiva"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        return

    tipo = args[0].lower()

    if tipo == "temporal":
        text = (
            "🔄 <b>SUSPENSIÓN TEMPORAL DE ACTIVIDADES</b>\n\n"
            "<b>Requisitos:</b>\n"
            "• No tener facturas vigentes pendientes\n"
            "• No tener obligaciones fiscales pendientes\n\n"
            "<b>Pasos:</b>\n"
            "1. Portal SAT → Mi Portal → Actualización de Obligaciones\n"
            "2. Selecciona 'Suspensión de Actividades'\n"
            "3. Indica fecha de inicio\n"
            "4. Confirma (aplica en 24-48 hrs)\n\n"
            "<b>Durante la suspensión:</b>\n"
            "✅ NO pagas ISR\n"
            "✅ NO presentas declaraciones mensuales\n"
            "✅ Mantienes RFC activo\n"
            "⚠️ SI facturas durante suspensión = multas\n\n"
            "<b>Para reactivar:</b>\n"
            "Portal SAT → Reactivación (mismo proceso)\n\n"
            "_Si estás en empresa moral y no facturas en personal, SUSPENSIÓN es tu mejor opción._"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    else:  # definitiva
        text = (
            "🔒 <b>BAJA DEFINITIVA DEL RFC</b>\n\n"
            "⚠️ <b>ADVERTENCIA:</b> Esta acción NO se puede deshacer fácilmente.\n\n"
            "<b>¿Qué implica?</b>\n"
            "• Cancelas tu inscripción en el SAT\n"
            "• Ya NO puedes facturar\n"
            "• Si trabajas como empleado, NO necesitas RFC (tu empleado lo hace por ti)\n\n"
            "<b>Antes de dar de baja:</b>\n"
            "1. Regularizar todas las declaraciones pendientes\n"
            "2. Pagar todo ISR adeudado\n"
            "3. Cancelar todas las facturas pendientes\n"
            "4. Descargar acuses de presentación de años anteriores\n\n"
            "<b>Pasos:</b>\n"
            "1. Portal SAT → Mi Portal → Actualización de Obligaciones\n"
            "2. Selecciona 'Cancelación de Inscripción'\n"
            "3. Presenta última declaración\n"
            "4. Espera confirmación del SAT (5-10 días)\n\n"
            "💡 <b>Alternativa:</b>\n"
            "Considera SUSPENSIÓN TEMPORAL primero. Puedes reactivarte cuando quieras.\n"
            "Si después de 1 año sigues sin facturar, entonces da de baja.\n\n"
            "_/baja temporal para suspender sin cancelar_"
        )
        await update.message.reply_text(text, parse_mode="HTML")


async def cmd_regularizar(update: Update, context):
    """
    /regularizar - Genera plan de regularización como PDF descargable.
    Analiza tu historial SAT y dice exactamente qué declarar y cómo.
    """
    await update.message.reply_text(
        "🔍 Analizando tu historial fiscal para regularización...", parse_mode="HTML"
    )

    try:
        # Obtener plan
        r = client.get("/regularizacion?formato=json")
        data = r.json() if hasattr(r, "json") else {"status": "error"}

        if data.get("status") == "success":
            plan = data.get("plan", {})
            riesgo = plan.get("riesgo", "DESCONOCIDO")
            rec = plan.get("recomendacion_principal", "")
            totales = plan.get("totales", {})
            estrategia = plan.get("estrategia", {})

            color = {"BAJO": "🟢", "MEDIO": "🟡", "ALTO": "🔴"}.get(riesgo, "⚪")

            text = (
                f"🎯 <b>PLAN DE REGULARIZACIÓN</b>\n\n"
                f"Riesgo SAT: {color} <b>{riesgo}</b>\n"
                f"Recomendación: {rec}\n\n"
                f"📊 <b>Resumen:</b>\n"
                f"• Períodos esperados: {totales.get('periodos_esperados', 0)}\n"
                f"• Con ingresos: {totales.get('periodos_con_ingresos', 0)}\n"
                f"• Sin ingresos: {totales.get('periodos_sin_ingresos', 0)}\n"
                f"• ISR estimado total: ${totales.get('isr_estimado_total', 0):,.2f}\n\n"
                f"✅ <b>Estrategia:</b>\n"
                f"• Declarar en ceros: {estrategia.get('periodos_a_declarar_ceros', 0)} meses\n"
                f"• Declarar normal: {estrategia.get('periodos_a_declarar_normal', 0)} meses\n"
                f"• Prescritos (no necesarios): {estrategia.get('periodos_prescritos_no_necesarios', 0)}\n\n"
                f"📎 Descargando PDF con el plan completo..."
            )
            await update.message.reply_text(text, parse_mode="HTML")

            # Descargar PDF
            r_pdf = client.get("/regularizacion?formato=pdf")
            if r_pdf.status_code == 200:
                buffer = io.BytesIO(r_pdf.content)
                buffer.name = (
                    f"plan_regularizacion_{date.today().strftime('%Y%m%d')}.pdf"
                )
                await update.message.reply_document(
                    document=InputFile(buffer, filename=buffer.name),
                    caption="📋 Tu plan de regularización completo",
                )
            else:
                await update.message.reply_text(
                    "⚠️ No se pudo generar el PDF, pero el plan JSON está listo.",
                    parse_mode="HTML",
                )
        else:
            error = data.get("message", "Error desconocido")
            await update.message.reply_text(f"❌ Error: {error}", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Setup morning jobs
    setup_morning_jobs(app)

    # Commands
    handlers = [
        ("start", start),
        ("dashboard", dashboard),
        ("cfdis", cfdis),
        ("obligaciones", cmd_obligaciones),
        ("opinion", opinion),
        ("estrategia", estrategia),
        ("sync", sync_sat),
        ("factura", factura),
        ("timbrar", timbrar),
        ("cancelar", cmd_cancelar),
        ("estado", cmd_estado),
        ("optimizar", cmd_optimize),
        ("proyeccion", cmd_proyeccion),
        ("sugerir", cmd_sugerir),
        ("panorama", cmd_panorama),
        ("declarar", cmd_declarar),
        ("baja", cmd_baja),
        ("regularizar", cmd_regularizar),
    ]

    for command, handler in handlers:
        app.add_handler(CommandHandler(command, handler))

    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 FiscoMind Bot v3.3 - PANORAMA + DECLARAR + BAJA + ALERTAS")
    app.run_polling()


if __name__ == "__main__":
    main()
