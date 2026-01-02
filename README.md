# Bomberil System 🚒

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-5.2.1-green.svg)](https://www.djangoproject.com/)
[![Docker Support](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
![GitHub repo size](https://img.shields.io/github/repo-size/ipsoteric/sistema_bomberil)
![Status](https://img.shields.io/badge/Status-Tesis%20Aprobada-success)

**Bomberil System** es mi proyecto de tesis, el cual consiste en una solución integral de gestión administrativa y operativa para compañías de bomberos. Originado por un desafío académico para la **Segunda Compañía de Bomberos de Iquique**, el sistema adopta una arquitectura **Multi-tenant** capaz de gestionar múltiples estaciones de forma autónoma pero centralizada.




## Arquitectura y Escalabilidad (Multi-tenant)

Bomberil System permite que cada compañía sea autónoma en su gestión, compartiendo una infraestructura común pero con aislamiento total de datos.




## Funcionalidades Clave

El sistema está estructurado en módulos especializados:

* **Administración Global (Core Admin):** Panel maestro para la gestión de estaciones (compañías), catálogos globales de marcas y productos, y orquestación de usuarios a nivel de cuerpo de bomberos.

* **Gestión de Inventario:** Diferenciación entre *Productos* (catálogo) y *Existencias* (unidades físicas trazables). Soporta control de stock crítico, gestión por lotes y ubicaciones físicas específicas.

* **Gestión de Voluntarios (Bitácora de Hoja de Vida):** Registro de identidad y trayectoria bomberil. Utiliza un sistema de bitácora inmutable donde cada evento (cargos, cursos, sanciones) es firmado por la estación que lo registra.

* **Módulo Médico y Emergencia:** Fichas médicas digitales que incluyen compatibilidad sanguínea y antecedentes críticos. Generación de **Códigos QR de emergencia** para acceso rápido a información vital del voluntario en terreno.

* **Mantenimiento de Herramientas:** Gestión de planes preventivos y órdenes de trabajo correctivas para equipos serializados y herramientas de la flota.

* **Usuarios, Seguridad y Auditoría:** Control de acceso granular mediante roles y permisos, gestión de sesiones activas (con opción de forzar cierre) y registro detallado de actividad para auditorías.

* **Gestión Documental:** Repositorio centralizado para manuales de capacitación y documentación histórica pública y confidencial.

* **Ecosistema API:** Endpoints REST para la integración con la aplicación móvil.




## Stack Tecnológico

### Backend & API
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Django](https://img.shields.io/badge/django-%23092e20.svg?style=for-the-badge&logo=django&logoColor=white)
![DjangoDRF](https://img.shields.io/badge/DJANGO-REST-ff1709?style=for-the-badge&logo=django&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-black?style=for-the-badge&logo=JSON%20web%20tokens)

### Base de Datos & Caché
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)

### Infraestructura & Asincronía
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Celery](https://img.shields.io/badge/celery-%2337814A.svg?style=for-the-badge&logo=celery&logoColor=white)

### Frontend
![Bootstrap](https://img.shields.io/badge/bootstrap-%238511FA.svg?style=for-the-badge&logo=bootstrap&logoColor=white)
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=F7DF1E)
![CSS3](https://img.shields.io/badge/css3-%231572B6.svg?style=for-the-badge&logo=css3&logoColor=white)




## Configuración del Entorno (.env)

El sistema utiliza variables de entorno para gestionar credenciales y configuraciones críticas. Antes de iniciar, crea un archivo `.env` en la raíz del proyecto basándote en la siguiente estructura:

```env
# Seguridad y Debug
DEBUG=TRUE
SECRET_KEY=django-insecure-uxe5xeewvacdqz&6pv=_&9=#z_0n&uerrlylx_zpvt7dzqdqx7
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,[http://127.0.0.1:8000](http://127.0.0.1:8000)


# Base de Datos (PostgreSQL)
DB_URL=postgres://bomberil_user:123456@db:5432/bomberildb
DB_NAME=bomberildb
DB_USER=bomberil_user
DB_PASSWORD=123456
SQL_ENGINE=django.db.backends.postgresql
SQL_HOST=db
SQL_PORT=5432


# Redis & Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0


# Configuración de Correo (Opcional para local)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu_correo@gmail.com
EMAIL_HOST_PASSWORD=tu_password_de_aplicacion

# Superusuarios Iniciales (Se crean automáticamente en la migración)
# Superusuario 1 (Juan)
BOMBERIL_SU1_RUT=11111111-1
BOMBERIL_SU1_FIRST_NAME=Juan
BOMBERIL_SU1_LAST_NAME=Castillo
BOMBERIL_SU1_EMAIL=juan@gmail.com
BOMBERIL_SU1_PASSWORD=Juan123456#

# Superusuario 2 (Polett)
BOMBERIL_SU2_RUT=22222222-2
BOMBERIL_SU2_FIRST_NAME=Polett
BOMBERIL_SU2_LAST_NAME=Casanga
BOMBERIL_SU2_EMAIL=polett@gmail.com
BOMBERIL_SU2_PASSWORD=Polett123456#

# Superusuario 3
BOMBERIL_SU3_RUT=33333333-3
BOMBERIL_SU3_FIRST_NAME=Guiliano
BOMBERIL_SU3_LAST_NAME=Punulaf
BOMBERIL_SU3_EMAIL=guiliano@gmail.com
BOMBERIL_SU3_PASSWORD=Guiliano123456#

# Usuarios de prueba creados en fixtures
# Administrador
BOMBERIL_ADMIN_GERMANIA_RUT=14765450-2
BOMBERIL_ADMIN_GERMANIA_PASSWORD=Carlos123456#

BOMBERIL_USER2_GERMANIA_RUT=18950469-1
BOMBERIL_USER2_GERMANIA_PASSWORD=Alexa123456#

BOMBERIL_USER3_GERMANIA_RUT=14567342-9
BOMBERIL_USER3_GERMANIA_PASSWORD=Lucho123456#

```




## Instalación y Despliegue

El sistema está diseñado para ejecutarse de forma consistente mediante **Docker**, lo que garantiza que todas las dependencias (PostgreSQL, Redis, Celery) se configuren automáticamente.


### Requisitos Previos
* **Docker** y **Docker Compose** instalados.
* **Git** configurado (se recomienda `git config --global core.autocrlf true` en Windows para evitar conflictos de formato).


### Pasos para el Despliegue (Docker)

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/ipsoteric/sistema_bomberil
    cd sistema_bomberil
    ```

2.  **Configurar variables de entorno:**
    Crea un archivo `.env` en la raíz del proyecto basándote en la configuración requerida por el sistema (incluyendo credenciales de base de datos y claves de API).

3.  **Construir e iniciar los contenedores:**
    Este comando levantará el servidor web, la base de datos PostgreSQL, el broker Redis y los workers de Celery:
    ```bash
    docker compose up --build -d
    ```
    *El sistema aplicará las migraciones automáticamente durante el inicio.*

4.  **Carga de datos maestros (Fixtures):**
    Para agilizar la puesta en marcha, ejecuta el script de automatización que carga los datos base de la compañía (estaciones, marcas, categorías, etc.):
    ```bash
    docker compose exec web bash scripts/load_fixtures.sh
    ```


### Acceso al Sistema
Una vez iniciados los contenedores, el sistema estará disponible en:
* **Portal Principal:** [http://localhost:8000](http://localhost:8000)
* **Credenciales de prueba:** Utiliza los RUT y contraseñas definidos en tus variables de entorno o fixtures iniciales.

---

> 💡 Si encuentras errores de ejecución en los scripts `.sh` dentro de Docker (tipo `": not found"`), asegúrate de que los archivos `entrypoint.sh` y `load_fixtures.sh` tengan finales de línea **LF** y no **CRLF**.

## Equipo de Desarrollo

Este proyecto fue desarrollado como memoria de título para la carrera de **Ingeniería en Informática** por:

* **Juan Castillo** – [GitHub](https://github.com/ipsoteric)
* **Polett Casanga** – [GitHub](https://github.com/poleth-casanga)
* **Guiliano Punulaf** – [GitHub](https://github.com/Guiliano002)