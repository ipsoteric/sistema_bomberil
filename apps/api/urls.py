from django.urls import path
from .views import BuscarUsuarioAPIView, alternar_tema_oscuro, ActualizarAvatarUsuarioView, ComunasPorRegionAPIView, GraficoEstadosInventarioView, GraficoExistenciasCategoriaView

app_name = "api"

urlpatterns = [
    # Alternar tema oscuro
    path('alternar-tema-oscuro/', alternar_tema_oscuro, name='ruta_alternar_tema'),
    path('buscar-usuario-para-agregar', BuscarUsuarioAPIView.as_view(), name='ruta_buscar_usuario'),
    # Modificar avatar
    path('usuarios/<int:id>/editar-avatar/', ActualizarAvatarUsuarioView.as_view(), name="ruta_editar_avatar_usuario"),

    # Obtener comunas por región
    path('comunas-por-region/<int:region_id>/', ComunasPorRegionAPIView.as_view(), name='comunas_por_region'),

    # Obtener gráfico de existencias por categoría
    path('existencias-por-categoria/', GraficoExistenciasCategoriaView.as_view(), name="ruta_obtener_grafico_categoria"),
    # Obtener gráfico existencias por estado
    path('existencias-por-estado/', GraficoEstadosInventarioView.as_view(), name="ruta_grafico_estado"),
]