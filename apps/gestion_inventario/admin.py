from django.contrib import admin
from .models import (
    TipoEstado, Estado, Region, Comuna, Estacion,
    TipoUbicacion, Ubicacion, Marca, TipoVehiculo, Vehiculo, Compartimento,
    Proveedor, ContactoProveedor, Categoria, ProductoGlobal, Producto,
    Activo, RegistroUsoActivo, LoteInsumo, Destinatario,
    Prestamo, PrestamoDetalle, MovimientoInventario
)
from apps.common.admin_mixins import ImagenPreviewMixin, SysPermissionMixin


# --- CONFIGURACIÓN DE TABLAS MAESTRAS / SIMPLE ---
@admin.register(TipoEstado)
class TipoEstadoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(Estado)
class EstadoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'tipo_estado', 'descripcion')
    list_filter = ('tipo_estado',)
    search_fields = ('nombre',)

@admin.register(Region)
class RegionAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Comuna)
class ComunaAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'region')
    list_filter = ('region',)
    search_fields = ('nombre',)

@admin.register(TipoUbicacion)
class TipoUbicacionAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(Marca)
class MarcaAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(TipoVehiculo)
class TipoVehiculoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(Categoria)
class CategoriaAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'descripcion')
    search_fields = ('nombre', 'codigo')


# --- ESTRUCTURA ORGANIZACIONAL ---

@admin.register(Estacion)
class EstacionAdmin(SysPermissionMixin, ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'comuna', 'es_departamento', 'mostrar_preview')
    list_filter = ('es_departamento', 'comuna__region')
    search_fields = ('nombre', 'codigo')
    readonly_fields = ('codigo', 'imagen_thumb_medium', 'imagen_thumb_small', 'logo_thumb_medium', 'logo_thumb_small')
    
    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'codigo', 'descripcion', 'es_departamento')
        }),
        ('Ubicación', {
            'fields': ('direccion', 'comuna')
        }),
        ('Multimedia', {
            'fields': ('imagen', 'logo')
        }),
    )

@admin.register(Ubicacion)
class UbicacionAdmin(SysPermissionMixin, ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'estacion', 'tipo_ubicacion', 'mostrar_preview')
    list_filter = ('estacion', 'tipo_ubicacion')
    search_fields = ('nombre', 'codigo', 'estacion__nombre')
    readonly_fields = ('codigo', 'imagen_thumb_medium', 'imagen_thumb_small')
    autocomplete_fields = ['estacion']

@admin.register(Vehiculo)
class VehiculoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('ubicacion', 'patente', 'marca', 'modelo', 'tipo_vehiculo', 'anho')
    list_filter = ('tipo_vehiculo', 'marca')
    search_fields = ('patente', 'chasis', 'ubicacion__nombre')
    autocomplete_fields = ['ubicacion', 'marca', 'tipo_vehiculo']

@admin.register(Compartimento)
class CompartimentoAdmin(SysPermissionMixin, ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'ubicacion', 'mostrar_preview')
    search_fields = ('nombre', 'codigo', 'ubicacion__nombre')
    list_filter = ('ubicacion__estacion',)
    readonly_fields = ('codigo', 'imagen_thumb_medium', 'imagen_thumb_small')
    autocomplete_fields = ['ubicacion']


# --- PROVEEDORES ---

# Nota: Los inlines también necesitan chequear permisos si quieres que sigan la lógica sys_
class ContactoProveedorInline(SysPermissionMixin, admin.StackedInline):
    model = ContactoProveedor
    extra = 0
    classes = ['collapse']

@admin.register(Proveedor)
class ProveedorAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'rut', 'giro_comercial', 'estacion_creadora')
    search_fields = ('nombre', 'rut')
    list_filter = ('estacion_creadora',)
    inlines = [ContactoProveedorInline]


# --- PRODUCTOS Y CATÁLOGO ---

