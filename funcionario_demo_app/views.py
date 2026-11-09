import json
import secrets
from datetime import date, timedelta
from pathlib import PurePosixPath
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from admin_demo_app.models import (
    AtencionSocial,
    Actividad,
    Compromiso,
    CompromisoEstadoHistorial,
    Delegacion,
    Evidencia,
    Meta,
    Periodo,
    PersonaUsuaria,
    Usuario,
    Validacion,
)
from main.notifications import notificar, notificar_accion_funcionario, notificar_administradores

from .forms import (
    AtencionSocialForm,
    ActividadForm,
    CompromisoEstadoForm,
    CompromisoForm,
    DelegadoCompromisoForm,
    EvidenciaForm,
    VerificacionEvidenciaForm,
)


def funcionario_demo_view(request):
    funcionario = _funcionario_actual(request)
    if funcionario is None:
        return redirect('main:login_view')
    actividades = Actividad.objects.filter(funcionario=funcionario).order_by('-fecha_actividad') if funcionario else Actividad.objects.none()
    compromisos = Compromiso.objects.filter(responsable=funcionario).order_by('fecha_comprometida') if funcionario else Compromiso.objects.none()
    periodo = _periodo_actual()
    metricas = _calcular_metricas_funcionario(funcionario, periodo) if funcionario and periodo else None
    return render(request, 'funcionario_demo_app/funcionario_demo.html', {
        'funcionario': funcionario,
        'actividades_recientes': actividades[:5],
        'compromisos_proximos': compromisos[:5],
        'metricas': metricas,
    })


def delegado_demo_view(request):
    delegado = _delegado_actual(request)
    if delegado is None:
        return redirect('main:login_view')

    delegacion = _delegacion_del_delegado(delegado)
    compromisos = (
        Compromiso.objects.filter(delegacion=delegacion)
        .select_related('responsable')
        .order_by('fecha_comprometida')
        if delegacion else Compromiso.objects.none()
    )
    fecha_actual = date.today()
    compromisos_pendientes = compromisos.exclude(estado='realizado')
    equipo = (
        Usuario.objects.filter(delegacion=delegacion, estado='activo').order_by('apellidos', 'nombres')
        if delegacion else Usuario.objects.none()
    )
    actividades = (
        Actividad.objects.filter(funcionario__delegacion=delegacion)
        .select_related('funcionario', 'item')
        .order_by('-fecha_actividad')
        if delegacion else Actividad.objects.none()
    )
    atenciones = (
        AtencionSocial.objects.filter(funcionario__delegacion=delegacion)
        .select_related('persona', 'catalogo_tipo', 'funcionario')
        .order_by('-fecha', '-id')
        if delegacion else AtencionSocial.objects.none()
    )
    tubo_data = _datos_tubo_delegacion(request, delegacion)

    return render(request, 'funcionario_demo_app/delegado_demo.html', {
        'delegado': delegado,
        'delegacion': delegacion,
        'compromisos': compromisos[:3],
        'compromisos_total': compromisos.count(),
        'compromisos_en_proceso': compromisos.filter(estado='en_proceso').count(),
        'compromisos_revision': compromisos.filter(estado='revision').count(),
        'compromisos_pendientes': compromisos_pendientes.count(),
        'compromisos_vencidos': compromisos_pendientes.filter(fecha_comprometida__lt=fecha_actual).count(),
        'equipo': equipo[:5],
        'equipo_total': equipo.count(),
        'actividades_recientes': actividades[:3],
        'actividades_total': actividades.count(),
        'atenciones_recientes': atenciones[:3],
        'atenciones_total': atenciones.count(),
        'fecha_actual': fecha_actual,
        **tubo_data,
    })


def delegado_actividades_view(request):
    delegado = _delegado_actual(request)
    if delegado is None:
        return redirect('main:login_view')
    delegacion = _delegacion_del_delegado(delegado)
    actividades = (
        Actividad.objects.filter(funcionario__delegacion=delegacion)
        .select_related('funcionario', 'item')
        .order_by('-fecha_actividad')
        if delegacion else Actividad.objects.none()
    )
    return render(request, 'funcionario_demo_app/delegado_actividades.html', {
        'delegado': delegado,
        'delegacion': delegacion,
        'actividades': actividades,
        'active_section': 'actividades',
        'page_title': 'Actividades de la delegación',
        'page_description': 'Consulta las actividades registradas por el equipo de tu delegación.',
    })


def delegado_atenciones_view(request):
    delegado = _delegado_actual(request)
    if delegado is None:
        return redirect('main:login_view')
    delegacion = _delegacion_del_delegado(delegado)
    atenciones = (
        AtencionSocial.objects.filter(funcionario__delegacion=delegacion)
        .select_related('persona', 'catalogo_tipo', 'catalogo_subtipo', 'funcionario')
        .order_by('-fecha', '-id')
        if delegacion else AtencionSocial.objects.none()
    )
    return render(request, 'funcionario_demo_app/delegado_atenciones.html', {
        'delegado': delegado,
        'delegacion': delegacion,
        'atenciones': atenciones,
        'active_section': 'atenciones',
        'page_title': 'Atención Social',
        'page_description': 'Revisa las gestiones sociales registradas en tu delegación.',
    })


def delegado_equipo_view(request):
    delegado = _delegado_actual(request)
    if delegado is None:
        return redirect('main:login_view')
    delegacion = _delegacion_del_delegado(delegado)
    equipo = (
        Usuario.objects.filter(delegacion=delegacion, estado='activo')
        .select_related('cargo')
        .order_by('apellidos', 'nombres')
        if delegacion else Usuario.objects.none()
    )
    return render(request, 'funcionario_demo_app/delegado_equipo.html', {
        'delegado': delegado,
        'delegacion': delegacion,
        'equipo': equipo,
        'active_section': 'equipo',
        'page_title': 'Equipo activo',
        'page_description': 'Personas activas asignadas a tu delegación.',
    })


