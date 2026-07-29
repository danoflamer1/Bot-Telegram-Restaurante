import os
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
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
from app.bot.admin import notificar_admin_nuevo_comprobante

# Rutas de archivos
COMPROBANTES_DIR = os.path.join("docs", "comprobantes")
os.makedirs(COMPROBANTES_DIR, exist_ok=True)
RUTA_QR_PAGO = os.path.join("docs", "qr_pago.png")

# Estados para la FSM
(
    SELECCIONANDO_PLATOS,
    SOLICITANDO_UBICACION,
    CONFIRMANDO_PEDIDO,
    ESPERANDO_COMPROBANTE,
) = range(4)


async def notificar_cliente_cambio_estado(context: ContextTypes.DEFAULT_TYPE, pedido_id: int, mensaje_estado: str):
    """Envía un mensaje automático al cliente cuando cambia el estado de su pedido."""
    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        db.close()
        return

    # Usamos getattr(pedido, "cliente_id") para alinearnos a tu modelo
    usuario = db.query(Usuario).filter(Usuario.id == getattr(pedido, "cliente_id")).first()
    if not usuario or not getattr(usuario, "telegram_id"):
        db.close()
        return

    chat_id = int(getattr(usuario, "telegram_id"))
    codigo = str(getattr(pedido, "codigo_seguimiento", ""))
    db.close()

    texto = f"🔔 *ACTUALIZACIÓN DE TU PEDIDO #{pedido_id}*\n🔑 Código: `{codigo}`\n\n{mensaje_estado}"
    try:
        await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
    except Exception as e:
        print(f"Error notificando al cliente {chat_id}: {e}")


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

    from app.bot.router import obtener_teclado_por_rol
    teclado_persistente = obtener_teclado_por_rol(RolUsuario.CLIENTE)

    mensaje = (
        f"👋 *¡Hola, {nombre_mostrar}! Bienvenido a El Sabor Boliviano.* 🇧🇴✨\n\n"
        "Consulta nuestro menú del día y realiza tu pedido desde este chat.\n"
        "Usa las opciones del menú de abajo para interactuar:"
    )

    await update.message.reply_text(mensaje, reply_markup=teclado_persistente, parse_mode="Markdown")
    return SELECCIONANDO_PLATOS


async def mostrar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Despliega los platillos disponibles con fotos reales y botón de agregar."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return SELECCIONANDO_PLATOS

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    db = SessionLocal()
    platos = (
        db.query(Plato)
        .filter(
            Plato.fecha_menu == fecha_hoy,
            Plato.disponible == True,
            Plato.stock > 0,
        )
        .all()
    )

    lista_platos = [
        {
            "id": getattr(p, "id"),
            "nombre": getattr(p, "nombre"),
            "desc": getattr(p, "descripcion", ""),
            "precio": float(getattr(p, "precio", 0.0)),
            "stock": int(getattr(p, "stock", 0)),
            "img_path": getattr(p, "imagen_path", None),
        }
        for p in platos
    ]
    db.close()

    if not lista_platos:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📋 *No hay platillos disponibles en el menú para hoy ({fecha_hoy}).*",
            parse_mode="Markdown",
        )
        return SELECCIONANDO_PLATOS

    carrito = context.user_data.get("carrito", {}) if context.user_data is not None else {}

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🍽️ *Menú del Día ({fecha_hoy})*\nSelecciona los platillos que deseas pedir:",
        parse_mode="Markdown",
    )

    for p in lista_platos:
        p_id = p["id"]
        cant_carrito = carrito.get(p_id, 0)

        texto_card = (
            f"🍲 *{p['nombre']}*\n"
            f"📝 _{p['desc']}_\n"
            f"💰 *Precio:* `Bs. {p['precio']:.2f}`\n"
            f"📦 *Stock disponible:* {p['stock']} porciones\n"
            f"🛒 *En tu carrito:* {cant_carrito}"
        )

        teclado = [[InlineKeyboardButton("➕ Agregar al Carrito", callback_data=f"agregar_{p_id}")]]
        reply_markup = InlineKeyboardMarkup(teclado)

        if p["img_path"] and os.path.exists(str(p["img_path"])):
            with open(str(p["img_path"]), "rb") as foto:
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

    await query.answer(f"Se agregó {plato.nombre} al carrito.")
    return SELECCIONANDO_PLATOS


