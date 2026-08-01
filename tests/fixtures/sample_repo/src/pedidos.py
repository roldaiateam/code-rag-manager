from carrito import aplicar_descuento


class Pedido:
    def __init__(self, items):
        self.items = items

    def total_con_descuento(self, porcentaje):
        return aplicar_descuento(self.items, porcentaje)


class PedidoUrgente(Pedido):
    def __init__(self, items, recargo):
        super().__init__(items)
        self.recargo = recargo
