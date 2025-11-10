from django.shortcuts import render
from django.views import View
from django.db.models import Prefetch

# Importamos los modelos de voluntarios
from .models import Voluntario, HistorialCargo, Cargo, TipoCargo, Profesion

# Importamos Membresia desde la app gestion_usuarios [cite: 6]
# (Ajusta la ruta si 'apps.gestion_usuarios' no es el path correcto)
from apps.gestion_usuarios.models import Membresia

# Página Inicial
class VoluntariosInicioView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/home.html")
    

# Lista de voluntarios
class VoluntariosListaView(View):
    def get(self, request):
        
        # 1. Prefetch para la membresía activa (para obtener Estación y Estado)
        # Buscamos la membresía activa del usuario [cite: 13]
        active_membresia_prefetch = Prefetch(
            'usuario__membresias',
            queryset=Membresia.objects.filter(estado='ACTIVO').select_related('estacion'),
            to_attr='membresia_activa_list' # Guardamos en un atributo temporal
        )

        # 2. Prefetch para el cargo actual (para obtener el Rango)
        # Buscamos en el historial el cargo que no tiene fecha de fin 
        current_cargo_prefetch = Prefetch(
            'historial_cargos',
            queryset=HistorialCargo.objects.filter(fecha_fin__isnull=True).select_related('cargo'),
            to_attr='cargo_actual_list' # Guardamos en un atributo temporal
        )

        # 3. Query principal
        # Obtenemos todos los Voluntarios 
        # Usamos select_related para el usuario y prefetch_related para los datos complejos
        voluntarios = Voluntario.objects.select_related('usuario').prefetch_related(
            active_membresia_prefetch,
            current_cargo_prefetch
        ).all()

        cargos = Cargo.objects.all().order_by('nombre')

        context = {
            'voluntarios': voluntarios,
            'cargos': cargos,          # <- Nueva data para el filtro
        }
        return render(request, "gestion_voluntarios/pages/lista_voluntarios.html", context)

# Crear voluntario
class VoluntariosCrearView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/crear_voluntario.html")

    def post(self, request):
        # Lógica para guardar voluntario (más adelante)
        return render(request, "gestion_voluntarios/pages/crear_voluntario.html")


# Ver voluntario
class VoluntariosVerView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/ver_voluntario.html")


# Editar voluntario
class VoluntariosModificarView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html")

    def post(self, request, id):
        # Lógica para actualizar voluntario
        return render(request, "gestion_voluntarios/pages/modificar_voluntario.html")


# Eliminar voluntario
class VoluntariosEliminarView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/eliminar_voluntario.html")

    def post(self, request, id):
        # Lógica para eliminar voluntario
        return render(request, "gestion_voluntarios/pages/eliminar_voluntario.html")



# GESTIÓN DE CARGOS Y PROFESIONES

# Lista de cargos y profesiones
class CargosListaView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/lista_cargos_profes.html")

# Crear profesion
class ProfesionesCrearView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/crear_profesion.html")

    def post(self, request):
        # Lógica para guardar profesion
        return render(request, "gestion_voluntarios/pages/crear_profesion.html")


# Editar profesion
class ProfesionesModificarView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/modificar_profesion.html")

    def post(self, request, id):
        # Lógica para actualizar profesion
        return render(request, "gestion_voluntarios/pages/modificar_profesion.html")


# Eliminar profesion
class ProfesionesEliminarView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/eliminar_profesion.html")

    def post(self, request, id):
        # Lógica para eliminar profesion
        return render(request, "gestion_voluntarios/pages/eliminar_profesion.html")

# Crear cargo
class CargosCrearView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/crear_cargo.html")

    def post(self, request):
        # Lógica para guardar cargo
        return render(request, "gestion_voluntarios/pages/crear_cargo.html")


# Editar cargo
class CargosModificarView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/modificar_cargo.html")

    def post(self, request, id):
        # Lógica para actualizar cargo
        return render(request, "gestion_voluntarios/pages/modificar_cargo.html")


# Eliminar cargo
class CargosEliminarView(View):
    def get(self, request, id):
        return render(request, "gestion_voluntarios/pages/eliminar_cargo.html")

    def post(self, request, id):
        # Lógica para eliminar cargo
        return render(request, "gestion_voluntarios/pages/eliminar_cargo.html")
    

# MODULO DE REPORTES EXPORTAR Y GENERAR HOJA DE VIDA

# Generar hoja de vida del voluntario
class HojaVidaView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/hoja_vida.html")

# Exportar listado 
class ExportarListadoView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/exportar_listado.html")
