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

# Página Inicial
class VoluntariosInicioView(View):
    def get(self, request):
        
        # --- 1. Datos para las Tarjetas (Cards) ---
        voluntarios_activos = Membresia.objects.filter(estado='ACTIVO').count()
        voluntarios_inactivos = Membresia.objects.filter(estado='INACTIVO').count()
        total_voluntarios_general = Voluntario.objects.count() 

        # --- 2. Datos para Gráfico de Rangos (Cargos) ---
        rangos_data = HistorialCargo.objects.filter(fecha_fin__isnull=True) \
                      .values('cargo__nombre') \
                      .annotate(count=Count('cargo')) \
                      .order_by('-count')

        chart_rangos_labels = [item['cargo__nombre'] for item in rangos_data]
        chart_rangos_counts = [item['count'] for item in rangos_data]

        # --- 3. Datos para Gráfico de Profesiones (Top 5) ---
        profesiones_data = Voluntario.objects.exclude(profesion__isnull=True) \
                            .values('profesion__nombre') \
                            .annotate(count=Count('profesion')) \
                            .order_by('-count')[:5] 

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
class VoluntariosListaView(View):
    def get(self, request):
        
        # 1. Capturamos los parámetros de la URL (Filtros)
        estacion_id = request.GET.get('estacion')
        rango_id = request.GET.get('rango')
        busqueda = request.GET.get('q') # Para la caja de búsqueda

        # 2. Iniciamos la consulta base
        voluntarios_qs = Voluntario.objects.select_related('usuario')

        # 3. Aplicamos Filtro de Estación (si existe y no es 'global')
        if estacion_id and estacion_id != 'global':
            voluntarios_qs = voluntarios_qs.filter(
                usuario__membresias__estacion_id=estacion_id,
                usuario__membresias__estado='ACTIVO'
            )

        # 4. Aplicamos Filtro de Rango (si existe y no es 'global')
        if rango_id and rango_id != 'global':
            voluntarios_qs = voluntarios_qs.filter(
                historial_cargos__cargo_id=rango_id,
                historial_cargos__fecha_fin__isnull=True # Solo cargo actual
            )

        # 5. Aplicamos Búsqueda por Texto (Nombre o RUT)
        if busqueda:
            voluntarios_qs = voluntarios_qs.filter(
                Q(usuario__first_name__icontains=busqueda) | 
                Q(usuario__last_name__icontains=busqueda) | 
                Q(usuario__rut__icontains=busqueda)
            )

        # 6. Prefetches (para optimizar la carga de datos relacionados en la tarjeta)
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
        
        # Ejecutamos la consulta final con 'distinct' para evitar duplicados por los joins
        voluntarios = voluntarios_qs.prefetch_related(
            active_membresia_prefetch,
            current_cargo_prefetch
        ).distinct().all()

        # 7. Datos para llenar los selectores de filtro
        estaciones = Estacion.objects.all().order_by('nombre')
        cargos = Cargo.objects.all().order_by('nombre')
        
        context = {
            'voluntarios': voluntarios,
            'estaciones': estaciones,
            'cargos': cargos,
        }
        return render(request, "gestion_voluntarios/pages/lista_voluntarios.html", context)


