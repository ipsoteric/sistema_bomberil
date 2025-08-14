from django.contrib import admin
from .models import Estacion


@admin.register(Estacion)
class EstacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion')
    # ¡Esta línea es la clave! Le dice a Django cómo buscar Estaciones.
    search_fields = ('nombre',)