def delegado_compromisos_view(request):
    delegado = _delegado_actual(request)
    if delegado is None:
        return redirect('main:login_view')
    delegacion = _delegacion_del_delegado(delegado)
    compromisos = (
        Compromiso.objects.filter(delegacion=delegacion)
        .select_related('responsable')
        .order_by('fecha_comprometida')
        if delegacion else Compromiso.objects.none()
    )
    return render(request, 'funcionario_demo_app/delegado_compromisos.html', {
        'delegado': delegado,
        'delegacion': delegacion,
        'compromisos': compromisos,
        'active_section': 'compromisos',
    })


def delegado_compromiso_view(request, compromiso_id=None):
    delegado = _delegado_actual(request)
    if delegado is None:
        return redirect('main:login_view')
    delegacion = _delegacion_del_delegado(delegado)
    if delegacion is None:
        messages.error(request, 'No tienes una delegación asignada para gestionar compromisos.')
        return redirect('delegado_demo_view')

    compromiso = None
    if compromiso_id is not None:
        compromiso = get_object_or_404(
            Compromiso.objects.select_related('responsable', 'delegacion'),
            pk=compromiso_id,
            delegacion=delegacion,
        )

    if compromiso and compromiso.estado == 'revision':
        estados_permitidos = [('realizado', 'Validar cumplimiento'), ('en_proceso', 'Devolver a seguimiento')]
    elif compromiso and compromiso.estado == 'realizado':
        estados_permitidos = [('en_proceso', 'Reabrir compromiso')]
    else:
        estados_permitidos = []

    form = DelegadoCompromisoForm(
        request.POST if request.method == 'POST' and request.POST.get('accion') == 'guardar' else None,
        instance=compromiso,
        delegacion=delegacion,
    )
    estado_form = CompromisoEstadoForm(
        request.POST if request.method == 'POST' and request.POST.get('accion') == 'estado' else None,
        estados_permitidos=estados_permitidos,
    )

    if request.method == 'POST' and request.POST.get('accion') == 'guardar':
        if form.is_valid():
            with transaction.atomic():
                nuevo_compromiso = form.save(commit=False)
                nuevo_compromiso.delegacion = delegacion
                if compromiso is None:
                    nuevo_compromiso.estado = 'ingresado'
                nuevo_compromiso.save()
                if compromiso is None:
                    _registrar_cambio_compromiso(
                        nuevo_compromiso,
                        'ingresado',
                        delegado,
                        'Compromiso asignado por la delegación.',
                    )
            messages.success(request, 'Compromiso asignado correctamente.' if compromiso is None else 'Compromiso actualizado.')
            return redirect('delegado_compromiso_view', compromiso_id=nuevo_compromiso.pk)
    elif request.method == 'POST' and request.POST.get('accion') == 'estado' and compromiso:
        if estado_form.is_valid():
            nuevo_estado = estado_form.cleaned_data['estado']
            if nuevo_estado in dict(estados_permitidos):
                observacion = estado_form.cleaned_data['observacion']
                with transaction.atomic():
                    estado_anterior = compromiso.estado
                    compromiso.estado = nuevo_estado
                    compromiso.save(update_fields=['estado'])
                    _registrar_cambio_compromiso(
                        compromiso,
                        nuevo_estado,
                        delegado,
                        observacion,
                        estado_anterior=estado_anterior,
                    )
                messages.success(request, 'Revisión del compromiso guardada.')
                return redirect('delegado_compromiso_view', compromiso_id=compromiso.pk)

    return render(request, 'funcionario_demo_app/gestionar_compromiso.html', {
        'delegado': delegado,
        'delegacion': delegacion,
        'compromiso': compromiso,
        'form': form,
        'estado_form': estado_form,
        'estados_permitidos': estados_permitidos,
        'historial': compromiso.historial_estados.select_related('autor').order_by('-fecha') if compromiso else [],
    })


def funcionario_compromiso_view(request, compromiso_id):
    funcionario = _funcionario_actual(request)
    if funcionario is None:
        return redirect('main:login_view')
    compromiso = get_object_or_404(
        Compromiso.objects.select_related('responsable', 'delegacion'),
        pk=compromiso_id,
        responsable=funcionario,
    )
    if compromiso.estado in ('ingresado', 'pendiente'):
        estados_permitidos = [('en_proceso', 'Marcar en proceso')]
    elif compromiso.estado == 'en_proceso':
        estados_permitidos = [('revision', 'Enviar a revisión')]
    else:
        estados_permitidos = []
    estado_form = CompromisoEstadoForm(
        request.POST if request.method == 'POST' else None,
        estados_permitidos=estados_permitidos,
    )

    if request.method == 'POST' and estado_form.is_valid():
        nuevo_estado = estado_form.cleaned_data['estado']
        if nuevo_estado in dict(estados_permitidos):
            observacion = estado_form.cleaned_data['observacion']
            with transaction.atomic():
                estado_anterior = compromiso.estado
                compromiso.estado = nuevo_estado
                compromiso.save(update_fields=['estado'])
                _registrar_cambio_compromiso(
                    compromiso,
                    nuevo_estado,
                    funcionario,
                    observacion,
                    estado_anterior=estado_anterior,
                )
            messages.success(request, 'Estado del compromiso actualizado.')
            return redirect('funcionario_compromiso_view', compromiso_id=compromiso.pk)

    return render(request, 'funcionario_demo_app/actualizar_compromiso.html', {
        'funcionario': funcionario,
        'compromiso': compromiso,
        'estado_form': estado_form,
        'estados_permitidos': estados_permitidos,
        'historial': compromiso.historial_estados.select_related('autor').order_by('-fecha'),
    })


