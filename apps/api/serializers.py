from rest_framework import serializers
from apps.gestion_inventario.models import Comuna

class ComunaSerializer(serializers.ModelSerializer):
    """
    Serializador simple para el modelo Comuna.
    Solo expone los campos 'id' y 'nombre', que es lo que necesita el frontend.
    """
    class Meta:
        model = Comuna
        fields = ['id', 'nombre']