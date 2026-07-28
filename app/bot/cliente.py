from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from app.core.database import SessionLocal
from app.core.logica import calcular_total_carrito, validar_stock_disponible
from app.models.modelos import Usuario, Plato, RolUsuario

# Estados para la FSM (ConversationHandler)
SELECCIONANDO_PLATOS, SOLICITANDO_UBICACION, CONFIRMANDO_PEDIDO = range(3)


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
    """Handler del comando /start: Limpia contexto previo y muestra bienvenida."""
    if not update.message or not update.effective_user:
        return ConversationHandler.END

    user = update.effective_user
    nombre_mostrar = getattr(user, "first_name", "Cliente")
    nombre_completo = getattr(user, "full_name", nombre_mostrar)

    obtener_o_crear_usuario(str(user.id), nombre_completo)

    # Inicializar carrito en el contexto de la sesion
    if context.user_data is not None:
        context.user_data["carrito"] = {}

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
    return SELECCIONANDO_PLATOS


async def mostrar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta la BD y despliega los platos con sus opciones de agregado."""
    query = update.callback_query
    if not query:
        return SELECCIONANDO_PLATOS

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
        return ConversationHandler.END

    carrito = context.user_data.get("carrito", {}) if context.user_data is not None else {}
    mensaje = f"Menu del Dia ({fecha_hoy})\nSelecciona un plato para agregarlo al carrito:\n"
    teclado = []

    for plato in platos:
        cant_en_carrito = carrito.get(plato.id, 0)
        precio_val = getattr(plato, "precio", 0.0)
        texto_boton = f"{plato.nombre} - Bs. {precio_val:.2f} [En carrito: {cant_en_carrito}]"
        teclado.append(
            [InlineKeyboardButton(texto_boton, callback_data=f"agregar_{plato.id}")]
        )

    if carrito:
        teclado.append([InlineKeyboardButton("Ver Carrito / Confirmar", callback_data="ver_carrito")])

    teclado.append([InlineKeyboardButton("Volver al Inicio", callback_data="inicio")])
    reply_markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(mensaje, reply_markup=reply_markup)
    return SELECCIONANDO_PLATOS


async def agregar_al_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Agrega una unidad del plato seleccionado al carrito validando stock."""
    query = update.callback_query
    if not query or not query.data or context.user_data is None:
        return SELECCIONANDO_PLATOS

    plato_id = int(query.data.split("_")[1])
    carrito = context.user_data.get("carrito", {})

    db = SessionLocal()
    plato = db.query(Plato).filter(Plato.id == plato_id).first()
    db.close()

    if not plato:
        await query.answer("El plato seleccionado ya no existe.", show_alert=True)
        return SELECCIONANDO_PLATOS

    cantidad_actual = carrito.get(plato_id, 0)
    stock_int: int = getattr(plato, "stock", 0)

    if not validar_stock_disponible(stock_int, cantidad_actual + 1):
        await query.answer(f"Stock insuficiente. Solo quedan {stock_int} unidades disponibles.", show_alert=True)
        return SELECCIONANDO_PLATOS

    carrito[plato_id] = cantidad_actual + 1
    context.user_data["carrito"] = carrito

    await query.answer(f"Se agrego {plato.nombre} al carrito.")
    return await mostrar_menu(update, context)


async def ver_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el resumen de items en el carrito con total recalculado."""
    query = update.callback_query
    if not query or context.user_data is None:
        return SELECCIONANDO_PLATOS

    await query.answer()
    carrito = context.user_data.get("carrito", {})

    if not carrito:
        await query.edit_message_text(
            "Tu carrito esta vacio. Agrega platos desde el menu para continuar.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Ver Menu", callback_data="ver_menu")]
            ]),
        )
        return SELECCIONANDO_PLATOS

    db = SessionLocal()
    items_calculo = []
    lineas_resumen = []

    for plato_id, cantidad in carrito.items():
        plato = db.query(Plato).filter(Plato.id == plato_id).first()
        if plato:
            precio_float: float = getattr(plato, "precio", 0.0)
            subtotal = precio_float * cantidad
            items_calculo.append({"precio": precio_float, "cantidad": cantidad})
            lineas_resumen.append(f"- {plato.nombre} x{cantidad} = Bs. {subtotal:.2f}")

    db.close()

    total = calcular_total_carrito(items_calculo)
    context.user_data["total_pedido"] = total

    resumen_texto = "Tu Carrito de Compras:\n\n" + "\n".join(lineas_resumen)
    resumen_texto += f"\n\nTotal a Pagar: Bs. {total:.2f}"

    teclado = [
        [InlineKeyboardButton("Confirmar y Enviar Ubicacion", callback_data="pedir_ubicacion")],
        [InlineKeyboardButton("Vaciar Carrito", callback_data="vaciar_carrito")],
        [InlineKeyboardButton("Seguir Comprando", callback_data="ver_menu")],
    ]

    await query.edit_message_text(resumen_texto, reply_markup=InlineKeyboardMarkup(teclado))
    return SELECCIONANDO_PLATOS


async def vaciar_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Limpia el carrito activo del cliente."""
    query = update.callback_query
    if not query or context.user_data is None:
        return SELECCIONANDO_PLATOS

    await query.answer("Carrito vaciado.")
    context.user_data["carrito"] = {}
    return await mostrar_menu(update, context)


