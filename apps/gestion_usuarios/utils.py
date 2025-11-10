import secrets
import string


def generar_contraseña_segura(longitud=12):
    """Genera una contraseña aleatoria y segura."""
    alfabeto = string.ascii_letters + string.digits + string.punctuation
    contraseña = ''.join(secrets.choice(alfabeto) for i in range(longitud))
    return contraseña