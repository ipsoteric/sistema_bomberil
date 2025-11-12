from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from .views import LoginView, LogoutView, CustomPasswordResetView


app_name = "acceso"

urlpatterns = [
    path('login/', LoginView.as_view(), name="ruta_login"),

    path('logout/', LogoutView.as_view(), name="ruta_logout"),

    path('reset_password/', CustomPasswordResetView.as_view(), name="password_reset"),

    path('reset_password/done/',
         auth_views.PasswordResetDoneView.as_view(template_name="acceso/pages/password_reset_done.html"),
         name="password_reset_done"),

    path('reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name="acceso/pages/password_reset_confirm.html",
            success_url = reverse_lazy('acceso:password_reset_complete')
        ),    
        name="password_reset_confirm"),

    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name="acceso/pages/password_reset_complete.html"),
         name="password_reset_complete"),
]