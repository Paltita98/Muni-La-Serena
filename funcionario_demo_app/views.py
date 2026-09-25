import json
import secrets
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from admin_demo_app.models import Actividad, Compromiso, Evidencia, Meta, Periodo, Usuario

from .forms import ActividadForm, CompromisoForm, EvidenciaForm


def funcionario_demo_view(request):
    funcionario = Usuario.objects.select_related('cargo', 'delegacion').filter(estado='activo').order_by('id').first()
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
    actividades = Actividad.objects.select_related('funcionario').order_by('-fecha_actividad')
    datos = [{
        'id': actividad.id,
        'titulo': actividad.descripcion,
        'codigo': actividad.codigo_evidencia,
        'fecha': actividad.fecha_actividad.strftime('%d/%m/%Y'),
        'estado': actividad.estado,
        'url': reverse('actividad_detalle_view', args=[actividad.id]),
    } for actividad in actividades]
    return render(request, 'funcionario_demo_app/actividades.html', {'actividades_json': datos})


def agenda_colectiva_view(request):
    compromisos = Compromiso.objects.select_related('responsable').order_by('fecha_comprometida')
    datos = [{
        'titulo': compromiso.observacion or compromiso.solicitante,
        'solicitante': compromiso.solicitante,
        'vence': compromiso.fecha_comprometida.strftime('%d/%m/%Y'),
        'estado': compromiso.estado,
    } for compromiso in compromisos]
    return render(request, 'funcionario_demo_app/agenda_colectiva.html', {'compromisos_json': datos})


def mis_evidencias_view(request):
    return render(request, 'funcionario_demo_app/mis_evidencias.html')


def actividad_detalle_view(request, actividad_id):
    actividad = get_object_or_404(
        Actividad.objects.select_related('funcionario', 'periodo', 'item'),
        pk=actividad_id,
    )
    funcionario = actividad.funcionario
    if request.method == 'POST':
        form = EvidenciaForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']
            Evidencia.objects.create(
                actividad=actividad,
                archivo=archivo,
                formato=archivo.name.rsplit('.', 1)[-1].lower()[:10],
                tamanio_bytes=archivo.size,
                autor=funcionario,
            )
            messages.success(request, 'La evidencia fue incorporada correctamente.')
            return redirect('actividad_detalle_view', actividad_id=actividad.id)
    else:
        form = EvidenciaForm()
    return render(request, 'funcionario_demo_app/actividad_detalle.html', {
        'actividad': actividad,
        'evidencias': actividad.evidencias.select_related('autor').order_by('-fecha_carga'),
        'form': form,
    })


def evidencias_json_view(request):
    evidencias = [{
        'nombre': evidencia.actividad.descripcion,
        'codigo': evidencia.actividad.codigo_evidencia,
        'imagen': evidencia.archivo.url if evidencia.archivo else '',
    } for evidencia in Evidencia.objects.select_related('actividad').order_by('-fecha_carga')]
    return JsonResponse(evidencias, safe=False)


def registrar_actividad_view(request):
    funcionario = Usuario.objects.filter(estado='activo').order_by('id').first()
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
            return redirect('actividades_view')
    else:
        form = ActividadForm(funcionario=funcionario)
    return render(request, 'funcionario_demo_app/registrar_actividad.html', {'form': form})


def nuevo_compromiso_view(request):
    funcionario = Usuario.objects.filter(estado='activo').order_by('id').first()
    if request.method == 'POST':
        form = CompromisoForm(request.POST)
        if form.is_valid() and funcionario:
            compromiso = form.save(commit=False)
            compromiso.responsable = funcionario
            compromiso.save()
            messages.success(request, 'Compromiso guardado en la agenda colectiva.')
            return redirect('agenda_colectiva_view')
    else:
        form = CompromisoForm()
    return render(request, 'funcionario_demo_app/nuevo_compromiso.html', {'form': form, 'funcionario': funcionario})


def _periodo_actual():
    return Periodo.objects.filter(estado='abierto').order_by('-fecha_inicio').first()


def _generar_codigo():
    while True:
        codigo = f'ACT-{secrets.token_hex(4).upper()}'[:12]
        if not Actividad.objects.filter(codigo_evidencia=codigo).exists():
            return codigo
