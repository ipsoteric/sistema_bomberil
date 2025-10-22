from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError


# ESTADOS
class TipoEstado(models.Model):
    '''(Global) Modelo para registrar los tipos de estado'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del tipo de estado")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Tipo de estado"
        verbose_name_plural = "Tipos de estado"

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

    def __str__(self):
        return self.nombre




# LOCACIONES
class Region(models.Model):
    '''(Global) Modelo para registrar las regiones del país'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100, help_text="Ingrese el nombre de la región")

    class Meta:
        verbose_name = "Región de Chile"
        verbose_name_plural = "Regiones de Chile"

    def __str__(self):
        return self.nombre




class Comuna(models.Model):
    '''(Global) Modelo para registrar las comunas del país'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100, help_text="Ingrese el nombre de la comuna")
    region = models.ForeignKey(Region, on_delete=models.PROTECT, verbose_name="Región", help_text="Seleccione la región correspondiente")

    class Meta:
        verbose_name = "Comuna de Chile"
        verbose_name_plural = "Comunas de Chile"

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
    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación", default=timezone.now, editable=False)
    fecha_modificacion = models.DateTimeField(verbose_name="Última modificación", default=timezone.now)

    class Meta:
        verbose_name = "Estación"
        verbose_name_plural = "Estaciones"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre




class TipoUbicacion(models.Model):
    '''(Global) Modelo para registrar los tipos de ubicaciones/secciones dentro de una compañía (bodega, habitación, vehículo)'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del tipo de ubicación")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Tipo de ubicación"
        verbose_name_plural = "Tipos de ubicación"

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


    def __str__(self):
        return self.nombre




class Marca(models.Model):
    '''(Global) Modelo para registrar marcas comerciales'''
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre de la marca")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"

    def __str__(self):
        return self.nombre




class TipoVehiculo(models.Model):
    '''(Global) Modelo para registrar los tipos de vehículo/unidad bomberil'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del tipo de vehículo")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Tipo de vehículo"
        verbose_name_plural = "Tipos de vehículos"

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

    def __str__(self):
        return self.ubicacion.nombre




class Compartimento(models.Model):
    '''(Local) Modelo para registrar los compartimentos/gavetas de las secciones. Funcionan como sub-secciones.'''

    nombre = models.CharField(verbose_name="Nombre", max_length=50, help_text="Ingrese el nombre del compartimento")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
    # Ubicación/sección correspondiente
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, verbose_name="Ubicación/sección", help_text="Seleccionar ubicación correspondiente")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Compartimento"
        verbose_name_plural = "Compartimentos"

    def __str__(self):
        return self.nombre




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
    es_expirable = models.BooleanField(verbose_name="¿Es expirable?", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto de Compañía"
        verbose_name_plural = "Productos de Compañía"
        # Restricciones para mantener la integridad de los datos
        unique_together = [('estacion', 'producto_global'), ('estacion', 'sku')]

    def __str__(self):
        return f"{self.producto_global.nombre_oficial} ({self.estacion.nombre})"




class Activo(models.Model):
    """
    Representa un objeto físico, único y rastreable (un Activo Serializado).
    Cada fila es un equipo con su propio historial.
    """

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, verbose_name="Producto")
    codigo_activo = models.CharField(verbose_name="(opcional) Código de barras", max_length=1, blank=True, null=True, help_text="(Opcional) Ingrese el código de barras de la unidad / lote")
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación", help_text="Seleccionar estación propietaria de la existencia")
    numero_serie_fabricante = models.CharField(max_length=100, blank=True)

    horas_de_uso = models.IntegerField(verbose_name="(opcional) Horas de uso", null=True, blank=True)
    horas_de_uso_totales = models.IntegerField(verbose_name="(opcional) Horas de uso totales", null=True, blank=True)
    notas_adicionales = models.TextField(verbose_name="(opcional) Notas adicionales", blank=True, null=True)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, verbose_name="Estado de la existencia/lote")
    compartimento = models.ForeignKey(Compartimento, on_delete=models.PROTECT, verbose_name="Compartimento", help_text="Seleccionar compartimento donde se encuentra la existencia")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, verbose_name="Proveedor")
    asignado_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True) # Asumiendo que Bombero es el usuario
    fecha_fabricacion = models.DateField(verbose_name="Fecha de fabricación", null=True, blank=True)
    fecha_puesta_en_servicio = models.DateField(verbose_name="Fecha de puesta en servicio", null=True, blank=True)
    fecha_expiracion = models.DateField(verbose_name="Fecha de expiración", null=True, blank=True, help_text="Usar solo para activos que tienen una fecha de caducidad específica.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    @property
    def fin_vida_util(self):
        """Calcula la fecha de fin de vida útil. Lógica de negocio."""
        vida_util_anos = self.producto.producto_global.vida_util_recomendada_anos
        if not vida_util_anos:
            return None
        
        # La vida útil puede contar desde la fabricación o puesta en servicio.
        # Aquí un ejemplo que prioriza la fecha de fabricación.
        fecha_inicio = self.fecha_fabricacion or self.fecha_puesta_en_servicio
        if not fecha_inicio:
            return None
            
        from dateutil.relativedelta import relativedelta
        return fecha_inicio + relativedelta(years=vida_util_anos)
    

    class Meta:
        verbose_name = "Activo"
        verbose_name_plural = "Activos"


    def save(self, *args, **kwargs):
        # Asegura que el producto asignado pertenezca a la misma compañía que el activo
        if self.producto.estacion != self.estacion:
            raise ValueError("El producto de un activo debe pertenecer a la misma compañía.")
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.producto.producto_global.nombre_oficial} ({self.codigo_activo})"




class LoteInsumo(models.Model):
    """
    Gestiona el stock de insumos fungibles por lotes, permitiendo
    el seguimiento de fechas de expiración individuales.
    """
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, limit_choices_to={'es_serializado': False})
    compartimento = models.ForeignKey(Compartimento, on_delete=models.PROTECT, verbose_name="Compartimento")
    cantidad = models.PositiveIntegerField(default=0)
    fecha_expiracion = models.DateField(verbose_name="Fecha de expiración", null=True, blank=True)
    numero_lote_fabricante = models.CharField(max_length=100, blank=True, null=True, help_text="Número de lote del fabricante para trazabilidad.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lote de Insumo"
        verbose_name_plural = "Lotes de Insumos"

    def __str__(self):
        exp_date = self.fecha_expiracion.strftime('%Y-%m-%d') if self.fecha_expiracion else "N/A"
        return f"{self.cantidad} x {self.producto.sku} | Exp: {exp_date}"