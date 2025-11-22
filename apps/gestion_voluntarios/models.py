import uuid
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

        default_permissions = []
        permissions = [
            ("sys_view_nacionalidad", "System: Puede ver Nacionalidades"),
            ("sys_add_nacionalidad", "System: Puede agregar Nacionalidades"),
            ("sys_change_nacionalidad", "System: Puede cambiar Nacionalidades"),
            ("sys_delete_nacionalidad", "System: Puede eliminar Nacionalidades"),
        ]

    def __str__(self):
        return self.gentilicio




class Profesion(models.Model):
    """(Global) Modelo para registrar profesiones/oficios civiles de los voluntarios"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100, help_text="Nombre de la profesión u oficio")

    class Meta:
        verbose_name = "Profesión"
        verbose_name_plural = "Profesiones"
        ordering = ['nombre']

        default_permissions = []
        permissions = [
            ("sys_view_profesion", "System: Puede ver Profesiones"),
            ("sys_add_profesion", "System: Puede agregar Profesiones"),
            ("sys_change_profesion", "System: Puede cambiar Profesiones"),
            ("sys_delete_profesion", "System: Puede eliminar Profesiones"),
        ]

    def __str__(self):
        return self.nombre




class TipoCargo(models.Model):
    """(Global) Categoría de un cargo, ej: 'Operativo', 'Administrativo', 'Honorario'"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        default_permissions = []
        permissions = [
            ("sys_view_tipocargo", "System: Puede ver Tipos de Cargo"),
            ("sys_add_tipocargo", "System: Puede agregar Tipos de Cargo"),
            ("sys_change_tipocargo", "System: Puede cambiar Tipos de Cargo"),
            ("sys_delete_tipocargo", "System: Puede eliminar Tipos de Cargo"),
        ]
    
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

        default_permissions = []
        permissions = [
            ("sys_view_cargo", "System: Puede ver Cargos / Rangos"),
            ("sys_add_cargo", "System: Puede agregar Cargos / Rangos"),
            ("sys_change_cargo", "System: Puede cambiar Cargos / Rangos"),
            ("sys_delete_cargo", "System: Puede eliminar Cargos / Rangos"),
        ]

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

        default_permissions = []
        permissions = [
            ("sys_view_tiporeconocimiento", "System: Puede ver Tipos de Reconocimientos"),
            ("sys_add_tiporeconocimiento", "System: Puede agregar Tipos de Reconocimientos"),
            ("sys_change_tiporeconocimiento", "System: Puede cambiar Tipos de Reconocimientos"),
            ("sys_delete_tiporeconocimiento", "System: Puede eliminar Tipos de Reconocimientos"),
        ]

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
        primary_key=True,
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
    imagen_thumb_medium = models.ImageField(verbose_name="Thumbnail (600x600)", upload_to="voluntarios/imagen/medium/", blank=True, null=True,editable=False)
    imagen_thumb_small = models.ImageField(verbose_name="Thumbnail (50x50)",upload_to="voluntarios/imagen/small/", blank=True, null=True,editable=False)
    
    fecha_creacion = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Voluntario"
        verbose_name_plural = "Voluntarios"

        default_permissions = []
        permissions = [
            ("sys_view_voluntario", "System: Puede ver Voluntarios"),
            ("sys_add_voluntario", "System: Puede agregar Voluntarios"),
            ("sys_change_voluntario", "System: Puede cambiar Voluntarios"),
            ("sys_delete_voluntario", "System: Puede eliminar Voluntarios"),
        ]

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

        default_permissions = []
        permissions = [
            ("sys_view_historialpertenencia", "System: Puede ver Historial de Pertenencia"),
            ("sys_add_historialpertenencia", "System: Puede agregar Historial de Pertenencia"),
            ("sys_change_historialpertenencia", "System: Puede cambiar Historial de Pertenencia"),
            ("sys_delete_historialpertenencia", "System: Puede eliminar Historial de Pertenencia"),
        ]




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

        default_permissions = []
        permissions = [
            ("sys_view_historialcargo", "System: Puede ver Historial de Cargos"),
            ("sys_add_historialcargo", "System: Puede agregar Historial de Cargos"),
            ("sys_change_historialcargo", "System: Puede cambiar Historial de Cargos"),
            ("sys_delete_historialcargo", "System: Puede eliminar Historial de Cargos"),
        ]




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

        default_permissions = []
        permissions = [
            ("sys_view_historialreconocimiento", "System: Puede ver Historial de Reconocimientos"),
            ("sys_add_historialreconocimiento", "System: Puede agregar Historial de Reconocimientos"),
            ("sys_change_historialreconocimiento", "System: Puede cambiar Historial de Reconocimientos"),
            ("sys_delete_historialreconocimiento", "System: Puede eliminar Historial de Reconocimientos"),
        ]




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

        default_permissions = []
        permissions = [
            ("sys_view_historialsancion", "System: Puede ver Historial de Sanciones"),
            ("sys_add_historialsancion", "System: Puede agregar Historial de Sanciones"),
            ("sys_change_historialsancion", "System: Puede cambiar Historial de Sanciones"),
            ("sys_delete_historialsancion", "System: Puede eliminar Historial de Sanciones"),
        ]




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

        default_permissions = []
        permissions = [
            ("sys_view_historialcurso", "System: Puede ver Historial de Cursos"),
            ("sys_add_historialcurso", "System: Puede agregar Historial de Cursos"),
            ("sys_change_historialcurso", "System: Puede cambiar Historial de Cursos"),
            ("sys_delete_historialcurso", "System: Puede eliminar Historial de Cursos"),
        ]




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

        default_permissions = []
        permissions = [
            ("sys_view_anotacionhojavida", "System: Puede ver Anotaciones en Hoja de Vida"),
            ("sys_add_anotacionhojavida", "System: Puede agregar Anotaciones en Hoja de Vida"),
            ("sys_change_anotacionhojavida", "System: Puede cambiar Anotaciones en Hoja de Vida"),
            ("sys_delete_anotacionhojavida", "System: Puede eliminar Anotaciones en Hoja de Vida"),
        ]