from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.gestion_inventario.models import Comuna
from apps.gestion_usuarios.models import Membresia


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Claims extra para el token encriptado (útil para decodificar sin llamar a la BD)
        token['rut'] = user.rut
        token['nombre'] = user.get_full_name
        return token

    def validate(self, attrs):
        # 1. Validación estándar (verifica credenciales RUT/Pass)
        data = super().validate(attrs)

        # 2. Información del Usuario (Basada en el modelo Usuario)
        user_data = {
            'id': self.user.id,
            'rut': self.user.rut,
            'email': self.user.email,
            'nombre_completo': self.user.get_full_name,
            'avatar': self.user.avatar.url if self.user.avatar else None,
        }
        data['usuario'] = user_data

        # 3. Obtener la Membresía Activa
        # Gracias al constraint 'membresia_activa_unica_por_usuario', sabemos que solo habrá una o ninguna.
        membresia_activa = Membresia.objects.filter(
            usuario=self.user, 
            estado=Membresia.Estado.ACTIVO
        ).select_related('estacion').prefetch_related('roles__permisos').first()
        print(membresia_activa)

        if membresia_activa:
            # A. Datos de la Estación
            data['estacion'] = {
                'id': membresia_activa.estacion.id,
                'nombre': membresia_activa.estacion.nombre,
            }
            print(data['estacion'])

            # B. Recopilación de Permisos (Flattening)
            # Recorre todos los roles de la membresía y extraemos los codenames de los permisos.
            # set() para evitar duplicados si dos roles tienen el mismo permiso.
            permisos_set = set()
            
            for rol in membresia_activa.roles.all():
                for permiso in rol.permisos.all():
                    # Guardamos el 'codename' (ej: 'accion_gestion_inventario_ver_stock')
                    permisos_set.add(permiso.codename)

            # Convertimos a lista para que sea JSON serializable
            data['permisos'] = list(permisos_set)
            
            # C. ID de membresía para futuras referencias
            data['membresia_id'] = membresia_activa.id

        else:
            # Caso borde: Usuario logueado pero sin estación activa (ej: Superusuario global o usuario nuevo)
            data['estacion'] = None
            data['permisos'] = []
            # Opcional: Levantar un error aquí si la app móvil EXIGE estación.

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