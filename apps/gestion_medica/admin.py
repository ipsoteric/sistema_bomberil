from django.contrib import admin
from django.utils.html import format_html
from apps.common.admin_mixins import SysPermissionMixin
from .models import (
    SistemaSalud, GrupoSanguineo, Medicamento, Enfermedad, Alergia, Cirugia,
    FichaMedica, FichaMedicaEnfermedad, FichaMedicaMedicamento,
    FichaMedicaCirugia, FichaMedicaAlergia, ContactoEmergencia
)

# --- INLINES (HISTORIAL CLÍNICO) ---
# Estos inlines permiten editar todo el historial médico dentro de la misma Ficha

class FichaEnfermedadInline(SysPermissionMixin, admin.TabularInline):
    model = FichaMedicaEnfermedad
    extra = 0
    autocomplete_fields = ['enfermedad']
    verbose_name = "Antecedente Mórbido / Enfermedad"
    verbose_name_plural = "Enfermedades y Patologías"

class FichaMedicamentoInline(SysPermissionMixin, admin.TabularInline):
    model = FichaMedicaMedicamento
    extra = 0
    autocomplete_fields = ['medicamento']
    verbose_name = "Medicamento Permanente"
    verbose_name_plural = "Tratamientos Farmacológicos"

class FichaAlergiaInline(SysPermissionMixin, admin.TabularInline):
    model = FichaMedicaAlergia
    extra = 0
    autocomplete_fields = ['alergia']
    verbose_name = "Alergia Registrada"
    verbose_name_plural = "Alergias"

class FichaCirugiaInline(SysPermissionMixin, admin.TabularInline):
    model = FichaMedicaCirugia
    extra = 0
    autocomplete_fields = ['cirugia']
    verbose_name = "Cirugía / Operación"
    verbose_name_plural = "Historial Quirúrgico"


# --- CATÁLOGOS MÉDICOS ---
# Configurados con search_fields para soportar el autocompletado en los inlines

@admin.register(SistemaSalud)
class SistemaSaludAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(GrupoSanguineo)
class GrupoSanguineoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Medicamento)
class MedicamentoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre_completo', 'clasificacion_riesgo', 'concentracion', 'unidad')
    list_filter = ('unidad', 'clasificacion_riesgo')
    search_fields = ('nombre',) 
    ordering = ('nombre',)

@admin.register(Enfermedad)
class EnfermedadAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Alergia)
class AlergiaAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Cirugia)
class CirugiaAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


# --- FICHA MÉDICA PRINCIPAL ---

@admin.register(FichaMedica)
class FichaMedicaAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = (
        'get_voluntario', 
        'grupo_sanguineo', 
        'sistema_salud', 
        'conteo_alertas_medicas',
        'fecha_modificacion'
    )
    list_filter = (
        'grupo_sanguineo', 
        'sistema_salud', 
        'fecha_modificacion'
    )
    # Buscamos por datos del voluntario asociado
    search_fields = (
        'voluntario__usuario__first_name', 
        'voluntario__usuario__last_name', 
        'voluntario__usuario__rut'
    )
    autocomplete_fields = ['voluntario', 'grupo_sanguineo', 'sistema_salud']
    
    inlines = [
        FichaEnfermedadInline,
        FichaAlergiaInline,
        FichaMedicamentoInline,
        FichaCirugiaInline
    ]

    fieldsets = (
        ('Paciente', {
            'fields': ('voluntario',)
        }),
        ('Datos Fisiológicos y Administrativos', {
            'fields': (
                ('grupo_sanguineo', 'sistema_salud'),
                ('peso_kg', 'altura_mts'),
                ('presion_arterial_sistolica', 'presion_arterial_diastolica')
            )
        }),
        ('Notas Adicionales', {
            'fields': ('observaciones_generales',)
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')

    def get_voluntario(self, obj):
        return obj.voluntario.usuario.get_full_name
    get_voluntario.short_description = "Voluntario"
    get_voluntario.admin_order_field = 'voluntario__usuario__last_name'

    def conteo_alertas_medicas(self, obj):
        """Muestra visualmente si el usuario tiene condiciones preexistentes importantes"""
        alertas = []
        c_alergias = obj.alergias.count()
        c_enfermedades = obj.enfermedades.count()
        
        if c_alergias > 0:
            alertas.append(f'<span style="color:red; font-weight:bold;">{c_alergias} Alergias</span>')
        if c_enfermedades > 0:
            alertas.append(f'<span style="color:orange; font-weight:bold;">{c_enfermedades} Patologías</span>')
            
        if not alertas:
            return format_html('<span style="color:green;">Sin alertas registradas</span>')
        
        return format_html(" | ".join(alertas))
    conteo_alertas_medicas.short_description = "Alertas Médicas"


# --- CONTACTOS DE EMERGENCIA ---
# Se mantiene separado porque vincula a Voluntario directamente, no a la Ficha.

@admin.register(ContactoEmergencia)
class ContactoEmergenciaAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre_completo', 'parentesco', 'telefono', 'get_voluntario')
    search_fields = ('nombre_completo', 'voluntario__usuario__last_name', 'voluntario__usuario__first_name')
    autocomplete_fields = ['voluntario']
    
    def get_voluntario(self, obj):
        return obj.voluntario.usuario.get_full_name
    get_voluntario.short_description = "Voluntario Asociado"