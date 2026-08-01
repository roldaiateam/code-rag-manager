def calcular_total(items):
    total = 0
    for item in items:
        total += item["precio"] * item["cantidad"]
    return total


def aplicar_descuento(items, porcentaje):
    total = calcular_total(items)
    descuento = total * (porcentaje / 100)
    return total - descuento
