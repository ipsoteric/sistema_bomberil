from django.urls import path
from .views import InicioView, LoginView, LogoutView

app_name = "portal"

urlpatterns = [
    path('', InicioView.as_view(), name="ruta_inicio"),
    path('login/', LoginView.as_view(), name="ruta_login"),
    path('logout/', LogoutView.as_view(), name="ruta_logout"),
]