def _calcular_metricas_funcionario(funcionario, periodo, fecha_actual=None):
    fecha_actual = fecha_actual or date.today()
    metas = list(
        Meta.objects.filter(periodo=periodo, vigente=True)
        .filter(Q(funcionario=funcionario) | Q(cargo=funcionario.cargo))
        .select_related('item')
        .order_by('-funcionario_id')
    )

    metas_por_item = {}
    for meta in metas:
        metas_por_item.setdefault(meta.item_id, meta)
    metas = list(metas_por_item.values())
    if not metas:
        return None

    avances = dict(
        Actividad.objects.filter(
            funcionario=funcionario,
            periodo=periodo,
            estado='validada',
            fecha_actividad__range=(
                periodo.fecha_inicio,
                min(fecha_actual, periodo.fecha_termino),
            ),
            item_id__in=metas_por_item,
        )
        .values_list('item_id')
        .annotate(total=Count('id'))
    )

    dias_esperados = _dias_habiles_transcurridos(
        periodo.fecha_inicio,
        periodo.fecha_termino,
        fecha_actual,
    )
    dias_computables = periodo.dias_computables
    meta_esperada = min(Decimal('100'), Decimal(dias_esperados) * 100 / dias_computables) if dias_computables else Decimal('0')

    peso_total = sum((meta.ponderador_pct for meta in metas), Decimal('0'))
    avance_ponderado = Decimal('0')
    umbral_ponderado = Decimal('0')
    if peso_total:
        for meta in metas:
            peso = meta.ponderador_pct
            avance_pct = Decimal(avances.get(meta.item_id, 0)) * 100 / meta.valor_objetivo
            avance_pct = min(avance_pct, meta.maximo_computable_pct)
            avance_ponderado += avance_pct * peso
            umbral_ponderado += meta.umbral_minimo_pct * peso
        avance_ponderado /= peso_total
        umbral_ponderado /= peso_total

    if avance_ponderado >= meta_esperada:
        semaforo = 'verde'
    elif avance_ponderado >= meta_esperada * umbral_ponderado / 100:
        semaforo = 'ambar'
    else:
        semaforo = 'rojo'

    return {
        'avance_real_pct': round(avance_ponderado, 2),
        'meta_esperada_pct': round(meta_esperada, 2),
        'semaforo': semaforo,
        'periodo': periodo,
    }


def _dias_habiles_transcurridos(fecha_inicio, fecha_termino, fecha_actual):
    fecha_final = min(fecha_actual, fecha_termino)
    if fecha_final < fecha_inicio:
        return 0
    return sum(
        1
        for desplazamiento in range((fecha_final - fecha_inicio).days + 1)
        if (fecha_inicio + timedelta(days=desplazamiento)).weekday() < 5
    )


def actividades_view(request):
    delegado = _delegado_actual(request)
    funcionario = _funcionario_actual(request)
    if delegado:
        delegacion = _delegacion_del_delegado(delegado)
        actividades = Actividad.objects.filter(funcionario__delegacion=delegacion) if delegacion else Actividad.objects.none()
        panel_url = reverse('delegado_demo_view')
        is_delegado = True
    elif funcionario:
        actividades = Actividad.objects.filter(funcionario=funcionario)
        panel_url = reverse('funcionario_demo_view')
        is_delegado = False
    else:
        return redirect('main:login_view')
    actividades = actividades.select_related('funcionario').order_by('-fecha_actividad')
    datos = [{
        'id': actividad.id,
        'titulo': actividad.descripcion,
        'codigo': actividad.codigo_evidencia,
        'fecha': actividad.fecha_actividad.strftime('%d/%m/%Y'),
        'estado': actividad.estado,
        'url': reverse('actividad_detalle_view', args=[actividad.id]),
    } for actividad in actividades]
    return render(request, 'funcionario_demo_app/actividades.html', {
        'actividades_json': datos,
        'is_delegado': is_delegado,
        'panel_url': panel_url,
    })


def atenciones_sociales_view(request):
    delegado = _delegado_actual(request)
    funcionario = _funcionario_actual(request)
    if delegado:
        delegacion = _delegacion_del_delegado(delegado)
        atenciones = AtencionSocial.objects.filter(funcionario__delegacion=delegacion) if delegacion else AtencionSocial.objects.none()
        panel_url = reverse('delegado_demo_view')
        is_delegado = True
    elif funcionario:
        atenciones = AtencionSocial.objects.filter(funcionario=funcionario)
        panel_url = reverse('funcionario_demo_view')
        is_delegado = False
    else:
        return redirect('main:login_view')
    atenciones = atenciones.select_related(
        'persona', 'catalogo_tipo', 'catalogo_subtipo', 'delegacion', 'actividad', 'funcionario',
    ).order_by('-fecha', '-id')
    datos = [{
        'persona': atencion.persona.referencia_anonima,
        'tipo': atencion.catalogo_tipo.nombre,
        'subatencion': atencion.catalogo_subtipo.nombre if atencion.catalogo_subtipo_id else '',
        'solicitante': atencion.solicitante,
        'descripcion': atencion.descripcion,
        'delegacion': atencion.delegacion.nombre if atencion.delegacion_id else '',
        'categoria': atencion.catalogo_tipo.categoria,
        'categoria_display': atencion.catalogo_tipo.get_categoria_display(),
        'orden_gestion': atencion.orden_gestion,
        'fecha': atencion.fecha.strftime('%d/%m/%Y'),
        'resultado': atencion.resultado or '',
        'actividad': atencion.actividad.descripcion if atencion.actividad else '',
        'actividad_url': reverse('actividad_detalle_view', args=[atencion.actividad_id]) if atencion.actividad_id else '',
    } for atencion in atenciones]
    return render(request, 'funcionario_demo_app/atenciones_sociales.html', {
        'atenciones_json': datos,
        'is_delegado': is_delegado,
        'panel_url': panel_url,
    })


