from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.db.models import Prefetch, Count, Q
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
import csv
import json
import io
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string 
from django.utils import timezone
import openpyxl
from xhtml2pdf import pisa
from .utils import link_callback

from .models import (
    Voluntario, HistorialCargo, Cargo, TipoCargo, Profesion,
    HistorialReconocimiento, HistorialSancion
)
from apps.gestion_usuarios.models import Membresia
from apps.common.mixins import BaseEstacionMixin, AuditoriaMixin
from apps.gestion_usuarios.models import Membresia

# Importamos TODOS los formularios
try:
    from .forms import (
        ProfesionForm, CargoForm, UsuarioForm, VoluntarioForm,
        HistorialCargoForm, HistorialReconocimientoForm, HistorialSancionForm
    )
except ImportError:
    ProfesionForm = CargoForm = UsuarioForm = VoluntarioForm = None
    HistorialCargoForm = HistorialReconocimientoForm = HistorialSancionForm = None


class VoluntariosInicioView(BaseEstacionMixin, View):
    """
    Dashboard principal del módulo de Voluntarios.
    Permiso requerido: Acceso al módulo (Manejado por BaseEstacionMixin).
    """
    def get(self, request):
        estacion = self.estacion_activa

        # 1. Métricas rápidas (Count directo en DB)
        qs_base = Membresia.objects.filter(estacion=estacion)
        total_voluntarios = qs_base.count()
        voluntarios_activos = qs_base.filter(estado='ACTIVO').count()
        voluntarios_inactivos = qs_base.filter(estado='INACTIVO').count()

        # 2. Datos para Gráfico de Rangos (Cargos vigentes en la estación)
        rangos_data = HistorialCargo.objects.filter(
            fecha_fin__isnull=True,
            voluntario__usuario__membresias__estacion=estacion,
            voluntario__usuario__membresias__estado='ACTIVO'
        ).values('cargo__nombre').annotate(count=Count('cargo')).order_by('-count')

        # 3. Datos para Gráfico de Profesiones (Top 5)
        profesiones_data = Voluntario.objects.filter(
            usuario__membresias__estacion=estacion,
            usuario__membresias__estado='ACTIVO'
        ).exclude(profesion__isnull=True).values('profesion__nombre').annotate(count=Count('profesion')).order_by('-count')[:5]

        context = {
            'total_voluntarios_general': total_voluntarios,
            'voluntarios_activos': voluntarios_activos,
            'voluntarios_inactivos': voluntarios_inactivos,
            'chart_rangos_labels': json.dumps([x['cargo__nombre'] for x in rangos_data]),
            'chart_rangos_counts': json.dumps([x['count'] for x in rangos_data]),
            'chart_profes_labels': json.dumps([x['profesion__nombre'] for x in profesiones_data]),
            'chart_profes_counts': json.dumps([x['count'] for x in profesiones_data]),
        }
        return render(request, "gestion_voluntarios/pages/home.html", context)




