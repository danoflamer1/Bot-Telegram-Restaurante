"""Módulo de administración avanzada: Notificación de comprobantes, FSM nuevo plato, menú global y reportes."""
import os
from datetime import datetime
from app.models.modelos import Pedido, Usuario, Plato, RolUsuario, EstadoPedido, DetallePedido
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

PLATOS_DIR = os.path.join("docs", "platos")
os.makedirs(PLATOS_DIR, exist_ok=True)

(NOMBRE_PLATO, DESCRIPCION_PLATO, PRECIO_STOCK_PLATO, FOTO_PLATO) = range(10, 14)

# --- 1. NOTIFICACIÓN AUTOMÁTICA AL ADMIN (Refactor HTML - Issue #38) ---
async def notificar_admin_nuevo_comprobante(context: ContextTypes.DEFAULT_TYPE, pedido_id: int):
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
        f"🚨 <b>NUEVO COMPROBANTE DE PAGO RECEPCIONADO</b>\n\n"
        f"📦 <b>Pedido:</b> #{pedido_id}\n"
        f"🔑 <b>Código:</b> <code>{codigo}</code>\n"
        f"💰 <b>Monto Total:</b> Bs. {total:.2f}\n\n"
        "Revisa la imagen del comprobante y selecciona una acción:"
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
                            parse_mode="HTML",
                        )
                else:
                    await context.bot.send_message(
                        chat_id=int(telegram_id),
                        text=texto_notificacion,
                        reply_markup=reply_markup,
                        parse_mode="HTML",
                    )
            except Exception as e:
                print(f"Error enviando notificación a admin {telegram_id}: {e}")