def nueva_atencion_social_view(request):
    funcionario = _funcionario_actual(request)
    if funcionario is None:
        return redirect('main:login_view')
    if request.method == 'POST':
        form = AtencionSocialForm(request.POST, funcionario=funcionario)
        if form.is_valid():
            with transaction.atomic():
                atencion = form.save()
            notificar_accion_funcionario(
                funcionario.pk,
                f'Registraste una atención social para {atencion.persona.referencia_anonima}.',
                reverse('atenciones_sociales_view'),
                tipo='actividad',
            )
            messages.success(request, f'Atención social de {atencion.persona.referencia_anonima} registrada correctamente.')
            return redirect('atenciones_sociales_view')
    else:
        form = AtencionSocialForm(funcionario=funcionario)
    return render(request, 'funcionario_demo_app/nueva_atencion_social.html', {
        'form': form,
        'funcionario': funcionario,
    })


def buscar_personas_view(request):
    funcionario = _funcionario_actual(request)
    if funcionario is None:
        return JsonResponse({'results': []}, status=403)
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})
    personas = PersonaUsuaria.objects.filter(
        Q(nombre__icontains=query)
        | Q(rut__icontains=query)
        | Q(referencia_anonima__icontains=query)
    ).order_by('nombre', 'rut')[:10]
    return JsonResponse({'results': [{
        'id': persona.pk,
        'nombre': persona.nombre or 'Persona sin nombre',
        'rut': persona.rut or '',
        'telefono': persona.telefono or '',
        'referencia': persona.referencia_anonima,
    } for persona in personas]})


def agenda_colectiva_view(request):
    delegado = _delegado_actual(request)
    funcionario = _funcionario_actual(request)
    if delegado:
        delegacion = _delegacion_del_delegado(delegado)
        compromisos = Compromiso.objects.filter(delegacion=delegacion) if delegacion else Compromiso.objects.none()
        panel_url = reverse('delegado_demo_view')
        is_delegado = True
    elif funcionario:
        compromisos = Compromiso.objects.filter(responsable=funcionario)
        panel_url = reverse('funcionario_demo_view')
        is_delegado = False
    else:
        return redirect('main:login_view')
    compromisos = compromisos.select_related('responsable').order_by('fecha_comprometida')
    datos = [{
        'id': compromiso.pk,
        'titulo': compromiso.observacion or compromiso.solicitante,
        'solicitante': compromiso.solicitante,
        'vence': compromiso.fecha_comprometida.strftime('%d/%m/%Y'),
        'estado': compromiso.estado,
        'url': reverse(
            'delegado_compromiso_view' if is_delegado else 'funcionario_compromiso_view',
            args=[compromiso.pk],
        ),
    } for compromiso in compromisos]
    return render(request, 'funcionario_demo_app/agenda_colectiva.html', {
        'compromisos_json': datos,
        'is_delegado': is_delegado,
        'panel_url': panel_url,
    })


def mis_evidencias_view(request):
    delegado = _delegado_actual(request)
    funcionario = _funcionario_actual(request)
    if delegado:
        is_delegado = True
        panel_url = reverse('delegado_demo_view')
        delegacion = _delegacion_del_delegado(delegado)
        evidencias = Evidencia.objects.filter(actividad__funcionario__delegacion=delegacion) if delegacion else Evidencia.objects.none()
    elif funcionario:
        is_delegado = False
        panel_url = reverse('funcionario_demo_view')
        evidencias = Evidencia.objects.filter(autor=funcionario)
    else:
        return redirect('main:login_view')
    evidencias = evidencias.select_related('actividad', 'actividad__item', 'autor').prefetch_related(Prefetch(
        'validaciones',
        queryset=Validacion.objects.select_related('verificador').order_by('-fecha'),
    )).order_by('-fecha_carga')
    for evidencia in evidencias:
        evidencia.es_imagen = _es_imagen_previsualizable(evidencia.archivo.name)
        if evidencia.es_imagen:
            evidencia.url_previsualizacion = reverse('evidencia_previsualizacion_view', args=[evidencia.pk])
    return render(request, 'funcionario_demo_app/mis_evidencias.html', {
        'is_delegado': is_delegado,
        'panel_url': panel_url,
        'evidencias': evidencias,
        'funcionario': funcionario,
    })


