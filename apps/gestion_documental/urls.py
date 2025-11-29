from django.urls import path
# Importamos las nuevas vistas que crearemos
from .views import ListaDocumentoView, SubirDocumentoView, EliminarDocumentoView

app_name = 'gestion_documental'

urlpatterns = [
    # Página Inicial de la gestión documental
    path('', ListaDocumentoView.as_view(), name="ruta_inicio"),

    # --- NUEVAS RUTAS (RF10) ---
    
    # Muestra el listado de documentos
    path('documentos/', ListaDocumentoView.as_view(), name="ruta_lista_documentos"),
    
    # Muestra el formulario para subir un nuevo documento
    path('documentos/subir/', SubirDocumentoView.as_view(), name="ruta_subir_documento"),

    # Eliminar documento
    path('documentos/<int:pk>/eliminar/', EliminarDocumentoView.as_view(), name="ruta_eliminar_documento")
]
