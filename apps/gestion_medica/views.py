from django.shortcuts import render
from django.views import View


class MedicoInicioView(View):
    '''Vista para ver la página principal del módulo'''
    def get(self, request):
        return render(request, "gestion_medica/pages/home.html")
    


class MedicoCrearView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/crear_voluntario.html")



class MedicoListaView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/lista_voluntarios.html")
    
class MedicoDatosView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/datos_paciente.html")
    #def get(self, request, id):
        #return HttpResponse("mostrar datos")

class MedicoNumEmergView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/contacto_emergencia.html")
    #def get(self, request, id):
        #return HttpResponse("mostrar datos")

class MedicoEnfermedadView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/enfermedad_paciente.html")
    #def get(self, request, id):
        #return HttpResponse("mostrar datos")

class MedicoAlergiasView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/alergias_paciente.html")
    #def get(self, request, id):
        #return HttpResponse("mostrar datos")

class MedicoInfoView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/informacion_paciente.html")
    #def get(self, request, id):
        #return HttpResponse("mostrar datos")

class MedicoVerView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/ver_voluntario.html")



class MedicoModificarView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/modificar_voluntario.html")
    
class MedicamentoCrearView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/crear_medicamento.html")
    
class MedicamentoListView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/lista_medicamentos.html")