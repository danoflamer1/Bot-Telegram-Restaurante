"""Módulo enrutador principal que gestiona el acceso según el rol del usuario."""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from app.core.database import SessionLocal
from app.models.modelos import Usuario, RolUsuario


def obtener_o_registrar_usuario(telegram_id: str, nombre: str) -> Usuario:
    """Busca al usuario en la BD o lo registra como CLIENTE por defecto."""
    db = SessionLocal()
    usuario = db.query(Usuario).filter(Usuario.telegram_id == str(telegram_id)).first()
    if not usuario:
        usuario = Usuario(
            telegram_id=str(telegram_id),
            nombre=nombre or "Usuario Telegram",
            rol=RolUsuario.CLIENTE,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
    db.close()
    return usuario


async def comando_start_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Identifica el rol del usuario y muestra el mensaje inicial de bienvenida."""
    if not update.effective_user or not update.message:
        return ConversationHandler.END

    user = update.effective_user
    nombre_completo = getattr(user, "full_name", "Usuario")

    usuario = obtener_o_registrar_usuario(str(user.id), nombre_completo)
    rol = getattr(usuario, "rol", RolUsuario.CLIENTE)

    if rol == RolUsuario.ADMINISTRADOR:
        mensaje = (
            f"👑 *Bienvenido al Panel de Administracion*, {nombre_completo}.\n\n"
            "Desde este chat recibiras notificaciones automaticas de comprobantes de pago "
            "y podras aprobar o rechazar pedidos en tiempo real."
        )
        await update.message.reply_text(mensaje, parse_mode="Markdown")
        return ConversationHandler.END

    elif rol == RolUsuario.REPARTIDOR:
        mensaje = (
            f"🛵 *Bienvenido al Panel de Delivery*, {nombre_completo}.\n\n"
            "Usa el comando /pedidos_pendientes para ver los pedidos en preparacion y listos para entregar."
        )
        await update.message.reply_text(mensaje, parse_mode="Markdown")
        return ConversationHandler.END

    # Si es CLIENTE, redirige al comando_start normal del cliente
    from app.bot.cliente import comando_start
    return await comando_start(update, context)