"""Módulo enrutador principal que gestiona el acceso según el rol del usuario."""
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from app.core.database import SessionLocal
from app.models.modelos import Usuario, RolUsuario


def obtener_teclado_por_rol(rol: RolUsuario) -> ReplyKeyboardMarkup:
    """Devuelve el teclado fijo inferior en Telegram según el rol del usuario."""
    if rol == RolUsuario.ADMINISTRADOR:
        teclado = [
            ["📥 Pagos Pendientes", "🍔 Gestionar Menú"],
            ["➕ Nuevo Platillo", "📊 Reporte de Ventas"], # ⚡ AQUÍ ESTÁ EL BOTÓN AÑADIDO
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
    """Intercepta /start, refresca el rol y despliega las opciones correspondientes."""
    if not update.effective_user or not update.message:
        return ConversationHandler.END

    user = update.effective_user
    nombre = getattr(user, "first_name", "Usuario")
    nombre_completo = getattr(user, "full_name", nombre)

    # 1. Limpiar memoria de conversación anterior
    if context.user_data is not None:
        context.user_data.clear()

    # 2. Obtener rol actualizado de la BD
    usuario = obtener_o_registrar_usuario(str(user.id), nombre_completo)
    rol = getattr(usuario, "rol", RolUsuario.CLIENTE)
    teclado = obtener_teclado_por_rol(rol)

    # 3. Mensajes personalizados por rol
    if rol == RolUsuario.ADMINISTRADOR:
        mensaje = (
            f"👑 *¡Panel de Administración — Chef {nombre}!* 👨‍🍳\n\n"
            "Usa los botones del menú de abajo para revisar los pagos recibidos, "
            "gestionar el stock, publicar nuevos platos o ver reportes:"
        )
    elif rol == RolUsuario.REPARTIDOR:
        mensaje = (
            f"🛵 *¡Panel de Entregas — {nombre}!* 💨\n\n"
            "Usa el botón de abajo para consultar los pedidos listos en cocina para entregar."
        )
    else:
        mensaje = (
            f"👋 *¡Bienvenido a El Sabor Boliviano, {nombre}!* 🇧🇴✨\n\n"
            "Selecciona una opción del menú de abajo para realizar tu pedido:"
        )

    await update.message.reply_text(mensaje, reply_markup=teclado, parse_mode="Markdown")
    
    # Si es cliente entra al estado 0, si es admin/repartidor finaliza FSM de cliente
    if rol == RolUsuario.CLIENTE:
        return 0
    return ConversationHandler.END