# --- 2. BANDEJA DE PAGOS PENDIENTES (Refactor HTML) ---
async def ver_pagos_pendientes_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    db = SessionLocal()
    pedidos = db.query(Pedido).filter(Pedido.estado == EstadoPedido.PENDIENTE_PAGO).all()
    db.close()

    if not pedidos:
        await update.message.reply_text("✅ <b>No hay comprobantes de pago pendientes de revisión.</b>", parse_mode="HTML")
        return

    for p in pedidos:
        p_id = getattr(p, "id")
        codigo = str(getattr(p, "codigo_seguimiento", ""))
        total = float(getattr(p, "monto_total", 0.0))
        ruta = str(getattr(p, "comprobante_pago", ""))

        texto = (
            f"📦 <b>Pedido #{p_id}</b>\n"
            f"🔑 Código: <code>{codigo}</code>\n"
            f"💰 Monto Total: Bs. {total:.2f}\n"
            "📌 Estado: <b>Esperando Aprobación</b>"
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
                await update.message.reply_photo(photo=foto, caption=texto, reply_markup=markup, parse_mode="HTML")
        else:
            await update.message.reply_text(texto, reply_markup=markup, parse_mode="HTML")


# --- 3. GESTIÓN DE MENÚ GLOBAL (Issue #39) ---
async def gestionar_menu_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra TODOS los platos (históricos y actuales) y permite gestionarlos."""
    if not update.message:
        return

    db = SessionLocal()
    platos = db.query(Plato).order_by(Plato.id.desc()).all()
    db.close()

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    if not platos:
        await update.message.reply_text("📋 <b>Catálogo Vacío.</b> No hay platillos registrados.", parse_mode="HTML")
        return

    await update.message.reply_text(f"🍔 <b>CATÁLOGO GLOBAL DE PLATILLOS</b>\n📅 <i>Menú activo: {fecha_hoy}</i>", parse_mode="HTML")

    for p in platos:
        p_id = getattr(p, "id")
        nombre = getattr(p, "nombre")
        precio = float(getattr(p, "precio", 0.0))
        stock = int(getattr(p, "stock", 0))
        disp = bool(getattr(p, "disponible", True))
        fecha_menu = str(getattr(p, "fecha_menu", ""))

        esta_activo_hoy = disp and (fecha_menu == fecha_hoy)

        if esta_activo_hoy:
            estado_txt = "✅ <b>HABILITADO HOY</b>"
            btn_estado = "❌ Deshabilitar"
        else:
            estado_txt = "❌ <b>DESHABILITADO</b>"
            btn_estado = "✅ Habilitar para Hoy"

        texto = f"🍲 <b>{nombre}</b>\n💰 Precio: Bs. {precio:.2f} | 📦 Stock: {stock}\n📌 Estado: {estado_txt}"

        teclado = [
            [
                InlineKeyboardButton(btn_estado, callback_data=f"toggle_{p_id}"),
                InlineKeyboardButton("➕ 5 Stock", callback_data=f"addstock_{p_id}_5"),
            ]
        ]
        await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="HTML")


async def callback_toggle_disponible(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    plato_id = int(query.data.split("_")[1])
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    db = SessionLocal()
    plato = db.query(Plato).filter(Plato.id == plato_id).first()
    if plato:
        esta_activo_hoy = bool(getattr(plato, "disponible")) and str(getattr(plato, "fecha_menu")) == fecha_hoy
        
        if esta_activo_hoy:
            setattr(plato, "disponible", False)
            estado_txt = "❌ DESHABILITADO"
        else:
            setattr(plato, "disponible", True)
            setattr(plato, "fecha_menu", fecha_hoy)
            if getattr(plato, "stock", 0) <= 0:
                setattr(plato, "stock", 10)
            estado_txt = "✅ HABILITADO PARA HOY"
            
        db.commit()
        db.close()
        await query.edit_message_text(f"📌 Estado actualizado a: <b>{estado_txt}</b>", parse_mode="HTML")
    else:
        db.close()

async def callback_add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await query.edit_message_text(f"✅ <b>Stock actualizado:</b> {stock_actual + cant} unidades.", parse_mode="HTML")
    else:
        db.close()

# --- 4. REPORTE DE VENTAS (Issue #40) ---
async def ver_reporte_ventas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera un reporte consolidado con botones interactivos para los pedidos."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return

    db = SessionLocal()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    pedidos = db.query(Pedido).all()
    
    entregados = [p for p in pedidos if getattr(p, "estado") == EstadoPedido.ENTREGADO]
    pendientes = [
        p for p in pedidos if getattr(p, "estado") in (
            EstadoPedido.PENDIENTE_PAGO, EstadoPedido.EN_PREPARACION, EstadoPedido.ASIGNADO, EstadoPedido.EN_CAMINO
        )
    ]
    cancelados = [p for p in pedidos if getattr(p, "estado") == EstadoPedido.CANCELADO]

    ingresos = sum(float(getattr(p, "monto_total", 0.0)) for p in entregados)
    
    # ⚡ Creamos un teclado interactivo con los últimos 15 pedidos (para no saturar la pantalla)
    teclado = []
    for p in pedidos[-15:]:
        p_id = getattr(p, "id")
        estado = getattr(p, "estado")
        total = float(getattr(p, "monto_total", 0.0))
        emoji = "✅" if estado == EstadoPedido.ENTREGADO else "❌" if estado == EstadoPedido.CANCELADO else "⏳"
        
        texto_btn = f"{emoji} Pedido #{p_id} - Bs. {total:.2f}"
        teclado.append([InlineKeyboardButton(texto_btn, callback_data=f"detalle_pedido_{p_id}")])

    db.close()

    reporte = (
        f"📊 <b>REPORTE FINANCIERO</b>\n"
        f"📅 <b>Fecha:</b> {fecha_hoy}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💵 <b>Ingresos Confirmados:</b> Bs. {ingresos:.2f}\n\n"
        f"📦 <b>Resumen General:</b>\n"
        f"  • ✅ Entregados: {len(entregados)}\n"
        f"  • ⏳ En proceso: {len(pendientes)}\n"
        f"  • ❌ Cancelados: {len(cancelados)}\n\n"
        f"👇 <b>Toca un pedido para ver su detalle:</b>"
    )

    markup = InlineKeyboardMarkup(teclado) if teclado else None

    # ⚡ SOLUCIÓN LINTER-FRIENDLY: Usamos context.bot.send_message con el chat_id validado
    if update.callback_query and update.callback_query.message:
        await update.callback_query.edit_message_text(text=reporte, reply_markup=markup, parse_mode="HTML")
    else:
        await context.bot.send_message(chat_id=chat_id, text=reporte, reply_markup=markup, parse_mode="HTML")
async def callback_detalle_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta los productos exactos de un pedido y muestra su ticket."""
    query = update.callback_query
    
    # ⚡ SOLUCIÓN LINTER: Validamos que 'query' exista antes de hacer answer()
    if not query or not query.data:
        return
        
    await query.answer()
    pedido_id = int(query.data.split("_")[2])
    
    db = SessionLocal()
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        db.close()
        return
        
    cliente = db.query(Usuario).filter(Usuario.id == getattr(pedido, "cliente_id")).first()
    nombre_cliente = getattr(cliente, "nombre", "Desconocido") if cliente else "Desconocido"
    
    # Buscar los productos comprados en este pedido
    detalles = db.query(DetallePedido).filter(DetallePedido.pedido_id == pedido_id).all()
    lista_items = []
    
    for d in detalles:
        plato = db.query(Plato).filter(Plato.id == getattr(d, "plato_id")).first()
        nombre_plato = getattr(plato, "nombre", "Plato Eliminado") if plato else "Plato"
        cant = getattr(d, "cantidad")
        subt = float(getattr(d, "subtotal", 0.0))
        lista_items.append(f"  • <b>{cant}x</b> {nombre_plato} <i>(Bs. {subt:.2f})</i>")
        
    db.close()
    
    texto_items = "\n".join(lista_items)
    estado_str = getattr(pedido, "estado").value if hasattr(getattr(pedido, "estado"), 'value') else str(getattr(pedido, "estado"))
    
    detalle_texto = (
        f"🧾 <b>TICKET DE PEDIDO #{pedido_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Cliente:</b> {nombre_cliente}\n"
        f"📌 <b>Estado:</b> <code>{estado_str.upper()}</code>\n"
        f"🔑 <b>Código:</b> {getattr(pedido, 'codigo_seguimiento')}\n\n"
        f"🛒 <b>Productos Comprados:</b>\n{texto_items}\n\n"
        f"💰 <b>Total Pagado:</b> Bs. {float(getattr(pedido, 'monto_total', 0)):.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    
    # Botón para regresar al menú de reportes
    teclado = [[InlineKeyboardButton("🔙 Volver al Reporte", callback_data="volver_reporte")]]
    
    # ⚡ Extra protección linter para el mensaje
    if query.message:
        await query.edit_message_text(text=detalle_texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="HTML")
# --- 5. FSM CREAR NUEVO PLATILLO ---
async def iniciar_crear_platillo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or context.user_data is None:
        return ConversationHandler.END
    context.user_data["nuevo_plato"] = {}
    await update.message.reply_text("➕ <b>Nuevo Platillo</b>\n\nPor favor, escribe el <b>nombre</b> del platillo:", parse_mode="HTML")
    return NOMBRE_PLATO

async def recibir_nombre_plato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or context.user_data is None:
        return NOMBRE_PLATO
    context.user_data["nuevo_plato"]["nombre"] = update.message.text
    await update.message.reply_text("Escribe una breve <b>descripción</b> del platillo:", parse_mode="HTML")
    return DESCRIPCION_PLATO

async def recibir_descripcion_plato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or context.user_data is None:
        return DESCRIPCION_PLATO
    context.user_data["nuevo_plato"]["descripcion"] = update.message.text
    await update.message.reply_text("Ingresa el <b>precio</b> y el <b>stock</b> separado por espacio (Ejemplo: <code>25.50 15</code>):", parse_mode="HTML")
    return PRECIO_STOCK_PLATO

async def recibir_precio_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or context.user_data is None:
        return PRECIO_STOCK_PLATO
    try:
        partes = update.message.text.split()
        context.user_data["nuevo_plato"]["precio"] = float(partes[0])
        context.user_data["nuevo_plato"]["stock"] = int(partes[1])
        await update.message.reply_text("📷 Ahora envía una <b>FOTO</b> del platillo preparado:", parse_mode="HTML")
        return FOTO_PLATO
    except Exception:
        await update.message.reply_text("Formato inválido. Ingresa precio y stock separado por espacio (Ejemplo: <code>25.50 15</code>):", parse_mode="HTML")
        return PRECIO_STOCK_PLATO

async def recibir_foto_plato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo or context.user_data is None:
        return FOTO_PLATO
    foto = update.message.photo[-1]
    datos = context.user_data.get("nuevo_plato", {})

    archivo_foto = await context.bot.get_file(foto.file_id)
    nombre_img = f"plato_{int(datetime.now().timestamp())}.jpg"
    ruta_img = os.path.join(PLATOS_DIR, nombre_img)
    await archivo_foto.download_to_drive(ruta_img)

    db = SessionLocal()
    nuevo = Plato(
        nombre=datos.get("nombre", "Plato"),
        descripcion=datos.get("descripcion", ""),
        precio=datos.get("precio", 0.0),
        stock=datos.get("stock", 0),
        fecha_menu=datetime.now().strftime("%Y-%m-%d"),
        disponible=True,
        imagen_path=ruta_img,
    )
    db.add(nuevo)
    db.commit()
    db.close()
    context.user_data.pop("nuevo_plato", None)
    await update.message.reply_text(f"🎉 <b>¡Platillo '{datos.get('nombre')}' registrado y habilitado exitosamente!</b>", parse_mode="HTML")
    return ConversationHandler.END

# --- 6. CALLBACKS DE APROBACIÓN ---# --- 6. CALLBACKS DE APROBACIÓN ---
async def callback_aprobar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        texto_estado = f"✅ <b>PEDIDO #{p_id} APROBADO Y EN PREPARACIÓN</b>"
        
        # ⚡ SOLUCIÓN SEGURA: Verificamos que el mensaje exista y extraemos 'photo' con getattr
        if query.message and getattr(query.message, "photo", None):
            await query.edit_message_caption(caption=texto_estado, parse_mode="HTML")
        else:
            await query.edit_message_text(text=texto_estado, parse_mode="HTML")
    else:
        db.close()

async def callback_rechazar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        texto_estado = f"❌ <b>PEDIDO #{p_id} RECHAZADO Y CANCELADO</b>"
        
        # ⚡ SOLUCIÓN SEGURA: Verificamos que el mensaje exista y extraemos 'photo' con getattr
        if query.message and getattr(query.message, "photo", None):
            await query.edit_message_caption(caption=texto_estado, parse_mode="HTML")
        else:
            await query.edit_message_text(text=texto_estado, parse_mode="HTML")
    else:
        db.close()
def registrar_handlers_admin(app: Application) -> None:
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
    app.add_handler(MessageHandler(filters.Regex("^📊 Reporte de Ventas$"), ver_reporte_ventas))
    app.add_handler(MessageHandler(filters.Regex("^📥 Pagos Pendientes$"), ver_pagos_pendientes_admin))
    app.add_handler(MessageHandler(filters.Regex("^🍔 Gestionar Menú$"), gestionar_menu_global))
    app.add_handler(CallbackQueryHandler(callback_detalle_pedido, pattern="^detalle_pedido_"))
    app.add_handler(CallbackQueryHandler(ver_reporte_ventas, pattern="^volver_reporte$"))
    app.add_handler(CallbackQueryHandler(callback_toggle_disponible, pattern="^toggle_"))
    app.add_handler(CallbackQueryHandler(callback_add_stock, pattern="^addstock_"))
    app.add_handler(CallbackQueryHandler(callback_aprobar_pago, pattern="^aprobar_"))
    app.add_handler(CallbackQueryHandler(callback_rechazar_pago, pattern="^rechazar_"))