"""
FiscoMind Bot v3.0 - Railway API + HTML safe
Fix: can't parse entities error (escape all dynamic HTML)
"""
import os, json, logging, httpx
from datetime import date, timedelta
from html import escape as h

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8707174381:AAEMPvzE-j123z1bETTZEDDtJCURiE--yiI")
API = os.environ.get("FISCOMIND_API_URL", "https://fiscomind-api-production.up.railway.app")
WEBAPP = os.environ.get("FISCOMIND_WEBAPP_URL", "https://miniapp-react-livid.vercel.app")

client = httpx.Client(base_url=API, timeout=30)

def api_get(path, **kw):
    try: return client.get(path, params=kw).json()
    except Exception as e: return {"error": str(e)}

def api_post(path, data=None):
    try: return client.post(path, json=data or {}).json()
    except Exception as e: return {"error": str(e)}

async def start(update: Update, context):
    d = api_get("/dashboard"); s = d.get("summary", {})
    text = (
        f"🧠 <b>FiscoMind - Tu Contador IA</b>\n\n"
        f"Hola {h(update.effective_user.first_name)}!\n\n"
        f"✨ <b>Tu Estado:</b>\n"
        f"• Ingresos: ${s.get('total_ingresos',0):,.2f}\n"
        f"• Egresos: ${s.get('total_egresos',0):,.2f}\n"
        f"• CFDIs: {s.get('total_recibidos',0)} recibidos\n"
        f"• Ahorro ISR: ${s.get('ahorro_isr_estimado',0):,.2f}\n"
    )
    kb = [
        [InlineKeyboardButton("📊 Dashboard", callback_data='dash'),
         InlineKeyboardButton("📄 CFDIs", callback_data='cfdis')],
        [InlineKeyboardButton("📝 Factura", callback_data='factura'),
         InlineKeyboardButton("💡 Estrategia", callback_data='estrategia')],
        [InlineKeyboardButton("📅 Obligaciones", callback_data='oblig'),
         InlineKeyboardButton("🔒 Opinión SAT", callback_data='opinion')],
        [InlineKeyboardButton("📥 Sincronizar", callback_data='sync'),
         InlineKeyboardButton("🌐 Mini App", web_app=WebAppInfo(url=WEBAPP))],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

async def dashboard(update: Update, context):
    d = api_get("/dashboard"); s = d.get("summary", {})
    text = (
        f"📊 <b>Dashboard Fiscal</b>\n\n"
        f"📥 Recibidos: {s.get('total_recibidos',0)}\n"
        f"📤 Emitidos: {s.get('total_emitidos',0)}\n"
        f"💰 Ingresos: ${s.get('total_ingresos',0):,.2f}\n"
        f"💸 Egresos: ${s.get('total_egresos',0):,.2f}\n"
        f"✅ Deducible: ${s.get('total_deducible',0):,.2f}\n"
        f"💡 Ahorro ISR: ${s.get('ahorro_isr_estimado',0):,.2f}\n\n"
        f"<i>Sync: {h(d.get('last_sync','Nunca'))}</i>"
    )
    await update.message.reply_text(text, parse_mode='HTML')

async def cfdis(update: Update, context):
    d = api_get("/cfdis"); c = d.get("cfdis", [])
    if not c:
        await update.message.reply_text("❌ No hay CFDIs. Sincroniza con SAT primero.", parse_mode='HTML'); return
    text = f"📄 <b>CFDIs ({len(c)})</b>\n\n"
    for x in c[:15]:
        icon = {"I":"📥","E":"📤","P":"💳"}.get(x.get("efecto",""),"📄")
        st = "✅" if x.get("estatus")=="1" else "❌"
        text += f"{icon}{st} <b>${x.get('monto',0):,.2f}</b> - {h(x.get('nombre_emisor',x.get('emisor',''))[:30])}\n"
        text += f"   📅 {x.get('fecha_emision','')}\n"
    await update.message.reply_text(text, parse_mode='HTML')

async def obligaciones(update: Update, context):
    d = api_get("/obligaciones"); o = d.get("obligaciones_pendientes",[]); r = d.get("resumen",{})
    if not o:
        await update.message.reply_text("✅ Sin obligaciones pendientes.", parse_mode='HTML'); return
    text = "📅 <b>Obligaciones Fiscales</b>\n\n"
    for x in o:
        e = {"critical":"🔴","high":"🟡","overdue":"⛔","normal":"🟢","low":"⚪"}.get(x.get("urgencia",""),"⚪")
        text += f"{e} <b>{h(x.get('titulo',''))}</b>\n   Vence: {x.get('vence','')} · {x.get('dias_restantes','?')} días\n\n"
    text += f"Resumen: 🔴{r.get('criticas',0)} 🟡{r.get('altas',0)} 🟢{r.get('normales',0)}"
    await update.message.reply_text(text, parse_mode='HTML')

async def opinion(update: Update, context):
    d = api_get("/opinion")
    if d.get("status")=="Positiva":
        await update.message.reply_text("✅ <b>Opinión de Cumplimiento: POSITIVA</b>\nEstás al corriente con el SAT.", parse_mode='HTML')
    else:
        await update.message.reply_text(f"📋 Opinión: {h(str(d.get('status','Error')))}\nPendientes: {d.get('pending_obligations','?')}", parse_mode='HTML')

async def estrategia(update: Update, context):
    d = api_get("/dashboard"); s = d.get("summary",{})
    o = api_get("/obligaciones").get("obligaciones_pendientes",[])
    ing = s.get("total_ingresos",0); egr = s.get("total_egresos",0); ded = s.get("total_deducible",0); ah = s.get("ahorro_isr_estimado",0)
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
        text += f"2. IVA a cargo: ${ing*0.16:,.2f}\n\n"
    text += "3. Evalúa Régimen Simplificado de Confianza (626)\n\n"
    crit = [x for x in o if x.get("urgencia")=="critical"]
    if crit:
        text += f"<b>🚨 Urgente:</b>\n"
        for x in crit: text += f"• {h(x.get('titulo',''))} - {x.get('dias_restantes','?')} días\n"
    await update.message.reply_text(text, parse_mode='HTML')

async def sync_sat(update: Update, context):
    today = date.today(); start = (today - timedelta(days=30)).isoformat()
    r = api_post("/sync", {"date_start": start, "date_end": today.isoformat(), "tipo": "recibidos"})
    if r.get("status")=="submitted":
        await update.message.reply_text(f"📥 Sync iniciada ✅\n\nID: <code>{h(r['id_solicitud'])}</code>\nSAT procesa en 30-60s.", parse_mode='HTML')
    else:
        await update.message.reply_text(f"❌ Error: {h(str(r.get('message',r)))}", parse_mode='HTML')

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
    kb = [[InlineKeyboardButton("🌐 Mini App (recomendado)", web_app=WebAppInfo(url=WEBAPP))]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

# Conversational AI
async def handle_message(update: Update, context):
    text = update.message.text.lower()
    if any(w in text for w in ['isr','impuesto','renta']):
        d = api_get("/dashboard"); s = d.get("summary",{})
        await update.message.reply_text(
            f"💰 <b>ISR Estimado</b>\n\nIngresos: ${s.get('total_ingresos',0):,.2f}\nISR ~30%: ${s.get('total_ingresos',0)*0.30:,.2f}\nDeducciones: ${s.get('total_deducible',0):,.2f}\nAhorro: ${s.get('ahorro_isr_estimado',0):,.2f}", parse_mode='HTML')
    elif 'iva' in text:
        d = api_get("/dashboard"); s = d.get("summary",{})
        await update.message.reply_text(
            f"📊 <b>IVA</b>\n\nA cargo: ${s.get('total_ingresos',0)*0.16:,.2f}\nA acreditar: ${s.get('total_egresos',0)*0.16:,.2f}\nPor pagar: ${(s.get('total_ingresos',0)-s.get('total_egresos',0))*0.16:,.2f}", parse_mode='HTML')
    elif any(w in text for w in ['deduc','gasto']):
        d = api_get("/dashboard"); s = d.get("summary",{})
        await update.message.reply_text(
            f"📝 <b>Deducciones</b>\n\nTotal: ${s.get('total_deducible',0):,.2f}\nAhorro: ${s.get('ahorro_isr_estimado',0):,.2f}\n\n💡 Agrega: médicos, transporte, software, donativos", parse_mode='HTML')
    elif any(w in text for w in ['estrategia','optim','ahorr']):
        await estrategia(update, context)
    elif any(w in text for w in ['oblig','calendario','venc']):
        await obligaciones(update, context)
    elif any(w in text for w in ['opinión','cumpl']):
        await opinion(update, context)
    elif any(w in text for w in ['sincron','descarg','sync']):
        await sync_sat(update, context)
    elif any(w in text for w in ['factura','emitir','crear']):
        await factura(update, context)
    elif any(w in text for w in ['hola','hi','hello','buenas']):
        await start(update, context)
    else:
        await update.message.reply_text(
            "Puedo ayudarte con:\n• ISR, IVA, deducciones\n• Estrategia fiscal\n• Obligaciones\n• Sincronizar SAT\n• Crear factura\n\nPregúntame algo 😊", parse_mode='HTML')

async def button(update: Update, context):
    q = update.callback_query; await q.answer()
    d = q.data
    if d=='dash':
        s = api_get("/dashboard").get("summary",{})
        await q.message.edit_text(f"📊 <b>Dashboard</b>\n\nIngresos: ${s.get('total_ingresos',0):,.2f}\nEgresos: ${s.get('total_egresos',0):,.2f}\nDeducible: ${s.get('total_deducible',0):,.2f}\nAhorro ISR: ${s.get('ahorro_isr_estimado',0):,.2f}", parse_mode='HTML')
    elif d=='cfdis':
        c = api_get("/cfdis").get("cfdis",[])
        t = f"📄 <b>CFDIs: {len(c)}</b>\n\n"
        for x in c[:10]: t += f"• ${x.get('monto',0):,.2f} - {h(x.get('nombre_emisor',x.get('emisor',''))[:25])}\n"
        await q.message.edit_text(t, parse_mode='HTML')
    elif d=='factura':
        kb = [[InlineKeyboardButton("🌐 Abrir Mini App", web_app=WebAppInfo(url=WEBAPP))]]
        await q.message.edit_text("📝 <b>Crear Factura</b>\n\nUsa la Mini App para facturas completas con múltiples conceptos:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    elif d=='estrategia':
        s = api_get("/dashboard").get("summary",{})
        await q.message.edit_text(f"💡 <b>Estrategia</b>\n\nIngresos: ${s.get('total_ingresos',0):,.2f}\nDeducciones: ${s.get('total_deducible',0):,.2f}\nAhorro ISR: ${s.get('ahorro_isr_estimado',0):,.2f}\n\n1. Maximiza deducciones\n2. Acredita IVA\n3. Evalúa Régimen 626", parse_mode='HTML')
    elif d=='oblig':
        o = api_get("/obligaciones").get("obligaciones_pendientes",[])
        t = "📅 <b>Obligaciones</b>\n\n"
        for x in o[:5]:
            e = {"critical":"🔴","high":"🟡","normal":"🟢"}.get(x.get("urgencia",""),"⚪")
            t += f"{e} {h(x.get('titulo',''))} - {x.get('dias_restantes','?')}d\n"
        await q.message.edit_text(t or "✅ Todo al día", parse_mode='HTML')
    elif d=='opinion':
        o = api_get("/opinion")
        await q.message.edit_text(f"🔒 <b>Opinión SAT:</b> {h(str(o.get('status','Error')))}", parse_mode='HTML')
    elif d=='sync':
        today = date.today(); r = api_post("/sync", {"date_start":(today-timedelta(days=30)).isoformat(),"date_end":today.isoformat(),"tipo":"recibidos"})
        if r.get("status")=="submitted":
            await q.message.edit_text(f"📥 Sync iniciada ✅\n\nID: <code>{h(r['id_solicitud'])}</code>\nEspera ~60s.", parse_mode='HTML')
        else:
            await q.message.edit_text(f"❌ {h(str(r.get('message',r)))}", parse_mode='HTML')

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("cfdis", cfdis))
    app.add_handler(CommandHandler("obligaciones", obligaciones))
    app.add_handler(CommandHandler("opinion", opinion))
    app.add_handler(CommandHandler("estrategia", estrategia))
    app.add_handler(CommandHandler("sync", sync_sat))
    app.add_handler(CommandHandler("factura", factura))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 FiscoMind Bot v3.0 starting...")
    app.run_polling()

if __name__ == "__main__":
    main()