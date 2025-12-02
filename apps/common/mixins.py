import os
import uuid
from datetime import date, timedelta
from PIL import Image
from django import forms
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin, PermissionRequiredMixin
from django.apps import apps
from django.shortcuts import get_object_or_404, redirect
from django.http import Http404
from django.contrib import messages

from apps.gestion_inventario.models import Estacion
from .utils import procesar_imagen_en_memoria, generar_thumbnail_en_memoria
from .services import core_registrar_actividad


class ModuleAccessMixin(AccessMixin):
    """
    Verifica que el usuario tenga el permiso de acceso principal para el módulo.
    (Actualizado para la arquitectura de permisos centralizada en Membresia)
    """
    redirect_url_sin_acceso_modulo = 'portal:ruta_inicio'

    def dispatch(self, request, *args, **kwargs):
        # 1. Obtenemos la ruta del módulo de la vista (ej: 'apps.gestion_usuarios.views')
        view_module_path = self.request.resolver_match.func.__module__

        # 2. Django nos dice a qué app pertenece ese módulo
        app_config = apps.get_containing_app_config(view_module_path)
        if not app_config:
            raise PermissionDenied("No se pudo determinar la aplicación para la vista.")

        # 3. Construimos el codename del permiso (ej: 'acceso_gestion_usuarios')
        codename = f'acceso_{app_config.label}'

        # 4. Construimos el nombre completo del permiso.
        #    Tal como lo espera el RolBackend (que usa el content_type
        #    de Membresia), el app_label correcto es 'gestion_usuarios'.
        permission_required = f'gestion_usuarios.{codename}'

        # 5. Verificamos si el usuario tiene el permiso
        #    Esto llamará a RolBackend.has_perm(request.user, permission_required)
        if not request.user.has_perm(permission_required):
            raise PermissionDenied # Lanza un error 403 Prohibido
        # Si todo está en orden, la vista continúa.
        print("El usuario tiene permiso para entrar al módulo")
        return super().dispatch(request, *args, **kwargs)




class EstacionActivaRequiredMixin(AccessMixin):
    """
    Mixin que verifica que 'active_estacion_id' exista en la sesión,
    que sea una Estacion válida, y adjunta 'self.estacion_activa'
    a la vista para su uso.
    """
    
    mensaje_sin_estacion = "No se ha seleccionado una estación activa."
    redirect_url_sin_estacion = 'portal:ruta_inicio'

    def dispatch(self, request, *args, **kwargs):
        
        # 1. Obtenemos el ID de la sesión
        self.estacion_activa_id = request.session.get('active_estacion_id')
        
        if not self.estacion_activa_id:
            # Caso 1: No hay ID en la sesión.
            return self.handle_no_station()
        
        try:
            # 2. Hay ID, intentamos obtener el objeto Estacion
            self.estacion_activa = Estacion.objects.get(id=self.estacion_activa_id)
        
        except (Estacion.DoesNotExist, ValueError, TypeError):
            # Caso 3: El ID es inválido o la estación fue eliminada (sesión corrupta)
            messages.error(request, "La estación activa en sesión no es válida.")
            
            # Limpiamos la sesión corrupta
            if 'active_estacion_id' in request.session:
                del request.session['active_estacion_id']
            
            return self.handle_no_station()
        
        # ¡Éxito! El usuario tiene un ID y es válido.
        # self.estacion_activa y self.estacion_activa_id están ahora
        # disponibles en la vista (en self.get, self.post, etc.)
        print("El usuario tiene una estación activa")
        return super().dispatch(request, *args, **kwargs)
    

    def handle_no_station(self):
        """
        Método PROPIO para errores de estación.
        No choca con el PermissionRequiredMixin de Django.
        """
        messages.error(self.request, self.mensaje_sin_estacion)
        return redirect(self.redirect_url_sin_estacion)




class EstacionContextMixin(AccessMixin):
    """
    Mixin 'Blando': Intenta obtener la estación activa de la sesión.
    Si existe, la carga en self.estacion_activa.
    Si NO existe, self.estacion_activa será None (y no redirige ni da error).
    Ideal para el Portal, Perfil o Home.
    """
    def dispatch(self, request, *args, **kwargs):
        self.estacion_activa = None
        self.estacion_activa_id = request.session.get('active_estacion_id')
        
        if self.estacion_activa_id:
            try:
                self.estacion_activa = Estacion.objects.get(id=self.estacion_activa_id)
            except Estacion.DoesNotExist:
                # Si el ID en sesión es inválido, limpiamos silenciosamente
                request.session.pop('active_estacion_id', None)
                self.estacion_activa_id = None
        
        # Continuamos con la vista sin importar si encontramos estación o no
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # Inyectamos la estación al template automáticamente
        context = super().get_context_data(**kwargs)
        context['estacion_activa'] = self.estacion_activa
        return context




class BaseEstacionMixin(
    LoginRequiredMixin, 
    EstacionActivaRequiredMixin, 
    ModuleAccessMixin, 
):
    """
    Este "super-mixin" agrupa las 3 validaciones más comunes
    del proyecto:
    1. Que el usuario esté logueado.
    2. Que el usuario tenga acceso al módulo actual.
    3. Que el usuario tenga una estación activa en su sesión.
    """
    pass