# Ver voluntario
class VoluntariosVerView(View):
    def get(self, request, id):
        active_membresia_prefetch = Prefetch('usuario__membresias', queryset=Membresia.objects.filter(estado='ACTIVO').select_related('estacion'), to_attr='membresia_activa_list')
        current_cargo_prefetch = Prefetch('historial_cargos', queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'), to_attr='cargo_actual_list')
        cargos_prefetch = Prefetch('historial_cargos', queryset=HistorialCargo.objects.all().select_related('cargo', 'estacion_registra').order_by('-fecha_inicio'))
        reconocimientos_prefetch = Prefetch('historial_reconocimientos', queryset=HistorialReconocimiento.objects.all().select_related('tipo_reconocimiento', 'estacion_registra').order_by('-fecha_evento'))
        sanciones_prefetch = Prefetch('historial_sanciones', queryset=HistorialSancion.objects.all().select_related('estacion_registra', 'estacion_evento').order_by('-fecha_evento'))
        
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario', 'nacionalidad', 'profesion', 'domicilio_comuna').prefetch_related(active_membresia_prefetch, current_cargo_prefetch, cargos_prefetch, reconocimientos_prefetch, sanciones_prefetch), usuario__id=id)
        
        membresia_activa = voluntario.usuario.membresia_activa_list[0] if voluntario.usuario.membresia_activa_list else None
        cargo_actual = voluntario.cargo_actual_list[0] if voluntario.cargo_actual_list else None

        # --- Enviamos los 3 formularios al template ---
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

class VoluntarioAgregarCargoView(View):
    def post(self, request, id):
        voluntario = get_object_or_404(Voluntario, id=id)
        form = HistorialCargoForm(request.POST)
        if form.is_valid():
            try:
                # Obtenemos la estación del usuario logueado
                membresia_admin = request.user.membresias.filter(estado='ACTIVO').first()
                estacion_registra = membresia_admin.estacion if membresia_admin else None
                
                # Lógica de Bitácora: Cerrar cargo anterior
                fecha_inicio_nuevo = form.cleaned_data['fecha_inicio']
                cargo_anterior = HistorialCargo.objects.filter(voluntario=voluntario, fecha_fin__isnull=True).first()

                if cargo_anterior:
                    if fecha_inicio_nuevo < cargo_anterior.fecha_inicio:
                        messages.error(request, "La fecha del nuevo cargo no puede ser anterior al actual.")
                        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)
                    cargo_anterior.fecha_fin = fecha_inicio_nuevo
                    cargo_anterior.save()

                # Crear nuevo cargo
                nuevo_cargo = form.save(commit=False)
                nuevo_cargo.voluntario = voluntario
                nuevo_cargo.estacion_registra = estacion_registra
                nuevo_cargo.es_historico = False
                nuevo_cargo.save()
                
                messages.success(request, "Cargo registrado exitosamente.")
            except Exception as e:
                messages.error(request, f"Error: {e}")
        else:
            messages.error(request, "Error en el formulario de cargo.")
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)


class VoluntarioAgregarReconocimientoView(View):
    def post(self, request, id):
        voluntario = get_object_or_404(Voluntario, id=id)
        form = HistorialReconocimientoForm(request.POST)
        
        if form.is_valid():
            try:
                membresia_admin = request.user.membresias.filter(estado='ACTIVO').first()
                
                nuevo_reco = form.save(commit=False)
                nuevo_reco.voluntario = voluntario
                nuevo_reco.estacion_registra = membresia_admin.estacion if membresia_admin else None
                nuevo_reco.es_historico = False
                nuevo_reco.save()
                
                messages.success(request, "Reconocimiento agregado exitosamente.")
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
        else:
             messages.error(request, "Error en el formulario de reconocimiento.")
             
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)


class VoluntarioAgregarSancionView(View):
    def post(self, request, id):
        voluntario = get_object_or_404(Voluntario, id=id)
        # Nota: request.FILES para subir el documento adjunto
        form = HistorialSancionForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                membresia_admin = request.user.membresias.filter(estado='ACTIVO').first()
                
                nueva_sancion = form.save(commit=False)
                nueva_sancion.voluntario = voluntario
                nueva_sancion.estacion_registra = membresia_admin.estacion if membresia_admin else None
                nueva_sancion.es_historico = False
                nueva_sancion.save()
                
                messages.success(request, "Sanción registrada exitosamente.")
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
        else:
             messages.error(request, "Error en el formulario de sanción.")
             
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)


# ... (Resto de vistas Modificar, Configuración, Reportes... se mantienen igual) ...
class VoluntariosModificarView(View):
    
    def get(self, request, id):
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), usuario__id=id)
        
        usuario_form = UsuarioForm(instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(instance=voluntario)

        context = {
            'voluntario': voluntario,
            'usuario_form': usuario_form,
            'voluntario_form': voluntario_form
        }
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)

    def post(self, request, id):
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), id=id)
        
        # ¡IMPORTANTE! Agregamos request.FILES para procesar la imagen del avatar
        usuario_form = UsuarioForm(request.POST, request.FILES, instance=voluntario.usuario)
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
     

