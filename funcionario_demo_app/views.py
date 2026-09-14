import json
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render


def funcionario_demo_view(request):
    return render(request, 'funcionario_demo_app/funcionario_demo.html')


def actividades_view(request):
    return render(request, 'funcionario_demo_app/actividades.html')


def agenda_colectiva_view(request):
    return render(request, 'funcionario_demo_app/agenda_colectiva.html')


def mis_evidencias_view(request):
    return render(request, 'funcionario_demo_app/mis_evidencias.html')


def evidencias_json_view(request):
    data_path = Path(__file__).resolve().parent / 'templates' / 'funcionario_demo_app' / 'data' / 'evidencias.json'
    with data_path.open('r', encoding='utf-8') as file:
        evidencias = json.load(file)
    return JsonResponse(evidencias, safe=False)


def registrar_actividad_view(request):
    return render(request, 'funcionario_demo_app/registrar_actividad.html')


def nuevo_compromiso_view(request):
    return render(request, 'funcionario_demo_app/nuevo_compromiso.html')