class VoluntariosListaView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Listado de voluntarios de la estación activa.
    """
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_ver_voluntarios'

    def get(self, request):
        # 1. Filtros de URL
        rango_id = request.GET.get('rango')
        busqueda = request.GET.get('q')

        # 2. QuerySet Base: Filtrado estrictamente por estación activa
        voluntarios_qs = Voluntario.objects.select_related('usuario').filter(
            usuario__membresias__estacion=self.estacion_activa,
            usuario__membresias__estado='ACTIVO'
        )

        # 3. Aplicar Filtros
        if rango_id and rango_id != 'global':
            voluntarios_qs = voluntarios_qs.filter(
                historial_cargos__cargo_id=rango_id,
                historial_cargos__fecha_fin__isnull=True
            )

        if busqueda:
            voluntarios_qs = voluntarios_qs.filter(
                Q(usuario__first_name__icontains=busqueda) | 
                Q(usuario__last_name__icontains=busqueda) | 
                Q(usuario__rut__icontains=busqueda)
            )

        # 4. Optimización (Prefetch): Solo traer datos relevantes para la lista
        active_membresia_prefetch = Prefetch(
            'usuario__membresias',
            queryset=Membresia.objects.filter(estado='ACTIVO', estacion=self.estacion_activa),
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

        context = {
            'voluntarios': voluntarios,
            'cargos': Cargo.objects.all().order_by('nombre'),
        }
        return render(request, "gestion_voluntarios/pages/lista_voluntarios.html", context)




class VoluntariosVerView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Ficha detallada del voluntario (Hoja de Vida).
    """
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_ver_voluntarios'

    def get(self, request, id):
        # Prefetches complejos para armar la hoja de vida completa
        # Nota: Mostramos historial completo (cargos, sanciones) aunque hayan ocurrido en otras estaciones.
        qs_cargos = HistorialCargo.objects.all().select_related('cargo', 'estacion_registra').order_by('-fecha_inicio')
        qs_reco = HistorialReconocimiento.objects.all().select_related('tipo_reconocimiento', 'estacion_registra').order_by('-fecha_evento')
        qs_sanciones = HistorialSancion.objects.all().select_related('estacion_registra', 'estacion_evento').order_by('-fecha_evento')
        
        # Query principal con seguridad de estación
        voluntario = get_object_or_404(
            Voluntario.objects.select_related('usuario', 'nacionalidad', 'profesion', 'domicilio_comuna')
            .prefetch_related(
                # Importante: Prefetch de membresía SOLO para la estación activa para validar estado actual
                Prefetch('usuario__membresias', 
                         queryset=Membresia.objects.filter(estacion=self.estacion_activa), 
                         to_attr='membresia_local_list'),
                # Prefetch de cargo actual (vigente)
                Prefetch('historial_cargos', 
                         queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True), 
                         to_attr='cargo_actual_list'),
                # Historicos completos
                Prefetch('historial_cargos', queryset=qs_cargos),
                Prefetch('historial_reconocimientos', queryset=qs_reco),
                Prefetch('historial_sanciones', queryset=qs_sanciones),
            ),
            usuario__id=id,
            # CRÍTICO: El voluntario debe tener membresía en ESTA estación
            usuario__membresias__estacion=self.estacion_activa
        )
        
        # Extraer objetos de las listas prefetched
        membresia_local = voluntario.usuario.membresia_local_list[0] if voluntario.usuario.membresia_local_list else None
        cargo_actual = voluntario.cargo_actual_list[0] if voluntario.cargo_actual_list else None

        context = {
            'voluntario': voluntario,
            'membresia': membresia_local,
            'cargo_actual': cargo_actual,
            # Formularios vacíos para los modales de "Agregar Evento"
            'form_cargo': HistorialCargoForm(),
            'form_reconocimiento': HistorialReconocimientoForm(),
            'form_sancion': HistorialSancionForm(),
        }
        return render(request, "gestion_voluntarios/pages/ver_voluntario.html", context)




