"""Módulo de administración avanzada: Notificación de comprobantes, FSM nuevo plato con foto, gestión de stock y pagos."""
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    Application,
    filters,
)
from app.core.database import SessionLocal
from app.models.modelos import Pedido, Usuario, Plato, RolUsuario, EstadoPedido

# Directorio para guardar imagenes de platillos
PLATOS_DIR = os.path.join("docs", "platos")
os.makedirs(PLATOS_DIR, exist_ok=True)

# Estados FSM para crear un nuevo platillo
(
    NOMBRE_PLATO,
    DESCRIPCION_PLATO,
    PRECIO_STOCK_PLATO,
    FOTO_PLATO,
) = range(10, 14)


# --- 1. NOTIFICACIÓN AUTOMÁTICA AL ADMIN (Mantenida intacta) ---
async def notificar_admin_nuevo_comprobante(context: ContextTypes.DEFAULT_TYPE, pedido_id: int):
    """Envia una notificacion con la foto del comprobante a todos los administradores."""
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


# --- 2. BANDEJA DE PAGOS PENDIENTES (Botón '📥 Pagos Pendientes') ---
async def ver_pagos_pendientes_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la lista de comprobantes que requieren revision del administrador."""
    if not update.message:
        return

    db = SessionLocal()
    pedidos = db.query(Pedido).filter(Pedido.estado == EstadoPedido.PENDIENTE_PAGO).all()
    db.close()

    if not pedidos:
        await update.message.reply_text("✅ No hay comprobantes de pago pendientes de revision.")
        return

    for p in pedidos:
        p_id = getattr(p, "id")
        codigo = str(getattr(p, "codigo_seguimiento", ""))
        total = float(getattr(p, "monto_total", 0.0))
        ruta = str(getattr(p, "comprobante_pago", ""))

        texto = (
            f"📦 *Pedido #{p_id}*\n"
            f"🔑 Codigo: `{codigo}`\n"
            f"💰 Monto Total: Bs. {total:.2f}\n"
            "Estado: Esperando Aprobacion"
        )
        teclado = [
            [
                InlineKeyboardButton("✅ Aprobar", callback_data=f"aprobar_{p_id}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar_{p_id}"),
            ]
        ]
        markup = InlineKeyboardMarkup(teclado)

        if os.path.exists(ruta):
            with open(ruta, "rb") as foto:
                await update.message.reply_photo(photo=foto, caption=texto, reply_markup=markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


# --- 3. GESTIÓN DE MENÚ Y STOCK (Botón '🍔 Gestionar Menú') ---
async def gestionar_menu_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Despliega los platos del dia para que el Admin alterne disponibilidad o aumente stock."""
    if not update.message:
        return

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    db = SessionLocal()
    platos = db.query(Plato).filter(Plato.fecha_menu == fecha_hoy).all()
    db.close()

    if not platos:
        await update.message.reply_text(f"No hay platillos creados para la fecha de hoy ({fecha_hoy}).")
        return

    for plato in platos:
        p_id = getattr(plato, "id")
        nombre = getattr(plato, "nombre")
        stock = int(getattr(plato, "stock", 0))
        disp = bool(getattr(plato, "disponible", True))

        estado_txt = "🟢 Disponible" if disp else "🔴 Pausado"
        texto = f"🍔 *{nombre}*\nEstado: {estado_txt}\nStock: {stock} unidades"

        btn_estado = "Pausar ⏸️" if disp else "Activar 🟢"
        teclado = [
            [
                InlineKeyboardButton(btn_estado, callback_data=f"toggle_{p_id}"),
                InlineKeyboardButton("➕ 5 Stock", callback_data=f"addstock_{p_id}_5"),
            ]
        ]
        await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="Markdown")


