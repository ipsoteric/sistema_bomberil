from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


# ESTADOS
class TipoEstado(models.Model):
    '''(Global) Modelo para registrar los tipos de estado'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del tipo de estado")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Tipo de estado"
        verbose_name_plural = "Tipos de estado"

        permissions = [
            ("sys_view_tipoestado", "System: Puede ver Tipos de Estado"),
            ("sys_add_tipoestado", "System: Puede agregar Tipos de Estado"),
            ("sys_change_tipoestado", "System: Puede cambiar Tipos de Estado"),
            ("sys_delete_tipoestado", "System: Puede eliminar Tipos de Estado"),
        ]

    def __str__(self):
        return self.nombre




class Estado(models.Model):
    '''(Global) Modelo para registrar los diferentes estados que pueden tener los insumos, y otras actividades'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del estado")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
    tipo_estado = models.ForeignKey(TipoEstado, on_delete=models.PROTECT, verbose_name="Tipo de estado")

    class Meta:
        verbose_name = "Estado"
        verbose_name_plural = "Estados"

        permissions = [
            ("sys_view_estado", "System: Puede ver Estados"),
            ("sys_add_estado", "System: Puede agregar Estados"),
            ("sys_change_estado", "System: Puede cambiar Estados"),
            ("sys_delete_estado", "System: Puede eliminar Estados"),
        ]

    def __str__(self):
        return self.nombre




# LOCACIONES
class Region(models.Model):
    '''(Global) Modelo para registrar las regiones del país'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100, help_text="Ingrese el nombre de la región")

    class Meta:
        verbose_name = "Región de Chile"
        verbose_name_plural = "Regiones de Chile"

        permissions = [
            ("sys_view_region", "System: Puede ver Regiones"),
            ("sys_add_region", "System: Puede agregar Regiones"),
            ("sys_change_region", "System: Puede cambiar Regiones"),
            ("sys_delete_region", "System: Puede eliminar Regiones"),
        ]

    def __str__(self):
        return self.nombre




class Comuna(models.Model):
    '''(Global) Modelo para registrar las comunas del país'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100, help_text="Ingrese el nombre de la comuna")
    region = models.ForeignKey(Region, on_delete=models.PROTECT, verbose_name="Región", help_text="Seleccione la región correspondiente")

    class Meta:
        verbose_name = "Comuna de Chile"
        verbose_name_plural = "Comunas de Chile"

        permissions = [
            ("sys_view_comuna", "System: Puede ver Comunas"),
            ("sys_add_comuna", "System: Puede agregar Comunas"),
            ("sys_change_comuna", "System: Puede cambiar Comunas"),
            ("sys_delete_comuna", "System: Puede eliminar Comunas"),
        ]

    def __str__(self):
        return self.nombre
    
    def get_region_name(self):
        return self.region.nombre




class Estacion(models.Model):
    '''(Global) Modelo para registrar las Compañías de Bomberos que serán parte del sistema. Es necesario que exista una compañía para que existan usuarios'''

    nombre = models.CharField(verbose_name="Nombre", max_length=100, help_text="Ingrese el nombre de la compañía")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
    direccion = models.CharField(verbose_name="Dirección", null=True, blank=True, max_length=100, help_text="Ingrese la dirección (calle y número) de la compañía")
    es_departamento = models.BooleanField(verbose_name="Es Cuerpo", default=False, help_text="Seleccione si esta estación corresponde a un Cuerpo de Bomberos")
    imagen = models.ImageField(verbose_name="Imagen de la compañía", null=True, blank=True, upload_to="temporal/estaciones/imagenes/")
    logo = models.ImageField(verbose_name="Logo de la compañía", null=True, blank=True, upload_to="temporal/estaciones/logos/")
    comuna = models.ForeignKey(Comuna, on_delete=models.PROTECT, verbose_name="Comuna", help_text="Seleccione la comuna correspondiente")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Estación"
        verbose_name_plural = "Estaciones"
        ordering = ['nombre']

        permissions = [
            ("sys_view_estacion", "System: Puede ver Estaciones"),
            ("sys_add_estacion", "System: Puede agregar Estaciones"),
            ("sys_change_estacion", "System: Puede cambiar Estaciones"),
            ("sys_delete_estacion", "System: Puede eliminar Estaciones"),
        ]

    def __str__(self):
        return self.nombre




