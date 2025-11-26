from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.db.models import Prefetch, Count, Q
from django.contrib import messages
import csv
import json
import io
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string 
from django.utils import timezone
from django.core import serializers
import openpyxl
from xhtml2pdf import pisa
from .utils import link_callback

from .models import (
    Voluntario, HistorialCargo, Cargo, TipoCargo, Profesion,
    HistorialReconocimiento, HistorialSancion
)
from apps.gestion_usuarios.models import Membresia
from apps.gestion_inventario.models import Estacion

# Importamos TODOS los formularios
try:
    from .forms import (
        ProfesionForm, CargoForm, UsuarioForm, VoluntarioForm,
        HistorialCargoForm, HistorialReconocimientoForm, HistorialSancionForm
    )
except ImportError:
    ProfesionForm = CargoForm = UsuarioForm = VoluntarioForm = None
    HistorialCargoForm = HistorialReconocimientoForm = HistorialSancionForm = None


# Mixin de ayuda para validar estación (Opcional, pero recomendado para limpiar código)
class EstacionActivaMixin:
    def get_estacion_activa(self, request):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Debes seleccionar una estación de trabajo.")
            return None
        return estacion_id

# Página Inicial
class VoluntariosInicioView(View, EstacionActivaMixin):
    def get(self, request):
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id:
            return redirect('portal:ruta_:inicio') # O donde corresponda si no hay sesión

        # --- 1. Datos para las Tarjetas (SOLO ESTACIÓN ACTIVA) ---
        # Filtramos membresías que pertenezcan a la estación activa
        voluntarios_activos = Membresia.objects.filter(estacion_id=estacion_id, estado='ACTIVO').count()
        voluntarios_inactivos = Membresia.objects.filter(estacion_id=estacion_id, estado='INACTIVO').count()
        
        # Total de gente vinculada a esta estación (activa o inactiva)
        total_voluntarios_general = Membresia.objects.filter(estacion_id=estacion_id).count()

        # --- 2. Datos para Gráfico de Rangos (Cargos) ---
        # Filtramos cargos vigentes de voluntarios que pertenecen a la estación activa
        rangos_data = HistorialCargo.objects.filter(
            fecha_fin__isnull=True,
            voluntario__usuario__membresias__estacion_id=estacion_id, # JOIN CRITICO
            voluntario__usuario__membresias__estado='ACTIVO'
        ).values('cargo__nombre').annotate(count=Count('cargo')).order_by('-count')

        chart_rangos_labels = [item['cargo__nombre'] for item in rangos_data]
        chart_rangos_counts = [item['count'] for item in rangos_data]

        # --- 3. Datos para Gráfico de Profesiones (Top 5) ---
        profesiones_data = Voluntario.objects.filter(
            usuario__membresias__estacion_id=estacion_id, # JOIN CRITICO
            usuario__membresias__estado='ACTIVO'
        ).exclude(profesion__isnull=True).values('profesion__nombre').annotate(count=Count('profesion')).order_by('-count')[:5] 

        chart_profes_labels = [item['profesion__nombre'] for item in profesiones_data]
        chart_profes_counts = [item['count'] for item in profesiones_data]

        # --- 4. Preparamos el Contexto ---
        context = {
            'total_voluntarios_general': total_voluntarios_general,
            'voluntarios_activos': voluntarios_activos,
            'voluntarios_inactivos': voluntarios_inactivos,
            'chart_rangos_labels': json.dumps(chart_rangos_labels),
            'chart_rangos_counts': json.dumps(chart_rangos_counts),
            'chart_profes_labels': json.dumps(chart_profes_labels),
            'chart_profes_counts': json.dumps(chart_profes_counts),
        }
        
        return render(request, "gestion_voluntarios/pages/home.html", context)
  
