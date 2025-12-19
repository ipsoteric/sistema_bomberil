#!/bin/sh

# Si la base de datos configurada es postgres...
if [ "$SQL_ENGINE" = "django.db.backends.postgresql" ]
then
    echo "Esperando a la base de datos en: $SQL_HOST..."

    # Usamos las variables de entorno para saber a quién esperar
    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.5
    done

    echo "Base de datos iniciada exitosamente."
fi

# Solo ejecutamos migraciones si la variable RUN_MIGRATIONS es 'true'
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Aplicando migraciones..."
    python manage.py migrate
fi
# -------------------

exec "$@"