# =============================================================================
#  ACCIONES DE BITÁCORA (AGREGAR EVENTOS)
# =============================================================================
class VoluntarioAgregarCargoView(BaseEstacionMixin, AuditoriaMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_voluntarios'

    def post(self, request, id):
        # Validamos pertenencia a la estación
        voluntario = get_object_or_404(Voluntario, usuario__id=id, usuario__membresias__estacion=self.estacion_activa)
        form = HistorialCargoForm(request.POST)

        if form.is_valid():
            try:
                es_historico = form.cleaned_data.get('es_registro_antiguo', False)
                nuevo_cargo = form.save(commit=False)
                nuevo_cargo.voluntario = voluntario
                nuevo_cargo.estacion_registra = self.estacion_activa  # Firmado por la estación actual

                # Usamos el nombre del usuario como representación legible
                nombre_usuario = voluntario.usuario.get_full_name
                nombre_cargo = nuevo_cargo.cargo.nombre
                
                if es_historico:
                    # MODO HISTÓRICO: Solo insertar registro, no afectar vigencia actual
                    nuevo_cargo.es_historico = True
                    nuevo_cargo.save()
                    
                    # --- AUDITORÍA ---
                    self.auditar(
                        verbo="registró un cargo histórico para",
                        objetivo=voluntario.usuario,
                        objetivo_repr=nombre_usuario,
                        detalles={
                            'cargo': nombre_cargo,
                            'periodo_inicio': str(nuevo_cargo.fecha_inicio),
                            'tipo': 'Histórico (Carga de datos)'
                        }
                    )

                    messages.success(request, "Cargo histórico registrado en la hoja de vida.")

                else:
                    # MODO VIVO: Lógica de negocio estricta
                    fecha_inicio = form.cleaned_data['fecha_inicio']
                    cargo_vigente = HistorialCargo.objects.filter(voluntario=voluntario, fecha_fin__isnull=True).first()

                    detalles_audit = {'cargo_nuevo': nombre_cargo}

                    if cargo_vigente:
                        if fecha_inicio < cargo_vigente.fecha_inicio:
                            messages.error(request, "Fecha inválida: El nuevo cargo no puede ser anterior al cargo vigente actual.")
                            return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)
                        
                        detalles_audit['cargo_anterior'] = cargo_vigente.cargo.nombre
                        # Cerrar cargo anterior
                        cargo_vigente.fecha_fin = fecha_inicio
                        cargo_vigente.save()

                    nuevo_cargo.es_historico = False
                    nuevo_cargo.save()

                    # --- AUDITORÍA ---
                    self.auditar(
                        verbo=f"asignó el cargo de {nombre_cargo} a",
                        objetivo=voluntario.usuario,
                        objetivo_repr=nombre_usuario,
                        detalles=detalles_audit
                    )

                    messages.success(request, "Nuevo cargo vigente registrado y actualizado.")

            except Exception as e:
                messages.error(request, f"Error interno: {e}")
        else:
            messages.error(request, "No se pudo agregar el cargo. Revisa los campos del formulario.")
                    
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)




class VoluntarioAgregarReconocimientoView(BaseEstacionMixin, AuditoriaMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_voluntarios'

    def post(self, request, id):
        voluntario = get_object_or_404(Voluntario, usuario__id=id, usuario__membresias__estacion=self.estacion_activa)
        form = HistorialReconocimientoForm(request.POST)
        
        if form.is_valid():
            try:
                nuevo_reco = form.save(commit=False)
                nuevo_reco.voluntario = voluntario
                nuevo_reco.estacion_registra = self.estacion_activa
                nuevo_reco.es_historico = form.cleaned_data.get('es_registro_antiguo', False)
                nuevo_reco.save()

                # --- AUDITORÍA ---
                nombre_premio = nuevo_reco.tipo_reconocimiento.nombre
                es_hist = "Histórico" if nuevo_reco.es_historico else "En ceremonia"
                self.auditar(
                    verbo="otorgó/registró el reconocimiento",
                    objetivo=voluntario.usuario,
                    objetivo_repr=voluntario.usuario.get_full_name,
                    detalles={
                        'reconocimiento': nombre_premio,
                        'fecha_evento': str(nuevo_reco.fecha_evento),
                        'modo': es_hist
                    }
                )
                messages.success(request, "Reconocimiento registrado exitosamente.")
            except Exception as e:
                messages.error(request, f"Error interno al guardar reconocimiento: {e}")

        else:
             messages.error(request, "Error en formulario. Verifique fechas.")
             
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)