# Lista de voluntarios
class VoluntariosListaView(View, EstacionActivaMixin):
    def get(self, request):
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id:
            return redirect('portal:home')

        # 1. Capturamos los parámetros de la URL (Filtros ADICIONALES)
        # NOTA: Ya no leemos 'estacion' del GET porque forzamos la de la sesión.
        rango_id = request.GET.get('rango')
        busqueda = request.GET.get('q')

        # 2. Iniciamos la consulta base RESTRINGIDA A LA ESTACIÓN
        voluntarios_qs = Voluntario.objects.select_related('usuario').filter(
            usuario__membresias__estacion_id=estacion_id,
            usuario__membresias__estado='ACTIVO'
        )

        # 3. (El filtro de estación por GET se elimina o se ignora por seguridad)

        # 4. Aplicamos Filtro de Rango (si existe y no es 'global')
        if rango_id and rango_id != 'global':
            voluntarios_qs = voluntarios_qs.filter(
                historial_cargos__cargo_id=rango_id,
                historial_cargos__fecha_fin__isnull=True 
            )

        # 5. Aplicamos Búsqueda por Texto (Nombre o RUT)
        if busqueda:
            voluntarios_qs = voluntarios_qs.filter(
                Q(usuario__first_name__icontains=busqueda) | 
                Q(usuario__last_name__icontains=busqueda) | 
                Q(usuario__rut__icontains=busqueda)
            )

        # 6. Prefetches (Optimizados para solo traer data relevante)
        # Solo traemos la membresía de ESTA estación
        active_membresia_prefetch = Prefetch(
            'usuario__membresias',
            queryset=Membresia.objects.filter(estado='ACTIVO', estacion_id=estacion_id).select_related('estacion'),
            to_attr='membresia_activa_list'
        )
        current_cargo_prefetch = Prefetch(
            'historial_cargos',
            queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'),
            to_attr='cargo_actual_list'
        )
        
        voluntarios = voluntarios_qs.prefetch_related(
            active_membresia_prefetch,
            current_cargo_prefetch
        ).distinct().all()

        # 7. Datos para llenar los selectores de filtro
        # Ya no enviamos todas las estaciones, solo cargos
        cargos = Cargo.objects.all().order_by('nombre')
        
        context = {
            'voluntarios': voluntarios,
            # 'estaciones': estaciones,  <-- ELIMINADO: El usuario no debe poder cambiar de estación aquí
            'cargos': cargos,
        }
        return render(request, "gestion_voluntarios/pages/lista_voluntarios.html", context)

