"""Módulo de repartidor: Consulta de pedidos, actualización de entrega y GPS."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

async def callback_en_camino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
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
            f"🚀 <b>Pedido #{pedido_id} marcado como EN CAMINO.</b>\nEnvíale tu ubicación GPS actual al cliente y luego presiona Entregado.",
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode="HTML",
        )

        try:
            from app.bot.cliente import notificar_cliente_cambio_estado
            await notificar_cliente_cambio_estado(
                context, pedido_id, "🛵💨 <b>¡Tu pedido está EN CAMINO!</b>\nEl repartidor ya salió del restaurante."
            )
        except Exception as e:
            print(f"Aviso notificación cliente: {e}")
    else:
        db.close()

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

# --- NUEVO: Rastreo GPS (Issue #41) ---
async def recibir_ubicacion_gps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enruta la ubicación enviada por el repartidor al cliente del pedido en camino."""
    if not update.message or not update.message.location or not update.effective_user:
        return

    lat = update.message.location.latitude
    lon = update.message.location.longitude
    db = SessionLocal()

    repartidor = db.query(Usuario).filter(Usuario.telegram_id == str(update.effective_user.id)).first()
    if not repartidor:
        db.close()
        return

    # Buscar el pedido EN CAMINO de este repartidor
    pedido = db.query(Pedido).filter(
        Pedido.repartidor_id == getattr(repartidor, "id"),
        Pedido.estado == EstadoPedido.EN_CAMINO
    ).first()

    if pedido:
        pedido_id = getattr(pedido, "id")
        cliente_id = getattr(pedido, "usuario_id") # O cliente_id dependiendo de tu modelo exacto
        cliente = db.query(Usuario).filter(Usuario.id == cliente_id).first()
        db.close()

        if cliente and getattr(cliente, "telegram_id"):
            chat_cliente = int(getattr(cliente, "telegram_id"))
            enlace_mapa = f"https://www.google.com/maps?q={lat},{lon}"
            
            mensaje_cliente = (
                f"📍 <b>¡TU PEDIDO ESTÁ CERCA!</b>\n\n"
                f"El repartidor ha actualizado su posición en tiempo real para el Pedido #{pedido_id}.\n\n"
                f"🗺️ <a href='{enlace_mapa}'>Ver ubicación del repartidor en Google Maps</a>"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=chat_cliente,
                    text=mensaje_cliente,
                    parse_mode="HTML",
                    disable_web_page_preview=False
                )
                await update.message.reply_text("✅ Ubicación enviada al cliente con éxito.")
            except Exception as e:
                print(f"Error enviando GPS al cliente: {e}")
    else:
        db.close()
        await update.message.reply_text("📍 Ubicación recibida, pero no tienes pedidos en estado 'EN CAMINO'.")

def registrar_handlers_repartidor(app: Application) -> None:
    app.add_handler(CommandHandler("pedidos_pendientes", comando_pedidos_pendientes))
    app.add_handler(MessageHandler(filters.Regex("^🛵 Pedidos Pendientes$"), comando_pedidos_pendientes))
    # ⚡ Escucha de ubicación para reenviar al cliente (Issue #41)
    app.add_handler(MessageHandler(filters.LOCATION, recibir_ubicacion_gps))
    
    app.add_handler(CallbackQueryHandler(callback_tomar_pedido, pattern="^tomar_"))
    app.add_handler(CallbackQueryHandler(callback_en_camino, pattern="^encamino_"))
    app.add_handler(CallbackQueryHandler(callback_entregado, pattern="^entregado_"))