import multiprocessing
import os

# Configuración de Gunicorn Profesional

# Dirección y puerto
bind = "0.0.0.0:8000"

# Workers
# Fórmula recomendada: (2 x CPUs) + 1
# Usamos una variable de entorno o un default seguro
workers_per_core = float(os.getenv("GUNICORN_WORKERS_PER_CORE", "2"))
cores = multiprocessing.cpu_count()
default_workers = int(workers_per_core * cores) + 1
workers = int(os.getenv("GUNICORN_WORKERS", default_workers))

# Threads (opcional, útil para I/O bound apps)
threads = int(os.getenv("GUNICORN_THREADS", "1"))

# Timeouts
# A veces procesos largos necesitan más tiempo (ej: reportes)
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# --- LOGGING PROFESIONAL ---

# 1. Access Log (Peticiones)
# '-' significa stdout (consola). Si no se pone, no se loguean peticiones.
accesslog = '-' 

# Formato del log de acceso (Similar a Nginx/Apache combinado)
# %(h)s: IP remota
# %(l)s: Identidad (suele ser guión)
# %(u)s: Usuario (si hay auth básica)
# %(t)s: Fecha y hora
# "%(r)s": Línea de petición (GET /url HTTP/1.1)
# %(s)s: Código de estado (200, 404, etc)
# %(b)s: Tamaño de respuesta en bytes
# "%(f)s": Referer
# "%(a)s": User Agent
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 2. Error Log (Errores de Gunicorn y stderr de la app)
# '-' significa stderr (consola de error).
errorlog = '-'

# Nivel de log
# Opciones: debug, info, warning, error, critical
# 'info' es el estándar para producción. 'debug' es muy verboso.
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Nombre del proceso (útil para ps/top)
proc_name = "bomberil_gunicorn"

# Preload (opcional)
# Carga el código de la aplicación antes de forkear los workers.
# Ahorra RAM y acelera el inicio, pero cuidado si usas conexiones a BD en el inicio global.
preload_app = True