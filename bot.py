"""
FiscoMind Bot v3.0 - Railway API + HTML safe
Fix: can't parse entities error (escape all dynamic HTML)
"""

import os, json, logging, httpx
from datetime import date, timedelta
from html import escape as h

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
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
WEBAPP = os.environ.get(
    "FISCOMIND_WEBAPP_URL", "https://miniapp-react-livid.vercel.app"
)

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


async def start(update: Update, context):
    d = api_get("/dashboard")
    s = d.get("summary", {})
    text = (
        f"🧠 <b>FiscoMind - Tu Contador IA</b>\n\n"
        f"Hola {h(update.effective_user.first_name)}!\n\n"
        f"✨ <b>Tu Estado:</b>\n"
        f"• Ingresos: ${s.get('total_ingresos', 0):,.2f}\n"
        f"• Egresos: ${s.get('total_egresos', 0):,.2f}\n"
        f"• CFDIs: {s.get('total_recibidos', 0)} recibidos\n"
        f"• Ahorro ISR: ${s.get('ahorro_isr_estimado', 0):,.2f}\n"
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


async def resumen_mes(update: Update, context):
    mes = context.args[0] if context.args else date.today().strftime("%Y-%m")
    d = api_get("/resumen-mensual", mes=mes)
    if d.get("error"):
        await update.message.reply_text(
            f"❌ Error: {h(str(d.get('error')))}", parse_mode="HTML"
        )
        return
    text = (
        f"📊 <b>Resumen {h(d.get('nombre_mes', mes))}</b>\n\n"
        f"💰 Ingresos: ${d.get('ingresos', 0):,.2f}\n"
        f"💸 Egresos: ${d.get('egresos', 0):,.2f}\n"
        f"✅ Deducciones: ${d.get('deducciones', 0):,.2f}\n"
        f"📄 CFDIs: {d.get('cfdis_recibidos', 0)}\n\n"
        f"<b>ISR Estimado:</b>\n"
        f"Base gravable: ${d.get('isr', {}).get('base_gravable', 0):,.2f}\n"
        f"ISR estimado: ${d.get('isr', {}).get('isr_estimado', 0):,.2f}\n"
        f"Reserva mensual: ${d.get('isr', {}).get('reserva_mensual', 0):,.2f}\n\n"
        f"<i>Usa /mes 2026-04 para otro mes</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def resumen_trimestre(update: Update, context):
    q = context.args[0] if context.args else None
    d = (
        api_get("/resumen-trimestral", trimestre=q)
        if q
        else api_get("/resumen-trimestral")
    )
    if d.get("error"):
        await update.message.reply_text(
            f"❌ Error: {h(str(d.get('error')))}", parse_mode="HTML"
        )
        return
    t = d.get("totales", {})
    meses = d.get("resumen_meses", [])
    text = (
        f"📊 <b>Resumen {h(d.get('trimestre', ''))}</b>\n\n"
        f"💰 Ingresos: ${t.get('ingresos', 0):,.2f}\n"
        f"✅ Deducciones: ${t.get('deducciones', 0):,.2f}\n"
        f"Base gravable: ${t.get('base_gravable', 0):,.2f}\n"
        f"ISR estimado: ${t.get('isr_estimado', 0):,.2f}\n"
        f"Reserva/mes: ${t.get('reserva_mensual', 0):,.2f}\n\n"
        f"<b>Meses:</b>\n"
    )
    for m in meses:
        text += f"• {m.get('mes', '')}: ${m.get('ingresos', 0):,.0f} | {m.get('cfdis', 0)} CFDIs\n"
    text += "\n<i>Usa /trimestre 2026-Q1 para otro trimestre</i>"
    await update.message.reply_text(text, parse_mode="HTML")


async def calculo_isr(update: Update, context):
    anio = context.args[0] if context.args else str(date.today().year)
    d = api_get("/calculo-isr", anio=anio)
    if d.get("error"):
        await update.message.reply_text(
            f"❌ Error: {h(str(d.get('error')))}", parse_mode="HTML"
        )
        return
    a = d.get("acumulado", {})
    p = d.get("proyeccion_anual", {})
    text = (
        f"🧮 <b>ISR {anio}</b>\n\n"
        f"<b>Acumulado a {d.get('mes_actual', 0)}/{anio}:</b>\n"
        f"Ingresos: ${a.get('ingresos', 0):,.2f}\n"
        f"Deducciones: ${a.get('deducciones', 0):,.2f}\n"
        f"ISR estimado: ${a.get('isr_estimado', 0):,.2f}\n\n"
        f"<b>Proyección anual:</b>\n"
        f"Ingresos: ${p.get('ingresos_estimados', 0):,.2f}\n"
        f"ISR anual: ${p.get('isr_estimado', 0):,.2f}\n"
        f"Reserva mensual: ${p.get('reserva_mensual', 0):,.2f}\n"
        f"Reserva acumulada: ${p.get('reserva_acumulada', 0):,.2f}\n\n"
        f"💡 <b>{h(d.get('recomendacion', ''))}</b>\n\n"
        f"<i>Usa /isr 2025 para otro año</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def complementos_pendientes(update: Update, context):
    d = api_get("/complementos-pendientes")
    if d.get("error"):
        await update.message.reply_text(
            f"❌ Error: {h(str(d.get('error')))}", parse_mode="HTML"
        )
        return
    p = d.get("pendientes", [])
    if not p:
        await update.message.reply_text(
            "✅ No hay complementos de pago pendientes.", parse_mode="HTML"
        )
        return
    text = (
        f"💳 <b>Complementos Pendientes</b>\n"
        f"Total: {d.get('total_pendientes', 0)} | "
        f"Saldo: ${d.get('total_saldo', 0):,.2f}\n"
        f"Urgentes: {d.get('urgentes', 0)}\n\n"
    )
    for x in p[:10]:
        e = (
            "🔴"
            if x.get("urgencia") == "critical"
            else ("🟡" if x.get("urgencia") == "high" else "🟢")
        )
        text += (
            f"{e} <b>${x.get('saldo_pendiente', 0):,.2f}</b>\n"
            f"   Para: {h(x.get('nombre_receptor', '')[:25])}\n"
            f"   Vence: {x.get('fecha_limite_complemento', '')}\n"
            f"   Días: {x.get('dias_restantes', '?')}\n\n"
        )
    await update.message.reply_text(text, parse_mode="HTML")


async def clasificacion_gastos(update: Update, context):
    mes = context.args[0] if context.args else date.today().strftime("%Y-%m")
    d = api_get("/clasificacion-gastos", mes=mes)
    if d.get("error"):
        await update.message.reply_text(
            f"❌ Error: {h(str(d.get('error')))}", parse_mode="HTML"
        )
        return
    cats = d.get("categorias", {})
    if not cats:
        await update.message.reply_text(f"📊 No hay gastos en {mes}", parse_mode="HTML")
        return
    text = (
        f"📊 <b>Gastos por Categoría - {mes}</b>\n\n"
        f"Total deducible: ${d.get('total_deducible', 0):,.2f}\n"
        f"Total no deducible: ${d.get('total_no_deducible', 0):,.2f}\n\n"
        f"<b>Top Categorías:</b>\n"
    )
    for nom, info in list(cats.items())[:8]:
        icon = "✅" if info.get("deducible") else "❌"
        text += f"{icon} {h(nom[:30])}: ${info.get('total', 0):,.2f} ({info.get('count', 0)})\n"
    text += "\n<i>Usa /gastos 2026-04 para otro mes</i>"
    await update.message.reply_text(text, parse_mode="HTML")


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


async def sync_sat(update: Update, context):
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    r = api_post(
        "/sync",
        {"date_start": start, "date_end": today.isoformat(), "tipo": "recibidos"},
    )
    if r.get("status") == "submitted":
        await update.message.reply_text(
            f"📥 Sync iniciada ✅\n\nID: <code>{h(r['id_solicitud'])}</code>\nSAT procesa en 30-60s.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"❌ Error: {h(str(r.get('message', r)))}", parse_mode="HTML"
        )


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


# Conversational AI
async def handle_message(update: Update, context):
    text = update.message.text.lower()
    words = text.split()

    # Detectar comandos por palabras clave
    if "mes" in text or ("resumen" in text and "mes" in text):
        await resumen_mes(update, context)
    elif "trimestre" in text or "quarter" in text:
        await resumen_trimestre(update, context)
    elif (
        text.startswith("/isr")
        or ("calculo" in text and "isr" in text)
        or ("proyeccion" in text and "isr" in text)
    ):
        await calculo_isr(update, context)
    elif "complemento" in text or "ppd" in text or "pendiente" in text:
        await complementos_pendientes(update, context)
    elif "categoria" in text or "clasificacion" in text or "gastos por" in text:
        await clasificacion_gastos(update, context)
    elif (
        text.startswith("/simular")
        or "simular" in text
        or "que pasaria si" in text
        or "ahorro si" in text
    ):
        await simular(update, context)
    elif (
        text.startswith("/comparar")
        or ("comparar" in text and "ano" in text)
        or ("comparar" in text and "año" in text)
        or "ano pasado" in text
    ):
        await comparar(update, context)
    elif any(w in text for w in ["isr", "impuesto", "renta"]):
        d = api_get("/dashboard")
        s = d.get("summary", {})
        await update.message.reply_text(
            f"💰 <b>ISR Estimado</b>\n\nIngresos: ${s.get('total_ingresos', 0):,.2f}\nISR ~30%: ${s.get('total_ingresos', 0) * 0.30:,.2f}\nDeducciones: ${s.get('total_deducible', 0):,.2f}\nAhorro: ${s.get('ahorro_isr_estimado', 0):,.2f}\n\nUsa <code>/isr</code> para cálculo detallado",
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
        await clasificacion_gastos(update, context)
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
    elif "ayuda" in text or "help" in text or "comandos" in text:
        await update.message.reply_text(
            "📋 <b>Comandos disponibles:</b>\n\n"
            "/start - Inicio y menú\n"
            "/dashboard - Estado general\n"
            "/cfdis - Ver facturas\n"
            "/mes [YYYY-MM] - Resumen mensual\n"
            "/trimestre [YYYY-Q#] - Resumen trimestral\n"
            "/isr [año] - Cálculo ISR\n"
            "/complementos - PPDs pendientes\n"
            "/gastos [mes] - Clasificación\n"
            "/obligaciones - Vencimientos\n"
            "/estrategia - Recomendaciones\n"
            "/sync - Sincronizar SAT\n"
            "/factura - Crear factura\n\n"
            "💬 También puedes preguntar en lenguaje natural",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "Puedo ayudarte con:\n"
            "• ISR, IVA, deducciones\n"
            "• Resumen mensual/trimestral\n"
            "• Complementos de pago\n"
            "• Clasificación de gastos\n"
            "• Estrategia fiscal\n"
            "• Obligaciones\n"
            "• Sincronizar SAT\n"
            "• Crear factura\n\n"
            "Usa <code>/ayuda</code> para ver todos los comandos",
            parse_mode="HTML",
        )


async def simular(update: Update, context):
    """Simulador de escenarios what-if"""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "💡 <b>Simulador de Escenarios</b>\n\n"
            "Ejemplos:\n"
            "<code>/simular laptop 25000</code>\n"
            "<code>/simular facturar 50000</code>\n"
            "<code>/simular deducir 10000</code>\n\n"
            "Calcula el impacto fiscal antes de decidir.",
            parse_mode="HTML",
        )
        return

    tipo = context.args[0].lower()
    try:
        monto = float(context.args[1])
    except:
        await update.message.reply_text(
            "❌ Monto inválido. Ejemplo: /simular laptop 25000", parse_mode="HTML"
        )
        return

    # Mapa de tipos
    tipo_map = {
        "laptop": ("compra_activo", "Laptop"),
        "computadora": ("compra_activo", "Computadora"),
        "equipo": ("compra_activo", "Equipo de oficina"),
        "facturar": ("incremento_ingresos", "Ingresos adicionales"),
        "ingreso": ("incremento_ingresos", "Ingresos adicionales"),
        "deducir": ("incremento_deducciones", "Gastos deducibles"),
        "gasto": ("incremento_deducciones", "Gastos deducibles"),
        "honorarios": ("honorarios", "Pago de honorarios"),
    }

    tipo_api, descripcion = tipo_map.get(tipo, ("compra_activo", tipo))

    # Llamar API
    r = api_post(
        "/simular", {"tipo": tipo_api, "monto": monto, "descripcion": descripcion}
    )

    if r.get("error"):
        await update.message.reply_text(
            f"❌ Error: {h(str(r.get('error')))}", parse_mode="HTML"
        )
        return

    actual = r.get("situacion_actual", {})
    simulado = r.get("situacion_simulada", {})
    resultado = r.get("resultado", {})

    text = (
        f"💡 <b>Simulación: {h(descripcion)} ${monto:,.2f}</b>\n\n"
        f"<b>Situación Actual:</b>\n"
        f"• Ingresos: ${actual.get('ingresos', 0):,.2f}\n"
        f"• Deducciones: ${actual.get('deducciones', 0):,.2f}\n"
        f"• ISR estimado: ${actual.get('isr_estimado', 0):,.2f}\n\n"
        f"<b>Después del cambio:</b>\n"
        f"• Ingresos: ${simulado.get('ingresos', 0):,.2f}\n"
        f"• Deducciones: ${simulado.get('deducciones', 0):,.2f}\n"
        f"• ISR estimado: ${simulado.get('isr_estimado', 0):,.2f}\n\n"
    )

    ahorro = resultado.get("ahorro_isr", 0)
    if ahorro > 0:
        text += f"✅ <b>Ahorro: ${ahorro:,.2f} ({resultado.get('porcentaje_ahorro', 0)}%)</b>\n\n"
    elif ahorro < 0:
        text += f"⚠️ <b>ISR adicional: ${abs(ahorro):,.2f}</b>\n\n"

    text += f"💡 {h(resultado.get('nota', ''))}"

    await update.message.reply_text(text, parse_mode="HTML")


async def comparar(update: Update, context):
    """Comparativa año vs año"""
    anio = context.args[0] if context.args else str(date.today().year - 1)

    r = api_get("/comparar", anio=anio)
    if r.get("error"):
        await update.message.reply_text(
            f"❌ Error: {h(str(r.get('error')))}", parse_mode="HTML"
        )
        return

    actual = r.get("resumen_actual", {})
    comparar = r.get("resumen_comparar", {})
    diff = r.get("diferencias", {})

    def trend(v):
        if v > 0:
            return f"+{v}% 📈"
        elif v < 0:
            return f"{v}% 📉"
        return "0% ➡️"

    text = (
        f"📊 <b>Comparativa: {actual.get('anio', '')} vs {comparar.get('anio', '')}</b>\n"
        f"<i>(Hasta {actual.get('meses', 0)} de {actual.get('anio', '')})</i>\n\n"
        f"<b>Ingresos:</b>\n"
        f"• {actual.get('anio', '')}: ${actual.get('ingresos', 0):,.2f} {trend(diff.get('ingresos', 0))}\n"
        f"• {comparar.get('anio', '')}: ${comparar.get('ingresos', 0):,.2f}\n\n"
        f"<b>Deducciones:</b>\n"
        f"• {actual.get('anio', '')}: ${actual.get('deducciones', 0):,.2f} ({actual.get('porcentaje_deducciones', 0)}%) {trend(diff.get('deducciones', 0))}\n"
        f"• {comparar.get('anio', '')}: ${comparar.get('deducciones', 0):,.2f} ({comparar.get('porcentaje_deducciones', 0)}%)\n\n"
        f"<b>ISR Estimado:</b>\n"
        f"• {actual.get('anio', '')}: ${actual.get('isr_estimado', 0):,.2f}\n"
        f"• {comparar.get('anio', '')}: ${comparar.get('isr_estimado', 0):,.2f} {trend(diff.get('isr', 0))}\n\n"
    )

    # Alertas
    for alerta in r.get("alertas", []):
        text += f"{alerta}\n"

    await update.message.reply_text(text, parse_mode="HTML")


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


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("cfdis", cfdis))
    app.add_handler(CommandHandler("mes", resumen_mes))
    app.add_handler(CommandHandler("trimestre", resumen_trimestre))
    app.add_handler(CommandHandler("isr", calculo_isr))
    app.add_handler(CommandHandler("complementos", complementos_pendientes))
    app.add_handler(CommandHandler("gastos", clasificacion_gastos))
    app.add_handler(CommandHandler("obligaciones", obligaciones))
    app.add_handler(CommandHandler("opinion", opinion))
    app.add_handler(CommandHandler("estrategia", estrategia))
    app.add_handler(CommandHandler("sync", sync_sat))
    app.add_handler(CommandHandler("factura", factura))
    app.add_handler(CommandHandler("simular", simular))
    app.add_handler(CommandHandler("comparar", comparar))
    app.add_handler(CommandHandler("ayuda", handle_message))  # Handle /ayuda
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 FiscoMind Bot v3.2 starting...")
    print(
        "Commands: /start /dashboard /cfdis /mes /trimestre /isr /complementos /gastos /simular /comparar /ayuda"
    )
    app.run_polling()


if __name__ == "__main__":
    main()