def actividad_detalle_view(request, actividad_id):
    delegado = _delegado_actual(request)
    funcionario_actual = _funcionario_actual(request)
    actividades = Actividad.objects.select_related('funcionario', 'periodo', 'item')
    if delegado:
        delegacion = _delegacion_del_delegado(delegado)
        if not delegacion:
            raise Http404
        actividades = actividades.filter(funcionario__delegacion=delegacion)
        if request.method == 'POST':
            return HttpResponseForbidden('El Delegado puede consultar la actividad, pero no cargar evidencias por el responsable.')
        puede_adjuntar = False
    elif funcionario_actual:
        actividades = actividades.filter(funcionario=funcionario_actual)
        puede_adjuntar = True
    else:
        return redirect('main:login_view')
    actividad = get_object_or_404(actividades, pk=actividad_id)
    funcionario = actividad.funcionario
    if funcionario_actual:
        tiene_pendiente = actividad.evidencias.filter(estado='pendiente').exists()
        tiene_aprobada = actividad.evidencias.filter(estado='aprobada').exists()
        tiene_correccion = actividad.evidencias.filter(estado__in=('en_correccion', 'rechazada')).exists()
        puede_subir_evidencia = not tiene_pendiente and (not tiene_aprobada or tiene_correccion)
    else:
        puede_subir_evidencia = False
    if request.method == 'POST':
        if not puede_subir_evidencia:
            messages.error(request, 'No puedes enviar otra evidencia mientras exista una pendiente de revisión o aprobada.')
            return redirect('actividad_detalle_view', actividad_id=actividad.id)
        form = EvidenciaForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']
            Evidencia.objects.create(
                actividad=actividad,
                archivo=archivo,
                formato=archivo.name.rsplit('.', 1)[-1].lower()[:10],
                tamanio_bytes=archivo.size,
                autor=funcionario,
                estado='pendiente',
            )
            actividad.estado = 'pendiente'
            actividad.save(update_fields=['estado'])
            notificar_accion_funcionario(
                funcionario.pk,
                f'Enviaste una evidencia para la actividad {actividad.codigo_evidencia}.',
                reverse('mis_evidencias_view'),
                tipo='evidencia',
            )
            messages.success(request, 'La evidencia fue incorporada correctamente.')
            return redirect('actividad_detalle_view', actividad_id=actividad.id)
    else:
        form = EvidenciaForm()
    evidencias = actividad.evidencias.select_related('autor').prefetch_related(Prefetch(
        'validaciones',
        queryset=Validacion.objects.select_related('verificador').order_by('-fecha'),
    )).order_by('-fecha_carga')
    for evidencia in evidencias:
        evidencia.es_imagen = _es_imagen_previsualizable(evidencia.archivo.name)
        if evidencia.es_imagen:
            evidencia.url_previsualizacion = reverse('evidencia_previsualizacion_view', args=[evidencia.pk])
    return render(request, 'funcionario_demo_app/actividad_detalle.html', {
        'actividad': actividad,
        'evidencias': evidencias,
        'form': form,
        'puede_adjuntar': puede_adjuntar,
        'puede_subir_evidencia': puede_subir_evidencia,
        'is_delegado': delegado is not None,
        'panel_url': reverse('delegado_demo_view' if delegado else 'funcionario_demo_view'),
    })


def verificador_evidencias_view(request):
    verificador = _verificador_actual(request)
    if not verificador:
        return redirect('main:login_view')
    evidencias = Evidencia.objects.filter(estado='pendiente').select_related(
        'actividad', 'actividad__funcionario', 'actividad__item', 'autor',
    ).order_by('fecha_carga')
    for evidencia in evidencias:
        evidencia.es_imagen = _es_imagen_previsualizable(evidencia.archivo.name)
        if evidencia.es_imagen:
            evidencia.url_previsualizacion = reverse('evidencia_previsualizacion_view', args=[evidencia.pk])
    return render(request, 'funcionario_demo_app/verificador_evidencias.html', {
        'evidencias': evidencias,
        'verificador': verificador,
    })


def validar_evidencia_view(request, evidencia_id):
    verificador = _verificador_actual(request)
    if not verificador:
        return redirect('main:login_view')
    if request.method != 'POST':
        return redirect('verificador_evidencias_view')
    form = VerificacionEvidenciaForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Para rechazar la evidencia debes escribir una descripción de lo que se debe corregir.')
        return redirect('verificador_evidencias_view')
    with transaction.atomic():
        evidencia = get_object_or_404(
            Evidencia.objects.select_for_update().select_related('actividad'),
            pk=evidencia_id,
            estado='pendiente',
        )
        decision = form.cleaned_data['decision']
        observacion = form.cleaned_data['observacion'].strip()
        Validacion.objects.create(
            evidencia=evidencia,
            verificador=verificador,
            decision=decision,
            observacion=observacion or None,
        )
        evidencia.estado = 'aprobada' if decision == 'aprobada' else 'en_correccion'
        evidencia.save(update_fields=['estado'])
        actividad = evidencia.actividad
        if decision == 'rechazada':
            actividad.estado = 'en_correccion'
            mensaje = 'Evidencia devuelta al funcionario con instrucciones de corrección.'
        else:
            otras_evidencias = actividad.evidencias.exclude(pk=evidencia.pk)
            if otras_evidencias.filter(estado='pendiente').exists():
                actividad.estado = 'pendiente'
            elif otras_evidencias.filter(estado__in=('en_correccion', 'rechazada')).exists():
                actividad.estado = 'en_correccion'
            else:
                actividad.estado = 'validada'
            mensaje = 'Evidencia aprobada correctamente.'
        actividad.save(update_fields=['estado'])
        verificador_nombre = f'{verificador.nombres} {verificador.apellidos}'.strip()
        if decision == 'aprobada':
            aviso_funcionario = f'Tu evidencia {evidencia.actividad.codigo_evidencia} fue revisada y aprobada por {verificador_nombre}.'
        else:
            aviso_funcionario = (
                f'Tu evidencia {evidencia.actividad.codigo_evidencia} fue revisada por {verificador_nombre} '
                f'y requiere corrección: {observacion}'
            )
        notificar(
            evidencia.actividad.funcionario_id,
            aviso_funcionario,
            tipo='evidencia',
            url=reverse('mis_evidencias_view'),
            actor_id=verificador.pk,
        )
        notificar_administradores(
            verificador.pk,
            f'{verificador_nombre} revisó la evidencia de {evidencia.actividad.codigo_evidencia}: {"aprobada" if decision == "aprobada" else "requiere corrección"}.',
            tipo='evidencia',
            url='/administrador/panel/',
        )
    messages.success(request, mensaje)
    return redirect('verificador_evidencias_view')


def evidencia_archivo_view(request, evidencia_id):
    evidencia = get_object_or_404(
        Evidencia.objects.select_related('actividad__funcionario'),
        pk=evidencia_id,
    )
    _autorizar_acceso_evidencia(request, evidencia)
    filename = PurePosixPath(evidencia.archivo.name).name
    return FileResponse(evidencia.archivo.open('rb'), as_attachment=True, filename=filename)


