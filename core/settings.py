from datetime import timedelta
from pathlib import Path
import os
import environ
from celery.schedules import crontab


# Crea rutas dentro del proyecto de esta forma: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuración de variables de entorno
env = environ.Env()
env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env.str('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
# Configuración de CSRF para HTTPS: Como Nginx maneja el HTTPS y le pasa HTTP a Docker, Django necesita confiar en el dominio seguro. Si no pongo esto, no se podrá iniciar sesión (error CSRF).
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])


# Aplicaciones predeterminadas de Django
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    # 'django.contrib.sessions',
    'user_sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]
# Aplicaciones del proyecto
PROJECT_APPS = [
    'apps.common',
    'apps.gestion_inventario',
    'apps.gestion_mantenimiento',
    'apps.gestion_voluntarios',
    'apps.gestion_medica',
    'apps.gestion_usuarios',
    'apps.gestion_documental',
    'apps.portal',
    'apps.acceso',
    'apps.api',
    'apps.perfil',
    'apps.core_admin',
]
# Aplicaciones de terceros
THIRD_PARTY_APPS = [
    #'jazzmin',
    'storages',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_cleanup.apps.CleanupConfig',
    'django_celery_results',
]
INSTALLED_APPS = THIRD_PARTY_APPS + DJANGO_APPS + PROJECT_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # 'django.contrib.sessions.middleware.SessionMiddleware',
    'user_sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.modulo_actual',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Base de datos
DATABASES = {
    "default": {
        "ENGINE": env.str('SQL_ENGINE'),
        "NAME": env.str('DB_NAME'),
        "USER": env.str('DB_USER'),
        "PASSWORD": env.str('DB_PASSWORD'),
        "HOST": env.str('SQL_HOST'),
        "PORT": env.str('SQL_PORT'),
        "TEST": {
            "NAME": "mytestdatabase",
        },
    },
}


# Validaciones de contraseña
AUTH_PASSWORD_VALIDATORS = [
    # 1. Similitud con el usuario: Evita que la contraseña se parezca al RUT, Email o Nombre.
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'user_attributes': ('rut', 'email', 'first_name', 'last_name'),
            'max_similarity': 0.7,
        }
    },
    # 2. Longitud Mínima: Tu regla de 12 caracteres.
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    # 3. Contraseñas Comunes: Bloquea las 20,000 contraseñas más usadas (ej: "123456", "bomberos1").
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    # 4. Evitar solo números: (Opcional, pero buena práctica básica)
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    # 5. NUESTRO VALIDADOR PERSONALIZADO (Mayúsculas, Símbolos, etc.)
    {
        'NAME': 'apps.common.password_validation.BomberilPasswordValidator',
    },
]


AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'apps.gestion_usuarios.backends.RolBackend',
]


# Internacionalización
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True


# Archivos estáticos (CSS, JavaScript, Imágenes)
STATIC_URL = 'static/'
# Directorio global de archivos estáticos
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
## Archivos multimedia cargados (configuración local)



# Tipo de campo de clave primaria por defecto
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Modelo personalizado de usuarios
AUTH_USER_MODEL = "gestion_usuarios.Usuario"


# Ruta del login
LOGIN_URL = 'acceso:ruta_login'


# Mapeo de nombres de apps a nombres legibles para el usuario (Aparecerán en el Header)
MODULOS = {
    'gestion_inventario': 'Inventario',
    'gestion_mantenimiento': 'Mantenimiento de Herramientas',
    'gestion_medica': 'Gestión Médica',
    'gestion_usuarios': 'Usuarios y Permisos',
    'gestion_voluntarios': 'Gestión Voluntarios',
    'gestion_documental': 'Gestión Documental',
    'portal': 'Portal',
    'acceso': 'Acceso',
    'api': 'api',
    'core_admin': 'Administración del sistema',
}


# Configuración de Jazzmin
JAZZMIN_SETTINGS = {
    # título de la ventana (por defecto usará current_admin_site.site_title si está ausente o es None)
    "site_title": "Administración de Bomberil",

    # Título en la pantalla de inicio de sesión (máximo 19 caracteres) (por defecto usará current_admin_site.site_header si está ausente o es None)  
    "site_header": "Bomberil",  

    # Título en la marca (máximo 19 caracteres) (por defecto usará current_admin_site.site_header si está ausente o es None)  
    "site_brand": "Bomberil",  

    # Logo para tu sitio, debe estar en los archivos estáticos, se usa como marca en la esquina superior izquierda  
    "site_logo": os.path.join(BASE_DIR, "static/imagenes/bomberil_logo_circle_white(100x100).png"),  

    # Logo para el formulario de inicio de sesión, debe estar en los archivos estáticos (por defecto usa site_logo)  
    "login_logo": None,  

    # Logo para el formulario de inicio de sesión en temas oscuros (por defecto usa login_logo)  
    "login_logo_dark": None,  

    # Clases CSS aplicadas al logo anterior  
    "site_logo_classes": "img-circle",  

    # Ruta relativa al favicon de tu sitio, por defecto usará site_logo si está ausente (idealmente 32x32 px)  
    "site_icon": None,  

    # Texto de bienvenida en la pantalla de inicio de sesión  
    "welcome_sign": "Bienvenido a la Administración de Bomberil",  

    # Copyright en el pie de página  
    "copyright": "Acme Library Ltd",  

    # Lista de modelos de administración para buscar desde la barra de búsqueda, se omite la barra si no se incluye  
    # Si quieres usar un solo campo de búsqueda, no necesitas una lista, puedes usar un string simple  
    "search_model": ["gestion_usuarios.Usuario", "gestion_usuarios.Rol"],  

    # Nombre del campo en el modelo de usuario que contiene el avatar (ImageField/URLField/CharField) o un objeto llamable que recibe el usuario  
    "user_avatar": "avatar",

    "hide_apps": ["auth"],
    "hide_models": ["auth.Group", "auth.User"],

    "topmenu_links": [
        # Url a la que quieres que te lleve el botón "Ver Sitio"
        {"name": "Home", "url": "index", "permissions": ["auth.view_user"]},

        # Agrega este diccionario para el enlace "Ver Sitio"
        {"name": "Ver Sitio", "url": "/", "new_window": True},

        # Puedes agregar otros enlaces si lo deseas
        # {"model": "auth.User"},
    ],
}


