"""Módulo enrutador principal con teclados persistentes por rol."""
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from app.core.database import SessionLocal
from app.models.modelos import Usuario, RolUsuario


def obtener_teclado_por_rol(rol: RolUsuario) -> ReplyKeyboardMarkup:
    """Devuelve el teclado fijo inferior en Telegram segun el rol del usuario."""
    if rol == RolUsuario.ADMINISTRADOR:
        teclado = [
            ["📥 Pagos Pendientes", "🍔 Gestionar Menú"],
            ["➕ Nuevo Platillo", "📊 Reporte de Ventas"],
        ]
    elif rol == RolUsuario.REPARTIDOR:
        teclado = [
            ["🛵 Pedidos Pendientes"],
        ]
    else:
        # CLIENTE
        teclado = [
            ["🍔 Ver Menú del Día", "🛒 Mi Carrito"],
            ["❓ Ayuda"],
        ]

    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)


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
    """Intercepta el comando /start o mensajes generales y despliega el teclado persistente."""
    if not update.effective_user or not update.message:
        return ConversationHandler.END

    user = update.effective_user
    nombre = getattr(user, "first_name", "Usuario")
    nombre_completo = getattr(user, "full_name", nombre)

    usuario = obtener_o_registrar_usuario(str(user.id), nombre_completo)
    rol = getattr(usuario, "rol", RolUsuario.CLIENTE)
    teclado = obtener_teclado_por_rol(rol)

    if rol == RolUsuario.ADMINISTRADOR:
        mensaje = f"👑 *Panel de Administracion - Restaurante El Sabor Boliviano*\nHola {nombre}. Selecciona una opcion del menu inferior:"
    elif rol == RolUsuario.REPARTIDOR:
        mensaje = f"🛵 *Panel de Delivery*\nHola {nombre}. Presiona el boton inferior para consultar entregas pendientes:"
    else:
        mensaje = f"👋 ¡Hola, {nombre}! Bienvenido a nuestro restaurante.\nUsa el menu interactivo de abajo para realizar tu pedido:"

    await update.message.reply_text(mensaje, reply_markup=teclado, parse_mode="Markdown")
    return ConversationHandler.END