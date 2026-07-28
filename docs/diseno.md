# Documento de Diseño Técnico

## 1. Arquitectura del Sistema
El sistema sigue una arquitectura monolítica modular compuesta por:
- **Bot de Telegram (Cliente & Delivery):** Basado en `python-telegram-bot` en modo Polling/Webhook[cite: 1].
- **Panel Web de Administración:** Desarrollado en `FastAPI` con plantillas Jinja2[cite: 1].
- **Capa de Persistencia:** `SQLite` gestionado mediante el ORM `SQLAlchemy`[cite: 1].

## 2. Maquina de Estados del Pedido (FSM)
Estados permitidos:
`PENDIENTE_PAGO` -> `PAGADO` -> `EN_PREPARACION` -> `ASIGNADO` -> `EN_CAMINO` -> `LLEGO` -> `ENTREGADO`
*(Transición alternativa: `CANCELADO` desde cualquier estado previo a `EN_CAMINO`)*[cite: 1].

## 3. Esquema Entidad-Relación (ERD)
- **Usuario** (1) ------ (N) **Pedido**
- **Pedido** (1) ------ (N) **DetallePedido** ------ (1) **Plato**
- **Pedido** (1) ------ (N) **RastreoUbicacion**