class ObjectInStationRequiredMixin(AccessMixin):
    """
    Versión mejorada que verifica si un objeto pertenece a la estación activa
    del usuario, incluso a través de relaciones anidadas (ej: 'seccion__ubicacion__estacion').
    """
    station_lookup = 'estacion' # Ruta de búsqueda al campo de la estación.

    def dispatch(self, request, *args, **kwargs):
        active_station_id = request.session.get('active_estacion_id')
        if not active_station_id:
            return self.handle_no_permission()

        pk = kwargs.get('pk') or kwargs.get('id')
        if not pk:
            return super().dispatch(request, *args, **kwargs)

        obj = get_object_or_404(self.model, pk=pk)

        try:
            # Empezamos con el objeto principal (ej: una Existencia)
            related_obj = obj
            # Dividimos la ruta (ej: 'seccion__ubicacion__estacion') en partes
            for part in self.station_lookup.split('__'):
                # Navegamos a través de cada relación (obj.seccion, luego obj.ubicacion, etc.)
                related_obj = getattr(related_obj, part)
            
            # Al final, 'related_obj' será la instancia de la Estacion
            object_station = related_obj
            
            # Comparamos si el ID de la estación del objeto es el correcto
            if object_station.id != active_station_id:
                raise Http404
                
        except AttributeError:
            raise ImproperlyConfigured(
                f"El modelo {self.model.__name__} no pudo resolver la ruta de búsqueda '{self.station_lookup}'."
            )

        return super().dispatch(request, *args, **kwargs)




class ImageProcessingFormMixin:
    """
    Mixin para procesar imágenes (Main + 2 Thumbs) dentro del método save() de un ModelForm.
    Utiliza las funciones personalizadas: procesar_imagen_en_memoria y generar_thumbnail_en_memoria.
    Es dinámico: funciona para 'imagen', 'logo', 'foto_perfil', etc.
    """

    def process_image_upload(self, instance, field_name='imagen', max_dim=(1024, 1024), crop=False, image_prefix=''):
        """
        Procesa la imagen subida, genera UUID, maneja transparencia, redimensiona y crea thumbnails.
        """
        # 1. Obtener el archivo del cleaned_data
        image_file = self.cleaned_data.get(field_name)

        # Si no hay nueva imagen, no hacemos nada
        if not image_file:
            return

        # 2. Generar nombres base con UUID
        ext = os.path.splitext(image_file.name)[1].lower() or '.jpg'
        uuid_str = str(uuid.uuid4())
        # Construir el nombre base con el prefijo (si existe)
        if image_prefix:
            base_name = f"{image_prefix}_{uuid_str}"
        else:
            base_name = uuid_str
        
        main_name = f"{base_name}{ext}"
        medium_name = f"{base_name}_medium.jpg"
        small_name = f"{base_name}_small.jpg"

        # 3. Procesar Imagen Principal (Usando TU función)
        # Nota: procesar_imagen_en_memoria retorna un ContentFile
        processed_image = procesar_imagen_en_memoria(
            image_field=image_file,
            max_dimensions=max_dim,
            new_filename=main_name,
            crop_to_square=crop
        )

        # Asignamos la imagen procesada al campo cuyo nombre recibimos en 'field_name'
        # Equivalente a: instance.imagen = processed_image (pero dinámico)
        setattr(instance, field_name, processed_image)


        # 4. Generar Thumbnails
        image_file.seek(0)
        with Image.open(image_file) as img_obj:
            
            # --- THUMBNAIL MEDIUM ---
            # Construimos el nombre esperado del campo en el modelo
            field_med_name = f"{field_name}_thumb_medium"
            
            # Verificamos si el modelo realmente tiene ese campo antes de intentar guardar
            if hasattr(instance, field_med_name):
                thumb_med = generar_thumbnail_en_memoria(
                    image_obj=img_obj,
                    dimensions=(600, 600),
                    new_filename=medium_name
                )
                setattr(instance, field_med_name, thumb_med)

            # --- THUMBNAIL SMALL ---
            field_small_name = f"{field_name}_thumb_small"
            
            if hasattr(instance, field_small_name):
                thumb_small = generar_thumbnail_en_memoria(
                    image_obj=img_obj,
                    dimensions=(60, 60),
                    new_filename=small_name
                )
                setattr(instance, field_small_name, thumb_small)




class AuditoriaMixin:
    """
    Mixin pasivo: No ejecuta nada automáticamente.
    Provee el método self.auditar() para usarlo manualmente donde sea seguro.
    """
    
    def auditar(self, verbo, objetivo=None, objetivo_repr=None, detalles=None):
        """
        Helper para registrar actividad usando el request de la vista.
        """
        # self.request siempre existe en las Class Based Views (CBV) de Django
        if hasattr(self, 'request'):
            core_registrar_actividad(
                request=self.request,
                verbo=verbo,
                objetivo=objetivo,
                detalles=detalles,
                objetivo_repr=objetivo_repr
            )
        else:
            # Fallback por si alguien usa el mixin fuera de una vista web
            print("Error: AuditoriaMixin usado sin self.request")