def evidencia_previsualizacion_view(request, evidencia_id):
    evidencia = get_object_or_404(
        Evidencia.objects.select_related('actividad__funcionario'),
        pk=evidencia_id,
    )
    _autorizar_acceso_evidencia(request, evidencia)
    extension = PurePosixPath(evidencia.archivo.name).suffix.lower()
    content_type = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
    }.get(extension)
    if not content_type:
        raise Http404
    response = FileResponse(
        evidencia.archivo.open('rb'),
        as_attachment=False,
        filename=PurePosixPath(evidencia.archivo.name).name,
        content_type=content_type,
    )
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


def _autorizar_acceso_evidencia(request, evidencia):
    role = request.session.get('user_role')
    user_id = request.session.get('user_id')
    is_owner = role == 'FUNCIONARIO' and evidencia.actividad.funcionario_id == user_id
    is_verifier = role == 'VERIFICADOR' and _verificador_actual(request) is not None
    delegado = _delegado_actual(request)
    delegacion = _delegacion_del_delegado(delegado) if delegado else None
    is_delegation_delegate = bool(
        delegacion and evidencia.actividad.funcionario.delegacion_id == delegacion.pk
    )
    if not (is_owner or is_verifier or is_delegation_delegate):
        raise Http404


def _es_imagen_previsualizable(filename):
    return PurePosixPath(filename).suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


def evidencias_json_view(request):
    delegado = _delegado_actual(request)
    funcionario = _funcionario_actual(request)
    if delegado:
        delegacion = _delegacion_del_delegado(delegado)
        evidencias = Evidencia.objects.filter(actividad__funcionario__delegacion=delegacion) if delegacion else Evidencia.objects.none()
    elif funcionario:
        evidencias = Evidencia.objects.filter(actividad__funcionario=funcionario)
    else:
        return JsonResponse({'error': 'Acceso no autorizado.'}, status=403)
    evidencias = evidencias.select_related('actividad').order_by('-fecha_carga')

    return JsonResponse([{
        'nombre': evidencia.actividad.descripcion,
        'codigo': evidencia.actividad.codigo_evidencia,
        'imagen': evidencia.archivo.url if evidencia.archivo else '',
    } for evidencia in evidencias], safe=False)


def registrar_actividad_view(request):
    funcionario = _funcionario_actual(request)
    if funcionario is None:
        return redirect('main:login_view')
    if request.method == 'POST':
        form = ActividadForm(request.POST, request.FILES, funcionario=funcionario)
        if form.is_valid() and funcionario and _periodo_actual():
            with transaction.atomic():
                actividad = form.save(commit=False)
                actividad.funcionario = funcionario
                actividad.periodo = _periodo_actual()
                actividad.codigo_evidencia = _generar_codigo()
                actividad.save()
                archivo = form.cleaned_data.get('evidencia')
                if archivo:
                    Evidencia.objects.create(
                        actividad=actividad,
                        archivo=archivo,
                        formato=archivo.name.rsplit('.', 1)[-1].lower()[:10],
                        tamanio_bytes=archivo.size,
                        autor=funcionario,
                    )
            messages.success(request, f'Actividad {actividad.codigo_evidencia} registrada correctamente.')
            notificar_accion_funcionario(
                funcionario.pk,
                f'Registraste la actividad {actividad.codigo_evidencia}'
                f'{" con evidencia adjunta" if archivo else ""}.',
                reverse('actividad_detalle_view', args=[actividad.pk]),
                tipo='evidencia' if archivo else 'actividad',
            )
            return redirect('actividades_view')
    else:
        form = ActividadForm(funcionario=funcionario)
    return render(request, 'funcionario_demo_app/registrar_actividad.html', {'form': form})


def nuevo_compromiso_view(request):
    funcionario = _funcionario_actual(request)
    if request.method == 'POST':
        form = CompromisoForm(request.POST, funcionario=funcionario)
        if form.is_valid() and funcionario:
            with transaction.atomic():
                compromiso = form.save(commit=False)
                compromiso.responsable = funcionario
                compromiso.save()
                _registrar_cambio_compromiso(
                    compromiso,
                    compromiso.estado,
                    funcionario,
                    'Compromiso registrado por el funcionario.',
                )
            notificar_accion_funcionario(
                funcionario.pk,
                f'Registraste un compromiso para {compromiso.solicitante}.',
                reverse('agenda_colectiva_view'),
                tipo='compromiso',
            )
            messages.success(request, 'Compromiso guardado en la agenda colectiva.')
            return redirect('agenda_colectiva_view')
    else:
        form = CompromisoForm(funcionario=funcionario)
    return render(request, 'funcionario_demo_app/nuevo_compromiso.html', {'form': form, 'funcionario': funcionario})


def _periodo_actual():
    return Periodo.objects.filter(estado='abierto').order_by('-fecha_inicio').first()


