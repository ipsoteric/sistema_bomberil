from django.shortcuts import render
from django.views import View


# Página Inicial
class VoluntariosInicioView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/home.html")
    

# Lista de voluntarios
class VoluntariosListaView(View):
    def get(self, request):
        #código
        return render(request, "gestion_voluntarios/pages/lista_voluntarios.html")


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



# GESTIÓN DE CARGOS / RANGOS BOMBERILES
# Lista de cargos
class CargosListaView(View):
    def get(self, request):
        return render(request, "gestion_voluntarios/pages/lista_cargos.html")


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