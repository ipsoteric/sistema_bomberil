from django.utils import timezone
from django.db import models
from apps.gestion_voluntarios.models import Voluntario


# ==============================================================================
# 1. TABLAS DE BÚSQUEDA (CATÁLOGOS)
# (Estos modelos están perfectos como los tienes)
# ==============================================================================
class SistemaSalud(models.Model):
    """(Global) Modelo para registrar los sistemas de salud (Fonasa, Isapre, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        verbose_name = "Sistema de salud"
        verbose_name_plural = "Sistemas de salud"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre



class GrupoSanguineo(models.Model):
    """(Global) Modelo para registrar los grupos sanguíneos (A+, O-, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50)

    class Meta:
        verbose_name = "Grupo sanguíneo"
        verbose_name_plural = "Grupos sanguíneos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre



class Medicamento(models.Model):
    """(Global) Catálogo de medicamentos comunes"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        verbose_name = "Medicamento"
        verbose_name_plural = "Medicamentos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre



class Enfermedad(models.Model):
    """(Global) Catálogo de enfermedades comunes (Hipertensión, Diabetes, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        verbose_name = "Enfermedad"
        verbose_name_plural = "Enfermedades"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre



class Alergia(models.Model):
    """(Global) Catálogo de alergias comunes (Penicilina, Mariscos, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        verbose_name = "Alergia"
        verbose_name_plural = "Alergias"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre



class Cirugia(models.Model):
    """(Global) Catálogo de cirugías comunes (Apendicectomía, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        verbose_name = "Cirugía"
        verbose_name_plural = "Cirugías"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre



# ==============================================================================
# 2. MODELO DE ENTIDAD / PERFIL (EL CONTENEDOR)
# ==============================================================================
# Este es el cambio de nombre principal: Paciente -> FichaMedica
class FichaMedica(models.Model):
    """
    El perfil médico global del Voluntario. Contiene datos generales de salud.
    Se crea automáticamente (vacía) junto con el perfil de Voluntario.
    """
    voluntario = models.OneToOneField(
        Voluntario,
        on_delete=models.CASCADE,
        related_name="ficha_medica",
        verbose_name="Voluntario"
    )

    # --- Datos Fisiológicos ---
    peso_kg = models.DecimalField(
        verbose_name="Peso (kg)", max_digits=5, decimal_places=2,
        null=True, blank=True, help_text="Usar punto (.) para decimal"
    )
    altura_mts = models.DecimalField(
        verbose_name="Altura (mts)", max_digits=3, decimal_places=2,
        null=True, blank=True, help_text="Ej: 1.75"
    )
    presion_arterial_sistolica = models.PositiveSmallIntegerField(
        verbose_name="Presión arterial Sistólica", blank=True, null=True
    )
    presion_arterial_diastolica = models.PositiveSmallIntegerField(
        verbose_name="Presión arterial Diastólica", blank=True, null=True
    )
    
    # --- Datos de Salud (Relaciones catálogo) ---
    grupo_sanguineo = models.ForeignKey(
        GrupoSanguineo, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Grupo Sanguíneo"
    )
    sistema_salud = models.ForeignKey(
        SistemaSalud, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Sistema de Salud"
    )
    
    observaciones_generales = models.TextField(
        verbose_name="Observaciones Generales", null=True, blank=True,
        help_text="Anotaciones relevantes no cubiertas en otros campos."
    )

    # Metadatos
    fecha_creacion = models.DateTimeField(default=timezone.now, editable=False)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ficha Médica"
        verbose_name_plural = "Fichas Médicas"

    def __str__(self):
        # Accedemos al nombre a través de la relación anidada
        return f"Ficha Médica de: {self.voluntario.usuario.get_full_name}"



# ==============================================================================
# 3. MODELOS DE RELACIÓN (TABLAS THROUGH)
# (Aquí también renombramos 'Paciente' a 'FichaMedica')
# ==============================================================================
class FichaMedicaEnfermedad(models.Model):
    """Registra las enfermedades (crónicas o pasadas) de una ficha"""
    ficha_medica = models.ForeignKey(FichaMedica, on_delete=models.CASCADE, related_name="enfermedades")
    enfermedad = models.ForeignKey(Enfermedad, on_delete=models.PROTECT)
    observaciones = models.CharField(max_length=255, null=True, blank=True, help_text="Ej: 'Crónica', 'En tratamiento'")

    class Meta:
        verbose_name = "Enfermedad de Ficha"
        verbose_name_plural = "Enfermedades de Ficha"
        unique_together = ('ficha_medica', 'enfermedad') # Evita duplicados

class FichaMedicaMedicamento(models.Model):
    """Registra los medicamentos permanentes de una ficha"""
    ficha_medica = models.ForeignKey(FichaMedica, on_delete=models.CASCADE, related_name="medicamentos")
    medicamento = models.ForeignKey(Medicamento, on_delete=models.PROTECT)
    dosis_frecuencia = models.CharField(
        verbose_name="Dosificación", max_length=100, null=True, blank=True,
        help_text="Ej: '10mg cada 8 horas'"
    )

    class Meta:
        verbose_name = "Medicamento de Ficha"
        verbose_name_plural = "Medicamentos de Ficha"
        unique_together = ('ficha_medica', 'medicamento') # Evita duplicados

class FichaMedicaCirugia(models.Model):
    """Registra las operaciones quirúrgicas de una ficha"""
    ficha_medica = models.ForeignKey(FichaMedica, on_delete=models.CASCADE, related_name="cirugias")
    cirugia = models.ForeignKey(Cirugia, on_delete=models.PROTECT)
    fecha_cirugia = models.DateField(verbose_name="Fecha (aprox.)", null=True, blank=True)
    observaciones = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        verbose_name = "Cirugía de Ficha"
        verbose_name_plural = "Cirugías de Ficha"
        ordering = ['-fecha_cirugia']

class FichaMedicaAlergia(models.Model):
    """Registra las alergias de una ficha"""
    ficha_medica = models.ForeignKey(FichaMedica, on_delete=models.CASCADE, related_name="alergias")
    alergia = models.ForeignKey(Alergia, on_delete=models.PROTECT)
    observaciones = models.CharField(
        max_length=255, null=True, blank=True, 
        help_text="Ej: 'Reacción grave', 'Solo produce picazón'"
    )
    
    class Meta:
        verbose_name = "Alergia de Ficha"
        verbose_name_plural = "Alergias de Ficha"
        unique_together = ('ficha_medica', 'alergia') # Evita duplicados



# ==============================================================================
# 4. CONTACTOS DE EMERGENCIA
# ==============================================================================
class ContactoEmergencia(models.Model):
    """
    Contactos de emergencia del voluntario.
    Se vincula a 'Voluntario' directamente, no a la ficha médica.
    """
    voluntario = models.ForeignKey(
        Voluntario, on_delete=models.CASCADE, 
        related_name="contactos_emergencia"
    )
    nombre_completo = models.CharField(max_length=200)
    parentesco = models.CharField(max_length=50, null=True, blank=True)
    telefono = models.CharField(max_length=20)
    
    class Meta:
        verbose_name = "Contacto de Emergencia"
        verbose_name_plural = "Contactos de Emergencia"

    def __str__(self):
        return f"{self.nombre_completo} (Contacto de {self.voluntario.usuario.username})"