from django.db import models
from django.utils import timezone
from django.conf import settings
from apps.gestion_inventario.models import Comuna, Estacion


# ==============================================================================
# 1. TABLAS DE BÚSQUEDA (GLOBALES)
# ==============================================================================
# Estos modelos definen las *opciones* que se pueden seleccionar.
# Son globales para todo el sistema.
class Nacionalidad(models.Model):
    '''(Global) Modelo para registrar nacionalidades para voluntarios'''

    pais = models.CharField(verbose_name="País/Nación", unique=True, max_length=100)
    gentilicio = models.CharField(verbose_name="Gentilicio", max_length=100, help_text="Ingrese el gentilicio")
    iso_nac = models.CharField(max_length=10)

    class Meta:
        verbose_name = "Nacionalidad"
        verbose_name_plural = "Nacionalidades"

    def __str__(self):
        return self.gentilicio




class Profesion(models.Model):
    """(Global) Modelo para registrar profesiones/oficios civiles de los voluntarios"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100, help_text="Nombre de la profesión u oficio")

    class Meta:
        verbose_name = "Profesión"
        verbose_name_plural = "Profesiones"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre




class TipoCargo(models.Model):
    """(Global) Categoría de un cargo, ej: 'Operativo', 'Administrativo', 'Honorario'"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)
    
    def __str__(self):
        return self.nombre




class Cargo(models.Model):
    """
    (Global) Catálogo de todos los cargos y rangos posibles
    Ej: 'Voluntario', 'Teniente', 'Capitán', 'Superintendente', 'Presidente Regional'
    """
    tipo_cargo = models.ForeignKey(TipoCargo, on_delete=models.SET_NULL, null=True, blank=True, related_name="cargos")
    nombre = models.CharField(verbose_name="Nombre del Cargo/Rango", unique=True, max_length=100)
    
    class Meta:
        verbose_name = "Cargo / Rango"
        verbose_name_plural = "Cargos / Rangos"
        ordering = ['tipo_cargo', 'nombre']

    def __str__(self):
        return self.nombre




class TipoReconocimiento(models.Model):
    """
    (Global) Catálogo de premios y distinciones
    Ej: 'Premio por 5 Años', 'Premio de Asistencia', 'Voluntario Insigne'
    """
    nombre = models.CharField(verbose_name="Nombre del Reconocimiento", unique=True, max_length=150)
    
    class Meta:
        verbose_name = "Tipo de Reconocimiento"
        verbose_name_plural = "Tipos de Reconocimientos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre




# ==============================================================================
# 2. MODELO DE ENTIDAD / PERFIL (GLOBAL)
# ==============================================================================
# Este es el "Contenedor" 1-a-1 con el Usuario. 
# Guarda solo información global y de identidad del voluntario.
class Voluntario(models.Model):
    """
    El perfil global del Voluntario. Contiene solo información personal
    y no-histórica. Se crea 1-a-1 con un Usuario del sistema.
    """
    # El enlace 1-a-1 al usuario (autenticación)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil_voluntario"
    )
    
    # --- Datos Personales ---
    nacionalidad = models.ForeignKey(
        Nacionalidad, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        verbose_name="Nacionalidad"
    )
    profesion = models.ForeignKey(
        Profesion, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        verbose_name="Profesión Civil"
    )
    lugar_nacimiento = models.CharField(verbose_name="Lugar de Nacimiento", max_length=100, null=True, blank=True)
    fecha_nacimiento = models.DateField(verbose_name="Fecha de Nacimiento", null=True, blank=True)
    
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('O', 'Otro'),
        ('P', 'Prefiero no decirlo'),
    ]
    genero = models.CharField(
        max_length=1, 
        choices=GENERO_CHOICES, 
        verbose_name="Género", 
        null=True, blank=True
    )

    ESTADO_CIVIL_CHOICES = [
        ('SOL', 'Soltero(a)'),
        ('CAS', 'Casado(a)'),
        ('CON', 'Conviviente'),
        ('DIV', 'Divorciado(a)'),
        ('VIU', 'Viudo(a)'),
    ]
    estado_civil = models.CharField(
        max_length=3, 
        choices=ESTADO_CIVIL_CHOICES, 
        verbose_name="Estado Civil", 
        null=True, blank=True
    )
    
    domicilio_comuna = models.ForeignKey(Comuna, on_delete=models.SET_NULL, null=True, blank=True)
    domicilio_calle = models.CharField(max_length=255, null=True, blank=True)
    domicilio_numero = models.CharField(max_length=20, null=True, blank=True)

    # --- Datos Bomberiles Globales ---
    fecha_primer_ingreso = models.DateField(
        verbose_name="Fecha de Primer Ingreso al Servicio",
        null=True, blank=True,
        help_text="Fecha de ingreso a su primera estación (para calcular antigüedad total)"
    )
    numero_registro_bomberil = models.CharField(
        verbose_name="N° Registro General de Bomberos", 
        max_length=50, null=True, blank=True, unique=True
    )
    imagen = models.ImageField(upload_to="voluntarios/imagen/main/", null=True, blank=True)
    
    fecha_creacion = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Voluntario"
        verbose_name_plural = "Voluntarios"

    def __str__(self):
        return self.usuario.get_full_name or self.usuario.rut