# Editar voluntario
class VoluntariosModificarView(View):
    
    def get(self, request, id):
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), usuario__id=id)
        
        if not UsuarioForm or not VoluntarioForm:
             messages.error(request, 'Faltan archivos de formulario (forms.py).')
             return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)

        usuario_form = UsuarioForm(instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(instance=voluntario)

        context = {
            'voluntario': voluntario,
            'usuario_form': usuario_form,
            'voluntario_form': voluntario_form
        }
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)

    def post(self, request, id):
        voluntario = get_object_or_404(Voluntario.objects.select_related('usuario'), id=id)
        
        # CAMBIO: request.FILES ahora va al voluntario_form (para el campo 'imagen')
        usuario_form = UsuarioForm(request.POST, instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(request.POST, request.FILES, instance=voluntario)

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
        pdf = pisa.CreatePDF(
            html_string,                # El HTML a convertir
            dest=result,                # El objeto "archivo" en memoria
            link_callback=link_callback # La función para encontrar estáticos
        )
        
        # 4. Verificamos si hubo errores
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="hoja_vida_{voluntario.usuario.rut}.pdf"'
            return response
        
        # Si hay un error, devolvemos un error HTML
        return HttpResponse(f'Error al generar el PDF: {pdf.err}')

# Exportar listado 
class ExportarListadoView(View):
    
    def _get_voluntarios_data(self, request):
        """
        Obtiene el queryset de voluntarios, filtrado según los 
        parámetros GET 'estacion' y 'rango'.
        """
        estacion_id = request.GET.get('estacion')
        cargo_id = request.GET.get('rango')
        
        voluntarios_qs = Voluntario.objects.select_related('usuario')

        if estacion_id and estacion_id != 'global':
            voluntarios_qs = voluntarios_qs.filter(
                usuario__membresias__estacion_id=estacion_id, 
                usuario__membresias__estado='ACTIVO'
            )
        
        if cargo_id and cargo_id != 'global':
            voluntarios_qs = voluntarios_qs.filter(
                historial_cargos__cargo_id=cargo_id,
                historial_cargos__fecha_fin__isnull=True
            )

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
        
        return voluntarios_qs.prefetch_related(
            active_membresia_prefetch,
            current_cargo_prefetch
        ).distinct()

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
                v.usuario.get_full_name, # Corregido (es propiedad)
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
                v.usuario.get_full_name, # Corregido (es propiedad)
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
        # (Asegúrate de que 'lista_voluntarios_pdf.html' existe)
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
                'nombre_completo': v.usuario.get_full_name, # Corregido (es propiedad)
                'email': v.usuario.email or '',
                'telefono': v.usuario.phone or '',
                'estacion': membresia.estacion.nombre if membresia and membresia.estacion else None,
                'estado': membresia.get_estado_display() if membresia else 'Inactivo',
                'cargo': cargo_actual.cargo.nombre if cargo_actual and cargo_actual.cargo else None
            })
        
        return JsonResponse(data_list, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})

    
    # --- VISTA GET PRINCIPAL ---
    def get(self, request):
        # Leemos el formato de la URL (?format=...)
        formato = request.GET.get('format')

        if formato:
            # Si se pide un formato, generar el archivo
            voluntarios = self._get_voluntarios_data(request) # Get filtered data
            
            if formato == 'excel':
                return self._export_excel(voluntarios)
            elif formato == 'pdf':
                return self._export_pdf(request, voluntarios)
            elif formato == 'json':
                return self._export_json(voluntarios)
            else: # Default to CSV
                return self._export_csv(voluntarios)
        
        else:
            # Si no se pide formato, mostrar la página de opciones
            estaciones = Estacion.objects.all().order_by('nombre')
            cargos = Cargo.objects.all().order_by('nombre')
            
            context = {
                'estaciones': estaciones,
                'cargos': cargos
            }
            return render(request, "gestion_voluntarios/pages/exportar_listado.html", context)