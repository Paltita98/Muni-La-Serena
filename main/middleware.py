from django.shortcuts import redirect


class ForceInitialPasswordChangeMiddleware:
    allowed_paths = {
        '/primer-cambio-password/',
        '/cerrar-sesion/',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.session.get('must_change_password')
            and request.path_info not in self.allowed_paths
            and not request.path_info.startswith('/static/')
        ):
            return redirect('main:primer_cambio_password')
        return self.get_response(request)