# ==============================================================================
# 3. MODELOS DE TRAYECTORIA / BITÁCORA (EVENTOS)
# ==============================================================================
# Esta es la "Hoja de Vida" dinámica. Cada modelo representa un evento
# en la historia del voluntario, "firmado" por una estación.
class HistorialPertenencia(models.Model):
    """
    Registra el ingreso, reincorporación o renuncia a una Compañía/Estación.
    """
    voluntario = models.ForeignKey(Voluntario, on_delete=models.CASCADE, related_name="historial_pertenencia")
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name="voluntarios_historicos")

    # La 'estacion_registra' y 'es_historico' de nuestra discusión
    estacion_registra = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name="registros_pertenencia")
    es_historico = models.BooleanField(default=False, help_text="Marcar si es un registro antiguo (backfill)")

    TIPO_EVENTO = [
        ('ingreso', 'Ingreso'),
        ('renuncia', 'Renuncia'),
        ('reincorporacion', 'Reincorporación'),
        ('traslado', 'Traslado'),
    ]
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO)
    fecha_evento = models.DateField(verbose_name="Fecha del Evento")
    descripcion_adicional = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Evento de Pertenencia"
        verbose_name_plural = "Historial de Pertenencia"
        ordering = ['-fecha_evento']




class HistorialCargo(models.Model):
    """
    Registra los cargos y rangos que el voluntario ha ostentado.
    Responde a las Secciones III, IV y V del PDF.
    """
    voluntario = models.ForeignKey(Voluntario, on_delete=models.CASCADE, related_name="historial_cargos")
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name="voluntarios_con_cargo")
    
    # Quién registra, y dónde fue el cargo (ámbito)
    estacion_registra = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name="cargos_registrados")
    ambito = models.CharField(
        max_length=255, 
        help_text="Dónde ejerció el cargo (Ej: 'Compañía', 'Cuerpo de Bomberos Florida', 'Consejo Regional', 'Junta Nacional')"
    )
    es_historico = models.BooleanField(default=False)

    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de Término", null=True, blank=True) # Nulo si es el cargo actual
    
    class Meta:
        verbose_name = "Historial de Cargo"
        verbose_name_plural = "Historial de Cargos"
        ordering = ['-fecha_inicio']




class HistorialReconocimiento(models.Model):
    """
    Registra las distinciones, premios y logros.
    Responde a las Secciones VI y VII del PDF.
    """
    voluntario = models.ForeignKey(Voluntario, on_delete=models.CASCADE, related_name="historial_reconocimientos")
    
    # Puede ser un tipo predefinido (Premio 5 Años) o uno especial
    tipo_reconocimiento = models.ForeignKey(
        TipoReconocimiento, 
        on_delete=models.PROTECT, 
        null=True, blank=True,
        help_text="Seleccione si es un premio estándar (ej: por años de servicio)"
    )
    descripcion_personalizada = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Use este campo si no es un premio estándar (ej: 'Medalla al Valor')"
    )
    
    fecha_evento = models.DateField(verbose_name="Fecha del Reconocimiento")
    
    # Quién registra y quién/dónde se otorga
    estacion_registra = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name="reconocimientos_registrados")
    ambito = models.CharField(
        max_length=255, 
        help_text="Quién otorga el premio (Ej: 'Compañía', 'Cuerpo de Bomberos Florida', 'Junta Nacional')"
    )
    es_historico = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Historial de Reconocimiento"
        verbose_name_plural = "Historial de Reconocimientos"
        ordering = ['-fecha_evento']