def _datos_tubo_delegacion(request, delegacion):
    filters = {
        'q': request.GET.get('q', '').strip(),
        'tipo': request.GET.get('tipo', '').strip(),
        'estado': request.GET.get('estado', '').strip(),
        'territorio': request.GET.get('territorio', '').strip(),
        'desde': request.GET.get('desde', '').strip(),
        'hasta': request.GET.get('hasta', '').strip(),
    }
    active_panel = request.GET.get('panel', '')
    if any(filters.values()) and not active_panel:
        active_panel = 'tubo'
    if active_panel not in {'resumen', 'tubo'}:
        active_panel = 'resumen'

    valid_types = {'compromiso', 'actividad', 'gestion'}
    valid_states = {'ingresado', 'pendiente', 'en_proceso', 'realizado'}
    selected_type = filters['tipo'] if filters['tipo'] in valid_types else ''
    selected_state = filters['estado'] if filters['estado'] in valid_states else ''
    date_from = parse_date(filters['desde'])
    date_to = parse_date(filters['hasta'])
    search_term = filters['q']
    territory_term = filters['territorio']

    commitments = Compromiso.objects.filter(delegacion=delegacion) if delegacion else Compromiso.objects.none()
    activities = Actividad.objects.filter(funcionario__delegacion=delegacion) if delegacion else Actividad.objects.none()
    attentions = AtencionSocial.objects.filter(funcionario__delegacion=delegacion) if delegacion else AtencionSocial.objects.none()

    commitment_rows = commitments
    if selected_type and selected_type != 'compromiso':
        commitment_rows = Compromiso.objects.none()
    else:
        if search_term:
            commitment_rows = commitment_rows.filter(
                Q(solicitante__icontains=search_term)
                | Q(territorio__icontains=search_term)
                | Q(observacion__icontains=search_term)
                | Q(responsable__nombres__icontains=search_term)
                | Q(responsable__apellidos__icontains=search_term)
                | Q(delegacion__nombre__icontains=search_term)
            )
        if territory_term:
            commitment_rows = commitment_rows.filter(
                Q(territorio__icontains=territory_term)
                | Q(delegacion__nombre__icontains=territory_term)
            )
        if selected_state:
            state_map = {
                'ingresado': ('ingresado',),
                'pendiente': ('pendiente', 'revision'),
                'en_proceso': ('en_proceso',),
                'realizado': ('realizado',),
            }
            commitment_rows = commitment_rows.filter(estado__in=state_map[selected_state])
        if date_from:
            commitment_rows = commitment_rows.filter(fecha_registro__date__gte=date_from)
        if date_to:
            commitment_rows = commitment_rows.filter(fecha_registro__date__lte=date_to)
        commitment_rows = commitment_rows.select_related(
            'delegacion', 'persona', 'responsable', 'actividad_origen',
        ).order_by('-fecha_registro')

    activity_rows = activities
    if selected_type and selected_type != 'actividad':
        activity_rows = Actividad.objects.none()
    else:
        if search_term:
            activity_rows = activity_rows.filter(
                Q(descripcion__icontains=search_term)
                | Q(accion__icontains=search_term)
                | Q(contacto_nombre__icontains=search_term)
                | Q(funcionario__nombres__icontains=search_term)
                | Q(funcionario__apellidos__icontains=search_term)
                | Q(item__nombre__icontains=search_term)
            )
        if territory_term:
            activity_rows = activity_rows.filter(funcionario__delegacion__nombre__icontains=territory_term)
        if selected_state:
            state_map = {
                'ingresado': (),
                'pendiente': ('pendiente', 'rechazada'),
                'en_proceso': ('en_correccion',),
                'realizado': ('validada',),
            }
            activity_rows = activity_rows.filter(estado__in=state_map[selected_state])
        if date_from:
            activity_rows = activity_rows.filter(fecha_registro__date__gte=date_from)
        if date_to:
            activity_rows = activity_rows.filter(fecha_registro__date__lte=date_to)
        activity_rows = activity_rows.select_related(
            'funcionario', 'funcionario__delegacion', 'item', 'catalogo_tipo',
        ).order_by('-fecha_registro')

    attention_rows = attentions
    if selected_type and selected_type != 'gestion':
        attention_rows = AtencionSocial.objects.none()
    else:
        if search_term:
            attention_rows = attention_rows.filter(
                Q(solicitante__icontains=search_term)
                | Q(descripcion__icontains=search_term)
                | Q(persona__nombre__icontains=search_term)
                | Q(persona__referencia_anonima__icontains=search_term)
                | Q(funcionario__nombres__icontains=search_term)
                | Q(funcionario__apellidos__icontains=search_term)
                | Q(delegacion__nombre__icontains=search_term)
                | Q(catalogo_tipo__nombre__icontains=search_term)
                | Q(catalogo_subtipo__nombre__icontains=search_term)
            )
        if territory_term:
            attention_rows = attention_rows.filter(delegacion__nombre__icontains=territory_term)
        if selected_state == 'pendiente':
            attention_rows = attention_rows.filter(Q(resultado='') | Q(resultado__isnull=True))
        elif selected_state == 'realizado':
            attention_rows = attention_rows.filter(resultado__gt='')
        elif selected_state in {'ingresado', 'en_proceso'}:
            attention_rows = AtencionSocial.objects.none()
        if date_from:
            attention_rows = attention_rows.filter(fecha_registro__date__gte=date_from)
        if date_to:
            attention_rows = attention_rows.filter(fecha_registro__date__lte=date_to)
        attention_rows = attention_rows.select_related(
            'persona', 'delegacion', 'funcionario', 'funcionario__delegacion',
            'catalogo_tipo', 'catalogo_subtipo', 'actividad',
        ).order_by('-fecha_registro')

    entries = []
    for compromiso in commitment_rows:
        status = 'pendiente' if compromiso.estado == 'revision' else compromiso.estado
        entries.append({
            'id': f'compromiso-{compromiso.pk}',
            'tipo_label': 'Compromiso',
            'title': compromiso.observacion or 'Solicitud de la comunidad',
            'description': compromiso.observacion or 'Sin descripción adicional.',
            'requester': compromiso.solicitante,
            'territory': compromiso.territorio or compromiso.delegacion.nombre,
            'responsible': f'{compromiso.responsable.nombres} {compromiso.responsable.apellidos}'.strip(),
            'requested_at': compromiso.fecha_registro,
            'event_date': None,
            'due_date': compromiso.fecha_comprometida,
            'status': status,
            'original_status': compromiso.get_estado_display(),
            'detail': compromiso.actividad_origen.descripcion if compromiso.actividad_origen_id else '',
            'delegation': compromiso.delegacion.nombre,
        })

    for actividad in activity_rows:
        status = {'pendiente': 'pendiente', 'rechazada': 'pendiente', 'en_correccion': 'en_proceso', 'validada': 'realizado'}.get(actividad.estado, 'ingresado')
        entries.append({
            'id': f'actividad-{actividad.pk}',
            'tipo_label': 'Actividad',
            'title': actividad.accion or actividad.item.nombre,
            'description': actividad.descripcion,
            'requester': actividad.contacto_nombre or 'No informado',
            'territory': actividad.funcionario.delegacion.nombre if actividad.funcionario.delegacion_id else 'Sin territorio',
            'responsible': f'{actividad.funcionario.nombres} {actividad.funcionario.apellidos}'.strip(),
            'requested_at': actividad.fecha_registro,
            'event_date': actividad.fecha_actividad,
            'due_date': None,
            'status': status,
            'original_status': actividad.get_estado_display(),
            'detail': f'{actividad.item.nombre} · {actividad.codigo_evidencia}',
            'delegation': actividad.funcionario.delegacion.nombre if actividad.funcionario.delegacion_id else 'Sin delegación',
        })

    for atencion in attention_rows:
        entries.append({
            'id': f'gestion-{atencion.pk}',
            'tipo_label': 'Gestión social',
            'title': atencion.catalogo_subtipo.nombre if atencion.catalogo_subtipo_id else atencion.catalogo_tipo.nombre,
            'description': atencion.descripcion,
            'requester': atencion.solicitante or atencion.persona.nombre or atencion.persona.referencia_anonima,
            'territory': atencion.delegacion.nombre if atencion.delegacion_id else 'Sin territorio',
            'responsible': f'{atencion.funcionario.nombres} {atencion.funcionario.apellidos}'.strip(),
            'requested_at': atencion.fecha_registro,
            'event_date': atencion.fecha,
            'due_date': None,
            'status': 'realizado' if atencion.resultado else 'pendiente',
            'original_status': 'Con resultado' if atencion.resultado else 'Sin resultado registrado',
            'detail': atencion.resultado or 'Sin resultado o acuerdo registrado.',
            'delegation': atencion.delegacion.nombre if atencion.delegacion_id else 'Sin delegación',
        })

    entries.sort(key=lambda entry: entry['requested_at'], reverse=True)
    status_labels = {'ingresado': 'Ingresado', 'pendiente': 'Pendiente', 'en_proceso': 'En proceso', 'realizado': 'Realizado'}
    status_styles = {
        'ingresado': 'border-gray-300 bg-gray-100',
        'pendiente': 'border-amber-200 bg-amber-50',
        'en_proceso': 'border-sky-200 bg-sky-50',
        'realizado': 'border-emerald-200 bg-emerald-50',
    }
    columns = [
        {'key': status, 'label': label, 'style': status_styles[status], 'entries': [entry for entry in entries if entry['status'] == status]}
        for status, label in status_labels.items()
    ]
    commitment_counts = dict(commitments.values('estado').annotate(total=Count('pk')).values_list('estado', 'total'))
    activity_counts = dict(activities.values('estado').annotate(total=Count('pk')).values_list('estado', 'total'))
    attention_counts = attentions.aggregate(
        realizado=Count('pk', filter=Q(resultado__gt='')),
        pendiente=Count('pk', filter=Q(resultado='') | Q(resultado__isnull=True)),
    )
    summary = {
        'realizado': commitment_counts.get('realizado', 0) + activity_counts.get('validada', 0) + attention_counts['realizado'],
        'en_proceso': commitment_counts.get('en_proceso', 0) + activity_counts.get('en_correccion', 0),
        'pendiente': commitment_counts.get('pendiente', 0) + commitment_counts.get('revision', 0) + activity_counts.get('pendiente', 0) + activity_counts.get('rechazada', 0) + attention_counts['pendiente'],
        'total': sum(commitment_counts.values()) + sum(activity_counts.values()) + attention_counts['realizado'] + attention_counts['pendiente'],
    }
    return {
        'active_dashboard_panel': active_panel,
        'active_section': 'tubo' if active_panel == 'tubo' else 'resumen',
        'backlog_filters': filters,
        'backlog_columns': columns,
        'backlog_total': len(entries),
        'backlog_summary': summary,
        'backlog_type_choices': (('', 'Todos los tipos'), ('compromiso', 'Compromisos'), ('actividad', 'Actividades'), ('gestion', 'Gestiones sociales')),
        'backlog_status_choices': (('', 'Todos los estados'), ('ingresado', 'Ingresado'), ('pendiente', 'Pendiente'), ('en_proceso', 'En proceso'), ('realizado', 'Realizado')),
        'backlog_scope_description': f'Casos registrados en {delegacion.nombre}.' if delegacion else 'No tienes una delegación asignada.',
    }


