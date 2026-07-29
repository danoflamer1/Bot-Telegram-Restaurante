"""Módulo de administración: Verificación de pagos y cambio de estados."""
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, Application
from app.core.database import SessionLocal
from app.models.modelos import Pedido, Usuario, RolUsuario, EstadoPedido


async def notificar_admin_nuevo_comprobante(context: ContextTypes.DEFAULT_TYPE, pedido_id: int):
    """Envia una notificacion con la foto del comprobante a todos los administradores (Issue #25)."""
    db = SessionLocal()
    admins = db.query(Usuario).filter(Usuario.rol == RolUsuario.ADMINISTRADOR).all()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()

    if not pedido or not admins:
        db.close()
        return

    ruta_comprobante = str(getattr(pedido, "comprobante_pago", ""))
    total = float(getattr(pedido, "monto_total", 0.0))
    codigo = str(getattr(pedido, "codigo_seguimiento", ""))
    db.close()

    texto_notificacion = (
        f"🚨 *NUEVO COMPROBANTE DE PAGO RECEPCIONADO*\n\n"
        f"📦 *Pedido:* #{pedido_id}\n"
        f"🔑 *Codigo:* `{codigo}`\n"
        f"💰 *Monto Total:* Bs. {total:.2f}\n\n"
        "Revisa la imagen del comprobante y selecciona una accion:"
    )

    teclado = [
        [
            InlineKeyboardButton("✅ Aprobar Pago", callback_data=f"aprobar_{pedido_id}"),
            InlineKeyboardButton("❌ Rechazar Pago", callback_data=f"rechazar_{pedido_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    for admin in admins:
        telegram_id = getattr(admin, "telegram_id", None)
        if telegram_id:
            try:
                if os.path.exists(ruta_comprobante):
                    with open(ruta_comprobante, "rb") as foto:
                        await context.bot.send_photo(
                            chat_id=int(telegram_id),
                            photo=foto,
                            caption=texto_notificacion,
                            reply_markup=reply_markup,
                            parse_mode="Markdown",
                        )
                else:
                    await context.bot.send_message(
                        chat_id=int(telegram_id),
                        text=texto_notificacion,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
            except Exception as e:
                print(f"Error enviando notificacion a admin {telegram_id}: {e}")


async def callback_aprobar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para que el admin apruebe un pago (Issue #26)."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    pedido_id = int(query.data.split("_")[1])

    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if pedido:
        setattr(pedido, "estado", EstadoPedido.EN_PREPARACION)
        db.commit()
        db.close()

        await query.edit_message_caption(
            caption=f"✅ *PEDIDO #{pedido_id} APROBADO Y EN PREPARACION*",
            parse_mode="Markdown",
        )
    else:
        db.close()
        await query.answer("El pedido ya no existe.", show_alert=True)


async def callback_rechazar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para que el admin rechace un pago (Issue #27)."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    pedido_id = int(query.data.split("_")[1])

    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if pedido:
        setattr(pedido, "estado", EstadoPedido.CANCELADO)
        db.commit()
        db.close()

        await query.edit_message_caption(
            caption=f"❌ *PEDIDO #{pedido_id} RECHAZADO Y CANCELADO*",
            parse_mode="Markdown",
        )
    else:
        db.close()
        await query.answer("El pedido ya no existe.", show_alert=True)


def registrar_handlers_admin(app: Application) -> None:
    """Registra los callback handlers de administración."""
    app.add_handler(CallbackQueryHandler(callback_aprobar_pago, pattern="^aprobar_"))
    app.add_handler(CallbackQueryHandler(callback_rechazar_pago, pattern="^rechazar_"))