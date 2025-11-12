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

# --- ¡Importamos TODOS los formularios de nuestro forms.py local! ---
from .forms import UsuarioForm, VoluntarioForm, ProfesionForm, CargoForm

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
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), id=id)
        
        # Creamos instancias de los formularios con los datos del voluntario
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
        
        usuario_form = UsuarioForm(request.POST, instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(request.POST, instance=voluntario)

        if usuario_form.is_valid() and voluntario_form.is_valid():
            usuario_form.save()
            voluntario_form.save()
            
            messages.success(request, f'Se han guardado los cambios de {voluntario.usuario.get_full_name}.')
            return redirect('gestion_voluntarios:ruta_ver_voluntario', id=voluntario.id)
        
        context = {
            'voluntario': voluntario,
            'usuario_form': usuario_form,
            'voluntario_form': voluntario_form
        }
        messages.error(request, 'Error al guardar. Por favor, revisa los campos.')
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)


# GESTIÓN DE CARGOS Y PROFESIONES

class CargosListaView(View):
    def get(self, request):
        
        profesiones = Profesion.objects.all().order_by('nombre')
        cargos = Cargo.objects.select_related('tipo_cargo').all().order_by('nombre')

        context = {
            'profesiones': profesiones,
            'cargos': cargos,
        }
        return render(request, "gestion_voluntarios/pages/lista_cargos_profes.html", context)


# --- VISTA "CREAR PROFESIÓN" (ACTUALIZADA) ---
class ProfesionesCrearView(View):
    def get(self, request):
        form = ProfesionForm()
        context = {
            'form': form
        }
        return render(request, "gestion_voluntarios/pages/crear_profesion.html", context)

    def post(self, request):
        form = ProfesionForm(request.POST)
        if form.is_valid():
            profesion = form.save()
            messages.success(request, f'Se ha agregado la profesión "{profesion.nombre}".')
            return redirect('gestion_voluntarios:ruta_cargos_lista')
        
        context = {
            'form': form
        }
        messages.error(request, 'Error al guardar. Revisa los campos.')
        return render(request, "gestion_voluntarios/pages/crear_profesion.html", context)


# --- VISTA "MODIFICAR PROFESIÓN" (ACTUALIZADA) ---
class ProfesionesModificarView(View):
    def get(self, request, id):
        profesion = get_object_or_404(Profesion, id=id)
        form = ProfesionForm(instance=profesion)
        context = {
            'form': form,
            'profesion': profesion
        }
        return render(request, "gestion_voluntarios/pages/modificar_profesion.html", context)

    def post(self, request, id):
        profesion = get_object_or_404(Profesion, id=id)
        form = ProfesionForm(request.POST, instance=profesion)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Se ha actualizado la profesión "{profesion.nombre}".')
            return redirect('gestion_voluntarios:ruta_cargos_lista')
        
        context = {
            'form': form,
            'profesion': profesion
        }
        messages.error(request, 'Error al guardar. Revisa los campos.')
        return render(request, "gestion_voluntarios/pages/modificar_profesion.html", context)


# --- VISTA "CREAR CARGO" (ACTUALIZADA) ---
class CargosCrearView(View):
    def get(self, request):
        form = CargoForm()
        context = {
            'form': form
        }
        return render(request, "gestion_voluntarios/pages/crear_cargo.html", context)

    def post(self, request):
        form = CargoForm(request.POST)
        if form.is_valid():
            cargo = form.save()
            messages.success(request, f'Se ha agregado el rango "{cargo.nombre}".')
            return redirect('gestion_voluntarios:ruta_cargos_lista')
        
        context = {
            'form': form
        }
        messages.error(request, 'Error al guardar. Revisa los campos.')
        return render(request, "gestion_voluntarios/pages/crear_cargo.html", context)


# --- VISTA "MODIFICAR CARGO" (ACTUALIZADA) ---
class CargosModificarView(View):
    def get(self, request, id):
        cargo = get_object_or_404(Cargo, id=id)
        form = CargoForm(instance=cargo)
        context = {
            'form': form,
            'cargo': cargo
        }
        return render(request, "gestion_voluntarios/pages/modificar_cargo.html", context)

    def post(self, request, id):
        cargo = get_object_or_404(Cargo, id=id)
        form = CargoForm(request.POST, instance=cargo)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Se ha actualizado el rango "{cargo.nombre}".')
            return redirect('gestion_voluntarios:ruta_cargos_lista')
        
        context = {
            'form': form,
            'cargo': cargo
        }
        messages.error(request, 'Error al guardar. Revisa los campos.')
        return render(request, "gestion_voluntarios/pages/modificar_cargo.html", context)
    

# MODULO DE REPORTES EXPORTAR Y GENERAR HOJA DE VIDA

# Generar hoja de vida del voluntario
class HojaVidaView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/hoja_vida.html")


# Exportar listado 
class ExportarListadoView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/exportar_listado.html")