class CustomPermissionRequiredMixin(PermissionRequiredMixin):
    """
    Extiende el mixin nativo para dar feedback visual en lugar de lanzar un 403 duro.
    """
    mensaje_sin_permiso = "No tienes permisos para realizar esta acción."
    url_redireccion = 'portal:ruta_inicio'

    def handle_no_permission(self):
        # 1. Si no está logueado, comportamiento estándar (al Login)
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()

        # 2. Mensaje de error
        messages.error(self.request, self.mensaje_sin_permiso)
        print("El usuario no tiene permisos para realizar esta acción")

        # 3. INTENTAR VOLVER ATRÁS
        # Obtenemos la URL desde donde vino el usuario
        referer = self.request.META.get('HTTP_REFERER')

        if referer:
            return redirect(referer)
        
        # 4. FALLBACK (Plan B)
        # Si el usuario escribió la URL directa o el navegador bloqueó el referer,
        # lo enviamos al inicio por defecto.
        return redirect(self.url_redireccion)




class BomberilFormMixin:
    """
    Mixin Maestro para Formularios del Sistema Bomberil.
    
    Funcionalidades:
    1. Inyección de Contexto: Extrae 'user' y 'estacion' de los kwargs para uso interno.
    2. Estilos UI (DRY): Aplica clases CSS estándar automáticamente según el tipo de widget,
       sin sobrescribir las clases personalizadas que defina el desarrollador.
    """

    def __init__(self, *args, **kwargs):
        # 1. Extracción de Contexto (Pop para que no falle el super().__init__)
        self.user = kwargs.pop('user', None)
        self.estacion_activa = kwargs.pop('estacion', None)

        # 2. Inicialización del formulario base
        super().__init__(*args, **kwargs)

        # 3. Lógica de Estilos CSS Centralizada
        self._aplicar_estilos_y_reglas()


    def _aplicar_estilos_y_reglas(self):
        # 1. Estilos Base (Ya los teníamos)
        ESTILO_BASE = 'text-base color_primario fondo_secundario_variante border-0'
        CLASES_POR_WIDGET = {
            forms.TextInput: f'form-control form-control-sm {ESTILO_BASE}',
            forms.EmailInput: f'form-control form-control-sm {ESTILO_BASE}',
            forms.NumberInput: f'form-control form-control-sm {ESTILO_BASE}',
            forms.Textarea: f'form-control form-control-sm {ESTILO_BASE}',
            forms.Select: f'form-select form-select-sm {ESTILO_BASE}',
            forms.DateInput: f'form-control form-control-sm {ESTILO_BASE}',
            forms.PasswordInput: f'form-control form-control-sm {ESTILO_BASE}',
        }

        for field_name, field in self.fields.items():
            widget = field.widget
            
            # --- A. INYECCIÓN DE ESTILOS ---
            # (Lógica que ya teníamos para clases CSS)
            clase_nueva = CLASES_POR_WIDGET.get(type(widget), CLASES_POR_WIDGET[forms.TextInput])
            clases_existentes = widget.attrs.get('class', '')
            if clases_existentes:
                widget.attrs['class'] = f"{clase_nueva} {clases_existentes}"
            else:
                widget.attrs['class'] = clase_nueva

            # --- B. INYECCIÓN DE REGLAS ---
            # Convertimos reglas de Python a atributos data-* para JS
            
            # 1. Requerido
            if field.required:
                widget.attrs['data-rule-required'] = 'true'
            
            # 2. Máximos y Mínimos (Solo para inputs de texto)
            if hasattr(field, 'max_length') and field.max_length:
                widget.attrs['maxlength'] = field.max_length # Nativo HTML
                widget.attrs['data-rule-max'] = field.max_length # Para JS
                
            if hasattr(field, 'min_length') and field.min_length:
                widget.attrs['minlength'] = field.min_length
                widget.attrs['data-rule-min'] = field.min_length

            # 3. Tipos Especiales (Marcamos el campo para validaciones específicas)
            if isinstance(field, forms.EmailField):
                widget.attrs['data-rule-type'] = 'email'
            elif isinstance(field, forms.IntegerField):
                widget.attrs['data-rule-type'] = 'integer'

            # 4. Reglas especiales para FECHAS
            if isinstance(field, forms.DateField):
                widget.attrs['data-rule-type'] = 'date'

                # Ejemplo de regla de negocio: Entre 18 y 100 años atrás
                hoy = date.today()
                fecha_minima = hoy - timedelta(days=365 * 100) # 100 años
                fecha_maxima = hoy - timedelta(days=365 * 18)  # 18 años (Mayor de edad)

                # Inyectamos atributos nativos de HTML5
                widget.attrs['min'] = fecha_minima.isoformat()
                widget.attrs['max'] = fecha_maxima.isoformat()

                # Atributos para nuestro JS validator
                widget.attrs['data-date-min'] = fecha_minima.isoformat()
                widget.attrs['data-date-max'] = fecha_maxima.isoformat()