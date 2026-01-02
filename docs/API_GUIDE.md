# Guía de Integración de la API - Bomberil System

Esta API es el núcleo de comunicación para el ecosistema de Bomberil System, diseñada para dar soporte a la aplicación móvil y servicios externos. Está construida sobre **Django REST Framework** y sigue el estándar **OpenAPI 3**.

## Documentación Interactiva
Para explorar y probar los endpoints en tiempo real, utiliza las interfaces generadas automáticamente:

* **Swagger UI (Interactivo):** [http://localhost:8000/api/v1/schema/swagger-ui/](http://localhost:8000/api/v1/schema/swagger-ui/)
* **ReDoc (Estático):** [http://localhost:8000/api/v1/schema/redoc/](http://localhost:8000/api/v1/schema/redoc/)

---

## Autenticación (JWT)

El sistema utiliza **JSON Web Tokens (JWT)** para la seguridad. El flujo de autenticación es el siguiente:

1. **Obtención de Token:** Envía las credenciales al endpoint `/auth/login/`.
2. **Uso del Token:** Incluye el `access token` en todas tus peticiones dentro del header de autorización:
   `Authorization: Bearer <tu_access_token>`
3. **Refresco de Sesión:** Cuando el token expire, utiliza el endpoint `/auth/refresh/` para obtener uno nuevo sin re-autenticar al usuario.

---

## Lógica Multi-tenant en la API

Esta API está diseñada para un entorno **Multi-estación**.
* **Contexto de Estación:** La mayoría de los endpoints de gestión (Inventario, Voluntarios, Médica) requieren que el usuario tenga una **Estación Activa** seleccionada.
* **Validación:** El sistema utiliza el permiso personalizado `IsEstacionActiva` para asegurar que un voluntario de la Estación A no acceda accidentalmente a recursos de la Estación B.

---

## Flujos de Datos Principales

### 1. Gestión de Inventarios
El módulo de inventario permite la trazabilidad completa mediante códigos QR.
* **Búsqueda Dinámica:** `/gestion_inventario/existencias/detalle/?codigo=XXX` permite identificar instantáneamente si un ítem es un **Activo** único o un **Lote** de productos.

### 2. Módulo Médico y Emergencias
Diseñado para el acceso rápido en terreno:
* **Ficha Crítica:** Los voluntarios pueden consultar sus antecedentes médicos y descargar su ficha en formato PDF directamente desde la API.

---

## Herramientas y Estándares
* **Formato de Respuesta:** Siempre JSON.
* **Manejo de Imágenes:** Soporte para carga y actualización de avatares con procesamiento en el servidor.
* **Arquitectura:** RESTful con versionado en la URL (`/v1/`).