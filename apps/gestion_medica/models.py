import uuid
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

        default_permissions = []
        permissions = [
            ("sys_view_sistemasalud", "System: Puede ver Sistemas de salud"),
            ("sys_add_sistemasalud", "System: Puede agregar Sistemas de salud"),
            ("sys_change_sistemasalud", "System: Puede cambiar Sistemas de salud"),
            ("sys_delete_sistemasalud", "System: Puede eliminar Sistemas de salud"),
        ]

    def __str__(self):
        return self.nombre




class GrupoSanguineo(models.Model):
    """(Global) Modelo para registrar los grupos sanguíneos (A+, O-, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=50)

    class Meta:
        verbose_name = "Grupo sanguíneo"
        verbose_name_plural = "Grupos sanguíneos"
        ordering = ['nombre']

        default_permissions = []
        permissions = [
            ("sys_view_gruposanguineo", "System: Puede ver Grupos sanguíneos"),
            ("sys_add_gruposanguineo", "System: Puede agregar Grupos sanguíneos"),
            ("sys_change_gruposanguineo", "System: Puede cambiar Grupos sanguíneos"),
            ("sys_delete_gruposanguineo", "System: Puede eliminar Grupos sanguíneos"),
        ]

    def __str__(self):
        return self.nombre




class Medicamento(models.Model):
    """(Global) Catálogo de medicamentos comunes"""

    # --- Opciones (Choices) ---
    class Unidades(models.TextChoices):
        MG = 'mg', 'mg (Miligramos)'
        ML = 'ml', 'ml (Mililitros)'
        GR = 'gr', 'gr (Gramos)'
        MCG = 'mcg', 'mcg (Microgramos)'
        G_ML = 'g/ml', 'g/ml'
        MG_ML = 'mg/ml', 'mg/ml'
        UI = 'ui', 'UI (Unidades Int.)'
        PORCENTAJE = '%', '% (Porcentaje)'
        PUFF = 'puff', 'Puff/Inhalación'
        COMPRIMIDO = 'comp', 'Comprimido(s)'
        CAPSULA = 'cap', 'Cápsula(s)'
        GOTAS = 'gotas', 'Gotas'
        AMPOLLA = 'amp', 'Ampolla'
        UNIDAD = 'unid', 'Unidad(es)'

    class Riesgo(models.TextChoices):
        NEUTRO = '', 'Neutro / Sin Alerta'
        ANTICOAGULANTE = 'ANTICOAGULANTE', 'ANTICOAGULANTE'
        COAGULANTE = 'COAGULANTE', 'COAGULANTE / HEMOSTÁTICO'
        ANTIPLAQUETARIO = 'ANTIPLAQUETARIO', 'ANTIPLAQUETARIO'

    # --- Campos Estructurados (Nuevos en BD) ---
    nombre = models.CharField(
        verbose_name="Nombre del Fármaco", 
        max_length=100,
        help_text="Ej: Paracetamol"
    )
    
    concentracion = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name="Dosis/Cantidad",
        help_text="Ej: 500"
    )
    
    # Aquí se guardará el código corto ('mg', 'ml', etc.)
    unidad = models.CharField(
        max_length=10, 
        choices=Unidades.choices, 
        default=Unidades.MG,
        verbose_name="Unidad"
    )

    clasificacion_riesgo = models.CharField(
        verbose_name="Clasificación de Riesgo",
        max_length=20,
        choices=Riesgo.choices,
        blank=True, default=''
    )

    class Meta:
        verbose_name = "Medicamento"
        verbose_name_plural = "Medicamentos"
        ordering = ['nombre', 'concentracion']
        # Evitamos duplicados lógicos (Ej: Paracetamol 500 mg vs Paracetamol 500 mg)
        unique_together = ['nombre', 'concentracion', 'unidad', 'clasificacion_riesgo']

        default_permissions = []
        permissions = [
            ("sys_view_medicamento", "System: Puede ver Medicamentos"),
            ("sys_add_medicamento", "System: Puede agregar Medicamentos"),
            ("sys_change_medicamento", "System: Puede cambiar Medicamentos"),
            ("sys_delete_medicamento", "System: Puede eliminar Medicamentos"),
        ]

    def save(self, *args, **kwargs):
        """
        MODIFICADO: Guarda el nombre tal cual lo escribe el usuario (limpio),
        sin concatenar dosis ni riesgos en la base de datos.
        """
        self.nombre = self.nombre.strip() # Solo limpieza básica de espacios
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        """Construye el nombre al vuelo cada vez que se pide."""
        # 1. Base
        partes = [self.nombre.title()]
        
        # 2. Dosis (Si existe)
        if self.concentracion:
            partes.append(f"{self.concentracion} {self.unidad}")
        
        # 3. Riesgo (Si existe)
        if self.clasificacion_riesgo:
            partes.append(f"[{self.clasificacion_riesgo}]")
            
        return " ".join(partes)

    def __str__(self):
        # Usamos la property para la representación
        return self.nombre_completo




class Enfermedad(models.Model):
    """(Global) Catálogo de enfermedades comunes (Hipertensión, Diabetes, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        verbose_name = "Enfermedad"
        verbose_name_plural = "Enfermedades"
        ordering = ['nombre']

        default_permissions = []
        permissions = [
            ("sys_view_enfermedad", "System: Puede ver Enfermedades"),
            ("sys_add_enfermedad", "System: Puede agregar Enfermedades"),
            ("sys_change_enfermedad", "System: Puede cambiar Enfermedades"),
            ("sys_delete_enfermedad", "System: Puede eliminar Enfermedades"),
        ]

    def __str__(self):
        return self.nombre




class Alergia(models.Model):
    """(Global) Catálogo de alergias comunes (Penicilina, Mariscos, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        verbose_name = "Alergia"
        verbose_name_plural = "Alergias"
        ordering = ['nombre']

        default_permissions = []
        permissions = [
            ("sys_view_alergia", "System: Puede ver Alergias"),
            ("sys_add_alergia", "System: Puede agregar Alergias"),
            ("sys_change_alergia", "System: Puede cambiar Alergias"),
            ("sys_delete_alergia", "System: Puede eliminar Alergias"),
        ]

    def __str__(self):
        return self.nombre




class Cirugia(models.Model):
    """(Global) Catálogo de cirugías comunes (Apendicectomía, etc.)"""
    nombre = models.CharField(verbose_name="Nombre", unique=True, max_length=100)

    class Meta:
        verbose_name = "Cirugía"
        verbose_name_plural = "Cirugías"
        ordering = ['nombre']

        default_permissions = []
        permissions = [
            ("sys_view_cirugia", "System: Puede ver Cirugías"),
            ("sys_add_cirugia", "System: Puede agregar Cirugías"),
            ("sys_change_cirugia", "System: Puede cambiar Cirugías"),
            ("sys_delete_cirugia", "System: Puede eliminar Cirugías"),
        ]

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
        primary_key=True,
        related_name="ficha_medica",
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

        default_permissions = []
        permissions = [
            ("sys_view_fichamedica", "System: Puede ver Fichas Médicas"),
            ("sys_add_fichamedica", "System: Puede agregar Fichas Médicas"),
            ("sys_change_fichamedica", "System: Puede cambiar Fichas Médicas"),
            ("sys_delete_fichamedica", "System: Puede eliminar Fichas Médicas"),
        ]

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

        default_permissions = []
        permissions = [
            ("sys_view_fichamedicaenfermedad", "System: Puede ver Enfermedades de Ficha"),
            ("sys_add_fichamedicaenfermedad", "System: Puede agregar Enfermedades de Ficha"),
            ("sys_change_fichamedicaenfermedad", "System: Puede cambiar Enfermedades de Ficha"),
            ("sys_delete_fichamedicaenfermedad", "System: Puede eliminar Enfermedades de Ficha"),
        ]




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

        default_permissions = []
        permissions = [
            ("sys_view_fichamedicamedicamento", "System: Puede ver Medicamentos de Ficha"),
            ("sys_add_fichamedicamedicamento", "System: Puede agregar Medicamentos de Ficha"),
            ("sys_change_fichamedicamedicamento", "System: Puede cambiar Medicamentos de Ficha"),
            ("sys_delete_fichamedicamedicamento", "System: Puede eliminar Medicamentos de Ficha"),
        ]




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

        default_permissions = []
        permissions = [
            ("sys_view_fichamedicacirugia", "System: Puede ver Cirugías de Ficha"),
            ("sys_add_fichamedicacirugia", "System: Puede agregar Cirugías de Ficha"),
            ("sys_change_fichamedicacirugia", "System: Puede cambiar Cirugías de Ficha"),
            ("sys_delete_fichamedicacirugia", "System: Puede eliminar Cirugías de Ficha"),
        ]




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

        default_permissions = []
        permissions = [
            ("sys_view_fichamedicaalergia", "System: Puede ver Alergias de Ficha"),
            ("sys_add_fichamedicaalergia", "System: Puede agregar Alergias de Ficha"),
            ("sys_change_fichamedicaalergia", "System: Puede cambiar Alergias de Ficha"),
            ("sys_delete_fichamedicaalergia", "System: Puede eliminar Alergias de Ficha"),
        ]





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

        default_permissions = []
        permissions = [
            ("sys_view_contactoemergencia", "System: Puede ver Contactos de Emergencia"),
            ("sys_add_contactoemergencia", "System: Puede agregar Contactos de Emergencia"),
            ("sys_change_contactoemergencia", "System: Puede cambiar Contactos de Emergencia"),
            ("sys_delete_contactoemergencia", "System: Puede eliminar Contactos de Emergencia"),
        ]

    def __str__(self):
        return f"{self.nombre_completo} (Contacto de {self.voluntario.usuario.username})"