async def ver_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el resumen de items en el carrito."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id or context.user_data is None:
        return SELECCIONANDO_PLATOS

    carrito = context.user_data.get("carrito", {})

    if not carrito:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛒 *Tu carrito está vacío.* Presiona *🍔 Ver Menú del Día* para agregar delicias.",
            parse_mode="Markdown",
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
            lineas_resumen.append(f"• *{cantidad}x* {plato.nombre} — `Bs. {subtotal:.2f}`")

    db.close()

    total = calcular_total_carrito(items_calculo)
    context.user_data["total_pedido"] = total

    resumen_texto = "🛒 *RESUMEN DE TU CARRITO:*\n\n" + "\n".join(lineas_resumen)
    resumen_texto += f"\n\n💵 *TOTAL A PAGAR:* `Bs. {total:.2f}`"

    teclado = [
        [InlineKeyboardButton("📍 Enviar Ubicación y Pedir", callback_data="pedir_ubicacion")],
        [InlineKeyboardButton("🗑️ Vaciar Carrito", callback_data="vaciar_carrito")],
    ]

    await context.bot.send_message(
        chat_id=chat_id,
        text=resumen_texto,
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode="Markdown",
    )
    return SELECCIONANDO_PLATOS


async def vaciar_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Limpia el carrito activo del cliente."""
    query = update.callback_query
    if query:
        await query.answer("Carrito vaciado.")

    if context.user_data is not None:
        context.user_data["carrito"] = {}

    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id:
        await context.bot.send_message(chat_id=chat_id, text="🗑️ Tu carrito ha sido vaciado correctamente.")
    return SELECCIONANDO_PLATOS


async def solicitar_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Solicita la ubicación GPS utilizando el teclado nativo de Telegram."""
    query = update.callback_query
    if query:
        await query.answer()

    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id:
        teclado_gps = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Compartir mi Ubicación Actual GPS", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text="📍 *Ubicación para la Entrega*\nPor favor, presiona el botón de abajo para enviar tu ubicación GPS actual:",
            reply_markup=teclado_gps,
            parse_mode="Markdown",
        )
    return SOLICITANDO_UBICACION