def _delegacion_del_delegado(delegado):
    return delegado.delegacion or Delegacion.objects.filter(responsable=delegado).first()


def _registrar_cambio_compromiso(compromiso, estado_nuevo, autor, observacion, estado_anterior=None):
    CompromisoEstadoHistorial.objects.create(
        compromiso=compromiso,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        autor=autor,
        observacion=observacion,
    )


def _funcionario_actual(request):
    if request.session.get('user_role') != 'FUNCIONARIO':
        return None
    return Usuario.objects.select_related('cargo', 'delegacion').filter(
        pk=request.session.get('user_id'),
        estado='activo',
    ).first()


def _delegado_actual(request):
    if request.session.get('user_role') != 'DELEGADO':
        return None
    return Usuario.objects.select_related('cargo', 'delegacion').filter(
        pk=request.session.get('user_id'),
        estado='activo',
    ).first()


def _verificador_actual(request):
    if request.session.get('user_role') != 'VERIFICADOR':
        return None
    return Usuario.objects.prefetch_related('roles').filter(
        pk=request.session.get('user_id'),
        estado='activo',
        roles__nombre__icontains='verificador',
    ).first()


def _generar_codigo():
    while True:
        codigo = f'ACT-{secrets.token_hex(4).upper()}'[:12]
        if not Actividad.objects.filter(codigo_evidencia=codigo).exists():
            return codigo
