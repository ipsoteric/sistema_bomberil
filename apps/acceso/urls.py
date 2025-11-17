from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from .views import LoginView, LogoutView, CustomPasswordResetView, SeleccionarEstacionView


app_name = "acceso"

urlpatterns = [
    # Iniciar sesión
    path('login/', LoginView.as_view(), name="ruta_login"),

    # Cerrar sesión
    path('logout/', LogoutView.as_view(), name="ruta_logout"),

    # Restablecer contraseña
    path('reset_password/', CustomPasswordResetView.as_view(), name="password_reset"),

    # Restablecer contraseña: Correo enviado
    path('reset_password/done/',
         auth_views.PasswordResetDoneView.as_view(template_name="acceso/pages/password_reset_done.html"),
         name="password_reset_done"),

    # Restablecer contraseña: Confirmación
    path('reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name="acceso/pages/password_reset_confirm.html",
            success_url = reverse_lazy('acceso:password_reset_complete')
        ),    
        name="password_reset_confirm"),

    # Restablecer contraseña: Completada
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name="acceso/pages/password_reset_complete.html"),
         name="password_reset_complete"),

    # Superuser: Seleccionar estación
    path('seleccionar-estacion/', SeleccionarEstacionView.as_view(), name="ruta_seleccionar_estacion"),
]