async def solicitar_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Solicita la ubicacion GPS utilizando el teclado nativo de Telegram."""
    query = update.callback_query
    if not query or not query.message or not hasattr(query.message, "chat_id"):
        return SOLICITANDO_UBICACION

    await query.answer()

    teclado_gps = ReplyKeyboardMarkup(
        [[KeyboardButton("Enviar mi Ubicacion Actual GPS", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Para realizar la entrega de tu pedido, por favor presiona el boton de abajo para compartir tu ubicacion GPS actual:",
        reply_markup=teclado_gps,
    )
    return SOLICITANDO_UBICACION


async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe y almacena las coordenadas enviadas por el usuario."""
    if not update.message or not update.message.location or context.user_data is None:
        return SOLICITANDO_UBICACION

    latitud = update.message.location.latitude
    longitud = update.message.location.longitude

    context.user_data["ubicacion"] = {
        "latitud": latitud,
        "longitud": longitud,
    }

    mensaje_confirmacion = (
        f"Ubicacion recibida correctamente.\n"
        f"Coordenadas: Lat {latitud:.4f}, Lon {longitud:.4f}\n\n"
        f"Monto total: Bs. {context.user_data.get('total_pedido', 0.0):.2f}\n\n"
        "Escribe /confirmar para registrar tu pedido."
    )

    await update.message.reply_text(
        mensaje_confirmacion,
        reply_markup=ReplyKeyboardRemove(),
    )
    return CONFIRMANDO_PEDIDO


async def cancelar_flujo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela el proceso activo y libera el estado de la FSM."""
    if context.user_data is not None:
        context.user_data.clear()

    if update.message:
        await update.message.reply_text(
            "Proceso cancelado. Tu carrito ha sido limpiado.\n"
            "Escribe /start para iniciar un nuevo pedido.",
            reply_markup=ReplyKeyboardRemove(),
        )
    return ConversationHandler.END


async def callback_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la informacion de ayuda."""
    query = update.callback_query
    if not query:
        return SELECCIONANDO_PLATOS

    await query.answer()

    mensaje = (
        "Instrucciones de Uso:\n\n"
        "1. Selecciona 'Ver Menu del Dia'.\n"
        "2. Agrega los platos deseados al carrito.\n"
        "3. Envia tu ubicacion GPS usando el boton de teclado.\n"
        "4. Confirma el pedido para enviar comprobante."
    )
    teclado = [[InlineKeyboardButton("Volver al Inicio", callback_data="inicio")]]
    
    await query.edit_message_text(
        mensaje, reply_markup=InlineKeyboardMarkup(teclado)
    )
    return SELECCIONANDO_PLATOS


async def callback_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Regresa al menu principal de la aplicacion."""
    query = update.callback_query
    if not query:
        return SELECCIONANDO_PLATOS

    await query.answer()

    mensaje = "Menu Principal. Selecciona una opcion:"
    teclado = [
        [InlineKeyboardButton("Ver Menu del Dia", callback_data="ver_menu")],
        [InlineKeyboardButton("Ayuda", callback_data="ver_ayuda")],
    ]
    
    await query.edit_message_text(
        mensaje, reply_markup=InlineKeyboardMarkup(teclado)
    )
    return SELECCIONANDO_PLATOS


def crear_aplicacion_bot(token: str) -> Application:
    """Configura e inicializa la aplicacion del bot con FSM ConversationHandler."""
    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", comando_start)],
        states={
            SELECCIONANDO_PLATOS: [
                CallbackQueryHandler(mostrar_menu, pattern="^ver_menu$"),
                CallbackQueryHandler(agregar_al_carrito, pattern="^agregar_"),
                CallbackQueryHandler(ver_carrito, pattern="^ver_carrito$"),
                CallbackQueryHandler(vaciar_carrito, pattern="^vaciar_carrito$"),
                CallbackQueryHandler(solicitar_ubicacion, pattern="^pedir_ubicacion$"),
                CallbackQueryHandler(callback_ayuda, pattern="^ver_ayuda$"),
                CallbackQueryHandler(callback_inicio, pattern="^inicio$"),
            ],
            SOLICITANDO_UBICACION: [
                MessageHandler(filters.LOCATION, recibir_ubicacion),
            ],
            CONFIRMANDO_PEDIDO: [],
        },
        fallbacks=[CommandHandler("cancelar", cancelar_flujo)],
    )

    app.add_handler(conv_handler)
    return app