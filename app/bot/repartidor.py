"""Módulo de repartidor: Consulta de pedidos, actualización de entrega y GPS."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import TypeHandler
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Application,
    ContextTypes,
    filters,
)
from app.core.database import SessionLocal
from app.models.modelos import Pedido, Usuario, RolUsuario, EstadoPedido

async def comando_pedidos_pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    db = SessionLocal()
    repartidor = db.query(Usuario).filter(Usuario.telegram_id == str(user.id)).first()

    if not repartidor or getattr(repartidor, "rol") != RolUsuario.REPARTIDOR:
        db.close()
        await update.message.reply_text("Acceso denegado. Este panel es solo para repartidores.")
        return

    pedidos = (
        db.query(Pedido)
        .filter(
            (Pedido.estado == EstadoPedido.EN_PREPARACION)
            | ((Pedido.estado == EstadoPedido.ASIGNADO) & (Pedido.repartidor_id == getattr(repartidor, "id")))
            | ((Pedido.estado == EstadoPedido.EN_CAMINO) & (Pedido.repartidor_id == getattr(repartidor, "id")))
        )
        .all()
    )
    db.close()

    if not pedidos:
        await update.message.reply_text("✨ <b>¡Sin entregas pendientes!</b> No hay pedidos asignados en este momento.", parse_mode="HTML")
        return

    for p in pedidos:
        p_id = getattr(p, "id")
        estado = getattr(p, "estado")
        total = float(getattr(p, "monto_total", 0.0))
        lat = getattr(p, "latitud_entrega", 0.0)
        lon = getattr(p, "longitud_entrega", 0.0)

        enlace_maps = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else "Sin ubicación GPS"

        mensaje = (
            f"📦 <b>Pedido #{p_id}</b>\n"
            f"📌 <b>Estado:</b> {estado.value if hasattr(estado, 'value') else estado}\n"
            f"💰 <b>Monto a Cobrar:</b> Bs. {total:.2f}\n"
            f"📍 <b>Ubicación de entrega:</b> <a href='{enlace_maps}'>Abrir en Google Maps</a>"
        )

        teclado = []
        if estado == EstadoPedido.EN_PREPARACION:
            teclado.append([InlineKeyboardButton("🛵 Tomar Pedido", callback_data=f"tomar_{p_id}")])
        elif estado == EstadoPedido.ASIGNADO:
            teclado.append([InlineKeyboardButton("🚀 En Camino", callback_data=f"encamino_{p_id}")])
        elif estado == EstadoPedido.EN_CAMINO:
            teclado.append([InlineKeyboardButton("✅ Entregado", callback_data=f"entregado_{p_id}")])

        await update.message.reply_text(
            mensaje,
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

async def callback_tomar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return
    await query.answer()
    pedido_id = int(query.data.split("_")[1])

    db = SessionLocal()
    repartidor = db.query(Usuario).filter(Usuario.telegram_id == str(update.effective_user.id)).first()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()

    if pedido and repartidor:
        setattr(pedido, "repartidor_id", getattr(repartidor, "id"))
        setattr(pedido, "estado", EstadoPedido.ASIGNADO)
        db.commit()
        db.close()

        teclado = [[InlineKeyboardButton("🚀 En Camino", callback_data=f"encamino_{pedido_id}")]]
        await query.edit_message_text(
            f"🛵 <b>Pedido #{pedido_id} asignado a tu cuenta.</b>\nPresiona cuando salgas del restaurante a entregarlo:",
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode="HTML",
        )
    else:
        db.close()

from telegram import ReplyKeyboardMarkup, KeyboardButton
from app.bot.router import obtener_teclado_por_rol # Para restaurar el teclado luego

async def callback_en_camino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not update.effective_chat:
        return
        
    chat_seguro_id = update.effective_chat.id
    await query.answer()
    pedido_id = int(query.data.split("_")[1])

    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if pedido:
        setattr(pedido, "estado", EstadoPedido.EN_CAMINO)
        db.commit()
        db.close()

        teclado = [[InlineKeyboardButton("✅ Entregado", callback_data=f"entregado_{pedido_id}")]]
        await query.edit_message_text(
            f"🚀 <b>Pedido #{pedido_id} marcado como EN CAMINO.</b>\nCuando llegues, presiona Entregado.",
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode="HTML",
        )

        # ⚡ INSTRUCCIÓN AL REPARTIDOR PARA QUE USE EL GPS EN VIVO NATIVO
        instrucciones_gps = (
            "👇 <b>PASO REQUERIDO PARA RASTREO:</b>\n\n"
            "1. Toca el ícono del clip (📎) a la izquierda de la barra de chat.\n"
            "2. Selecciona <b>Ubicación</b>.\n"
            "3. Presiona <b>Compartir ubicación en tiempo real</b> (por 1 hora).\n\n"
            "<i>El cliente podrá ver tu movimiento en vivo en el mapa de Telegram.</i>"
        )
        
        await context.bot.send_message(chat_id=chat_seguro_id, text=instrucciones_gps, parse_mode="HTML")

        try:
            from app.bot.cliente import notificar_cliente_cambio_estado
            await notificar_cliente_cambio_estado(
                context, pedido_id, "🛵💨 <b>¡Tu pedido está EN CAMINO!</b>\nEl repartidor ya salió. En breves segundos recibirás su mapa en tiempo real."
            )
        except Exception:
            pass
    else:
        db.close()


async def rastreador_ubicacion_en_vivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Atrapa tanto el primer mensaje de GPS en vivo como sus actualizaciones continuas."""
    # En Telegram el GPS en vivo manda updates constantemente como "edited_message"
    msg = update.message or update.edited_message
    
    if not msg or not getattr(msg, "location", None) or not update.effective_user:
        return

    user_id = update.effective_user.id
    db = SessionLocal()
    
    repartidor = db.query(Usuario).filter(Usuario.telegram_id == str(user_id)).first()
    if not repartidor or getattr(repartidor, "rol") != RolUsuario.REPARTIDOR:
        db.close()
        return

    pedido = db.query(Pedido).filter(
        Pedido.repartidor_id == getattr(repartidor, "id"),
        Pedido.estado == EstadoPedido.EN_CAMINO
    ).first()

    if not pedido:
        db.close()
        return
        
    cliente = db.query(Usuario).filter(Usuario.id == getattr(pedido, "cliente_id")).first()
    db.close()
    
    if not cliente or not getattr(cliente, "telegram_id"):
        return
        
    chat_cliente = int(getattr(cliente, "telegram_id"))
    lat = msg.location.latitude
    lon = msg.location.longitude
    
    # ⚡ Si es un mensaje nuevo (acaba de presionar "Compartir ubicación en tiempo real")
    if update.message:
        live_period = getattr(msg.location, "live_period", None)
        
        if live_period:
            # Enviamos el mapa nativo que se mueve solo al cliente
            sent_msg = await context.bot.send_location(
                chat_id=chat_cliente,
                latitude=lat,
                longitude=lon,
                live_period=live_period
            )
            # Guardamos el ID del mensaje enviado al cliente para actualizarlo luego
            context.bot_data[f"tracking_{getattr(pedido, 'id')}"] = {
                "chat_id": chat_cliente,
                "message_id": sent_msg.message_id
            }
            await msg.reply_text("📡 <b>Señal GPS conectada.</b> El cliente ahora te ve moverse en el mapa.", parse_mode="HTML")
        else:
            # Mandó ubicación estática normal (sin movimiento)
            enlace = f"https://www.google.com/maps?q={lat},{lon}"
            await context.bot.send_message(chat_cliente, f"📍 El repartidor actualizó su posición (estática):\n<a href='{enlace}'>Ver Mapa</a>", parse_mode="HTML")
            await msg.reply_text("✅ Ubicación estática enviada. Para que se mueva sola usa 'Compartir ubicación en tiempo real'.")
            
    # ⚡ Si es una actualización (el repartidor caminó o manejó unos metros)
    elif update.edited_message:
        tracking = context.bot_data.get(f"tracking_{getattr(pedido, 'id')}")
        if tracking:
            try:
                # Movemos el pin del cliente sin enviarle un mensaje nuevo
                await context.bot.edit_message_live_location(
                    chat_id=tracking["chat_id"],
                    message_id=tracking["message_id"],
                    latitude=lat,
                    longitude=lon
                )
            except Exception:
                pass # Silenciamos errores por si la ubicación no cambió lo suficiente

