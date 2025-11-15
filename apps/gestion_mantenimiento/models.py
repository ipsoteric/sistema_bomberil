from django.db import models
from django.conf import settings
from gestion_inventario.models import Activo


class PlanMantenimiento(models.Model):
    """
    Define la plantilla para un mantenimiento programado.
    Define el "qué" (activos) y el "por qué" (trigger).
    """
    class TipoTrigger(models.TextChoices):
        TIEMPO = 'TIEMPO', 'Basado en Tiempo'
        USO = 'USO', 'Basado en Horas de Uso'

    class FrecuenciaTiempo(models.TextChoices):
        DIARIO = 'DIARIO', 'Diario'
        SEMANAL = 'SEMANAL', 'Semanal'
        MENSUAL = 'MENSUAL', 'Mensual'
        ANUAL = 'ANUAL', 'Anual'

    nombre = models.CharField(
        max_length=255,
        verbose_name="Nombre del Plan"
    )
    tipo_trigger = models.CharField(
        max_length=10,
        choices=TipoTrigger.choices,
        verbose_name="Tipo de Trigger"
    )

    # --- Campos para trigger 'TIEMPO' ---
    frecuencia = models.CharField(
        max_length=10,
        choices=FrecuenciaTiempo.choices,
        blank=True,
        null=True,
        verbose_name="Frecuencia (si es por tiempo)"
    )
    intervalo = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Intervalo",
        help_text="Ej: si frecuencia es 'SEMANAL' e intervalo es 2, será 'cada 2 semanas'"
    )

    # --- Campos para trigger 'USO' ---
    horas_uso_trigger = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Horas de Uso (si es por uso)",
        help_text="Ej: 50.00 (para 'cada 50 horas de uso')"
    )

    activos = models.ManyToManyField(
        Activo,
        through='PlanActivoConfig',
        related_name='planes_mantenimiento',
        verbose_name="Activos Incluidos"
    )
    activo_en_sistema = models.BooleanField(
        default=True,
        verbose_name="Plan Activo",
        help_text="Desmarque para desactivar este plan sin borrarlo."
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Plan de Mantenimiento"
        verbose_name_plural = "Planes de Mantenimiento"

    def __str__(self):
        return self.nombre


class PlanActivoConfig(models.Model):
    """
    Modelo intermedio (through) para guardar el estado de
    CADA activo DENTRO de un plan.
    """
    plan = models.ForeignKey(
        'PlanMantenimiento',
        on_delete=models.CASCADE,
        verbose_name="Plan"
    )
    activo = models.ForeignKey(
        Activo,
        on_delete=models.CASCADE,
        related_name='configuraciones_plan',
        verbose_name="Activo"
    )

    # --- Campos de Tracking (por activo, por plan) ---
    fecha_ultima_mantencion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha Última Mantención"
    )
    horas_uso_en_ultima_mantencion = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0.00,
        verbose_name="Horas del Activo en Última Mantención",
        help_text="Guarda el total de horas_uso_totales del activo en su última mantención."
    )

    class Meta:
        verbose_name = "Configuración Activo-Plan"
        verbose_name_plural = "Configuraciones Activo-Plan"
        # Asegura que un activo solo esté una vez por plan
        unique_together = ('plan', 'activo')

    def __str__(self):
        return f"{self.activo.nombre_sku} en {self.plan.nombre}"


# --- Modelos de Ejecución (La Orden de Trabajo y el Log) ---

class OrdenMantenimiento(models.Model):
    """
    La orden de trabajo específica. Puede ser generada por un Plan
    (programada) o creada manualmente (correctiva).
    """
    class EstadoOrden(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        EN_CURSO = 'EN_CURSO', 'En Curso'
        REALIZADA = 'REALIZADA', 'Realizada'
        CANCELADA = 'CANCELADA', 'Cancelada'

    class TipoOrden(models.TextChoices):
        PROGRAMADA = 'PROGRAMADA', 'Programada (Trigger)'
        CORRECTIVA = 'CORRECTIVA', 'Correctiva (Manual)'

    plan_origen = models.ForeignKey(
        'PlanMantenimiento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_generadas',
        verbose_name="Plan de Origen"
    )
    activos_afectados = models.ManyToManyField(
        Activo,
        related_name='ordenes_mantenimiento',
        verbose_name="Activos Afectados",
        help_text="Activos que esta orden específica debe revisar."
    )
    fecha_programada = models.DateTimeField(
        verbose_name="Fecha Programada"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha Creación Orden"
    )
    fecha_cierre = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha Cierre Orden"
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoOrden.choices,
        default=EstadoOrden.PENDIENTE,
        verbose_name="Estado de la Orden"
    )
    tipo_orden = models.CharField(
        max_length=20,
        choices=TipoOrden.choices,
        verbose_name="Tipo de Orden"
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_asignadas',
        verbose_name="Responsable Asignado"
    )
    
    class Meta:
        verbose_name = "Orden de Mantenimiento"
        verbose_name_plural = "Órdenes de Mantenimiento"
        ordering = ['-fecha_programada']

    def __str__(self):
        return f"Orden {self.id} - {self.get_tipo_orden_display()} ({self.get_estado_display()})"


class RegistroMantenimiento(models.Model):
    """
    El registro individual de una acción de mantenimiento
    sobre un activo específico. Es el "logbook".
    """
    orden_mantenimiento = models.ForeignKey(
        'OrdenMantenimiento',
        on_delete=models.CASCADE,
        related_name='registros',
        verbose_name="Orden de Mantenimiento"
    )
    activo = models.ForeignKey(
        Activo,
        on_delete=models.PROTECT, # No borrar historial si se borra el activo
        related_name='historial_mantenimiento',
        verbose_name="Activo"
    )
    usuario_ejecutor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario Ejecutor"
    )
    fecha_ejecucion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Ejecución"
    )
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notas de la Ejecución"
    )
    fue_exitoso = models.BooleanField(
        default=True,
        verbose_name="¿Mantención Exitosa?",
        help_text="Indica si la mantención fue completada exitosamente."
    )

    class Meta:
        verbose_name = "Registro de Mantenimiento"
        verbose_name_plural = "Registros de Mantenimiento"
        ordering = ['-fecha_ejecucion']

    def __str__(self):
        return f"Registro de {self.activo.nombre_sku} en {self.fecha_ejecucion.strftime('%Y-%m-%d')}"