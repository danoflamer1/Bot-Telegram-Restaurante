"""Módulo de repartidor: Consulta de pedidos y actualización de entrega."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, Application, ContextTypes
from app.core.database import SessionLocal
from app.models.modelos import Pedido, Usuario, RolUsuario, EstadoPedido


async def comando_pedidos_pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la lista de pedidos en preparacion o asignados al repartidor (Issue #28)."""
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    db = SessionLocal()
    repartidor = db.query(Usuario).filter(Usuario.telegram_id == str(user.id)).first()

    if not repartidor or getattr(repartidor, "rol") != RolUsuario.REPARTIDOR:
        db.close()
        await update.message.reply_text("Acceso denegado. Este comando es solo para repartidores.")
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
        await update.message.reply_text("No hay pedidos pendientes para entregar en este momento.")
        return

    for p in pedidos:
        p_id = getattr(p, "id")
        estado = getattr(p, "estado")
        total = float(getattr(p, "monto_total", 0.0))
        lat = getattr(p, "latitud_entrega", 0.0)
        lon = getattr(p, "longitud_entrega", 0.0)

        mensaje = (
            f"📦 *Pedido #{p_id}*\n"
            f"📌 Estado: `{estado.value if hasattr(estado, 'value') else estado}`\n"
            f"💰 Monto Total: Bs. {total:.2f}\n"
            f"📍 Coordenadas Delivery: Lat {lat}, Lon {lon}"
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
            parse_mode="Markdown",
        )


async def callback_tomar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asigna el pedido al repartidor que presiono el boton (Issue #29)."""
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
            f"🛵 *Pedido #{pedido_id} asignado a tu cuenta.*\nPresiona cuando salgas a entregarlo:",
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode="Markdown",
        )
    else:
        db.close()


async def callback_en_camino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cambia el estado del pedido a EN_CAMINO (Issue #30)."""
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
            f"🚀 *Pedido #{pedido_id} en camino al cliente.*\nPresiona cuando entregues el pedido:",
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode="Markdown",
        )
    else:
        db.close()


async def callback_entregado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marca el pedido como ENTREGADO (Issue #30)."""
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

        await query.edit_message_text(f"🎉 *Pedido #{pedido_id} marcado como ENTREGADO.*", parse_mode="Markdown")
    else:
        db.close()


def registrar_handlers_repartidor(app: Application) -> None:
    """Registra handlers del panel de repartidores."""
    app.add_handler(CommandHandler("pedidos_pendientes", comando_pedidos_pendientes))
    app.add_handler(CallbackQueryHandler(callback_tomar_pedido, pattern="^tomar_"))
    app.add_handler(CallbackQueryHandler(callback_en_camino, pattern="^encamino_"))
    app.add_handler(CallbackQueryHandler(callback_entregado, pattern="^entregado_"))