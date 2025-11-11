from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.db.models import Prefetch
from django.contrib import messages

# Importamos los modelos de voluntarios
from .models import (
    Voluntario, HistorialCargo, Cargo, TipoCargo, Profesion,
    HistorialReconocimiento, HistorialSancion
)

# Importamos Membresia desde la app gestion_usuarios
from apps.gestion_usuarios.models import Membresia

# Importamos el modelo Estacion de gestion_inventario
from apps.gestion_inventario.models import Estacion

# --- ¡NUEVO! Importamos los formularios ---
from .forms import UsuarioForm, VoluntarioForm

# Página Inicial
class VoluntariosInicioView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/home.html")
    

# Lista de voluntarios
class VoluntariosListaView(View):
    def get(self, request):
        
        # 1. Prefetch para la membresía activa (para obtener Estación y Estado)
        # Buscamos la membresía activa del usuario [cite: 13]
        active_membresia_prefetch = Prefetch(
            'usuario__membresias',
            queryset=Membresia.objects.filter(estado='ACTIVO').select_related('estacion'),
            to_attr='membresia_activa_list' # Guardamos en un atributo temporal
        )

        # 2. Prefetch para el cargo actual (para obtener el Rango)
        # Buscamos en el historial el cargo que no tiene fecha de fin 
        current_cargo_prefetch = Prefetch(
            'historial_cargos',
            queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'),
            to_attr='cargo_actual_list' # Guardamos en un atributo temporal
        )

        # 3. Query principal
        # Obtenemos todos los Voluntarios 
        # Usamos select_related para el usuario y prefetch_related para los datos complejos
        voluntarios = Voluntario.objects.select_related('usuario').prefetch_related(
            active_membresia_prefetch,
            current_cargo_prefetch
        ).all()

        cargos = Cargo.objects.all().order_by('nombre')

        context = {
            'voluntarios': voluntarios,
            'cargos': cargos,          # <- Nueva data para el filtro
        }
        return render(request, "gestion_voluntarios/pages/lista_voluntarios.html", context)


# Ver voluntario
class VoluntariosVerView(View):
    def get(self, request, id):
        
        # --- Prefetches para datos del Header ---
        active_membresia_prefetch = Prefetch(
            'usuario__membresias', # Sigue a 'usuario'
            queryset=Membresia.objects.filter(estado='ACTIVO').select_related('estacion'),
            to_attr='membresia_activa_list'
        )
        current_cargo_prefetch = Prefetch(
            'historial_cargos', # Sigue a 'voluntario'
            queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'),
            to_attr='cargo_actual_list'
        )
        
        # --- Prefetches para las Pestañas del Historial ---
        cargos_prefetch = Prefetch(
            'historial_cargos',
            queryset=HistorialCargo.objects.all().select_related('cargo', 'estacion_registra').order_by('-fecha_inicio')
        )
        reconocimientos_prefetch = Prefetch(
            'historial_reconocimientos',
            queryset=HistorialReconocimiento.objects.all().select_related('tipo_reconocimiento', 'estacion_registra').order_by('-fecha_evento')
        )
        sanciones_prefetch = Prefetch(
            'historial_sanciones',
            queryset=HistorialSancion.objects.all().select_related('estacion_registra', 'estacion_evento').order_by('-fecha_evento')
        )
        
        # --- Query Principal ---
        voluntario = get_object_or_404(
            Voluntario.objects.select_related(
                'usuario', 'nacionalidad', 'profesion', 'domicilio_comuna'
            ).prefetch_related(
                active_membresia_prefetch,
                current_cargo_prefetch,
                cargos_prefetch,
                reconocimientos_prefetch,
                sanciones_prefetch
            ),
            id=id
        )

        # === LÓGICA CORREGIDA ===
        # Extraemos las listas de los atributos pre-cargados
        membresia_list = voluntario.usuario.membresia_activa_list
        cargo_list = voluntario.cargo_actual_list

        # Asignamos el primer elemento (si la lista NO está vacía) o None
        membresia_activa = membresia_list[0] if membresia_list else None
        cargo_actual = cargo_list[0] if cargo_list else None
        
        # --- Preparar Contexto ---
        context = {
            'voluntario': voluntario,
            'membresia': membresia_activa,    # <--- Variable corregida
            'cargo_actual': cargo_actual,   # <--- Variable corregida
        }
        return render(request, "gestion_voluntarios/pages/ver_voluntario.html", context)

# Editar voluntario
class VoluntariosModificarView(View):
    
    # Cuando se carga la página
    def get(self, request, id):
        # 1. Obtenemos el voluntario y su usuario asociado
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), id=id)
        
        # 2. Creamos instancias de los formularios con los datos del voluntario
        usuario_form = UsuarioForm(instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(instance=voluntario)

        context = {
            'voluntario': voluntario,
            'usuario_form': usuario_form,
            'voluntario_form': voluntario_form
        }
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)

    # Cuando se presiona "Guardar Cambios"
    def post(self, request, id):
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), id=id)
        
        # 1. Recibimos los datos del POST en los formularios
        usuario_form = UsuarioForm(request.POST, instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(request.POST, instance=voluntario)

        # 2. Validamos ambos formularios
        if usuario_form.is_valid() and voluntario_form.is_valid():
            # 3. Guardamos los cambios
            usuario_form.save()
            voluntario_form.save()
            
            messages.success(request, f'Se han guardado los cambios de {voluntario.usuario.get_full_name}.')
            # 4. Redirigimos a la "Hoja de Vida" (Ver Voluntario)
            return redirect('gestion_voluntarios:ruta_ver_voluntario', id=voluntario.id)
        
        # Si los formularios no son válidos, se re-renderiza la página con los errores
        context = {
            'voluntario': voluntario,
            'usuario_form': usuario_form,
            'voluntario_form': voluntario_form
        }
        messages.error(request, 'Error al guardar. Por favor, revisa los campos.')
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)


# GESTIÓN DE CARGOS Y PROFESIONES

# Lista de cargos y profesiones
class CargosListaView(View):
    def get(self, request):
        
        # --- Traemos los datos reales ---
        profesiones = Profesion.objects.all().order_by('nombre')
        # Usamos select_related para traer también la categoría (TipoCargo)
        cargos = Cargo.objects.select_related('tipo_cargo').all().order_by('nombre')

        context = {
            'profesiones': profesiones,
            'cargos': cargos, # 'cargos' es el modelo para "Rangos Bomberiles"
        }
        return render(request, "gestion_voluntarios/pages/lista_cargos_profes.html", context)


# Crear profesion
class ProfesionesCrearView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/crear_profesion.html")

    def post(self, request):
        # Lógica para guardar profesion
        return render(request, "gestion_voluntarios/pages/crear_profesion.html")


# Editar profesion
class ProfesionesModificarView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/modificar_profesion.html")

    def post(self, request, id):
        # Lógica para actualizar profesion
        return render(request, "gestion_voluntarios/pages/modificar_profesion.html")


# Crear cargo
class CargosCrearView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/crear_cargo.html")

    def post(self, request):
        # Lógica para guardar cargo
        return render(request, "gestion_voluntarios/pages/crear_cargo.html")


# Editar cargo
class CargosModificarView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/modificar_cargo.html")

    def post(self, request, id):
        # Lógica para actualizar cargo
        return render(request, "gestion_voluntarios/pages/modificar_cargo.html")
    

# MODULO DE REPORTES EXPORTAR Y GENERAR HOJA DE VIDA

# Generar hoja de vida del voluntario
class HojaVidaView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/hoja_vida.html")


# Exportar listado 
class ExportarListadoView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/exportar_listado.html")
