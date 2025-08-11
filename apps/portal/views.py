from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import FormularioLogin



class InicioView(LoginRequiredMixin, View):

    template_name = "portal/pages/home.html"

    def get(self, request):
        return render(request, self.template_name)






class LoginView(View):

    template_name = "portal/pages/login.html"

    def get(self, request):
        # Si el usuario ya está autenticado, redirige al inicio
        if request.user.is_authenticated:
            return redirect(reverse('portal:ruta_inicio'))
        
        formulario = FormularioLogin()
        return render(request, self.template_name, {'formulario': formulario})
    

    def post(self, request):
        formulario = FormularioLogin(request.POST)

        if not formulario.is_valid():
            return render(request, self.template_name, {'formulario': formulario})

        datos_limpios = formulario.cleaned_data
        user = authenticate(
            request, 
            email=datos_limpios.get('correo'), 
            password=datos_limpios.get('password')
        )

        if user is None:
            messages.add_message(request, messages.WARNING, "Usuario y/o contraseña incorrectos")
            return render(request, self.template_name, {'formulario': formulario})
            
        login(request, user)
        return redirect(reverse('portal:ruta_inicio'))






class LogoutView(LoginRequiredMixin, View):
    def get(self, request):
        logout(request)
        messages.add_message(request, messages.SUCCESS, "Se cerró la sesión correctamente")
        return redirect(reverse('portal:ruta_login'))
    