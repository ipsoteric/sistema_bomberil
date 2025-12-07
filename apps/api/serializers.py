from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import obtener_contexto_bomberil
from apps.gestion_inventario.models import Comuna
from apps.gestion_usuarios.models import Membresia, Usuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rut'] = user.rut
        token['nombre'] = user.get_full_name
        return token

    def validate(self, attrs):
        # 1. Valida credenciales (RUT/Pass)
        data = super().validate(attrs)
        
        # 2. Inyecta la lógica de negocio
        contexto = obtener_contexto_bomberil(self.user)
        data.update(contexto)
        
        return data




class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Refresh Token que valida que el usuario siga teniendo membresía activa
    y devuelve los permisos actualizados.
    """
    def validate(self, attrs):
        # 1. Valida que el refresh token sea correcto y devuelve el nuevo access
        data = super().validate(attrs)

        # 2. Decodificar el refresh token para encontrar al usuario
        # (El refresh token contiene el user_id)
        refresh = RefreshToken(attrs['refresh'])
        user_id = refresh['user_id'] # O el campo que uses como ID
        
        try:
            user = Usuario.objects.get(id=user_id)
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({"detail": "Usuario no encontrado."})

        # 3. Re-validar Membresía e inyectar datos actualizados
        # Si el usuario perdió la membresía hace 5 minutos, esto lanzará el error
        # y no le entregará el nuevo token.
        contexto = obtener_contexto_bomberil(user)
        data.update(contexto)

        return data




class ComunaSerializer(serializers.ModelSerializer):
    """
    Serializador simple para el modelo Comuna.
    Solo expone los campos 'id' y 'nombre', que es lo que necesita el frontend.
    """
    class Meta:
        model = Comuna
        fields = ['id', 'nombre']




class ProductoLocalInputSerializer(serializers.Serializer):
    productoglobal_id = serializers.IntegerField(required=True)
    sku = serializers.CharField(required=True, max_length=100)
    es_serializado = serializers.BooleanField(default=False)
    es_expirable = serializers.BooleanField(default=False)