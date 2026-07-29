import os
from app.bot.admin import notificar_admin_nuevo_comprobante
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
from app.models.modelos import Usuario, Plato, Pedido, DetallePedido, RolUsuario, EstadoPedido

# Rutas de archivos
COMPROBANTES_DIR = os.path.join("docs", "comprobantes")
os.makedirs(COMPROBANTES_DIR, exist_ok=True)
RUTA_QR_PAGO = os.path.join("docs", "qr_pago.png")

# Estados para la FSM (ConversationHandler)
(
    SELECCIONANDO_PLATOS,
    SOLICITANDO_UBICACION,
    CONFIRMANDO_PEDIDO,
    ESPERANDO_COMPROBANTE,
) = range(4)


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

    if context.user_data is not None:
        context.user_data.clear()
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
    """Despliega los platillos disponibles con fotos reales y boton de agregar."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return SELECCIONANDO_PLATOS

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
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"No hay platillos disponibles en el menu para hoy ({fecha_hoy}).",
        )
        return SELECCIONANDO_PLATOS

    carrito = context.user_data.get("carrito", {}) if context.user_data is not None else {}

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🍽️ *Menú del Día ({fecha_hoy})*\nSelecciona los platillos que deseas agregar a tu carrito:",
        parse_mode="Markdown",
    )

    for plato in platos:
        p_id = getattr(plato, "id")
        nombre = getattr(plato, "nombre")
        desc = getattr(plato, "descripcion", "")
        precio = float(getattr(plato, "precio", 0.0))
        stock = int(getattr(plato, "stock", 0))
        img_path = getattr(plato, "imagen_path", None)
        cant_carrito = carrito.get(p_id, 0)

        texto_card = (
            f"🍲 *{nombre}*\n"
            f"📝 _{desc}_\n"
            f"💰 *Precio:* Bs. {precio:.2f}\n"
            f"📦 *Stock disponible:* {stock} unidades\n"
            f"🛒 *En tu carrito:* {cant_carrito}"
        )

        teclado = [[InlineKeyboardButton("➕ Agregar al Carrito", callback_data=f"agregar_{p_id}")]]
        reply_markup = InlineKeyboardMarkup(teclado)

        if img_path and os.path.exists(str(img_path)):
            with open(str(img_path), "rb") as foto:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=foto,
                    caption=texto_card,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=texto_card,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

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
    """Recibe las coordenadas GPS y solicita confirmacion final del pedido."""
    if not update.message or not update.message.location or context.user_data is None:
        return SOLICITANDO_UBICACION

    latitud = update.message.location.latitude
    longitud = update.message.location.longitude

    context.user_data["ubicacion"] = {
        "latitud": latitud,
        "longitud": longitud,
    }

    total = context.user_data.get("total_pedido", 0.0)

    mensaje_confirmacion = (
        f"Ubicacion recibida correctamente.\n"
        f"Coordenadas: Lat {latitud:.4f}, Lon {longitud:.4f}\n\n"
        f"Monto total: Bs. {total:.2f}\n\n"
        "Presiona el boton de abajo para registrar tu pedido y ver los datos de pago por QR."
    )

    teclado = [
        [InlineKeyboardButton("Confirmar Pedido y Ver QR", callback_data="confirmar_pedido_final")],
        [InlineKeyboardButton("Cancelar Pedido", callback_data="cancelar_pedido")],
    ]

    await update.message.reply_text(
        mensaje_confirmacion,
        reply_markup=InlineKeyboardMarkup(teclado),
    )
    return CONFIRMANDO_PEDIDO


async def registrar_pedido_bd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Persiste el pedido en BD, descuenta stock y envia foto de QR para pago."""
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat or context.user_data is None:
        return CONFIRMANDO_PEDIDO

    await query.answer()

    carrito = context.user_data.get("carrito", {})
    ubicacion = context.user_data.get("ubicacion", {})
    total = context.user_data.get("total_pedido", 0.0)

    if not carrito or not ubicacion:
        await query.edit_message_text(
            "Hubo un problema con la informacion de tu pedido. Por favor inicia nuevamente con /start."
        )
        return ConversationHandler.END

    db = SessionLocal()
    try:
        user = update.effective_user
        usuario = db.query(Usuario).filter(Usuario.telegram_id == str(user.id)).first()
        if not usuario:
            usuario = Usuario(
                telegram_id=str(user.id),
                nombre=getattr(user, "full_name", "Cliente Telegram"),
                rol=RolUsuario.CLIENTE,
            )
            db.add(usuario)
            db.commit()
            db.refresh(usuario)

        codigo_seg = f"PED-{int(datetime.now().timestamp())}"

        nuevo_pedido = Pedido(
            codigo_seguimiento=codigo_seg,
            cliente_id=getattr(usuario, "id"),
            monto_total=total,
            latitud_entrega=ubicacion.get("latitud"),
            longitud_entrega=ubicacion.get("longitud"),
            estado=EstadoPedido.PENDIENTE_PAGO,
        )
        db.add(nuevo_pedido)
        db.commit()
        db.refresh(nuevo_pedido)

        pedido_id = getattr(nuevo_pedido, "id")

        for plato_id, cantidad in carrito.items():
            plato = db.query(Plato).filter(Plato.id == plato_id).first()
            if plato:
                precio_plato = float(getattr(plato, "precio", 0.0))
                subtotal = precio_plato * cantidad

                detalle = DetallePedido(
                    pedido_id=pedido_id,
                    plato_id=getattr(plato, "id"),
                    cantidad=cantidad,
                    precio_unitario=precio_plato,
                    subtotal=subtotal,
                )
                db.add(detalle)

                stock_actual = int(getattr(plato, "stock", 0))
                setattr(plato, "stock", max(0, stock_actual - cantidad))

        db.commit()
        db.close()

        context.user_data["pedido_id"] = pedido_id

    except Exception as e:
        db.rollback()
        db.close()
        print(f"Error detallado en registro de pedido: {e}")
        await query.edit_message_text("Ocurrio un error al registrar tu pedido. Intenta nuevamente.")
        return ConversationHandler.END

    chat_id = update.effective_chat.id

    # Intentar eliminar el mensaje anterior de forma segura usando bot API
    if query.message:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=query.message.message_id,
            )
        except Exception:
            pass

    # Instructivo que acompaña a la imagen
    instrucciones_pago = (
        f"*Pedido #{pedido_id} registrado exitosamente*\n"
        f"Codigo: `{codigo_seg}`\n"
        f"*Monto Total: Bs. {total:.2f}*\n\n"
        "📱 *Escanea el QR adjunto para realizar tu pago:*\n"
        "• Banco: Banco Union\n"
        "• Cuenta: 10000012345678\n"
        "• Titular: Restaurante El Sabor Boliviano\n\n"
        "*Envía una FOTO de tu comprobante en este chat para procesar tu pedido.*"
    )

    # Enviar foto del QR si existe o mensaje simple mediante update.effective_chat
    if os.path.exists(RUTA_QR_PAGO):
        with open(RUTA_QR_PAGO, "rb") as foto_qr:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=foto_qr,
                caption=instrucciones_pago,
                parse_mode="Markdown",
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=instrucciones_pago,
            parse_mode="Markdown",
        )

    return ESPERANDO_COMPROBANTE