# Ver voluntario
class VoluntariosVerView(View, EstacionActivaMixin):
    def get(self, request, id):
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id:
            return redirect('portal:home')

        # Prefetches
        active_membresia_prefetch = Prefetch('usuario__membresias', queryset=Membresia.objects.filter(estado='ACTIVO', estacion_id=estacion_id).select_related('estacion'), to_attr='membresia_activa_list')
        current_cargo_prefetch = Prefetch('historial_cargos', queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'), to_attr='cargo_actual_list')
        # Cargos históricos: ¿Quieres que vean cargos que tuvo en OTRAS estaciones? 
        # Generalmente sí (es su hoja de vida), pero la edición está restringida. Dejamos query all para lectura.
        cargos_prefetch = Prefetch('historial_cargos', queryset=HistorialCargo.objects.all().select_related('cargo', 'estacion_registra').order_by('-fecha_inicio'))
        reconocimientos_prefetch = Prefetch('historial_reconocimientos', queryset=HistorialReconocimiento.objects.all().select_related('tipo_reconocimiento', 'estacion_registra').order_by('-fecha_evento'))
        sanciones_prefetch = Prefetch('historial_sanciones', queryset=HistorialSancion.objects.all().select_related('estacion_registra', 'estacion_evento').order_by('-fecha_evento'))
        
        # SEGURIDAD CRÍTICA: get_object_or_404 ahora incluye el filtro de membresía en la estación actual
        # Si el ID existe pero es de otra estación, devolverá 404 (Not Found) protegiendo el dato.
        voluntario = get_object_or_404(
            Voluntario.objects.select_related('usuario', 'nacionalidad', 'profesion', 'domicilio_comuna')
            .prefetch_related(active_membresia_prefetch, current_cargo_prefetch, cargos_prefetch, reconocimientos_prefetch, sanciones_prefetch), 
            usuario__id=id,
            usuario__membresias__estacion_id=estacion_id  # <--- RESTRICCION
        )
        
        membresia_activa = voluntario.usuario.membresia_activa_list[0] if voluntario.usuario.membresia_activa_list else None
        cargo_actual = voluntario.cargo_actual_list[0] if voluntario.cargo_actual_list else None

        context = {
            'voluntario': voluntario,
            'membresia': membresia_activa,
            'cargo_actual': cargo_actual,
            'form_cargo': HistorialCargoForm(),
            'form_reconocimiento': HistorialReconocimientoForm(),
            'form_sancion': HistorialSancionForm(),
        }
        return render(request, "gestion_voluntarios/pages/ver_voluntario.html", context)


# --- VISTAS PARA AGREGAR EVENTOS (BITÁCORA) ---
# En estas vistas ya tenías la validación de `request.session`, pero
# agregamos la validación de que el voluntario destino pertenezca a la estación.

class VoluntarioAgregarCargoView(View, EstacionActivaMixin):
    def post(self, request, id):
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id: return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)

        voluntario = get_object_or_404(Voluntario, usuario__id=id, usuario__membresias__estacion_id=estacion_id)
        
        form = HistorialCargoForm(request.POST)
        if form.is_valid():
            try:
                estacion_registra = Estacion.objects.get(pk=estacion_id)
                es_historico = form.cleaned_data.get('es_registro_antiguo') # <--- CAPTURAMOS EL CHECK
                
                nuevo_cargo = form.save(commit=False)
                nuevo_cargo.voluntario = voluntario
                nuevo_cargo.estacion_registra = estacion_registra
                
                # --- LÓGICA DIFERENCIADA ---
                if es_historico:
                    # MODO HISTÓRICO (CARGA DE PAPELES VIEJOS)
                    # 1. Marcamos el flag del modelo
                    nuevo_cargo.es_historico = True
                    # 2. Guardamos la fecha fin que vino del formulario
                    nuevo_cargo.fecha_fin = form.cleaned_data['fecha_fin']
                    
                    # 3. NO cerramos el cargo actual ni validamos cronología contra el presente
                    nuevo_cargo.save()
                    messages.success(request, "Cargo histórico registrado correctamente.")
                    
                else:
                    # MODO EN VIVO (LO QUE PASA HOY)
                    fecha_inicio_nuevo = form.cleaned_data['fecha_inicio']
                    cargo_anterior = HistorialCargo.objects.filter(voluntario=voluntario, fecha_fin__isnull=True).first()

                    # Validaciones estrictas solo para modo en vivo
                    if cargo_anterior:
                        if fecha_inicio_nuevo < cargo_anterior.fecha_inicio:
                            messages.error(request, "Error: El nuevo cargo no puede ser anterior al actual. Si es un dato antiguo, marque la casilla '¿Es cargo antiguo?'.")
                            return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)
                        
                        # Cerrar ciclo anterior
                        cargo_anterior.fecha_fin = fecha_inicio_nuevo
                        cargo_anterior.save()

                    nuevo_cargo.es_historico = False
                    nuevo_cargo.save()
                    messages.success(request, "Nuevo cargo vigente registrado exitosamente.")

            except Exception as e:
                messages.error(request, f"Error: {e}")
        else:
            # Mostrar errores del formulario (ej: falta fecha fin en histórico)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
                    
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)


# (Hacer lo mismo con Reconocimiento y Sanción, agregando el filtro en el get_object_or_404)
class VoluntarioAgregarReconocimientoView(View, EstacionActivaMixin):
    def post(self, request, id):
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id: return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)

        # Validamos que el voluntario pertenezca a la estación activa
        voluntario = get_object_or_404(Voluntario, usuario__id=id, usuario__membresias__estacion_id=estacion_id)
        
        form = HistorialReconocimientoForm(request.POST)
        
        if form.is_valid():
            try:
                estacion_registra = Estacion.objects.get(pk=estacion_id)
                es_historico_check = form.cleaned_data.get('es_registro_antiguo', False)
                
                nuevo_reco = form.save(commit=False)
                nuevo_reco.voluntario = voluntario
                nuevo_reco.estacion_registra = estacion_registra
                
                # Guardamos si es histórico o "en vivo" según el checkbox
                nuevo_reco.es_historico = es_historico_check
                
                nuevo_reco.save()
                
                if es_historico_check:
                    messages.success(request, "Reconocimiento histórico agregado a la hoja de vida.")
                else:
                    messages.success(request, "Nuevo reconocimiento registrado exitosamente.")
                    
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
        else:
             messages.error(request, "Error en el formulario. Verifique las fechas.")
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)