@admin.register(ProductoGlobal)
class ProductoGlobalAdmin(SysPermissionMixin, ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('nombre_oficial', 'marca', 'modelo', 'categoria', 'mostrar_preview')
    list_filter = ('categoria', 'marca')
    search_fields = ('nombre_oficial', 'modelo', 'gtin')
    readonly_fields = ('imagen_thumb_medium', 'imagen_thumb_small')
    autocomplete_fields = ['marca', 'categoria']

@admin.register(Producto)
class ProductoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('__str__', 'sku', 'estacion', 'es_serializado', 'stock_critico')
    list_filter = ('estacion', 'es_serializado', 'es_expirable')
    search_fields = ('sku', 'producto_global__nombre_oficial')
    autocomplete_fields = ['producto_global', 'estacion', 'proveedor_preferido']


# --- ACTIVOS Y LOTES (INVENTARIO REAL) ---

@admin.register(Activo)
class ActivoAdmin(SysPermissionMixin, ImagenPreviewMixin, admin.ModelAdmin):
    list_display = (
        'codigo_activo', 
        'get_producto_nombre', 
        'estacion', 
        'estado', 
        'compartimento', 
        'fin_vida_util'
    )
    list_filter = ('estacion', 'estado', 'producto__producto_global__categoria')
    search_fields = ('codigo_activo', 'numero_serie_fabricante', 'producto__producto_global__nombre_oficial')
    readonly_fields = ('codigo_activo', 'fin_vida_util_calculada', 'imagen_thumb_medium', 'imagen_thumb_small')
    autocomplete_fields = ['producto', 'estacion', 'compartimento', 'proveedor', 'asignado_a']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('codigo_activo', 'producto', 'numero_serie_fabricante', 'imagen')
        }),
        ('Ubicación y Estado', {
            'fields': ('estacion', 'compartimento', 'estado', 'asignado_a')
        }),
        ('Ciclo de Vida', {
            'fields': ('fecha_fabricacion', 'fecha_recepcion', 'fecha_expiracion', 'fin_vida_util_calculada')
        }),
        ('Uso', {
            'fields': ('horas_uso_totales', 'notas_adicionales')
        }),
        ('Adquisición', {
            'fields': ('proveedor',)
        }),
    )

    def get_producto_nombre(self, obj):
        return obj.producto.producto_global.nombre_oficial
    get_producto_nombre.short_description = "Producto"
    get_producto_nombre.admin_order_field = 'producto__producto_global__nombre_oficial'

@admin.register(LoteInsumo)
class LoteInsumoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('codigo_lote', 'get_producto_nombre', 'cantidad', 'fecha_expiracion', 'compartimento')
    list_filter = ('estado', 'fecha_expiracion')
    search_fields = ('codigo_lote', 'numero_lote_fabricante', 'producto__producto_global__nombre_oficial')
    readonly_fields = ('codigo_lote',)
    autocomplete_fields = ['producto', 'compartimento', 'estado']

    def get_producto_nombre(self, obj):
        return obj.producto.producto_global.nombre_oficial
    get_producto_nombre.short_description = "Producto"


@admin.register(RegistroUsoActivo)
class RegistroUsoActivoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('activo', 'fecha_uso', 'horas_registradas', 'usuario_registra')
    list_filter = ('fecha_uso', 'usuario_registra')
    autocomplete_fields = ['activo', 'usuario_registra']
    date_hierarchy = 'fecha_uso'


# --- PRÉSTAMOS Y MOVIMIENTOS ---

class PrestamoDetalleInline(SysPermissionMixin, admin.TabularInline):
    model = PrestamoDetalle
    extra = 1
    autocomplete_fields = ['activo', 'lote']
    fields = ('activo', 'lote', 'cantidad_prestada', 'cantidad_devuelta', 'cantidad_extraviada')

@admin.register(Destinatario)
class DestinatarioAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre_entidad', 'estacion', 'nombre_contacto')
    search_fields = ('nombre_entidad',)
    list_filter = ('estacion',)

@admin.register(Prestamo)
class PrestamoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('id', 'destinatario', 'fecha_prestamo', 'fecha_devolucion_esperada', 'estado', 'usuario_responsable')
    list_filter = ('estado', 'fecha_prestamo', 'estacion')
    search_fields = ('destinatario__nombre_entidad',)
    inlines = [PrestamoDetalleInline]
    autocomplete_fields = ['estacion', 'usuario_responsable', 'destinatario']
    date_hierarchy = 'fecha_prestamo'

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('tipo_movimiento', 'fecha_hora', 'estacion', 'cantidad_movida', 'get_item_nombre')
    list_filter = ('tipo_movimiento', 'estacion', 'fecha_hora')
    search_fields = ('activo__codigo_activo', 'lote_insumo__codigo_lote')
    autocomplete_fields = ['usuario', 'estacion', 'proveedor_origen', 'compartimento_origen', 'compartimento_destino', 'activo', 'lote_insumo']
    date_hierarchy = 'fecha_hora'

    def get_item_nombre(self, obj):
        if obj.activo:
            return f"Activo: {obj.activo.codigo_activo}"
        elif obj.lote_insumo:
            return f"Lote: {obj.lote_insumo.codigo_lote}"
        return "-"
    get_item_nombre.short_description = "Item Afectado"