class HistorialSancion(models.Model):
    """
    Registra sanciones, suspensiones o amonestaciones.
    (No está en el PDF, pero es fundamental para un sistema real).
    """
    voluntario = models.ForeignKey(Voluntario, on_delete=models.CASCADE, related_name="historial_sanciones")
    
    TIPO_SANCION = [
        ('amonestacion_verbal', 'Amonestación Verbal'),
        ('amonestacion_escrita', 'Amonestación Escrita'),
        ('suspension', 'Suspensión'),
        ('expulsion', 'Expulsión'),
    ]
    tipo_sancion = models.CharField(max_length=30, choices=TIPO_SANCION)
    descripcion = models.TextField(verbose_name="Descripción y Motivo")
    documento_adjunto = models.FileField(upload_to='sanciones/', null=True, blank=True)

    fecha_evento = models.DateField(verbose_name="Fecha de la Sanción")
    fecha_inicio_suspension = models.DateField(null=True, blank=True)
    fecha_fin_suspension = models.DateField(null=True, blank=True)
    
    # Control de quién registra
    estacion_registra = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name="sanciones_registradas")
    estacion_evento = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name="sanciones_emitidas")
    es_historico = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Historial de Sanción"
        verbose_name_plural = "Historial de Sanciones"
        ordering = ['-fecha_evento']




class HistorialCurso(models.Model):
    """Registra cursos y capacitaciones aprobadas por el voluntario"""
    voluntario = models.ForeignKey(Voluntario, on_delete=models.CASCADE, related_name="historial_cursos")
    nombre_curso = models.CharField(max_length=255)
    institucion = models.CharField(max_length=255, help_text="Ej: 'ANB', 'Estación', 'Externo'")
    fecha_curso = models.DateField(verbose_name="Fecha de Aprobación")
    
    estacion_registra = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name="cursos_registrados")
    es_historico = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Historial de Curso"
        verbose_name_plural = "Historial de Cursos"
        ordering = ['-fecha_curso']




class AnotacionHojaVida(models.Model):
    """
    Registro genérico para "Otros Antecedentes" (Sección VIII del PDF).
    Ej: "Participó en la redacción del reglamento X", "Lideró la campaña Y"
    """
    voluntario = models.ForeignKey(Voluntario, on_delete=models.CASCADE, related_name="historial_anotaciones")
    descripcion = models.TextField(verbose_name="Descripción de la anotación")
    fecha_evento = models.DateField(verbose_name="Fecha")

    estacion_registra = models.ForeignKey(Estacion, on_delete=models.PROTECT, related_name="anotaciones_registradas")
    es_historico = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Anotación en Hoja de Vida"
        verbose_name_plural = "Anotaciones en Hoja de Vida"
        ordering = ['-fecha_evento']



