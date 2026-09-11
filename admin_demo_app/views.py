from django.shortcuts import render


def admin_demo_view(request):
    return render(request, 'admin_demo_app/admin_demo.html')
