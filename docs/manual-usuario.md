# Manual de Usuario - Sistema MVP Restaurante (Bot de Telegram)

Este documento contiene la guía operativa detallada para la interacción con el sistema para los tres roles: **Cliente**, **Repartidor / Delivery** y **Administrador**, reflejando la implementación técnica real del proyecto.

---

## 1. Introducción y Control de Acceso

El sistema opera sobre la **Telegram Bot API** mediante un enrutador de roles que reconoce el perfil del usuario utilizando su `telegram_id` registrado en la base de datos:

* **Cliente:** Acceso libre para cualquier usuario de Telegram.
* **Repartidor:** Acceso restringido a usuarios cuyo `telegram_id` esté registrado con el rol `REPARTIDOR`.
* **Administrador:** Acceso restringido a usuarios con rol `ADMINISTRADOR`.

---

## 2. Rol 1: Cliente (Bot de Telegram)

### 2.1. Iniciar el bot y registro automático
1. Inicie el chat con el bot en Telegram y presione **Iniciar** o envíe el comando `/start`.
2. El bot creará automáticamente su perfil en la base de datos utilizando su identificador único de Telegram (`chat_id`).
3. Se desplegará el teclado principal con las opciones: `🍔 Ver Menú`, `🛒 Mi Carrito`, `📦 Mis Pedidos` y `❓ Ayuda`.

### 2.2. Explorar el menú de platillos
1. Presione el botón **🍔 Ver Menú**.
2. El bot consultará los platillos habilitados para la fecha actual cuyo stock sea mayor a cero.
3. Para cada platillo se mostrará una tarjeta con su foto, nombre, descripción, precio en Bolivianos (Bs.) y stock disponible.
4. Presione los botones inline `➕` para agregar las unidades requeridas a su carrito.

### 2.3. Gestión del carrito de compras
1. Presione en cualquier momento el botón **🛒 Mi Carrito**.
2. El bot le desplegará el desglose de productos seleccionados, cantidades, subtotales e importe total.
3. Puede ajustar cantidades, eliminar productos o vaciar el carrito mediante los botones interactivos.

### 2.4. Envío de ubicación y pago por QR
1. Dentro de la vista de su carrito, presione el botón **Confirmar Pedido**.
2. El bot le solicitará su punto de entrega. Presione el botón nativo **Enviar mi ubicación actual**.
3. Una vez registradas las coordenadas (`latitud` y `longitud`), el bot generará y enviará una foto con el **Código QR de Pago**, el monto total y su **código único de seguimiento**.

### 2.5. Envío de comprobante y estado del pedido
1. Realice la transferencia desde su aplicación bancaria y **envíe la foto o captura del comprobante** directamente al chat.
2. Su pedido pasará al estado `PENDIENTE_PAGO`.
3. Recibirá notificaciones automáticas cada vez que el administrador apruebe su pago o el repartidor cambie el estado de su orden:
   * 💳 **Pago Aprobado:** El pedido pasa a `EN_PREPARACION`.
   * 🛵 **En Camino:** El repartidor ha salido con su comida.
   * 🎉 **Entregado:** ¡Pedido entregado con éxito!

---

## 3. Rol 2: Repartidor / Delivery (Bot de Telegram)

### 3.1. Identificación por `telegram_id`
* **Sin tokens ni logins:** El repartidor solo debe enviar el comando `/start` o presionar las opciones del teclado.
* Si el `telegram_id` del usuario no coincide con un usuario registrado como `REPARTIDOR`, el bot responderá: *"Acceso denegado. Este panel es solo para repartidores."*

### 3.2. Bandeja de Pedidos Pendientes
1. Envíe el comando `/pedidos_pendientes` o presione el botón del teclado **🛵 Pedidos Pendientes**.
2. El bot buscará los pedidos que están en estado `EN_PREPARACION` (libres para tomar), o los pedidos `ASIGNADO` / `EN_CAMINO` vinculados a su cuenta.
3. Cada tarjeta de pedido mostrará:
   * Número de pedido (`#ID`).
   * Estado actual.
   * Monto a cobrar (Bs.).
   * Enlace directo `<Abrir Google Maps en>` generado con la latitud y longitud del cliente.

### 3.3. Ciclo de entrega
1. **Tomar Pedido (`🛵 Tomar Pedido`):** Presione este botón en un pedido en preparación. El pedido cambiará a estado `ASIGNADO` y se vinculará a su cuenta de repartidor.
2. **Marcar En Camino (`🚀 En Camino`):** Presione este botón al salir del restaurante.
   * El estado del pedido cambiará a `EN_CAMINO`.
   * El cliente recibirá una notificación automática: *"🛵💨 ¡Tu pedido está EN CAMINO!"*.
   * El bot le enviará instrucciones para activar el rastreo GPS.
3. **Confirmar Entrega (`✅ Entregado`):** Al entregar la comida al cliente, presione este botón.
   * El pedido cambiará al estado final `ENTREGADO`.
   * El cliente recibirá la alerta de finalización: *"🎉 ¡Pedido Entregado! 🍽️"*.