class TipoUbicacion(models.Model):
    '''(Global) Modelo para registrar los tipos de ubicaciones/secciones dentro de una compañía (bodega, habitación, vehículo)'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del tipo de ubicación")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Tipo de ubicación"
        verbose_name_plural = "Tipos de ubicación"

        permissions = [
            ("sys_view_tipoubicacion", "System: Puede ver Tipos de Ubicación"),
            ("sys_add_tipoubicacion", "System: Puede agregar Tipos de Ubicación"),
            ("sys_change_tipoubicacion", "System: Puede cambiar Tipos de Ubicación"),
            ("sys_delete_tipoubicacion", "System: Puede eliminar Tipos de Ubicación"),
        ]

    def __str__(self):
        return self.nombre



class Ubicacion(models.Model):
    """
    (Local) Modelo para registrar las ubicaciones/secciones dentro de una estación. Cada estación puede tener múltiples ubicaciones.
    Una ubicación puede ser una bodega, un vehículo, una habitación, etc.
    """

    nombre = models.CharField(verbose_name="Nombre", max_length=128, help_text="Ingrese el nombre de la ubicación")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", blank=True, null=True, help_text="(Opcional) Ingrese una descripción de la ubicación")
    direccion = models.CharField(verbose_name="Dirección (opcional)", max_length=128, blank=True, null=True, help_text="(opcional) Ingrese la dirección en el caso de que la ubicación se encuentre en una dirección distinta a la de la estación (Ejemplo: AV GIRASOL #1234)")
    tipo_ubicacion = models.ForeignKey(TipoUbicacion, on_delete=models.PROTECT, verbose_name="Tipo de sección", help_text="Seleccione el tipo de ubicación")
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación", help_text="Seleccionar estación correspondiente")
    imagen = models.ImageField(verbose_name="Imagen (opcional)", upload_to="temporal/estaciones/secciones/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"

        permissions = [
            ("sys_view_ubicacion", "System: Puede ver Ubicaciones"),
            ("sys_add_ubicacion", "System: Puede agregar Ubicaciones"),
            ("sys_change_ubicacion", "System: Puede cambiar Ubicaciones"),
            ("sys_delete_ubicacion", "System: Puede eliminar Ubicaciones"),
        ]


    def __str__(self):
        return self.nombre




class Marca(models.Model):
    '''(Global) Modelo para registrar marcas comerciales'''
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre de la marca")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"

        permissions = [
            ("sys_view_marca", "System: Puede ver Marcas"),
            ("sys_add_marca", "System: Puede agregar Marcas"),
            ("sys_change_marca", "System: Puede cambiar Marcas"),
            ("sys_delete_marca", "System: Puede eliminar Marcas"),
        ]

    def __str__(self):
        return self.nombre




class TipoVehiculo(models.Model):
    '''(Global) Modelo para registrar los tipos de vehículo/unidad bomberil'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del tipo de vehículo")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Tipo de vehículo"
        verbose_name_plural = "Tipos de vehículos"

        permissions = [
            ("sys_view_tipovehiculo", "System: Puede ver Tipos de Vehículo"),
            ("sys_add_tipovehiculo", "System: Puede agregar Tipos de Vehículo"),
            ("sys_change_tipovehiculo", "System: Puede cambiar Tipos de Vehículo"),
            ("sys_delete_tipovehiculo", "System: Puede eliminar Tipos de Vehículo"),
        ]

    def __str__(self):
        return self.nombre




class Vehiculo(models.Model):
    '''(Local) Modelo para registrar los vehículos. Los registros tienen relación 1:1 con Seccion. Las secciones de tipo vehículo tendrán sí o sí un registro en este modelo.'''

    patente = models.CharField(verbose_name="Patente (Opcional)", max_length=10, unique=True, blank=True, null=True, help_text="(Opcional) Ingrese la patente del vehículo")
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, verbose_name="Marca (Opcional)", blank=True, null=True, help_text="(Opcional) Ingrese la marca del vehículo")
    modelo = models.CharField(verbose_name="Modelo (Opcional)", max_length=100, blank=True, null=True, help_text="(Opcional) Ingrese el modelo del vehículo")
    chasis = models.CharField(verbose_name="Chasis (Opcional)", max_length=100, unique=True, blank=True, null=True, help_text="(Opcional) Ingrese el número de chasis")
    anho = models.CharField(verbose_name="Año (Opcional)", max_length=4, blank=True, null=True, help_text="(Opcional) Ingrese el año del vehículo")
    tipo_vehiculo = models.ForeignKey(TipoVehiculo, on_delete=models.PROTECT, verbose_name="Tipo de vehículo", help_text="Ingrese el tipo de vehículo")
    # Ubicación/sección correspondiente (1:1)
    ubicacion = models.OneToOneField(Ubicacion, on_delete=models.CASCADE, related_name="detalles_vehiculo", limit_choices_to={'tipo_ubicacion__nombre': 'Vehículo'})

    class Meta:
        permissions = [
            ("sys_view_vehiculo", "System: Puede ver Vehículos"),
            ("sys_add_vehiculo", "System: Puede agregar Vehículos"),
            ("sys_change_vehiculo", "System: Puede cambiar Vehículos"),
            ("sys_delete_vehiculo", "System: Puede eliminar Vehículos"),
        ]

    def __str__(self):
        return self.ubicacion.nombre




