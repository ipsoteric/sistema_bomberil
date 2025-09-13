from pathlib import Path
import os
import environ


# Crea rutas dentro del proyecto de esta forma: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuración de variables de entorno
env = environ.Env()
env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env.str('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')


# Aplicaciones predeterminadas de Django
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]
# Aplicaciones del proyecto
PROJECT_APPS = [
    'apps.common',
    'apps.utilidades',
    'apps.gestion_inventario',
    'apps.gestion_mantenimiento',
    'apps.gestion_voluntarios',
    'apps.gestion_medica',
    'apps.gestion_usuarios',
    'apps.portal',
    'apps.acceso',
    'apps.api',
]
# Aplicaciones de terceros
THIRD_PARTY_APPS = [
    #'jazzmin',
    'storages',
    'rest_framework',
]
INSTALLED_APPS = THIRD_PARTY_APPS + DJANGO_APPS + PROJECT_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
        "ENGINE": env.str('DB_ENGINE'),
        "NAME": env.str('DB_NAME'),
        "USER": env.str('DB_USER'),
        "PASSWORD": env.str('DB_PASSWORD'),
        "HOST": env.str('DB_HOST'),
        "PORT": env.str('DB_PORT'),
        "TEST": {
            "NAME": "mytestdatabase",
        },
    },
}


# Validaciones de contraseña
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
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
    'portal': 'Bomberil',
    'acceso': 'Acceso',
    'api': 'api',
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
AWS_ACCESS_KEY_ID = env.str('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env.str('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env.str('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env.str('AWS_S3_REGION_NAME')
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'

AWS_DEFAULT_ACL = None            # evita ACL heredadas
AWS_QUERYSTRING_AUTH = False  

# URL del bucket de S3
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'


STORAGES = {
    # MEDIA -> S3
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "location": "media",                # <— clave: prefijo dentro del bucket
            "custom_domain": AWS_S3_CUSTOM_DOMAIN, 
        },
    },
    # STATIC -> local con WhiteNoise
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
    ]
}