# Configuración de AWS
AWS_ACCESS_KEY_ID = env.str('AWS_ACCESS_KEY_ID', default=None)
AWS_SECRET_ACCESS_KEY = env.str('AWS_SECRET_ACCESS_KEY', default=None)
AWS_STORAGE_BUCKET_NAME = env.str('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env.str('AWS_S3_REGION_NAME')
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
AWS_DEFAULT_ACL = None            # evita ACL heredadas
AWS_QUERYSTRING_AUTH = False  


# Configuración para envío de correos
EMAIL_BACKEND = env.str('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
DEFAULT_FROM_EMAIL = env.str('DEFAULT_FROM_EMAIL', default='no-reply@bomberil.cl')
# Configuración SES (Solo necesaria en Prod)
AWS_SES_REGION_NAME = env.str('AWS_SES_REGION_NAME', default='us-east-2')
AWS_SES_REGION_ENDPOINT = env.str('AWS_SES_REGION_ENDPOINT', default='email.us-east-2.amazonaws.com')
# Configuración SMTP
EMAIL_HOST = env.str('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_HOST_USER = env.str('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env.str('EMAIL_HOST_PASSWORD', default='')
EMAIL_PORT = env.str('EMAIL_PORT', default='587')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)


# ========================================================
# CONFIGURACIÓN DE ALMACENAMIENTO (MEDIA Y STATIC)
# ========================================================

# Configuración base de Static Files (siempre usa WhiteNoise según tu config actual)
STATICFILES_STORAGE_BACKEND = "whitenoise.storage.CompressedManifestStaticFilesStorage"

if not DEBUG:
    # ----------------------------------------------------
    # PRODUCCIÓN (AWS S3)
    # ----------------------------------------------------
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "location": "media",
                "custom_domain": AWS_S3_CUSTOM_DOMAIN,
            },
        },
        "staticfiles": {
            "BACKEND": STATICFILES_STORAGE_BACKEND,
        }
    }

else:
    # ----------------------------------------------------
    # DESARROLLO (LOCAL)
    # ----------------------------------------------------
    # URL pública para acceder a los archivos
    MEDIA_URL = '/media/'
    
    # Ruta física en tu disco duro donde se guardarán
    MEDIA_ROOT = BASE_DIR / 'media'

    STORAGES = {
        "default": {
            # Backend por defecto de Django para guardar en disco
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": STATICFILES_STORAGE_BACKEND,
        }
    }



# Configuración de Django Rest Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',  # Para la Web/Admin
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # Para el Móvil
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}


# Configuración de Rest Framework Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30), # Token de acceso (corto)
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),    # Token de refresco (largo)
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

## Configuración de django_redis
#CACHES = {
#    "default": {
#        "BACKEND": "django_redis.cache.RedisCache",
#        "LOCATION": env.str("REDIS_URL"),
#        "OPTIONS": {
#            "CLIENT_CLASS": "django_redis.client.DefaultClient",
#        }
#    }
#}
#

# Configurar el motor de sesión
SESSION_ENGINE = 'user_sessions.backends.db'
#SESSION_CACHE_ALIAS = "default"


# Configuración para que el Admin de Django reconozca el middleware de sesiones (django.contrib.sessions.middleware.SessionMiddleware)
SILENCED_SYSTEM_CHECKS = ['admin.E410']


# Configuración de Celery
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL") # Dónde buscar las tareas
CELERY_RESULT_BACKEND = 'django-db' # Guarda el resultado de una tarea en la base de datos
CELERY_ACCEPT_CONTENT = ['application/json'] # Sólo permitir mensajes en JSON
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/Santiago" # Configura la hora de las tareas
CELERY_BROKER_TRANSPORT_OPTIONS = { # Opciones avanzadas de conexión con Redis
    'visibility_timeout': 3600, # 1 hora de timeout para las tareas
    'socket_timeout': 5,
    'retry_on_timeout': True
}
CELERY_BEAT_SCHEDULE = {
    # 1. Generador de Mantenimiento (00:05 AM)
    'mantenimiento-diario-preventivo': {
        'task': 'apps.gestion_mantenimiento.tasks.tarea_generar_mantenimiento_diario',
        'schedule': crontab(hour=0, minute=5),  # A las 00:05 todos los días
        #'schedule': crontab(minute='*/2'),  # Ejecutar cada 2 minutos (ej: 14:00, 14:02, 14:04)
    },
    
    # 2. Reporte Diario de Actividad (23:30 PM)
    'reporte-diario-ejecutivo': {
        'task': 'apps.portal.tasks.tarea_enviar_reportes_diarios',
        'schedule': crontab(hour=23, minute=30),  # A las 23:30 todos los días
        #'schedule': crontab(minute='*/30'),  # Ejecutar cada 3 minutos (para que no se topen siempre)
    },
}

# Limita el tamaño del cuerpo de la petición (ej. 10MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Configuración de Inventario
INVENTARIO_UBICACION_AREA_NOMBRE = "ÁREA"
INVENTARIO_UBICACION_VEHICULO_NOMBRE = "VEHÍCULO"
INVENTARIO_UBICACION_ADMIN_NOMBRE = "ADMINISTRATIVA"