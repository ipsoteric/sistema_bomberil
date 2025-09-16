from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.views.generic import UpdateView
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import EditarPerfilForm


class VerPerfilView(LoginRequiredMixin, View):
    """
    Muestra la información del perfil del usuario que ha iniciado sesión.
    """
    template_name = 'perfil/pages/ver_perfil.html'

    def get(self, request, *args, **kwargs):
        # El contexto es simplemente el usuario logueado
        context = {
            'usuario': request.user
        }
        return render(request, self.template_name, context)




class EditarPerfilView(LoginRequiredMixin, View):
    """
    Maneja la edición de la información del perfil del usuario.
    """
    template_name = 'perfil/pages/editar_perfil.html'
    form_class = EditarPerfilForm
    success_url = reverse_lazy('perfil:ver')

    def get(self, request, *args, **kwargs):
        # Creamos una instancia del formulario con los datos actuales del usuario
        form = self.form_class(instance=request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        # Procesamos el formulario con los datos enviados y los archivos
        form = self.form_class(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Tu perfil ha sido actualizado correctamente!')
            return redirect(self.success_url)
        
        # Si el formulario no es válido, lo volvemos a mostrar con los errores
        messages.error(request, 'Por favor, corrige los errores en el formulario.')
        return render(request, self.template_name, {'form': form})




class CambiarContrasenaView(PasswordChangeView):
    """
    Utiliza la vista integrada y segura de Django para cambiar la contraseña.
    Solo necesita saber dónde están la plantilla y la URL de éxito.
    """
    template_name = 'perfil/pages/cambiar_contrasena.html'
    success_url = reverse_lazy('perfil:ver')

    def form_valid(self, form):
        messages.success(self.request, '¡Tu contraseña ha sido cambiada correctamente!')
        return super().form_valid(form)