### 3.4. Transmisión de señal GPS en vivo (Live Location)
Al marcar un pedido como `EN_CAMINO`, el repartidor debe transmitir su movimiento en tiempo real:
1. Toque el icono del **clip (📎)** a la izquierda del chat en Telegram.
2. Seleccione **Ubicación**.
3. Elija la opción **Compartir ubicación en tiempo real** (seleccionar 1 hora).

---

## 4. Rol 3: Administrador (Bot de Telegram)

El perfil de administrador gestiona la operación del restaurante de forma nativa desde Telegram.

### 4.1. Recepción y validación de comprobantes de pago
* Cuando un cliente envía una foto de su transferencia, el bot ejecuta la función `notificar_admin_nuevo_comprobante`:
  * Envía una notificación con formato HTML a todos los administradores registrados.
  * Adjunta la foto del comprobante de pago.
  * Despliega botones inline: `✅ Aprobar Pago` y `❌ Rechazar Pago`.
* **Aprobar Pago:** Presione `✅ Aprobar Pago`. El pedido cambia a `EN_PREPARACION` y el caption de la foto se actualiza a `✅ PEDIDO #ID APROBADO Y EN PREPARACIÓN`.
* **Rechazar Pago:** Presione `❌ Rechazar Pago`. El pedido cambia a `CANCELADO` y se actualiza el mensaje a `❌ PEDIDO #ID RECHAZADO Y CANCELADO`.

### 4.2. Bandeja de pagos pendientes (`📥 Pagos Pendientes`)
* Si no pudo revisar un comprobante al momento de la notificación, presione **📥 Pagos Pendientes**.
* El bot buscará todos los pedidos registrados en estado `PENDIENTE_PAGO` y mostrará sus comprobantes con los botones para **Aprobar** o **Rechazar**.

### 4.3. Gestión global del menú y stock (`🍔 Gestionar Menú`)
1. Presione el botón **🍔 Gestionar Menú**.
2. El bot mostrará todo el catálogo global de platillos con su precio, stock actual y su estado para la fecha de hoy:
   * **Habilitado hoy:** Se muestra en el menú del cliente.
   * **Deshabilitado:** Oculto para los clientes.
3. **Acciones disponibles por platillo:**
   * **Toggle de disponibilidad (`❌ Deshabilitar` / `✅ Habilitar para Hoy`):** Presione el botón para ocultar o activar el plato para la fecha actual. Si el plato no tenía stock al habilitarse, el sistema le asignará 10 unidades automáticamente.
   * **Incrementar Stock (`➕ 5 Stock`):** Presione este botón para sumar 5 unidades de forma inmediata al stock del platillo.

### 4.4. Registro de un nuevo platillo paso a paso (`➕ Nuevo Platillo`)
Presione **➕ Nuevo Platillo** para iniciar el flujo guiado por máquina de estados (FSM):

1. **Nombre:** Escriba el nombre del platillo (Ej: *Hamburguesa Doble Carne*).
2. **Descripción:** Escriba la descripción (Ej: *Con queso cheddar, tocino y papas fritas*).
3. **Precio y Stock:** Envíe el precio y el stock inicial separados por un espacio (Ejemplo: `35.50 20`).
4. **Fotografía:** Envíe una fotografía del platillo preparado.
5. **Finalización:** El bot descargará la imagen en la carpeta `docs/platos/`, creará el registro en la base de datos asignando la fecha de hoy y confirmará: *"🎉 ¡Platillo registrado y habilitado exitosamente!"*.

### 4.5. Reporte financiero y consulta de tickets (`📊 Reporte de Ventas`)
1. Presione el botón **📊 Reporte de Ventas**.
2. El bot calculará el consolidado financiero del día:
   * 💵 **Ingresos Confirmados:** Suma total de los pedidos en estado `ENTREGADO`.
   * 📦 **Resumen General:** Cantidad de pedidos Entregados, En proceso y Cancelados.
3. **Consulta de Tickets Individuales:**
   * Debajo del reporte se generará un listado interactivo con los últimos 15 pedidos (Ej: `✅ Pedido #12 - Bs. 45.00`).
   * Presione cualquier pedido para abrir su **Ticket Detallado**, donde podrá consultar el nombre del cliente, el código de seguimiento y la lista exacta de productos comprados con sus subtotales.
   * Presione `🔙 Volver al Reporte` para regresar al resumen financiero.

---

## 5. Manejo de Excepciones y Preguntas Frecuentes

| Situación | Causa | Solución |
| :--- | :--- | :--- |
| **El repartidor intenta usar el bot y recibe "Acceso Denegado"** | Su `telegram_id` no está registrado con el rol `REPARTIDOR` | El administrador debe verificar que el usuario exista en la tabla `usuarios` con `rol = REPARTIDOR`. |
| **El cliente no ve la ubicación del repartidor en movimiento** | El repartidor envió una ubicación estática en lugar de Live Location | El repartidor debe seleccionar "Compartir ubicación en tiempo real" al presionar el icono del clip. |
| **El platillo desaparece del menú del cliente** | El stock llegó a 0 o la fecha del menú no corresponde a la fecha actual | El administrador debe presionar `🍔 Gestionar Menú` y presionar `✅ Habilitar para Hoy` o `➕ 5 Stock`. |
| **Formato de precio y stock rechazado en FSM** | Se ingresaron letras o un formato incorrecto | Se deben enviar dos valores separados por espacio (Ejemplo: `25.50 10`). |