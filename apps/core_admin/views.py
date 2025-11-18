from django.shortcuts import render
from django.views import View

# Create your views here.
class AdministracionInicioView(View):
    template_name = "core_admin/pages/home.html"
    def get(self, request):
        return render(request, self.template_name)