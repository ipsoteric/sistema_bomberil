from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.db.models import Prefetch
from django.contrib import messages
# --- ¡NUEVAS IMPORTACIONES PARA PDF Y EXPORTACIÓN! ---
import csv
import json
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string 
from django.utils import timezone # Para el nombre del archivo
from django.core import serializers
import weasyprint
import openpyxl # <--- Biblioteca para Excel
# -------------------------------------

# Importamos los modelos de voluntarios
from .models import (
    Voluntario, HistorialCargo, Cargo, TipoCargo, Profesion,
    HistorialReconocimiento, HistorialSancion
)

# Importamos Membresia desde la app gestion_usuarios
from apps.gestion_usuarios.models import Membresia

# Importamos el modelo Estacion de gestion_inventario
from apps.gestion_inventario.models import Estacion

# Importamos los formularios
try:
    from .forms import ProfesionForm, CargoForm, UsuarioForm, VoluntarioForm
except ImportError:
    ProfesionForm = CargoForm = UsuarioForm = VoluntarioForm = None

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
        
        # Comprobamos que los formularios se hayan importado
        if not UsuarioForm or not VoluntarioForm:
            messages.error(request, 'Faltan archivos de formulario (forms.py).')
            return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)

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

# Ver cargo y profesiones
class CargosListaView(View):
    def get(self, request):
        
        profesiones = Profesion.objects.all().order_by('nombre')
        cargos = Cargo.objects.select_related('tipo_cargo').all().order_by('nombre')

        context = {
            'profesiones': profesiones,
            'cargos': cargos,
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
                active_membresia_prefetch,
                current_cargo_prefetch,
                cargos_prefetch,
                reconocimientos_prefetch,
                sanciones_prefetch
            ),
            id=id
        )
        
        membresia_list = voluntario.usuario.membresia_activa_list
        cargo_list = voluntario.cargo_actual_list
        membresia_activa = membresia_list[0] if membresia_list else None
        cargo_actual = cargo_list[0] if cargo_list else None
        
        context = {
            'voluntario': voluntario,
            'membresia': membresia_activa,
            'cargo_actual': cargo_actual,
            'request': request # Pasamos el request para construir URLs absolutas
        }
        
        # 2. Renderizamos la plantilla HTML a un string
        # Usamos la NUEVA plantilla hoja_vida_pdf.html
        html_string = render_to_string(
            "gestion_voluntarios/pages/hoja_vida_pdf.html", 
            context
        )
        
        # 3. Generamos el PDF
        # base_url es para que WeasyPrint pueda encontrar tus archivos estáticos (CSS, imágenes)
        base_url = request.build_absolute_uri('/')
        pdf = weasyprint.HTML(string=html_string, base_url=base_url).write_pdf()
        
        # 4. Creamos la respuesta HTTP
        response = HttpResponse(pdf, content_type='application/pdf')
        
        # 5. (Opcional) Forzar la descarga con un nombre de archivo
        # response['Content-Disposition'] = f'attachment; filename="hoja_vida_{voluntario.usuario.rut}.pdf"'
        
        # 5. (Alternativa) Mostrar en el navegador
        response['Content-Disposition'] = f'inline; filename="hoja_vida_{voluntario.usuario.rut}.pdf"'
        
        return response
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

        # Pre-cargamos los datos necesarios para el reporte
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
        ).distinct() # Evita duplicados si los filtros causan joins múltiples

    def _export_csv(self, voluntarios):
        """Genera y devuelve una respuesta HTTP con un archivo CSV."""
        response = HttpResponse(
            content_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="listado_voluntarios_{timezone.now().strftime("%Y-%m-%d")}.csv"'
            },
        )
        response.write(u'\ufeff'.encode('utf8')) # BOM para UTF-8 (acentos)
        writer = csv.writer(response, delimiter=';')
        
        writer.writerow(['RUT', 'Nombre Completo', 'Email', 'Teléfono', 'Estación Actual', 'Estado', 'Cargo Actual'])

        for v in voluntarios:
            membresia = v.usuario.membresia_activa_list[0] if v.usuario.membresia_activa_list else None
            cargo_actual = v.cargo_actual_list[0] if v.cargo_actual_list else None
            writer.writerow([
                v.usuario.rut or '',
                v.usuario.get_full_name, # <--- CORREGIDO (sin paréntesis)
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
                v.usuario.get_full_name, # <--- CORREGIDO (sin paréntesis)
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
        base_url = request.build_absolute_uri('/')
        pdf = weasyprint.HTML(string=html_string, base_url=base_url).write_pdf()
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="listado_voluntarios_{timezone.now().strftime("%Y-%m-%d")}.pdf"'
        return response

    def _export_json(self, voluntarios):
        """Genera y devuelve una respuesta HTTP con un archivo JSON."""
        data_list = []
        for v in voluntarios:
            membresia = v.usuario.membresia_activa_list[0] if v.usuario.membresia_activa_list else None
            cargo_actual = v.cargo_actual_list[0] if v.cargo_actual_list else None
            data_list.append({
                'rut': v.usuario.rut or '',
                'nombre_completo': v.usuario.get_full_name, # <--- CORREGIDO (sin paréntesis)
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