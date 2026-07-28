def calcular_total_carrito(items: list[dict]) -> float:
    total = 0.0
    for item in items:
        if item.get("cantidad", 0) <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        total += item.get("precio", 0.0) * item.get("cantidad", 0)
    return round(total, 2)


def validar_stock_disponible(stock_actual: int, cantidad_solicitada: int) -> bool:
    if cantidad_solicitada <= 0:
        return False
    return stock_actual >= cantidad_solicitada