async def recibir_comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descarga la foto del comprobante con proteccion ante cortes de red."""
    if not update.message or not update.message.photo or context.user_data is None:
        return ESPERANDO_COMPROBANTE

    pedido_id = context.user_data.get("pedido_id")
    if not pedido_id:
        await update.message.reply_text("No se encontro un pedido activo. Por favor usa /start para iniciar.")
        return ConversationHandler.END

    foto = update.message.photo[-1]

    # Descarga blindada ante micro-cortes de red
    try:
        archivo_foto = await context.bot.get_file(foto.file_id)
        nombre_archivo = f"comprobante_pedido_{pedido_id}.jpg"
        ruta_guardado = os.path.join(COMPROBANTES_DIR, nombre_archivo)

        await archivo_foto.download_to_drive(ruta_guardado)

    except Exception as e:
        print(f"Aviso: Reintento de red al descargar comprobante: {e}")
        await update.message.reply_text(
            "Hubo un problema temporal de conexion al descargar la imagen.\n"
            "Por favor, vuelve a enviar la foto de tu comprobante."
        )
        return ESPERANDO_COMPROBANTE

    # Actualizar ruta en SQLite
    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if pedido:
        setattr(pedido, "comprobante_pago", ruta_guardado)
        db.commit()
        # Actualizar ruta en SQLite
    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if pedido:
        setattr(pedido, "comprobante_pago", ruta_guardado)
        db.commit()
    db.close()

    # Disparar notificacion automatica al administrador
    await notificar_admin_nuevo_comprobante(context, pedido_id)
    db.close()

    context.user_data.clear()

    mensaje_exito = (
        f"Comprobante recibido correctamente para el Pedido #{pedido_id}.\n\n"
        "Tu pago esta en proceso de verificacion por el administrador.\n"
        "Te notificaremos cuando tu pedido sea despachado.\n\n"
        "¡Gracias por tu compra!"
    )

    await update.message.reply_text(mensaje_exito)
    return ConversationHandler.END


async def cancelar_flujo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela el proceso activo y libera el estado de la FSM."""
    if context.user_data is not None:
        context.user_data.clear()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Proceso cancelado. Tu carrito ha sido limpiado.\n"
            "Escribe /start para iniciar un nuevo pedido."
        )
    elif update.message:
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
        "4. Confirma el pedido y envia la foto de tu comprobante QR."
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
    """Configura e inicializa la aplicacion unificada del bot (Issue #31)."""
    app = Application.builder().token(token).build()

    from app.bot.router import comando_start_router
    from app.bot.admin import registrar_handlers_admin
    from app.bot.repartidor import registrar_handlers_repartidor

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", comando_start_router)],
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
            CONFIRMANDO_PEDIDO: [
                CallbackQueryHandler(registrar_pedido_bd, pattern="^confirmar_pedido_final$"),
                CallbackQueryHandler(cancelar_flujo, pattern="^cancelar_pedido$"),
            ],
            ESPERANDO_COMPROBANTE: [
                MessageHandler(filters.PHOTO, recibir_comprobante),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar_flujo)],
    )

    app.add_handler(conv_handler)

    # Registrar handlers de Admin y Repartidor
    registrar_handlers_admin(app)
    registrar_handlers_repartidor(app)

    return app
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
            CONFIRMANDO_PEDIDO: [
                CallbackQueryHandler(registrar_pedido_bd, pattern="^confirmar_pedido_final$"),
                CallbackQueryHandler(cancelar_flujo, pattern="^cancelar_pedido$"),
            ],
            ESPERANDO_COMPROBANTE: [
                MessageHandler(filters.PHOTO, recibir_comprobante),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar_flujo)],
    )

    app.add_handler(conv_handler)
    return app