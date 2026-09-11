from django.shortcuts import render


def funcionario_demo_view(request):
    return render(request, 'funcionario_demo_app/funcionario_demo.html')


def actividades_view(request):
    return render(request, 'funcionario_demo_app/actividades.html')


def agenda_colectiva_view(request):
    return render(request, 'funcionario_demo_app/agenda_colectiva.html')


def mis_evidencias_view(request):
    return render(request, 'funcionario_demo_app/mis_evidencias.html')


def registrar_actividad_view(request):
    return render(request, 'funcionario_demo_app/registrar_actividad.html')


def nuevo_compromiso_view(request):
    return render(request, 'funcionario_demo_app/nuevo_compromiso.html')
