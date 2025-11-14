from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404, redirect
from django.http import Http404
from django.contrib import messages
from django.urls import reverse_lazy

from .models import Membresia, Rol


class UsuarioDeMiEstacionMixin(AccessMixin):
    """
    Mixin que verifica que el usuario al que se intenta acceder
    pertenece a la misma estación que el usuario logueado.
    """
    def dispatch(self, request, *args, **kwargs):
        # Primero, asegúrate de que el usuario esté logueado
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Obtiene el ID de la estación del usuario que hace la petición
        estacion_actual_id = request.session.get('active_estacion_id')
        
        # Obtiene el ID del usuario que se quiere ver desde la URL
        usuario_a_ver_id = kwargs.get('id')

        # La validación clave:
        # ¿Existe una membresía activa para este usuario EN MI estación?
        es_miembro_valido = Membresia.objects.filter(
            usuario_id=usuario_a_ver_id,
            estacion_id=estacion_actual_id,
            estado__in=['ACTIVO', 'INACTIVO']
        ).exists()

        if not es_miembro_valido:
            # Si no existe, lanzamos un error 404 (No Encontrado).
            # Es más seguro que un 403 (Prohibido), ya que no revela
            # que el usuario existe.
            raise Http404("No se encontró el usuario en esta estación.")

        # Si la validación pasa, permite que la vista continúe.
        return super().dispatch(request, *args, **kwargs)




class RolValidoParaEstacionMixin(AccessMixin):
    """
    Verifica que el Rol al que se intenta acceder sea válido para la
    estación activa del usuario. Un rol es válido si:
    1. Es un rol universal (rol.estacion es None).
    2. Pertenece a la estación activa del usuario.
    """
    def dispatch(self, request, *args, **kwargs):
        # 1. Obtenemos la estación activa de la sesión.
        active_station_id = request.session.get('active_estacion_id')
        if not active_station_id:
            return self.handle_no_permission()

        # 2. Obtenemos el ID del rol desde la URL.
        rol_id = kwargs.get('pk') or kwargs.get('id')
        if not rol_id:
            # Si no hay ID, no es una vista de detalle/edición, así que continuamos.
            return super().dispatch(request, *args, **kwargs)

        # 3. Buscamos el objeto Rol.
        rol_obj = get_object_or_404(Rol, id=rol_id)

        # 4. La validación clave:
        es_rol_universal = rol_obj.estacion is None
        es_rol_de_mi_estacion = rol_obj.estacion and rol_obj.estacion.id == active_station_id

        if not (es_rol_universal or es_rol_de_mi_estacion):
            # Si el rol no es ni universal ni de la estación del usuario,
            # lanzamos un 404 para no revelar que el rol existe.
            raise Http404

        # Si la validación es exitosa, la vista continúa.
        return super().dispatch(request, *args, **kwargs)




class MembresiaGestionableMixin:
    """
    Este Mixin comprueba si la Membresia obtenida por la vista
    tiene un estado "gestionable" (ACTIVO o INACTIVO).
    
    Si está, por ejemplo, "FINALIZADA", redirige con un
    mensaje de error.
    
    Requiere que la vista que lo usa defina un método get_object().
    """
    
    # Estados que SÍ permitimos gestionar
    ESTADOS_GESTIONABLES = [
        Membresia.Estado.ACTIVO,
        Membresia.Estado.INACTIVO
    ]
    
    # URL a la que redirigir si la validación falla
    redirect_url_no_gestiona = reverse_lazy('gestion_usuarios:ruta_lista_usuarios')
    mensaje_no_gestiona = (
        "La membresía de este usuario no se puede gestionar "
        "porque su estado es 'Finalizada' o ya no es vigente."
    )

    def dispatch(self, request, *args, **kwargs):
        # 1. Obtenemos el objeto (la vista debe definir get_object)
        #    (El get_object de la vista debe validar la pertenencia a la estación)
        try:
            self.object = self.get_object()
        except Exception as e:
            # Si get_object() lanza 404, dejamos que Django lo maneje
            return super().dispatch(request, *args, **kwargs)

        # 2. Verificamos si el estado NO está en la lista permitida
        if self.object.estado not in self.ESTADOS_GESTIONABLES:
            messages.error(request, self.mensaje_no_gestiona)
            return redirect(self.redirect_url_no_gestiona)

        # 3. Si la validación pasa, continuamos con la vista normal
        #    El objeto está disponible en 'self.object'
        return super().dispatch(request, *args, **kwargs)