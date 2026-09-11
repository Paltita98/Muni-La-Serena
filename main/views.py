from django.shortcuts import render


def funcionario_demo(request):
    return render(request, 'funcionario_demo.html')


def admin_demo(request):
    return render(request, 'admin_demo.html')


def registrar_actividad(request):
    return render(request, 'registrar_actividad.html')


def nuevo_compromiso(request):
    return render(request, 'nuevo_compromiso.html')