class Compartimento(models.Model):
    '''(Local) Modelo para registrar los compartimentos/gavetas de las secciones. Funcionan como sub-secciones.'''

    nombre = models.CharField(verbose_name="Nombre", max_length=50, help_text="Ingrese el nombre del compartimento")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
    imagen = models.ImageField(verbose_name="Imagen (opcional)", upload_to="temporal/estaciones/compartimentos/", blank=True, null=True,help_text="(Opcional) Imagen del compartimento"
    )
    # Ubicación/sección correspondiente
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, verbose_name="Ubicación/sección", help_text="Seleccionar ubicación correspondiente")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Compartimento"
        verbose_name_plural = "Compartimentos"
        ordering = ['ubicacion__nombre', 'nombre']

        permissions = [
            ("sys_view_compartimento", "System: Puede ver Compartimentos"),
            ("sys_add_compartimento", "System: Puede agregar Compartimentos"),
            ("sys_change_compartimento", "System: Puede cambiar Compartimentos"),
            ("sys_delete_compartimento", "System: Puede eliminar Compartimentos"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.ubicacion.nombre})"




# INVENTARIO
class Proveedor(models.Model):
    '''(Global) Modelo para registrar proveedores de existencias. Los proveedores son los que entregan/prestan/donan equipos para que las compañías los usen'''

    nombre = models.CharField(verbose_name="Nombre", max_length=50, help_text="Ingrese el nombre del proveedor")
    rut = models.CharField(verbose_name="Rol Único Tributario (RUT)", max_length=10, help_text="Ingrese el rut de la compañía")
    giro_comercial = models.CharField(verbose_name="Giro", max_length=100, null=True, blank=True, help_text="(Opcional) Ingrese el giro comercial del proveedor")
    contacto_principal = models.OneToOneField(
        'ContactoProveedor', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='+', # '+' evita crear una relación inversa innecesaria
        verbose_name="Contacto Principal"
    )
    estacion_creadora = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación Origen")
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre']

        permissions = [
            ("sys_view_proveedor", "System: Puede ver Proveedores"),
            ("sys_add_proveedor", "System: Puede agregar Proveedores"),
            ("sys_change_proveedor", "System: Puede cambiar Proveedores"),
            ("sys_delete_proveedor", "System: Puede eliminar Proveedores"),
        ]

    def __str__(self):
        return self.nombre




class ContactoProveedor(models.Model):
    '''(Global) Modelo para registrar contactos específicos (personas, sucursales) de un Proveedor.'''
    proveedor = models.ForeignKey(
        Proveedor, 
        on_delete=models.CASCADE, 
        related_name="contactos", 
        verbose_name="Proveedor"
    )
    nombre_contacto = models.CharField(
        verbose_name="Nombre Sucursal/Contacto", 
        max_length=100, 
        help_text="Ej: 'Sucursal Iquique', 'Juan Pérez (Ventas)'"
    )
    direccion = models.CharField(verbose_name="Dirección", max_length=150, blank=True, null=True)
    comuna = models.ForeignKey(Comuna, on_delete=models.PROTECT, verbose_name="Comuna", null=True, blank=True)
    telefono = models.CharField(verbose_name="Teléfono", max_length=20, blank=True, null=True)
    email = models.EmailField(verbose_name="Email", max_length=100, blank=True, null=True)
    notas = models.TextField(verbose_name="Notas Adicionales", blank=True, null=True)
    
    # Campo opcional para indicar si este contacto es específico de una estación
    # Si es NULL, es un contacto general para todas las estaciones.
    estacion_especifica = models.ForeignKey(
        Estacion, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Específico para Estación",
        help_text="Si este contacto es solo relevante para una estación en particular."
    )

    class Meta:
        verbose_name = "Contacto de Proveedor"
        verbose_name_plural = "Contactos de Proveedor"
        ordering = ['proveedor', 'nombre_contacto']

        permissions = [
            ("sys_view_contactoproveedor", "System: Puede ver Contactos de Proveedor"),
            ("sys_add_contactoproveedor", "System: Puede agregar Contactos de Proveedor"),
            ("sys_change_contactoproveedor", "System: Puede cambiar Contactos de Proveedor"),
            ("sys_delete_contactoproveedor", "System: Puede eliminar Contactos de Proveedor"),
        ]

    def __str__(self):
        return f"{self.nombre_contacto} ({self.proveedor.nombre})"