async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe las coordenadas GPS y solicita confirmación final."""
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
        f"📍 *Ubicación recibida correctamente.*\n"
        f"Coordenadas: Lat `{latitud:.4f}`, Lon `{longitud:.4f}`\n\n"
        f"💰 *Monto total:* `Bs. {total:.2f}`\n\n"
        "Presiona el botón de abajo para registrar tu pedido y ver los datos de pago por QR:"
    )

    teclado = [
        [InlineKeyboardButton("✅ Confirmar Pedido y Ver QR", callback_data="confirmar_pedido_final")],
        [InlineKeyboardButton("❌ Cancelar Pedido", callback_data="cancelar_pedido")],
    ]

    await update.message.reply_text(
        mensaje_confirmacion,
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode="Markdown",
    )
    return CONFIRMANDO_PEDIDO


async def registrar_pedido_bd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Persiste el pedido en BD con el atributo cliente_id y subtotal en DetallePedido."""
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat or context.user_data is None:
        return CONFIRMANDO_PEDIDO

    await query.answer()

    carrito = context.user_data.get("carrito", {})
    ubicacion = context.user_data.get("ubicacion", {})
    total = context.user_data.get("total_pedido", 0.0)

    if not carrito or not ubicacion:
        await query.edit_message_text(
            "Hubo un problema con la información de tu pedido. Por favor inicia nuevamente con /start."
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

        # ⚡ 1. Uso exacto de cliente_id de tu modelo
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
                subtotal_item = precio_plato * cantidad

                # ⚡ 2. Asignación explícita de subtotal para DetallePedido
                detalle = DetallePedido(
                    pedido_id=pedido_id,
                    plato_id=getattr(plato, "id"),
                    cantidad=cantidad,
                    precio_unitario=precio_plato,
                    subtotal=subtotal_item,
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
        await query.edit_message_text("Ocurrió un error al registrar tu pedido. Intenta nuevamente.")
        return ConversationHandler.END

    chat_id = update.effective_chat.id

    instrucciones_pago = (
        f"✅ *Pedido #{pedido_id} registrado exitosamente*\n"
        f"🔑 Código: `{codigo_seg}`\n"
        f"💰 *Monto Total: Bs. {total:.2f}*\n\n"
        "📱 *Escanea el QR adjunto para realizar tu pago:*\n"
        "• Banco: Banco Unión\n"
        "• Cuenta: 10000012345678\n"
        "• Titular: Restaurante El Sabor Boliviano\n\n"
        "📸 *Envía una FOTO de tu comprobante en este chat para procesar tu pedido.*"
    )

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
    """Guarda la foto del comprobante y avisa al administrador."""
    if not update.message or not update.message.photo or context.user_data is None:
        return ESPERANDO_COMPROBANTE

    pedido_id = context.user_data.get("pedido_id")
    if not pedido_id:
        await update.message.reply_text("No se encontró un pedido activo. Por favor usa /start para iniciar.")
        return ConversationHandler.END

    foto = update.message.photo[-1]

    try:
        archivo_foto = await context.bot.get_file(foto.file_id)
        nombre_archivo = f"comprobante_pedido_{pedido_id}.jpg"
        ruta_guardado = os.path.join(COMPROBANTES_DIR, nombre_archivo)

        await archivo_foto.download_to_drive(ruta_guardado)

    except Exception as e:
        print(f"Aviso: Reintento de red al descargar comprobante: {e}")
        await update.message.reply_text(
            "Hubo un problema temporal de conexión al descargar la imagen.\n"
            "Por favor, vuelve a enviar la foto de tu comprobante."
        )
        return ESPERANDO_COMPROBANTE

    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if pedido:
        setattr(pedido, "comprobante_pago", ruta_guardado)
        db.commit()
    db.close()

    # Disparar notificación automática al administrador
    await notificar_admin_nuevo_comprobante(context, pedido_id)

    from app.bot.router import obtener_teclado_por_rol
    teclado_persistente = obtener_teclado_por_rol(RolUsuario.CLIENTE)

    mensaje_exito = (
        f"🎉 *¡Comprobante recibido para el Pedido #{pedido_id}!*\n\n"
        "Tu pago está en proceso de verificación por el administrador.\n"
        "Te notificaremos cuando tu pedido sea enviado a cocina. ¡Gracias por tu compra!"
    )

    await update.message.reply_text(mensaje_exito, reply_markup=teclado_persistente, parse_mode="Markdown")
    return SELECCIONANDO_PLATOS


async def cancelar_flujo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela el proceso activo y libera el estado."""
    if context.user_data is not None:
        context.user_data.clear()

    from app.bot.router import obtener_teclado_por_rol
    teclado_persistente = obtener_teclado_por_rol(RolUsuario.CLIENTE)

    msg = "Proceso cancelado. Tu carrito ha sido limpiado."
    chat_id = update.effective_chat.id if update.effective_chat else None

    if update.callback_query:
        await update.callback_query.answer()
        if chat_id:
            await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=teclado_persistente)
    elif update.message:
        await update.message.reply_text(msg, reply_markup=teclado_persistente)

    return SELECCIONANDO_PLATOS


async def callback_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la información de ayuda."""
    texto = (
        "❓ *Instrucciones de Uso:*\n\n"
        "1. Usa /start para iniciar el bot.\n"
        "2. Toca *🍔 Ver Menú del Día* en tu teclado.\n"
        "3. Agrega los platos deseados a tu carrito.\n"
        "4. Toca *🛒 Mi Carrito* y presiona *Enviar Ubicación*.\n"
        "5. Escanea el código QR y envía la foto de tu comprobante."
    )
    chat_id = update.effective_chat.id if update.effective_chat else None

    if update.callback_query:
        await update.callback_query.answer()
        if chat_id:
            await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(texto, parse_mode="Markdown")

    return SELECCIONANDO_PLATOS


def crear_aplicacion_bot(token: str) -> Application:
    """Configura e inicializa la aplicacion unificada del bot para todos los roles."""
    app = Application.builder().token(token).build()

    from app.bot.router import comando_start_router
    from app.bot.admin import registrar_handlers_admin
    from app.bot.repartidor import registrar_handlers_repartidor

    # 1. Registrar primero los handlers de Admin y Repartidor para mayor prioridad
    registrar_handlers_admin(app)
    registrar_handlers_repartidor(app)

    # 2. Registrar la conversacion principal de Cliente e inicio
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", comando_start_router),
            MessageHandler(filters.Regex("^🍔 Ver Menú del Día$"), mostrar_menu),
            MessageHandler(filters.Regex("^🛒 Mi Carrito$"), ver_carrito),
            MessageHandler(filters.Regex("^❓ Ayuda$"), callback_ayuda),
        ],
        states={
            SELECCIONANDO_PLATOS: [
                MessageHandler(filters.Regex("^🍔 Ver Menú del Día$"), mostrar_menu),
                CallbackQueryHandler(mostrar_menu, pattern="^ver_menu$"),
                CallbackQueryHandler(agregar_al_carrito, pattern="^agregar_"),
                MessageHandler(filters.Regex("^🛒 Mi Carrito$"), ver_carrito),
                CallbackQueryHandler(ver_carrito, pattern="^ver_carrito$"),
                CallbackQueryHandler(vaciar_carrito, pattern="^vaciar_carrito$"),
                CallbackQueryHandler(solicitar_ubicacion, pattern="^pedir_ubicacion$"),
                MessageHandler(filters.Regex("^❓ Ayuda$"), callback_ayuda),
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
        fallbacks=[
            CommandHandler("cancelar", cancelar_flujo),
            CommandHandler("start", comando_start_router),
        ],
        per_message=False,
    )

    app.add_handler(conv_handler)

    return app