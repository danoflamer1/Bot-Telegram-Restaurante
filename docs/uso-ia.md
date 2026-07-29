# Registro de uso de asistentes de IA

Herramientas utilizadas: Gemini (Google)[cite: 1].

| Fecha | Issue / PR | Para qué se usó | Qué devolvió | Cómo se verificó | Qué se modificó |
|---|---|---|---|---|---|
| 2026-07-27 | #1, #2, #3, #4, #5 | Estructuración inicial de repositorio y CI/CD | Estructura de carpetas, flujo de CI y plantillas | Se ejecutó prueba de sintaxis y validación local | Adaptación completa al idioma español y nombres de rutas |
| 2026-07-27 | #7, #8, #9, #10 |Pruebas con pytest |Tests unitarios | Ejecución local de pytest| Ajustes en nombres de campos de estado y restricciones |
| 2026-07-28 | #11, #12, #13, #14 | Implementación de bot cliente, persistencia por chat id y teclado inline de menú | Handlers de /start, callback query handlers y consultas filtradas por fecha | Pruebas de ejecución del bot y validación de inserción en SQLite | Adaptación del formato de mensaje y manejo de excepciones |
| 2026-07-28 | #15, #16, #17, #18 | Maquina de estados configurada, carrito de compras interactivo y captura de ubicacion GPS | Estados, calculo de totales, filtros de ubicacion y cancelacion | Pruebas de flujo completo de seleccion, validacion de stock y recepcion de coordenadas | Ajuste de respuestas para teclados nativos e inline |
| 2026-07-28 | #19, #20, #21, #22 | Persistencia de pedidos, descuento de stock, datos QR y captura de comprobantes de pago | Manejo de transacciones SQLAlchemy, flujo de descarga de imagenes y estados FSM | Verificacion de guardado de comprobantes en disco y registros en SQLite con descontado de stock | Optimizacion de nombres de archivo de comprobante por ID de pedido |
| 2026-07-28 | #24, #25, #26, #27, #28, #29, #30, #31 | Enrutador multirrol, notificaciones admin y panel de repartidor | Implementacion de router por BD, envio asincrono de notificaciones con foto y handlers de delivery | Verificacion de transiciones de estado de pedido (PENDIENTE_PAGO -> EN_PREPARACION -> ASIGNADO -> EN_CAMINO -> ENTREGADO) | Arquitectura modular desacoplada en app/bot/ |
| 2026-07-28 | #23 | Envio de foto QR y tolerancia a fallos de red en comprobantes | Integracion de send_photo con captura de excepciones httpx.ConnectError | Verificacion de reintento de foto en chat de Telegram y guardado en SQLite | Optimizacion UX mediante eliminacion dinamica del mensaje anterior |
## Dónde NO se usó IA
[Módulos o decisiones resueltas integramente por el postulante.][cite: 1]

## Declaración
Comprendo todo el código de este repositorio y puedo explicarlo, justificarlo y modificarlo sin asistencia[cite: 1].