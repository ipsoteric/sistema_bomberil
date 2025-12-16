# 1. Última versión estable de Python 12 (security bugfix release - 9/10/2025)
FROM python:3.12.12

# 2. Evitar que Python genere archivos .pyc y forzar salida logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Establecer directorio de trabajo
WORKDIR /app

# 4. Instalar dependencias del sistema necesarias para Postgres y compilación netcat-openbsd se usa para verificar si la base de datos está lista
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
    && apt-get clean

# 5. Copiar archivo de dependencias
COPY requirements.txt /app/requirements.txt

# 6. Instalar dependencias de Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 7. Copiar el script de entrada y darle permisos de ejecución
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 8. Copiar la aplicación al directorio de trabajo
COPY . /app

# 8. Ejecutar el script de entrada
ENTRYPOINT ["/app/entrypoint.sh"]