class VoluntarioAgregarSancionView(BaseEstacionMixin, AuditoriaMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_voluntarios'

    def post(self, request, id):
        voluntario = get_object_or_404(Voluntario, usuario__id=id, usuario__membresias__estacion=self.estacion_activa)
        form = HistorialSancionForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                nueva_sancion = form.save(commit=False)
                nueva_sancion.voluntario = voluntario
                nueva_sancion.estacion_registra = self.estacion_activa
                nueva_sancion.es_historico = form.cleaned_data.get('es_registro_antiguo', False)
                nueva_sancion.save()

                # --- AUDITORÍA ---
                tipo_sancion_str = str(nueva_sancion.tipo_sancion) if hasattr(nueva_sancion, 'tipo_sancion') else "Medida Disciplinaria"
                self.auditar(
                    verbo="aplicó una medida disciplinaria a",
                    objetivo=voluntario.usuario,
                    objetivo_repr=voluntario.usuario.get_full_name,
                    detalles={
                        'medida': tipo_sancion_str,
                        'fecha_incidente': str(nueva_sancion.fecha_evento),
                        'es_historico': nueva_sancion.es_historico
                    }
                )
                messages.warning(request, "Sanción disciplinaria registrada.")
            except Exception as e:
                messages.error(request, f"Error interno al guardar sanción: {e}")
        else:
             messages.error(request, "Error al registrar sanción. Verifique campos obligatorios.")
             
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)




class VoluntariosModificarView(BaseEstacionMixin, AuditoriaMixin, PermissionRequiredMixin, View):
    """
    Edita los datos básicos (perennes) del voluntario y su usuario.
    No edita historial.
    """
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_voluntarios'

    def get_voluntario(self, id):
        return get_object_or_404(
            Voluntario.objects.select_related('usuario'), 
            usuario__id=id, 
            usuario__membresias__estacion=self.estacion_activa
        )

    def get(self, request, id):
        voluntario = self.get_voluntario(id)
        context = {
            'voluntario': voluntario,
            'usuario_form': UsuarioForm(instance=voluntario.usuario),
            'voluntario_form': VoluntarioForm(instance=voluntario)
        }
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)

    def post(self, request, id):
        voluntario = self.get_voluntario(id)
        usuario_form = UsuarioForm(request.POST, instance=voluntario.usuario)
        voluntario_form = VoluntarioForm(request.POST, request.FILES, instance=voluntario)

        if usuario_form.is_valid() and voluntario_form.is_valid():
            try:
                usuario_form.save()
                voluntario_form.save()

                # --- AUDITORÍA ---
                self.auditar(
                    verbo="actualizó la ficha personal de",
                    objetivo=voluntario.usuario,
                    objetivo_repr=voluntario.usuario.get_full_name,
                    detalles={
                        'cambios_usuario': 'Se modificaron datos de contacto/perfil'
                    }
                )
                messages.success(request, f'Datos de {voluntario.usuario.get_full_name} actualizados.')
                return redirect('gestion_voluntarios:ruta_ver_voluntario', id=voluntario.usuario.id)
            except Exception as e:
                messages.error(request, f"Error crítico actualizando datos: {e}")
        
        context = {
            'voluntario': voluntario,
            'usuario_form': usuario_form,
            'voluntario_form': voluntario_form
        }
        messages.error(request, 'Error de validación.')
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html", context)




