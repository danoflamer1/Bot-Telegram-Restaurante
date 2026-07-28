import pytest
from app.core.logica import calcular_total_carrito, validar_stock_disponible


def test_calcular_total_carrito_correcto():
    items = [
        {"precio": 25.50, "cantidad": 2},
        {"precio": 10.00, "cantidad": 1}
    ]
    assert calcular_total_carrito(items) == 61.00


def test_calcular_total_carrito_cantidad_invalida():
    items = [{"precio": 25.50, "cantidad": -1}]
    with pytest.raises(ValueError):
        calcular_total_carrito(items)


def test_validar_stock_disponible():
    assert validar_stock_disponible(10, 5) is True
    assert validar_stock_disponible(2, 5) is False
    assert validar_stock_disponible(5, 0) is False