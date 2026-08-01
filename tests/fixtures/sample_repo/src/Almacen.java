package tienda;

interface Repositorio {
    void guardar(String clave, String valor);
}

class AlmacenMemoria implements Repositorio {
    private final java.util.Map<String, String> datos = new java.util.HashMap<>();

    public void guardar(String clave, String valor) {
        datos.put(clave, valor);
    }

    public String leer(String clave) {
        return datos.get(clave);
    }
}