class Categoria(models.Model):
    '''(Global) Modelo para registrar las categorías de insumos disponibles'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre de la categoría")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
    codigo = models.CharField(verbose_name="Código (opcional)", max_length=20, unique=True, help_text="Ingrese un código corto para la categoría (Ejemplo: 'EPP' para Equipos de Protección Personal)")

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

        permissions = [
            ("sys_view_categoria", "System: Puede ver Categorías"),
            ("sys_add_categoria", "System: Puede agregar Categorías"),
            ("sys_change_categoria", "System: Puede cambiar Categorías"),
            ("sys_delete_categoria", "System: Puede eliminar Categorías"),
        ]

    def __str__(self):
        return self.nombre




class ProductoGlobal(models.Model):
    """
    CATÁLOGO MAESTRO GLOBAL. Define un producto de forma universal, sin pertenecer a ninguna compañía.
    Es gestionado de forma colaborativa: la primera compañía que necesita un producto lo crea.
    Un administrador puede luego "curar" o "fusionar" duplicados.
    """
    nombre_oficial = models.CharField(max_length=255, help_text="Nombre estandarizado del producto. Ej: 'Equipo de Respiración Autónoma SCBA'")
    descripcion_general = models.TextField(blank=True, null=True, help_text="Descripción general del producto, sus usos y características.")
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, help_text="Seleccione la marca del producto", null=True, blank=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    gtin = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="GTIN/EAN/UPC del fabricante, si aplica.")
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, help_text="Seleccione la categoría a la que corresponde el producto")
    vida_util_recomendada_anos = models.PositiveIntegerField(verbose_name="Vida útil recomendada (años)", null=True, blank=True, help_text="Vida útil en años según el fabricante (para equipos).")
    imagen = models.ImageField(verbose_name="Imagen (opcional)", upload_to="temporal/estaciones/productos/", blank=True, null=True)
    imagen_thumb_medium = models.ImageField(verbose_name="Thumbnail (100x100)", upload_to="productos_globales/medium/", blank=True, null=True,editable=False)
    imagen_thumb_small = models.ImageField(verbose_name="Thumbnail (40x40)",upload_to="productos_globales/small/", blank=True, null=True,editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto Global"
        verbose_name_plural = "Productos Globales"

        constraints = [
            # Restricción 1: La combinación de marca y modelo debe ser única si AMBOS existen.
            models.UniqueConstraint(
                fields=['marca', 'modelo'], 
                name='unique_marca_modelo_cuando_no_nulos'
            ),
            # Restricción 2: El nombre_oficial debe ser único si la marca ES NULA.
            models.UniqueConstraint(
                fields=['nombre_oficial'], 
                condition=models.Q(marca__isnull=True), 
                name='unique_nombre_oficial_para_genericos'
            )
        ]

        permissions = [
            ("sys_view_productoglobal", "System: Puede ver Productos Globales"),
            ("sys_add_productoglobal", "System: Puede agregar Productos Globales"),
            ("sys_change_productoglobal", "System: Puede cambiar Productos Globales"),
            ("sys_delete_productoglobal", "System: Puede eliminar Productos Globales"),
        ]

    def clean(self):
        """Añade validaciones a nivel de modelo para asegurar la lógica."""
        super().clean()
        # Si es un producto de marca, el modelo no puede estar vacío.
        if self.marca and not self.modelo:
            raise ValidationError("Si se especifica una marca, el modelo es obligatorio.")
        # Si es un producto genérico, la marca y el modelo deben estar vacíos.
        if not self.marca and self.modelo:
            raise ValidationError("No se puede especificar un modelo sin una marca.")

    def __str__(self):
        return f"{self.marca} {self.modelo}"




class Producto(models.Model):
    """
    CATÁLOGO LOCAL. La gestión interna que cada compañía hace de un ProductoGlobal.
    Aquí se definen SKUs, costos y si es un activo serializado o un insumo.
    """

    producto_global = models.ForeignKey(ProductoGlobal, on_delete=models.PROTECT, related_name="variantes_locales")
    sku = models.CharField(max_length=50, help_text="SKU o código interno de la compañía para este producto.", null=True, blank=True)
    es_serializado = models.BooleanField(default=False, help_text="Marcar si este producto es un Activo que requiere seguimiento individual.")
    proveedor_preferido = models.ForeignKey(Proveedor, on_delete=models.PROTECT, verbose_name="Proveedor preferido", help_text="Seleccione el proveedor preferido para este producto", null=True, blank=True)
    costo_compra = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación Origen")
    vida_util_estacion_anos = models.PositiveIntegerField(verbose_name="Vida Útil (Años)", null=True, blank=True, help_text="Regla de la estación. Si se deja en blanco, se usará la recomendación global.")
    es_expirable = models.BooleanField(verbose_name="¿Es expirable?", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto de Compañía"
        verbose_name_plural = "Productos de Compañía"
        # Restricciones para mantener la integridad de los datos
        unique_together = [('estacion', 'producto_global'), ('estacion', 'sku')]

        permissions = [
            ("sys_view_producto", "System: Puede ver Productos Locales"),
            ("sys_add_producto", "System: Puede agregar Productos Locales"),
            ("sys_change_producto", "System: Puede cambiar Productos Locales"),
            ("sys_delete_producto", "System: Puede eliminar Productos Locales"),
        ]

    def __str__(self):
        return f"{self.producto_global.nombre_oficial} ({self.estacion.nombre})"
    
    @property
    def vida_util_efectiva(self):
        """
        Propiedad simple que devuelve la regla local si existe, 
        o la regla global como fallback.
        """
        if self.vida_util_estacion_anos is not None:
            return self.vida_util_estacion_anos
        return self.producto_global.vida_util_recomendada_anos




class Activo(models.Model):
    """
    Representa un objeto físico, único y rastreable (un Activo Serializado).
    Cada fila es un equipo con su propio historial.
    """

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, verbose_name="Producto")
    codigo_activo = models.CharField(verbose_name="Código de Activo (ID Interno)", max_length=50, blank=True, help_text="ID Interno único generado por el sistema (Ej: ACT-00123)")
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación", help_text="Seleccionar estación propietaria de la existencia")
    numero_serie_fabricante = models.CharField(max_length=100, blank=True)

    horas_uso_totales = models.DecimalField(max_digits=7, decimal_places=2, default=0.00, verbose_name="Horas de Uso Totales", help_text="Total acumulado de horas de uso del activo.")
    notas_adicionales = models.TextField(verbose_name="(opcional) Notas adicionales", blank=True, null=True)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, verbose_name="Estado de la existencia/lote", null=True, blank=True)
    compartimento = models.ForeignKey(Compartimento, on_delete=models.PROTECT, verbose_name="Compartimento", help_text="Seleccionar compartimento donde se encuentra la existencia")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, verbose_name="Proveedor")
    asignado_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True) # Asumiendo que Bombero es el usuario
    fecha_fabricacion = models.DateField(verbose_name="Fecha de fabricación", null=True, blank=True)
    fecha_recepcion = models.DateField(verbose_name="Fecha de Recepción", null=True, blank=True, db_index=True)
    fecha_expiracion = models.DateField(verbose_name="Fecha de expiración", null=True, blank=True, help_text="Usar solo para activos que tienen una fecha de caducidad específica.")
    fin_vida_util_calculada = models.DateField(verbose_name="Fin de Vida Útil (Calculada)", null=True, blank=True, db_index=True,editable=False)  # Se calcula siempre en save()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    @property
    def fin_vida_util(self):
        """
        Devuelve la fecha de vencimiento más próxima.
        Prioridad 1: Expiración (si la tiene, ej: un químico).
        Prioridad 2: Fin de vida útil calculado (ej: un casco).
        """
        if self.fecha_expiracion:
            return self.fecha_expiracion
        return self.fin_vida_util_calculada
    

    def _calcular_fin_vida_util(self):
        """
        Lógica interna para calcular y establecer la fecha de fin de vida útil.
        LEE LA REGLA LOCAL PRIMERO.
        """
        self.fin_vida_util_calculada = None
        
        # 1. Obtener la regla de vida útil (Local > Global)
        vida_util_anos = self.producto.vida_util_efectiva
        
        if not vida_util_anos:
            return # El producto (ni local ni global) no tiene vida útil

        # 2. La vida útil cuenta desde la fabricación (prioridad) o la recepción.
        fecha_inicio = self.fecha_fabricacion or self.fecha_recepcion
        if not fecha_inicio:
            return # No hay fecha de inicio para calcular

        # 3. Calcular y guardar
        self.fin_vida_util_calculada = fecha_inicio + relativedelta(years=vida_util_anos)
    

    class Meta:
        verbose_name = "Activo"
        verbose_name_plural = "Activos"
        unique_together = ('estacion', 'codigo_activo')

        permissions = [
            ("sys_view_activo", "System: Puede ver Activos"),
            ("sys_add_activo", "System: Puede agregar Activos"),
            ("sys_change_activo", "System: Puede cambiar Activos"),
            ("sys_delete_activo", "System: Puede eliminar Activos"),
        ]
    

    def save(self, *args, **kwargs):
        if self.producto.estacion != self.estacion:
            raise ValueError("El producto de un activo debe pertenecer a la misma compañía.")

        # ... (validación existente) ...
        if not self.codigo_activo and not self.pk and self.estacion: 
            # Construye el prefijo usando 'E' y el ID de la estación
            prefix = f"E{self.estacion.id}-ACT-" # Ej: "E1-ACT-", "E2-ACT-"

            last_activo = Activo.objects.filter(
                estacion=self.estacion, 
                codigo_activo__startswith=prefix 
            ).order_by('codigo_activo').last() 
            
            next_num = 1
            if last_activo and last_activo.codigo_activo:
                try:
                    last_num_str = last_activo.codigo_activo.split(prefix)[-1]
                    next_num = int(last_num_str) + 1
                except (IndexError, ValueError):
                    pass 

            self.codigo_activo = f"{prefix}{next_num:05d}" # Ej: "E1-ACT-00001"
            
            while Activo.objects.filter(estacion=self.estacion, codigo_activo=self.codigo_activo).exists():
                 next_num += 1
                 self.codigo_activo = f"{prefix}{next_num:05d}"
        
        # Recalcula el fin de vida útil antes de guardar
        self._calcular_fin_vida_util()
            
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.producto.producto_global.nombre_oficial} ({self.codigo_activo})"




class RegistroUsoActivo(models.Model):
    """
    Bitácora de cada uso que se le da a un activo, registrando las horas.
    """
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE, related_name="registros_uso", verbose_name="Activo Utilizado")
    usuario_registra = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario que registra")
    fecha_uso = models.DateTimeField(verbose_name="Fecha y Hora de Uso")
    horas_registradas = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Horas Registradas")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas/Observaciones")
    fecha_creacion_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación del Registro")

    class Meta:
        verbose_name = "Registro de Uso de Activo"
        verbose_name_plural = "Registros de Uso de Activos"
        ordering = ['-fecha_uso']

    def __str__(self):
        return f"Uso de {self.activo} ({self.horas_registradas}h) en {self.fecha_uso.strftime('%Y-%m-%d')}"




class LoteInsumo(models.Model):
    """
    Gestiona el stock de insumos fungibles por lotes, permitiendo
    el seguimiento de fechas de expiración individuales.
    """
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, limit_choices_to={'es_serializado': False})
    codigo_lote = models.CharField(verbose_name="Código de Lote (ID Interno)", max_length=50, unique=True, blank=True, editable=False, help_text="ID Interno único generado por el sistema (Ej: E1-LOT-00001)")
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, verbose_name="Estado del Lote", help_text="Estado actual del lote (Disponible, Anulado, etc.)")
    compartimento = models.ForeignKey(Compartimento, on_delete=models.PROTECT, verbose_name="Compartimento")
    cantidad = models.PositiveIntegerField(default=0)
    fecha_expiracion = models.DateField(verbose_name="Fecha de expiración", null=True, blank=True)
    numero_lote_fabricante = models.CharField(max_length=100, blank=True, null=True, help_text="Número de lote del fabricante para trazabilidad.")
    fecha_recepcion = models.DateField(verbose_name="Fecha de Recepción", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lote de Insumo"
        verbose_name_plural = "Lotes de Insumos"

        permissions = [
            ("sys_view_loteinsumo", "System: Puede ver Lotes de Insumos"),
            ("sys_add_loteinsumo", "System: Puede agregar Lotes de Insumos"),
            ("sys_change_loteinsumo", "System: Puede cambiar Lotes de Insumos"),
            ("sys_delete_loteinsumo", "System: Puede eliminar Lotes de Insumos"),
        ]

    
    def __str__(self):
        exp_date = self.fecha_expiracion.strftime('%Y-%m-%d') if self.fecha_expiracion else "N/A"
        codigo = self.codigo_lote if self.codigo_lote else "SIN CODIGO"
        return f"{self.cantidad} x {self.producto.sku} ({codigo}) | Exp: {exp_date}"
    

    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para generar un 'codigo_lote' único 
        al crear un nuevo lote, similar a como lo hace el modelo Activo.
        """

        # --- LÓGICA DE ESTADO POR DEFECTO ---
        # Si es un objeto nuevo (no tiene pk) Y no se le ha asignado un estado
        if not self.pk and not self.estado_id:
            try:
                # Buscamos 'DISPONIBLE' y lo asignamos
                estado_disponible = Estado.objects.get(nombre='DISPONIBLE')
                self.estado = estado_disponible
            except Estado.DoesNotExist:
                # Fallback por si 'DISPONIBLE' no existe
                # (en un sistema real, aquí se debería loggear un error crítico)
                pass
        
        # Comprueba si es un objeto nuevo (not self.pk) y si el código aún no se ha generado
        if not self.codigo_lote and not self.pk and self.compartimento:
            
            # Obtenemos la estación a través de la relación (Compartimento -> Ubicacion -> Estacion)
            estacion = self.compartimento.ubicacion.estacion
            
            # Construye el prefijo usando 'E' y el ID de la estación
            prefix = f"E{estacion.id}-LOT-" # Ej: "E1-LOT-", "E2-LOT-"

            # Busca el último lote de ESA estación que comience con el prefijo
            last_lote = LoteInsumo.objects.filter(
                compartimento__ubicacion__estacion=estacion, 
                codigo_lote__startswith=prefix
            ).order_by('codigo_lote').last()
            
            next_num = 1
            if last_lote and last_lote.codigo_lote:
                try:
                    # Intenta extraer el número del último código
                    last_num_str = last_lote.codigo_lote.split(prefix)[-1]
                    next_num = int(last_num_str) + 1
                except (IndexError, ValueError):
                    # Si falla (ej. código malformado), simplemente usa 1
                    pass 

            # Asigna el nuevo código formateado (ej: "E1-LOT-00001")
            self.codigo_lote = f"{prefix}{next_num:05d}"
            
            # Bucle de seguridad: verifica que el código sea realmente único
            # (En caso de concurrencia o un ID borrado)
            while LoteInsumo.objects.filter(
                compartimento__ubicacion__estacion=estacion, 
                codigo_lote=self.codigo_lote
            ).exists():
                 next_num += 1
                 self.codigo_lote = f"{prefix}{next_num:05d}"
            
        # Llama al método save() original para guardar el objeto
        super().save(*args, **kwargs)




class Destinatario(models.Model):
    """
    (Local) Registra a quién se le prestan existencias.
    Local a la estación, como acordamos.
    """
    estacion = models.ForeignKey(Estacion, on_delete=models.CASCADE, related_name='destinatarios')
    nombre_entidad = models.CharField(max_length=255, verbose_name="Nombre Entidad (Ej: Clínica XYZ)")
    rut_entidad = models.CharField(max_length=12, blank=True, null=True, verbose_name="RUT Entidad (Opcional)")
    nombre_contacto = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nombre Contacto (Opcional)")
    telefono_contacto = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono Contacto (Opcional)")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='destinatarios_creados')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Destinatario de Préstamo"
        verbose_name_plural = "Destinatarios de Préstamos"
        ordering = ['nombre_entidad']
        unique_together = ('estacion', 'nombre_entidad') # Evitar duplicados por estación

        permissions = [
            ("sys_view_destinatario", "System: Puede ver Destinatarios"),
            ("sys_add_destinatario", "System: Puede agregar Destinatarios"),
            ("sys_change_destinatario", "System: Puede cambiar Destinatarios"),
            ("sys_delete_destinatario", "System: Puede eliminar Destinatarios"),
        ]

    def __str__(self):
        return self.nombre_entidad




class Prestamo(models.Model):
    """
    (Local) Encabezado de un préstamo. Agrupa los ítems prestados.
    """
    class EstadoPrestamo(models.TextChoices):
        PENDIENTE = 'PEN', 'Pendiente'
        DEVUELTO_PARCIAL = 'PAR', 'Devuelto Parcialmente'
        COMPLETADO = 'COM', 'Completado'
        VENCIDO = 'VEN', 'Vencido' # (Opcional, se puede calcular)

    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name='prestamos_realizados')
    usuario_responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='prestamos_gestionados')
    destinatario = models.ForeignKey(Destinatario, on_delete=models.PROTECT, related_name='prestamos_recibidos')
    
    fecha_prestamo = models.DateTimeField(default=timezone.now, verbose_name="Fecha del Préstamo")
    fecha_devolucion_esperada = models.DateField(blank=True, null=True, verbose_name="Fecha Devolución Esperada")
    estado = models.CharField(max_length=3, choices=EstadoPrestamo.choices, default=EstadoPrestamo.PENDIENTE)
    notas_prestamo = models.TextField(blank=True, null=True, verbose_name="Notas/Motivo del Préstamo")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Préstamo"
        verbose_name_plural = "Préstamos"
        ordering = ['-fecha_prestamo']

        permissions = [
            ("sys_view_prestamo", "System: Puede ver Préstamos"),
            ("sys_add_prestamo", "System: Puede agregar Préstamos"),
            ("sys_change_prestamo", "System: Puede cambiar Préstamos"),
            ("sys_delete_prestamo", "System: Puede eliminar Préstamos"),
        ]

    def __str__(self):
        return f"Préstamo a {self.destinatario.nombre_entidad} ({self.get_estado_display()})"




class PrestamoDetalle(models.Model):
    """
    (Local) Ítem específico (Activo o Lote) incluido en un préstamo.
    """
    prestamo = models.ForeignKey(Prestamo, on_delete=models.CASCADE, related_name="items_prestados")
    
    # Uno de estos dos debe estar lleno
    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, null=True, blank=True, related_name='prestamos')
    lote = models.ForeignKey(LoteInsumo, on_delete=models.PROTECT, null=True, blank=True, related_name='prestamos')
    
    # Descripción/SKU en el momento del préstamo (para histórico)
    descripcion_item = models.CharField(max_length=255, blank=True)
    codigo_item = models.CharField(max_length=50, blank=True) # E1-ACT-123 o E1-LOT-456
    
    cantidad_prestada = models.PositiveIntegerField(default=1)
    cantidad_devuelta = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Detalle de Préstamo"
        verbose_name_plural = "Detalles de Préstamos"

        permissions = [
            ("sys_view_prestamodetalle", "System: Puede ver Detalles de Préstamo"),
            ("sys_add_prestamodetalle", "System: Puede agregar Detalles de Préstamo"),
            ("sys_change_prestamodetalle", "System: Puede cambiar Detalles de Préstamo"),
            ("sys_delete_prestamodetalle", "System: Puede eliminar Detalles de Préstamo"),
        ]

    def clean(self):
        if not self.activo and not self.lote:
            raise ValidationError("El detalle debe estar asociado a un Activo o a un Lote.")
        if self.activo and self.lote:
            raise ValidationError("El detalle no puede estar asociado a un Activo y a un Lote simultáneamente.")
        if self.activo and self.cantidad_prestada > 1:
            raise ValidationError("La cantidad para un Activo serializado solo puede ser 1.")

    def save(self, *args, **kwargs):
        # Guardar una "foto" del ítem para la historia
        if self.activo:
            self.descripcion_item = self.activo.producto.producto_global.nombre_oficial
            self.codigo_item = self.activo.codigo_activo
            self.cantidad_prestada = 1 # Forzar cantidad 1 para activos
        elif self.lote:
            self.descripcion_item = self.lote.producto.producto_global.nombre_oficial
            self.codigo_item = self.lote.codigo_lote
        super().save(*args, **kwargs)




class TipoMovimiento(models.TextChoices):
    ENTRADA = 'ENT', 'Entrada'
    SALIDA = 'SAL', 'Salida'
    TRANSFERENCIA_INTERNA = 'TRA', 'Transferencia'
    AJUSTE = 'AJU', 'Ajuste'
    TRASLADO = 'TRAS', 'Traslado'
    PRESTAMO = 'PRE', 'Préstamo Externo'
    DEVOLUCION = 'DEV', 'Devolución de Préstamo'

class MovimientoInventario(models.Model):
    """
    Registra todos los cambios en el inventario (entradas, salidas, transferencias, ajustes).
    """
    tipo_movimiento = models.CharField(max_length=4, choices=TipoMovimiento.choices)
    fecha_hora = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='movimientos_inventario')
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT) # Estación donde ocurrió

    # Campos específicos para cada tipo de movimiento (pueden ser Null)
    proveedor_origen = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='recepciones')
    compartimento_origen = models.ForeignKey(Compartimento, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_salida')
    compartimento_destino = models.ForeignKey(Compartimento, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_entrada')
    
    # Referencia al Activo o Lote afectado (Uno de estos debe estar presente)
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE, null=True, blank=True, related_name='movimientos')
    lote_insumo = models.ForeignKey(LoteInsumo, on_delete=models.CASCADE, null=True, blank=True, related_name='movimientos')
    
    cantidad_movida = models.IntegerField(help_text="Positivo para entradas/ajustes+, Negativo para salidas/ajustes-")
    
    notas = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-fecha_hora']

        permissions = [
            ("sys_view_movimientoinventario", "System: Puede ver Movimientos de Inventario"),
        ]

    def __str__(self):
        item_str = f"Activo ID {self.activo.id}" if self.activo else f"Lote ID {self.lote_insumo.id}" if self.lote_insumo else "Item Desconocido"
        return f"{self.get_tipo_movimiento_display()} de {self.cantidad_movida} ({item_str}) el {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"

    def clean(self):
        if self.tipo_movimiento == TipoMovimiento.ENTRADA and not self.proveedor_origen:
             raise ValidationError("Las entradas deben especificar un proveedor de origen.")
        if self.tipo_movimiento == TipoMovimiento.TRANSFERENCIA_INTERNA and (not self.compartimento_origen or not self.compartimento_destino):
             raise ValidationError("Las transferencias deben especificar origen y destino.")
        if not self.activo and not self.lote_insumo:
            raise ValidationError("El movimiento debe estar asociado a un Activo o a un Lote de Insumo.")
        if self.activo and self.lote_insumo:
            raise ValidationError("El movimiento no puede estar asociado a un Activo Y a un Lote de Insumo simultáneamente.")