# =============================================================================
#  GESTIÓN DE NORMALIZACIÓN (CARGOS Y PROFESIONES)
# =============================================================================
class CargosListaView(BaseEstacionMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_datos_normalizacion'

    def get(self, request):
        q_profesion = request.GET.get('q_profesion', '')
        q_cargo = request.GET.get('q_cargo', '')
        filtro_tipo_cargo = request.GET.get('tipo_cargo', '')

        profesiones = Profesion.objects.all().order_by('nombre')
        if q_profesion:
            profesiones = profesiones.filter(nombre__icontains=q_profesion)

        cargos = Cargo.objects.select_related('tipo_cargo').all().order_by('nombre')
        if q_cargo:
            cargos = cargos.filter(nombre__icontains=q_cargo)
        if filtro_tipo_cargo and filtro_tipo_cargo != 'global':
            cargos = cargos.filter(tipo_cargo_id=filtro_tipo_cargo)

        context = {
            'profesiones': profesiones,
            'cargos': cargos,
            'tipos_cargo': TipoCargo.objects.all().order_by('nombre'),
        }
        return render(request, "gestion_voluntarios/pages/lista_cargos_profes.html", context)




# CRUD simple para Profesiones y Cargos
class ProfesionesCrearView(BaseEstacionMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_datos_normalizacion'

    def get(self, request):
        return render(request, "gestion_voluntarios/pages/crear_profesion.html", {'form': ProfesionForm()})

    def post(self, request):
        form = ProfesionForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Profesión creada.")
                return redirect('gestion_voluntarios:ruta_cargos_lista')
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
        
        messages.error(request, "Error al crear la profesión. Revisa los datos.")
        return render(request, "gestion_voluntarios/pages/crear_profesion.html", {'form': form})




class ProfesionesModificarView(BaseEstacionMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_datos_normalizacion'

    def get(self, request, id):
        prof = get_object_or_404(Profesion, id=id)
        return render(request, "gestion_voluntarios/pages/modificar_profesion.html", {'form': ProfesionForm(instance=prof), 'profesion': prof})

    def post(self, request, id):
        prof = get_object_or_404(Profesion, id=id)
        form = ProfesionForm(request.POST, instance=prof)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Profesión actualizada.")
                return redirect('gestion_voluntarios:ruta_cargos_lista')
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")

        messages.error(request, "Error al modificar la profesión. Revisa los datos.")
        return render(request, "gestion_voluntarios/pages/modificar_profesion.html", {'form': form, 'profesion': prof})




class CargosCrearView(BaseEstacionMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_datos_normalizacion'

    def get(self, request):
        return render(request, "gestion_voluntarios/pages/crear_cargo.html", {'form': CargoForm()})

    def post(self, request):
        form = CargoForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Cargo creado.")
                return redirect('gestion_voluntarios:ruta_cargos_lista')
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
        messages.error(request, "Error al crear cargo. Revisa los datos.")
        return render(request, "gestion_voluntarios/pages/crear_cargo.html", {'form': form})




class CargosModificarView(BaseEstacionMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_gestionar_datos_normalizacion'

    def get(self, request, id):
        cargo = get_object_or_404(Cargo, id=id)
        return render(request, "gestion_voluntarios/pages/modificar_cargo.html", {'form': CargoForm(instance=cargo), 'cargo': cargo})

    def post(self, request, id):
        cargo = get_object_or_404(Cargo, id=id)
        form = CargoForm(request.POST, instance=cargo)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Cargo actualizado.")
                return redirect('gestion_voluntarios:ruta_cargos_lista')
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")

        messages.error(request, "Error al modificar el cargo. Revisa los datos.")
        return render(request, "gestion_voluntarios/pages/modificar_cargo.html", {'form': form, 'cargo': cargo})




# =============================================================================
#  REPORTES Y EXPORTACIONES
# =============================================================================
class HojaVidaView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Genera PDF de hoja de vida. Validamos acceso y auditoría de visualización.
    """
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_generar_hoja_vida'

    def get(self, request, id):
        # Reutilizamos la lógica de seguridad de VerVoluntario
        # No permitir generar hoja de vida de alguien de otra compañía
        voluntario_check = get_object_or_404(
            Voluntario, 
            usuario__id=id, 
            usuario__membresias__estacion=self.estacion_activa
        )
        
        # Obtenemos datos completos para el reporte (Query limpia)
        voluntario_full = Voluntario.objects.select_related(
            'usuario', 'nacionalidad', 'profesion', 'domicilio_comuna'
        ).prefetch_related(
            Prefetch('historial_cargos', queryset=HistorialCargo.objects.all().select_related('cargo').order_by('-fecha_inicio')),
            Prefetch('historial_reconocimientos', queryset=HistorialReconocimiento.objects.all().order_by('-fecha_evento')),
            Prefetch('historial_sanciones', queryset=HistorialSancion.objects.all().order_by('-fecha_evento')),
            Prefetch('usuario__membresias', queryset=Membresia.objects.filter(estacion=self.estacion_activa), to_attr='membresia_local_list')
        ).get(pk=voluntario_check.pk)

        context = {
            'voluntario': voluntario_full,
            'membresia': voluntario_full.usuario.membresia_local_list[0] if voluntario_full.usuario.membresia_local_list else None,
            'cargo_actual': voluntario_full.historial_cargos.filter(fecha_fin__isnull=True).first(),
            'request': request
        }
        
        html_string = render_to_string("gestion_voluntarios/pages/hoja_vida_pdf.html", context)
        result = io.BytesIO()
        pdf = pisa.pisaDocument(src=io.BytesIO(html_string.encode("UTF-8")), dest=result, link_callback=link_callback)
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="HV_{voluntario_full.usuario.rut}.pdf"'
            return response
        
        messages.error(request, "No se pudo generar el documento PDF. Por favor contacte a soporte.")
        return redirect('gestion_voluntarios:ruta_ver_voluntario', id=id)




class ExportarListadoView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Maneja CSV, Excel, PDF y JSON en una sola vista centralizada.
    """
    permission_required = 'gestion_voluntarios.accion_gestion_voluntarios_generar_reportes'

    def _get_queryset(self, request):
        estacion = self.estacion_activa
        rango_id = request.GET.get('rango')
        
        # Filtro base de seguridad
        qs = Voluntario.objects.filter(
            usuario__membresias__estacion=estacion,
            usuario__membresias__estado='ACTIVO'
        )
        if rango_id and rango_id != 'global':
            qs = qs.filter(historial_cargos__cargo_id=rango_id, historial_cargos__fecha_fin__isnull=True)
            
        return qs.select_related('usuario').prefetch_related(
            Prefetch('historial_cargos', queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'), to_attr='cargos_activos'),
            Prefetch('usuario__membresias', queryset=Membresia.objects.filter(estacion=estacion), to_attr='membresias_activas')
        ).distinct()

    def _extract_data(self, voluntarios):
        # Helper para extraer datos planos y evitar repetición en cada formato
        data = []
        for v in voluntarios:
            membresia = v.usuario.membresias_activas[0] if v.usuario.membresias_activas else None
            cargo = v.cargos_activos[0].cargo.nombre if v.cargos_activos else "Sin cargo"
            data.append({
                'rut': v.usuario.rut,
                'nombre': v.usuario.get_full_name,
                'email': v.usuario.email,
                'telefono': v.usuario.phone,
                'estado': membresia.get_estado_display() if membresia else "Desconocido",
                'cargo': cargo
            })
        return data

    def get(self, request):
        fmt = request.GET.get('format')
        
        # Si no hay formato, mostrar UI de selección
        if not fmt:
            return render(request, "gestion_voluntarios/pages/exportar_listado.html", {'cargos': Cargo.objects.all()})

        try:
            # Generar datos
            voluntarios = self._get_queryset(request)
            dataset = self._extract_data(voluntarios)
            filename = f"Voluntarios_{timezone.now().strftime('%Y-%m-%d')}"

            if fmt == 'json':
                return JsonResponse(dataset, safe=False)

            elif fmt == 'csv':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
                writer = csv.writer(response, delimiter=';')
                writer.writerow(['RUT', 'Nombre', 'Email', 'Teléfono', 'Estado', 'Cargo'])
                for d in dataset:
                    writer.writerow(d.values())
                return response

            elif fmt == 'excel':
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Voluntarios"
                ws.append(['RUT', 'Nombre', 'Email', 'Teléfono', 'Estado', 'Cargo'])
                for d in dataset:
                    ws.append(list(d.values()))

                response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
                wb.save(response)
                return response
        
        except Exception as e:
            messages.error(request, f"Error al generar el archivo de exportación: {e}")
            return redirect('gestion_voluntarios:ruta_exportar_listado')

        # ... (Implementar PDF similarmente si se requiere)
        return redirect('gestion_voluntarios:ruta_exportar_listado')