#class VoluntarioFormacion(models.Model):
#    '''(Local)'''
#
#
#
#class VoluntarioTelefono(models.Model):
#    '''(Local) Modelo para registrar los números de teléfono de los voluntarios'''
#
#    numero = models.CharField(verbose_name="Número de teléfono", max_length=12)
#    es_primario = models.BooleanField(verbose_name="Es primario")
#    voluntario = models.ForeignKey(Voluntario, on_delete=models.CASCADE)
#
#
#
#class VoluntarioExperiencia(models.Model):
#    '''(Local) Modelo para registrar la experiencia de los voluntarios'''
#
#    cargo = models.ForeignKey(RangoBomberil, on_delete=models.PROTECT)
#    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT)
#    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
#    fecha_fin = models.DateField(verbose_name="Fecha de Término")
#    responsabilidades = models.TextField(blank=True, null=True)
#
#
#
#class Actividad(models.Model):
#    '''(Local) Modelo para registrar las actividades bomberiles realizadas por cada voluntario'''
#
#    class NivelGeografico(models.TextChoices):
#        PROVINCIAL = 'PROVINCIAL', 'Provincial'
#        REGIONAL = 'REGIONAL', 'Regional'
#        NACIONAL = 'NACIONAL', 'Nacional'
#        INTERNACIONAL = 'INTERNACIONAL', 'Internacional'
#
#    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre de la actividad")
#    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
#    nivel_geografico = models.CharField(max_length=20, choices=NivelGeografico.choices)
#    fecha = models.DateField(verbose_name="Fecha de actividad")
#    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, help_text="Estación creadora de la actividad")
#    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación", default=timezone.now, editable=False)
#    fecha_modificacion = models.DateTimeField(verbose_name="Última modificación", default=timezone.now)
#
#
#
#class VoluntarioActividad(models.Model):
#    '''Modelo intermedio para relacionar las actividades bomberiles con los voluntarios. Cada registro aquí indica la participación del voluntario en la actividad.'''
#
#    voluntario = models.ForeignKey(Voluntario, on_delete=models.PROTECT)
#    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE)
#    descripcion = models.TextField(verbose_name="Descripción de las labores realizadas")
#
#
#
#class VoluntarioReconocimiento(models.Model):
#    '''(Local) Modelo para registrar los reconocimientos otorgados a los voluntarios'''
#
#    voluntario = models.ForeignKey(Voluntario, on_delete=models.PROTECT)
#    descripcion = models.TextField(verbose_name="Descripción del reconocimiento")
#    fecha = models.DateField(verbose_name="Fecha del reconocimiento")
#    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, help_text="Estación que registra el reconocimiento")
#    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación", default=timezone.now, editable=False)
#    fecha_modificacion = models.DateTimeField(verbose_name="Última modificación", default=timezone.now)
#
#
#
#class VoluntarioSancion(models.Model):
#    '''(Local) Modelo para registrar las sanciones aplicadas a los voluntarios'''
#
#    voluntario = models.ForeignKey(Voluntario, on_delete=models.PROTECT)
#    descripcion = models.TextField(verbose_name="Descripción de la sanción/motivo")
#    fecha = models.DateField(verbose_name="Fecha de la sanción")
#    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, help_text="Estación que registra la sanción")
#    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación", default=timezone.now, editable=False)
#    fecha_modificacion = models.DateTimeField(verbose_name="Última modificación", default=timezone.now)
#
#
#
#class LogroGeneralBomberil(models.Model):
#    '''(Global) Modelo para registrar logros bomberiles generales'''
#
#    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50, help_text="Ingrese el nombre del logro")
#    descripcion = models.TextField(verbose_name="Descripción (opcional)", null=True, blank=True)
#    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación", default=timezone.now, editable=False)
#    fecha_modificacion = models.DateTimeField(verbose_name="Última modificación", default=timezone.now)
#
#
#
#class VoluntarioLogroGeneralBomberil(models.Model):
#    '''Modelo para relacionar a los logros generales con los voluntarios. Cada registro indica que el voluntario obtuvo el logro'''
#
#    voluntario = models.ForeignKey(Voluntario, on_delete=models.PROTECT)
#    logro = models.ForeignKey(LogroGeneralBomberil, on_delete=models.CASCADE)
#    fecha = models.DateField(verbose_name="Fecha del logro")
#    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación", default=timezone.now, editable=False)
#
#
#
#class VoluntarioLogroEspecialBomberil(models.Model):
#    '''Modelo para registrar logros especiales para voluntarios'''
#
#    voluntario = models.ForeignKey(Voluntario, on_delete=models.PROTECT)
#    descripcion = models.TextField(verbose_name="Descripción del logro especial")
#    fecha = models.DateField(verbose_name="Fecha del logro especial")
#    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT, help_text="Estación que registra el logro especial")
#    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación", default=timezone.now, editable=False)
#    fecha_modificacion = models.DateTimeField(verbose_name="Última modificación", default=timezone.now)