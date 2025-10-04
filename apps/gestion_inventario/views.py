from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from django.db.models import Count
from django.urls import reverse
from django.contrib import messages
from .models import Seccion, Existencia, TipoSeccion, Estacion
from .forms import AlmacenForm


class InventarioInicioView(View):
    def get(self, request):
        context = {
            'existencias':range(10),
            'proveedores':range(5),
        }
        return render(request, "gestion_inventario/pages/home.html", context)


class InventarioPruebasView(View):
    def get(self, request):
        return render(request, "gestion_inventario/pages/pruebas.html")


# Obtener total de existencias por categoría (VISTA TEMPORAL, DEBE MOVERSE A LA APP API)
def grafico_existencias_por_categoria(request):
    datos = (
        Existencia.objects
        .values('catalogo__categoria__nombre')
        .annotate(score=Count('id'))
        .order_by('-score')
    )

    dataset = [['name', 'score']]
    for fila in datos:
        dataset.append([fila['catalogo__categoria__nombre'], fila['score']])

    return JsonResponse({'dataset': dataset})




class AlmacenListaView(View):
    def get(self, request):
        estacion_id = request.session.get('active_estacion_id')

        # Filtrar sólo secciones físicas (no vehículos)
        # Asumimos que el modelo TipoSeccion tiene un campo o nombre que permite distinguir físicas de vehículos
        # Ejemplo: nombre != 'Vehículo' (ajustar si el nombre es distinto)
        secciones_fisicas = (
            Seccion.objects
            .filter(estacion_id=estacion_id)
            .exclude(tipo_seccion__nombre__iexact='VEHÍCULO')
            .select_related('tipo_seccion')
        )

        # Obtener totales de compartimentos y existencias por sección
        # Prefetch compartimentos y existencias para eficiencia
        from .models import Compartimento, Existencia
        secciones = []
        for seccion in secciones_fisicas:
            compartimentos = Compartimento.objects.filter(seccion=seccion)
            total_compartimentos = compartimentos.count()
            # Sumar existencias en todos los compartimentos de la sección
            total_existencias = Existencia.objects.filter(compartimento__in=compartimentos).count()
            seccion.total_compartimentos = total_compartimentos
            seccion.total_existencias = total_existencias
            secciones.append(seccion)

        return render(request, "gestion_inventario/pages/lista_almacenes.html", {'secciones': secciones})


class AlmacenCrearView(View):
    def get(self, request):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No tienes una estación activa. No puedes crear almacenes.")
            return redirect(reverse('portal:ruta_inicio'))

        form = AlmacenForm()
        return render(request, 'gestion_inventario/pages/crear_almacen.html', {'formulario': form})

    def post(self, request):
        form = AlmacenForm(request.POST)
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No tienes una estación activa. No puedes crear almacenes.")
            return redirect(reverse('portal:ruta_inicio'))

        if form.is_valid():
            # Guardar sin confirmar para asignar tipo_seccion y potencialmente estacion desde sesión
            seccion = form.save(commit=False)

            # Obtener o crear el TipoSeccion con nombre 'AREA' (mayúsculas para consistencia)
            tipo_area, created = TipoSeccion.objects.get_or_create(nombre__iexact='AREA', defaults={'nombre': 'AREA'})
            # Si get_or_create con lookup no funciona en el dialecto usado, fallback a get_or_create por nombre exacto
            if not tipo_area:
                tipo_area, created = TipoSeccion.objects.get_or_create(nombre='AREA')

            seccion.tipo_seccion = tipo_area

            # Si hay una estación activa en sesión, asignarla; si no, mantener la seleccionada en el formulario
            # Asignar la estación desde la sesión (usuario sólo puede crear para su compañía)
            try:
                estacion_obj = Estacion.objects.get(id=estacion_id)
                seccion.estacion = estacion_obj
            except Estacion.DoesNotExist:
                messages.error(request, "La estación activa en sesión no es válida.")
                return redirect(reverse('portal:ruta_inicio'))

            seccion.save()
            messages.success(request, f'Almacén/ubicación "{seccion.nombre.title()}" creado exitosamente.')
            # Redirigir a la lista de almacenes
            return redirect(reverse('gestion_inventario:ruta_lista_almacenes'))
        # Si hay errores, volver a mostrar el formulario con errores
        return render(request, 'gestion_inventario/pages/crear_almacen.html', {'formulario': form})