# En tu función registrar_handlers_repartidor, quitas el de filters.LOCATION y pones:
def registrar_handlers_repartidor(app: Application) -> None:
    app.add_handler(CommandHandler("pedidos_pendientes", comando_pedidos_pendientes))
    app.add_handler(MessageHandler(filters.Regex("^🛵 Pedidos Pendientes$"), comando_pedidos_pendientes))
    
    # ⚡ Usamos TypeHandler porque es 100% seguro para atrapar el movimiento en vivo
    app.add_handler(TypeHandler(Update, rastreador_ubicacion_en_vivo))
    
    app.add_handler(CallbackQueryHandler(callback_tomar_pedido, pattern="^tomar_"))
    app.add_handler(CallbackQueryHandler(callback_en_camino, pattern="^encamino_"))
    app.add_handler(CallbackQueryHandler(callback_entregado, pattern="^entregado_"))
async def callback_entregado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    pedido_id = int(query.data.split("_")[1])

    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if pedido:
        setattr(pedido, "estado", EstadoPedido.ENTREGADO)
        db.commit()
        db.close()

        await query.edit_message_text(f"🎉 <b>Pedido #{pedido_id} marcado exitosamente como ENTREGADO.</b>", parse_mode="HTML")

        try:
            from app.bot.cliente import notificar_cliente_cambio_estado
            await notificar_cliente_cambio_estado(
                context, pedido_id, "🎉 <b>¡Pedido Entregado!</b> 🍽️\n¡Que disfrutes tu comida!"
            )
        except Exception as e:
            print(f"Aviso notificación cliente: {e}")
    else:
        db.close()
def registrar_handlers_repartidor(app: Application) -> None:
    app.add_handler(CommandHandler("pedidos_pendientes", comando_pedidos_pendientes))
    app.add_handler(MessageHandler(filters.Regex("^🛵 Pedidos Pendientes$"), comando_pedidos_pendientes))
    # ⚡ Escucha de ubicación para reenviar al cliente (Issue #41)
    app.add_handler(MessageHandler(filters.LOCATION, rastreador_ubicacion_en_vivo))
    
    app.add_handler(CallbackQueryHandler(callback_tomar_pedido, pattern="^tomar_"))
    app.add_handler(CallbackQueryHandler(callback_en_camino, pattern="^encamino_"))
    app.add_handler(CallbackQueryHandler(callback_entregado, pattern="^entregado_"))