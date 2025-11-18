from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
# --- ¡IMPORTANTE! Agregamos TipoDocumento a la importación ---
from .models import DocumentoHistorico, TipoDocumento
from .forms import DocumentoHistoricoForm
from apps.gestion_inventario.models import Estacion
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

    
class DocumentoInicioView(View):
    """
    Muestra el Dashboard/Inicio de la app documental.
    (Por ahora solo renderiza el 'home.html')
    """
    template_name = "gestion_documental/pages/home.html"

    def get(self, request):
        return render(request, self.template_name)
    
class ListaDocumentoView(View):
   def get(self, request):
        try:
            membresia_activa = request.user.membresias.get(estado='ACTIVO')
            estacion_usuario = membresia_activa.estacion
            
            # 1. Capturar el filtro de la URL
            tipo_filtro = request.GET.get('tipo')

            # 2. Consulta base (filtrada por estación)
            documentos = DocumentoHistorico.objects.filter(estacion=estacion_usuario) \
                         .select_related('tipo_documento', 'usuario_registra') \
                         .order_by('-fecha_documento')
            
            # 3. Aplicar filtro de Tipo si existe
            if tipo_filtro and tipo_filtro != 'todos':
                documentos = documentos.filter(tipo_documento_id=tipo_filtro)

            # 4. Obtener todos los tipos para el <select>
            tipos_documento = TipoDocumento.objects.all().order_by('nombre')
            
            context = {
                'documentos': documentos,
                'estacion_usuario': estacion_usuario,
                'tipos_documento': tipos_documento, # Enviamos la lista al template
                'filtro_actual': tipo_filtro        # Para mantener la selección
            }
            return render(request, "gestion_documental/pages/lista_documentos.html", context)

        except Exception as e:
            messages.error(request, f"Error al cargar los documentos: {e}")
            return render(request, "gestion_documental/pages/lista_documentos.html", {'documentos': []})


# --- NUEVA VISTA ---
class SubirDocumentoView(View):
    """
    (RF10) Maneja la subida de nuevos documentos históricos (PDF, JPG, PNG).
    """
    def get(self, request):
        # Muestra el formulario vacío
        form = DocumentoHistoricoForm()
        context = {
            'form': form
        }
        return render(request, "gestion_documental/pages/crear_documento.html", context)

    def post(self, request):
        # Procesa el formulario con los datos y los archivos
        form = DocumentoHistoricoForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Obtenemos la estación del usuario que registra
                membresia_activa = request.user.membresias.get(estado='ACTIVO')
                estacion_usuario = membresia_activa.estacion
                
                documento = form.save(commit=False)
                documento.usuario_registra = request.user # Asignamos el usuario que sube
                documento.estacion = estacion_usuario   # Asignamos la estación
                documento.save()
                
                messages.success(request, f'Documento "{documento.titulo}" subido exitosamente.')
                return redirect('gestion_documental:ruta_lista_documentos')

            except Exception as e:
                messages.error(request, f'Error al guardar el documento: {e}')
        
        else:
            messages.error(request, 'Error en el formulario. Revisa los campos.')
            
        context = {
            'form': form
        }
        return render(request, "gestion_documental/pages/crear_documento.html", context)