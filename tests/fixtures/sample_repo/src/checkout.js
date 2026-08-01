import { formatearPrecio } from "./formato.js";

function calcularEnvio(pesoKg) {
  return pesoKg * 4.5;
}

const resumenPedido = (items, pesoKg) => {
  const envio = calcularEnvio(pesoKg);
  return formatearPrecio(envio);
};

class Cesta {
  constructor(items) {
    this.items = items;
  }
}

class CestaRegalo extends Cesta {
  constructor(items, mensaje) {
    super(items);
    this.mensaje = mensaje;
  }
}