class VoluntarioAgregarSancionView(View, EstacionActivaMixin):
    def post(self, request, id):
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id: return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)

        voluntario = get_object_or_404(Voluntario, usuario__id=id, usuario__membresias__estacion_id=estacion_id)
        
        # OJO: request.FILES es necesario si suben PDF de la sanción
        form = HistorialSancionForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                estacion_registra = Estacion.objects.get(pk=estacion_id)
                es_historico_check = form.cleaned_data.get('es_registro_antiguo', False)
                
                nueva_sancion = form.save(commit=False)
                nueva_sancion.voluntario = voluntario
                nueva_sancion.estacion_registra = estacion_registra
                
                # Guardamos si es histórico o "en vivo"
                nueva_sancion.es_historico = es_historico_check
                
                nueva_sancion.save()
                
                if es_historico_check:
                    messages.success(request, "Registro de sanción antigua agregado correctamente.")
                else:
                    messages.success(request, "Sanción disciplinaria registrada.")
                    
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
        else:
             messages.error(request, "Error en el formulario. Revise fechas y campos obligatorios.")
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)
    

# Editar voluntario
class VoluntariosModificarView(View, EstacionActivaMixin):
    def get(self, request, id):
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id: return redirect('portal:home')

        # Restricción: Solo puedo editar voluntarios de mi estación
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), usuario__id=id, usuario__membresias__estacion_id=estacion_id)
        
        usuario_form = UsuarioForm(instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(instance=voluntario)

        context = {
            'voluntario': voluntario,
            'usuario_form': usuario_form,
            'voluntario_form': voluntario_form
        }
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)

    def post(self, request, id):
        estacion_id = self.get_estacion_activa(request)
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), usuario__id=id, usuario__membresias__estacion_id=estacion_id)
        
        usuario_form = UsuarioForm(request.POST, instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(request.POST, request.FILES, instance=voluntario)

        if usuario_form.is_valid() and voluntario_form.is_valid():
            usuario_form.save()
            voluntario_form.save()
            messages.success(request, f'Se han guardado los cambios de {voluntario.usuario.get_full_name}.')
            return redirect('gestion_voluntarios:ruta_ver_voluntario', id=voluntario.usuario.id)
        
        context = {
            'voluntario': voluntario,
            'usuario_form': usuario_form,
            'voluntario_form': voluntario_form
        }
        messages.error(request, 'Error al guardar.')
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)


# GESTIÓN DE CARGOS Y PROFESIONES

# Ver cargo y profesiones
class CargosListaView(View):
    def get(self, request):
        
        # 1. Capturar parámetros de búsqueda
        q_profesion = request.GET.get('q_profesion', '') # Buscador de profesiones
        q_cargo = request.GET.get('q_cargo', '')         # Buscador de cargos
        filtro_tipo_cargo = request.GET.get('tipo_cargo', '') # Filtro de categoría
        
        # 2. Filtrar Profesiones
        profesiones = Profesion.objects.all().order_by('nombre')
        if q_profesion:
            profesiones = profesiones.filter(nombre__icontains=q_profesion)

        # 3. Filtrar Cargos
        cargos = Cargo.objects.select_related('tipo_cargo').all().order_by('nombre')
        
        if q_cargo:
            cargos = cargos.filter(nombre__icontains=q_cargo)
            
        if filtro_tipo_cargo and filtro_tipo_cargo != 'global':
            cargos = cargos.filter(tipo_cargo_id=filtro_tipo_cargo)

        # 4. Obtener Tipos de Cargo para el <select>
        tipos_cargo = TipoCargo.objects.all().order_by('nombre')

        context = {
            'profesiones': profesiones,
            'cargos': cargos,
            'tipos_cargo': tipos_cargo, # Enviamos las categorías al template
        }
        return render(request, "gestion_voluntarios/pages/lista_cargos_profes.html", context)


#Crear profesiones
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


#Modificar profesiones
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


#Crear cargo
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


