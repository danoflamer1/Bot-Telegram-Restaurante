from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from app.core.database import SessionLocal
from app.models.modelos import Usuario, Plato, RolUsuario


def obtener_o_crear_usuario(telegram_id: str, nombre_usuario: str):
    """Identifica al cliente por su Chat ID y lo persiste si es nuevo."""
    db = SessionLocal()
    usuario = db.query(Usuario).filter(Usuario.telegram_id == str(telegram_id)).first()
    if not usuario:
        usuario = Usuario(
            telegram_id=str(telegram_id),
            nombre=nombre_usuario or "Cliente Telegram",
            rol=RolUsuario.CLIENTE,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
    db.close()
    return usuario


async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler del comando /start: Identifica cliente y muestra bienvenida."""
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    nombre_mostrar = getattr(user, "first_name", "Cliente")
    nombre_completo = getattr(user, "full_name", nombre_mostrar)

    obtener_o_crear_usuario(str(user.id), nombre_completo)

    mensaje = (
        f"Hola, {nombre_mostrar}. Bienvenido al sistema de pedidos.\n\n"
        "Consulta nuestro menu del dia y realiza tu pedido desde este chat.\n"
        "Usa las opciones para interactuar:"
    )

    teclado = [
        [InlineKeyboardButton("Ver Menu del Dia", callback_data="ver_menu")],
        [InlineKeyboardButton("Ayuda", callback_data="ver_ayuda")],
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    await update.message.reply_text(mensaje, reply_markup=reply_markup)


async def mostrar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta la BD por fecha y stock, generando botones inline."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    db = SessionLocal()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    platos = (
        db.query(Plato)
        .filter(
            Plato.fecha_menu == fecha_hoy,
            Plato.disponible == True,
            Plato.stock > 0,
        )
        .all()
    )
    db.close()

    if not platos:
        await query.edit_message_text(
            f"No hay platos disponibles en el menu para hoy ({fecha_hoy}).\n"
            "Por favor, intenta de nuevo mas tarde."
        )
        return

    mensaje = f"Menu del Dia ({fecha_hoy})\nSelecciona un plato para agregar a tu pedido:\n"
    teclado = []

    for plato in platos:
        texto_boton = f"{plato.nombre} - Bs. {plato.precio:.2f} (Disp: {plato.stock})"
        teclado.append(
            [InlineKeyboardButton(texto_boton, callback_data=f"plato_{plato.id}")]
        )

    teclado.append([InlineKeyboardButton("Volver al Inicio", callback_data="inicio")])
    reply_markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(mensaje, reply_markup=reply_markup)


async def callback_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la informacion de ayuda."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    mensaje = (
        "Instrucciones de Uso:\n\n"
        "1. Selecciona 'Ver Menu del Dia'.\n"
        "2. Elige tus platos deseados.\n"
        "3. Adjunta tu ubicacion GPS.\n"
        "4. Escanea el QR y envia tu comprobante de pago."
    )
    teclado = [[InlineKeyboardButton("Volver al Inicio", callback_data="inicio")]]
    await query.edit_message_text(
        mensaje, reply_markup=InlineKeyboardMarkup(teclado)
    )


async def callback_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Regresa al menu principal del comando start."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    mensaje = "Menu Principal. Selecciona una opcion:"
    teclado = [
        [InlineKeyboardButton("Ver Menu del Dia", callback_data="ver_menu")],
        [InlineKeyboardButton("Ayuda", callback_data="ver_ayuda")],
    ]
    await query.edit_message_text(
        mensaje, reply_markup=InlineKeyboardMarkup(teclado)
    )


def crear_aplicacion_bot(token: str) -> Application:
    """Configura e inicializa la aplicacion del bot."""
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(CallbackQueryHandler(mostrar_menu, pattern="^ver_menu$"))
    app.add_handler(CallbackQueryHandler(callback_ayuda, pattern="^ver_ayuda$"))
    app.add_handler(CallbackQueryHandler(callback_inicio, pattern="^inicio$"))

    return app