from django.db import models
from django.utils import timezone


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



class TipoSeccion(models.Model):
    '''(Global) Modelo para registrar los tipos de ubicaciones/secciones dentro de una compañía (bodega, habitación, vehículo)'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del tipo de ubicación")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Tipo de ubicación"
        verbose_name_plural = "Tipos de ubicación"

    def __str__(self):
        return self.nombre



class Seccion(models.Model):
    '''(Local) Modelo para registrar las ubicaciones/secciones de la compañía. Las secciones son las diferentes áreas o espacios físicos dentro de una estación de bomberos'''

    nombre = models.CharField(verbose_name="Nombre", max_length=128, help_text="Ingrese el nombre de la sección")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", blank=True, null=True, help_text="(Opcional) Ingrese una descripción de la sección")
    direccion = models.CharField(verbose_name="Dirección (opcional)", max_length=128, blank=True, null=True, help_text="(opcional) Ingrese la dirección en el caso de que la ubicación se encuentre en una dirección distinta a la de la estación (Ejemplo: AV GIRASOL #1234)")
    tipo_seccion = models.ForeignKey(TipoSeccion, on_delete=models.PROTECT, verbose_name="Tipo de sección", help_text="Seleccione el tipo de sección")
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación", help_text="Seleccionar estación correspondiente")
    imagen = models.ImageField(verbose_name="Imagen (opcional)", upload_to="temporal/estaciones/secciones/", blank=True, null=True)
    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación", default=timezone.now, editable=False)
    
    class Meta:
        verbose_name = "Sección"
        verbose_name_plural = "Secciones"

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
    seccion = models.OneToOneField(Seccion, on_delete=models.CASCADE, editable=False)



class Compartimento(models.Model):
    '''(Local) Modelo para registrar los compartimentos/gavetas de las secciones. Funcionan como sub-secciones.'''

    nombre = models.CharField(verbose_name="Nombre", max_length=50, help_text="Ingrese el nombre del compartimento")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
    # Ubicación/sección correspondiente
    seccion = models.ForeignKey(Seccion, on_delete=models.PROTECT, verbose_name="Ubicación/sección", help_text="Seleccionar sección correspondiente")

    class Meta:
        verbose_name = "Compartimento"
        verbose_name_plural = "Compartimentos"

    def __str__(self):
        return self.nombre



# INVENTARIO
class Categoria(models.Model):
    '''(Global) Modelo para registrar las categorías de insumos disponibles'''

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre de la categoría")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def __str__(self):
        return self.nombre



class Catalogo(models.Model):
    '''(Global) Modelo para registrar el catálogo de productos disponible. El catálogo incluye información del producto y no corresponde a existencias en las compañías.'''

    class VidaUtilUnidad(models.TextChoices):
        HORAS = 'HOR', 'Horas'
        DIAS = 'DIA', 'Días'
        SEMANAS = 'SEM', 'Semanas'
        ANHOS = 'ANO', 'Años'
        USOS = 'USO', 'Usos'

    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=255, help_text="Ingrese el nombre del producto")
    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, verbose_name="Marca (Opcional)", blank=True, null=True, help_text="(Opcional) Ingrese la marca del producto")
    modelo = models.CharField(verbose_name="Modelo (Opcional)", max_length=100, blank=True, null=True, help_text="(Opcional) Ingrese el modelo del producto")
    precio=models.IntegerField(verbose_name="(Opcional) Ingrese el valor estimado del equipamento", null=True, blank=True)
    imagen = models.ImageField(verbose_name="Imagen (opcional)", upload_to="temporal/estaciones/productos/", blank=True, null=True)
    vida_util = models.IntegerField(verbose_name="Vida útil", blank=True, null=True, help_text="(Opcional) Ingrese un número entero correspondiente a la vida útil del producto")
    vida_util_unidad = models.CharField(max_length=3, choices=VidaUtilUnidad.choices, blank=True, null=True, help_text="(Opcional) Seleccionar el tipo de unidad de medida para la cifra de vida útil.")
    es_expirable = models.BooleanField(verbose_name="¿Es expirable?", default=0)
    imagen = models.ImageField(verbose_name="Imagen (opcional)", upload_to="temporal/estaciones/productos/", blank=True, null=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, help_text="Seleccione la categoría a la que corresponde el producto")
    estacion_creadora = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación Origen")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self):
        return self.nombre



# Modelo intermedio para relacionar el catálogo con las estaciones. El catálogo es global, pero las estaciones eligen con qué productos quieren trabajar. De esa relación se encarga este modelo
class CatalogoEstacion(models.Model):
    catalogo = models.ForeignKey(Catalogo, on_delete=models.PROTECT)
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT)



class Proveedor(models.Model):
    '''(Global) Modelo para registrar proveedores de existencias. Los proveedores son los que entregan/prestan/donan equipos para que las compañías los usen'''

    nombre = models.CharField(verbose_name="Nombre", max_length=50, help_text="Ingrese el nombre del proveedor")
    rut = models.CharField(verbose_name="Rol Único Tributario (RUT)", max_length=10, help_text="Ingrese el rut de la compañía")
    giro_comercial = models.CharField(verbose_name="Giro", max_length=100, null=True, blank=True, help_text="(Opcional) Ingrese el giro comercial del proveedor")
    direccion = models.CharField(verbose_name="Dirección", null=True, blank=True, max_length=100, help_text="Ingrese la dirección del proveedor")
    email = models.EmailField(max_length=50, null=True, blank=True, verbose_name="Email contacto")
    telefono = models.CharField(max_length=9, null=True, blank=True, verbose_name="Teléfono contacto")
    comuna = models.ForeignKey(Comuna, on_delete=models.PROTECT, verbose_name="Comuna", help_text="Seleccione la comuna correspondiente")
    estacion_creadora = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación Origen")
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def __str__(self):
        return self.nombre



# Modelo intermedio para relacionar los proveedores con las estaciones. Las estaciones eligen con qué proveedores quieren trabajar. De esa relación se encarga este modelo
class ProveedorEstacion(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT)



class Existencia(models.Model):
    '''(Local) Modelo para registrar las existencias dentro de la compañía.'''

    codigo = models.CharField(verbose_name="(opcional) Código de barras", max_length=1, blank=True, null=True, help_text="(Opcional) Ingrese el código de barras de la unidad / lote")
    costo = models.IntegerField(verbose_name="(opcional) Valor monetario", blank=True, null=True, help_text="(opcional) Ingrese el costo monetario de la existencia/lote")
    horas_de_uso = models.IntegerField(verbose_name="(opcional) Horas de uso", null=True, blank=True)
    horas_de_uso_totales = models.IntegerField(verbose_name="(opcional) Horas de uso totales", null=True, blank=True)
    notas_adicionales = models.TextField(verbose_name="(opcional) Notas adicionales", blank=True, null=True)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, verbose_name="Estado de la existencia/lote")
    catalogo = models.ForeignKey(Catalogo, on_delete=models.PROTECT, verbose_name="Producto")
    compartimento = models.ForeignKey(Compartimento, on_delete=models.PROTECT, verbose_name="Compartimento/sub-sección", blank=True, null=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, verbose_name="Proveedor")
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, verbose_name="Estación", help_text="Seleccionar estación propietaria de la existencia")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Existencia"
        verbose_name_plural = "Existencias"



class ExistenciaExpirable(models.Model):
    '''(Local) Modelo para registrar las existencias expirables.'''

    existencia = models.OneToOneField(Existencia, on_delete=models.CASCADE)
    fecha_expiracion = models.DateField(verbose_name="Fecha de expiración")