#Modificar cargo
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
    def get(self, request, id):
        
        # 1. Obtenemos todos los datos del voluntario (igual que VoluntariosVerView)
        active_membresia_prefetch = Prefetch(
            'usuario__membresias',
            queryset=Membresia.objects.filter(estado='ACTIVO').select_related('estacion'),
            to_attr='membresia_activa_list'
        )
        current_cargo_prefetch = Prefetch(
            'historial_cargos',
            queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'),
            to_attr='cargo_actual_list'
        )
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
        voluntario = get_object_or_404(
            Voluntario.objects.select_related(
                'usuario', 'nacionalidad', 'profesion', 'domicilio_comuna'
            ).prefetch_related(
                active_membresia_prefetch, current_cargo_prefetch,
                cargos_prefetch, reconocimientos_prefetch, sanciones_prefetch
            ),
            usuario__id=id
        )
        membresia_list = voluntario.usuario.membresia_activa_list
        cargo_list = voluntario.cargo_actual_list
        membresia_activa = membresia_list[0] if membresia_list else None
        cargo_actual = cargo_list[0] if cargo_list else None
        
        context = {
            'voluntario': voluntario,
            'membresia': membresia_activa,
            'cargo_actual': cargo_actual,
            'request': request # Pasamos el request para el link_callback
        }
        
        # 2. Renderizamos la plantilla HTML a un string
        # (Asegúrate de que 'hoja_vida_pdf.html' existe)
        html_string = render_to_string(
            "gestion_voluntarios/pages/hoja_vida_pdf.html", 
            context
        )
        
        # 3. Creamos el PDF en memoria
        result = io.BytesIO()
        pdf = pisa.pisaDocument(
            src=io.BytesIO(html_string.encode("UTF-8")), # Convertimos string a bytes
            dest=result,
            link_callback=link_callback
        )
        
        # 4. Verificamos si hubo errores
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="hoja_vida_{voluntario.usuario.rut}.pdf"'
            return response
        
        # Si hay un error, devolvemos un error HTML
        return HttpResponse(f'Error al generar el PDF: {pdf.err}')

