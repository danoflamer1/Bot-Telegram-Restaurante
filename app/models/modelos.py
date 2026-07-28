import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    ForeignKey, Enum, Text, Boolean
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class RolUsuario(str, enum.Enum):
    CLIENTE = "cliente"
    REPARTIDOR = "repartidor"
    ADMINISTRADOR = "administrador"


class EstadoPedido(str, enum.Enum):
    PENDIENTE_PAGO = "pendiente_pago"
    PAGADO = "pagado"
    EN_PREPARACION = "en_preparacion"
    ASIGNADO = "asignado"
    EN_CAMINO = "en_camino"
    LLEGO = "llego"
    ENTREGADO = "entregado"
    CANCELADO = "cancelado"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=True)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    rol = Column(Enum(RolUsuario), default=RolUsuario.CLIENTE)
    activo = Column(Boolean, default=True)

    pedidos = relationship("Pedido", back_populates="cliente")


class Plato(Base):
    __tablename__ = "platos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    descripcion = Column(Text, nullable=True)
    precio = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    fecha_menu = Column(String, nullable=False)  # Formato YYYY-MM-DD
    disponible = Column(Boolean, default=True)


class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    codigo_seguimiento = Column(String, unique=True, index=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id"))
    repartidor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    estado = Column(Enum(EstadoPedido), default=EstadoPedido.PENDIENTE_PAGO)
    monto_total = Column(Float, default=0.0)
    latitud_entrega = Column(Float, nullable=True)
    longitud_entrega = Column(Float, nullable=True)
    comprobante_pago = Column(String, nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Usuario", foreign_keys=[cliente_id], back_populates="pedidos")
    detalles = relationship("DetallePedido", back_populates="pedido")
    rastreos = relationship("RastreoUbicacion", back_populates="pedido")


class DetallePedido(Base):
    __tablename__ = "detalles_pedido"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"))
    plato_id = Column(Integer, ForeignKey("platos.id"))
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    pedido = relationship("Pedido", back_populates="detalles")
    plato = relationship("Plato")


class RastreoUbicacion(Base):
    __tablename__ = "rastreos_ubicacion"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"))
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)

    pedido = relationship("Pedido", back_populates="rastreos")