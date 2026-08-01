import re

PATRON_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$")


def comprobar_direccion_correo(direccion):
    """Comprueba que una direccion de correo electronico tenga formato valido."""
    return bool(PATRON_EMAIL.match(direccion))