# Exportar listado 
class ExportarListadoView(View, EstacionActivaMixin):
    
    def _get_voluntarios_data(self, request):
        """
        Obtiene los voluntarios filtrados estrictamente por la estación activa
        y los filtros opcionales de rango.
        """
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id: 
            return Voluntario.objects.none()

        cargo_id = request.GET.get('rango')
        
        # 1. Filtro BASE: Solo voluntarios de la estación activa
        voluntarios_qs = Voluntario.objects.select_related('usuario').filter(
            usuario__membresias__estacion_id=estacion_id, 
            usuario__membresias__estado='ACTIVO'
        )
        
        # 2. Filtro Opcional: Rango
        if cargo_id and cargo_id != 'global':
            voluntarios_qs = voluntarios_qs.filter(
                historial_cargos__cargo_id=cargo_id,
                historial_cargos__fecha_fin__isnull=True
            )

        # 3. Prefetches para optimizar la exportación
        active_membresia_prefetch = Prefetch(
            'usuario__membresias',
            queryset=Membresia.objects.filter(estado='ACTIVO', estacion_id=estacion_id).select_related('estacion'),
            to_attr='membresia_activa_list'
        )
        current_cargo_prefetch = Prefetch(
            'historial_cargos',
            queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'),
            to_attr='cargo_actual_list'
        )
        
        return voluntarios_qs.prefetch_related(active_membresia_prefetch, current_cargo_prefetch).distinct()

    def _export_csv(self, voluntarios):
        """Genera y devuelve una respuesta HTTP con un archivo CSV."""
        response = HttpResponse(
            content_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="listado_voluntarios_{timezone.now().strftime("%Y-%m-%d")}.csv"'
            },
        )
        response.write(u'\ufeff'.encode('utf8'))
        writer = csv.writer(response, delimiter=';')
        
        writer.writerow(['RUT', 'Nombre Completo', 'Email', 'Teléfono', 'Estación Actual', 'Estado', 'Cargo Actual'])

        for v in voluntarios:
            membresia = v.usuario.membresia_activa_list[0] if v.usuario.membresia_activa_list else None
            cargo_actual = v.cargo_actual_list[0] if v.cargo_actual_list else None
            writer.writerow([
                v.usuario.rut or '',
                v.usuario.get_full_name,
                v.usuario.email or '',
                v.usuario.phone or '',
                membresia.estacion.nombre if membresia and membresia.estacion else 'Sin Estación',
                membresia.get_estado_display() if membresia else 'Inactivo',
                cargo_actual.cargo.nombre if cargo_actual and cargo_actual.cargo else 'Sin Cargo'
            ])
        return response

    def _export_excel(self, voluntarios):
        """Genera y devuelve una respuesta HTTP con un archivo Excel (.xlsx)."""
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="listado_voluntarios_{timezone.now().strftime("%Y-%m-%d")}.xlsx"'
            },
        )
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Listado Voluntarios"

        headers = ['RUT', 'Nombre Completo', 'Email', 'Teléfono', 'Estación Actual', 'Estado', 'Cargo Actual']
        ws.append(headers)

        for v in voluntarios:
            membresia = v.usuario.membresia_activa_list[0] if v.usuario.membresia_activa_list else None
            cargo_actual = v.cargo_actual_list[0] if v.cargo_actual_list else None
            ws.append([
                v.usuario.rut or '',
                v.usuario.get_full_name,
                v.usuario.email or '',
                v.usuario.phone or '',
                membresia.estacion.nombre if membresia and membresia.estacion else 'Sin Estación',
                membresia.get_estado_display() if membresia else 'Inactivo',
                cargo_actual.cargo.nombre if cargo_actual and cargo_actual.cargo else 'Sin Cargo'
            ])
        
        wb.save(response)
        return response
    
    def _export_pdf(self, request, voluntarios):
        """Genera y devuelve una respuesta HTTP con un archivo PDF."""
        context = {
            'voluntarios': voluntarios,
            'request': request
        }
        html_string = render_to_string(
            "gestion_voluntarios/pages/lista_voluntarios_pdf.html", 
            context
        )
        
        result = io.BytesIO()
        pdf = pisa.CreatePDF(
            html_string, 
            dest=result,
            link_callback=link_callback
        )
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="listado_voluntarios_{timezone.now().strftime("%Y-%m-%d")}.pdf"'
            return response
        
        return HttpResponse(f'Error al generar el PDF: {pdf.err}')

    def _export_json(self, voluntarios):
        """Genera y devuelve una respuesta HTTP con un archivo JSON."""
        data_list = []
        for v in voluntarios:
            membresia = v.usuario.membresia_activa_list[0] if v.usuario.membresia_activa_list else None
            cargo_actual = v.cargo_actual_list[0] if v.cargo_actual_list else None
            data_list.append({
                'rut': v.usuario.rut or '',
                'nombre_completo': v.usuario.get_full_name,
                'email': v.usuario.email or '',
                'telefono': v.usuario.phone or '',
                'estacion': membresia.estacion.nombre if membresia and membresia.estacion else None,
                'estado': membresia.get_estado_display() if membresia else 'Inactivo',
                'cargo': cargo_actual.cargo.nombre if cargo_actual and cargo_actual.cargo else None
            })
        
        return JsonResponse(data_list, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})

    
    # --- VISTA GET PRINCIPAL ---
    def get(self, request):
        estacion_id = self.get_estacion_activa(request)
        if not estacion_id:
            return redirect('portal:home')

        # Leemos el formato de la URL (?format=...)
        formato = request.GET.get('format')

        if formato:
            # Si se pide un formato, generar el archivo
            voluntarios = self._get_voluntarios_data(request)
            
            if formato == 'excel':
                return self._export_excel(voluntarios)
            elif formato == 'pdf':
                return self._export_pdf(request, voluntarios)
            elif formato == 'json':
                return self._export_json(voluntarios) # <--- Ahora sí encontrará este método
            else: # Default to CSV
                return self._export_csv(voluntarios)
        
        else:
            # Si no se pide formato, mostrar la página de opciones
            cargos = Cargo.objects.all().order_by('nombre')
            
            context = {
                'cargos': cargos
            }
            return render(request, "gestion_voluntarios/pages/exportar_listado.html", context)