async def callback_toggle_disponible(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alterna el estado disponible de un plato."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    plato_id = int(query.data.split("_")[1])

    db = SessionLocal()
    plato = db.query(Plato).filter(Plato.id == plato_id).first()
    if plato:
        nuevo_val = not bool(getattr(plato, "disponible"))
        setattr(plato, "disponible", nuevo_val)
        db.commit()
        db.close()

        estado_txt = "🟢 Disponible" if nuevo_val else "🔴 Pausado"
        await query.edit_message_text(f"Estado actualizado a: {estado_txt}")
    else:
        db.close()


async def callback_add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suma stock a un plato."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    partes = query.data.split("_")
    plato_id, cant = int(partes[1]), int(partes[2])

    db = SessionLocal()
    plato = db.query(Plato).filter(Plato.id == plato_id).first()
    if plato:
        stock_actual = int(getattr(plato, "stock", 0))
        setattr(plato, "stock", stock_actual + cant)
        db.commit()
        db.close()

        await query.edit_message_text(f"✅ Stock actualizado: {stock_actual + cant} unidades.")
    else:
        db.close()


# --- 4. FSM CREAR NUEVO PLATILLO CON FOTO (Botón '➕ Nuevo Platillo') ---
async def iniciar_crear_platillo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el flujo FSM para crear un nuevo platillo."""
    if not update.message or context.user_data is None:
        return ConversationHandler.END

    context.user_data["nuevo_plato"] = {}
    await update.message.reply_text("➕ *Nuevo Platillo*\n\nPor favor, escribe el *nombre* del platillo:")
    return NOMBRE_PLATO


async def recibir_nombre_plato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda el nombre y solicita la descripcion."""
    if not update.message or not update.message.text or context.user_data is None:
        return NOMBRE_PLATO

    context.user_data["nuevo_plato"]["nombre"] = update.message.text
    await update.message.reply_text("Escribe una breve *descripcion* del platillo:")
    return DESCRIPCION_PLATO


async def recibir_descripcion_plato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda la descripcion y solicita precio y stock."""
    if not update.message or not update.message.text or context.user_data is None:
        return DESCRIPCION_PLATO

    context.user_data["nuevo_plato"]["descripcion"] = update.message.text
    await update.message.reply_text("Ingresa el *precio* y el *stock* separado por espacio (Ejemplo: `25.50 15`):")
    return PRECIO_STOCK_PLATO


async def recibir_precio_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda precio y stock y solicita la foto."""
    if not update.message or not update.message.text or context.user_data is None:
        return PRECIO_STOCK_PLATO

    try:
        partes = update.message.text.split()
        precio = float(partes[0])
        stock = int(partes[1])

        context.user_data["nuevo_plato"]["precio"] = precio
        context.user_data["nuevo_plato"]["stock"] = stock

        await update.message.reply_text("📷 Ahora envía una *FOTO* del platillo preparado:")
        return FOTO_PLATO
    except Exception:
        await update.message.reply_text("Formato invalido. Ingresa precio y stock separado por espacio (Ejemplo: `25.50 15`):")
        return PRECIO_STOCK_PLATO


async def recibir_foto_plato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descarga la foto y guarda el platillo en la BD."""
    if not update.message or not update.message.photo or context.user_data is None:
        return FOTO_PLATO

    foto = update.message.photo[-1]
    datos = context.user_data.get("nuevo_plato", {})

    # Guardar foto
    archivo_foto = await context.bot.get_file(foto.file_id)
    nombre_img = f"plato_{int(datetime.now().timestamp())}.jpg"
    ruta_img = os.path.join(PLATOS_DIR, nombre_img)
    await archivo_foto.download_to_drive(ruta_img)

    # Persistir en BD
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    db = SessionLocal()
    nuevo = Plato(
        nombre=datos.get("nombre", "Plato"),
        descripcion=datos.get("descripcion", ""),
        precio=datos.get("precio", 0.0),
        stock=datos.get("stock", 0),
        fecha_menu=fecha_hoy,
        disponible=True,
        imagen_path=ruta_img,
    )
    db.add(nuevo)
    db.commit()
    db.close()

    context.user_data.pop("nuevo_plato", None)
    await update.message.reply_text(f"🎉 *¡Platillo '{datos.get('nombre')}' registrado y habilitado exitosamente!*")
    return ConversationHandler.END


# --- 5. CALLBACKS DE APROBACIÓN Y RECHAZO ---
async def callback_aprobar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para aprobar pago."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    p_id = int(query.data.split("_")[1])

    db = SessionLocal()
    p = db.query(Pedido).filter(Pedido.id == p_id).first()
    if p:
        setattr(p, "estado", EstadoPedido.EN_PREPARACION)
        db.commit()
        db.close()
        await query.edit_message_caption(caption=f"✅ *PEDIDO #{p_id} APROBADO Y EN PREPARACION*", parse_mode="Markdown")
    else:
        db.close()


async def callback_rechazar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para rechazar pago."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    p_id = int(query.data.split("_")[1])

    db = SessionLocal()
    p = db.query(Pedido).filter(Pedido.id == p_id).first()
    if p:
        setattr(p, "estado", EstadoPedido.CANCELADO)
        db.commit()
        db.close()
        await query.edit_message_caption(caption=f"❌ *PEDIDO #{p_id} RECHAZADO Y CANCELADO*", parse_mode="Markdown")
    else:
        db.close()


def registrar_handlers_admin(app: Application) -> None:
    """Registra handlers de administración en la app de Telegram."""
    conv_nuevo_plato = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Nuevo Platillo$"), iniciar_crear_platillo)],
        states={
            NOMBRE_PLATO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre_plato)],
            DESCRIPCION_PLATO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_descripcion_plato)],
            PRECIO_STOCK_PLATO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_precio_stock)],
            FOTO_PLATO: [MessageHandler(filters.PHOTO, recibir_foto_plato)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_nuevo_plato)
    app.add_handler(MessageHandler(filters.Regex("^📥 Pagos Pendientes$"), ver_pagos_pendientes_admin))
    app.add_handler(MessageHandler(filters.Regex("^🍔 Gestionar Menú$"), gestionar_menu_admin))
    app.add_handler(CallbackQueryHandler(callback_toggle_disponible, pattern="^toggle_"))
    app.add_handler(CallbackQueryHandler(callback_add_stock, pattern="^addstock_"))
    app.add_handler(CallbackQueryHandler(callback_aprobar_pago, pattern="^aprobar_"))
    app.add_handler(CallbackQueryHandler(callback_rechazar_pago, pattern="^rechazar_"))