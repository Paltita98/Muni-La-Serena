from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from .models import Alerta, Auditoria, Compromiso, Delegacion, Periodo, Usuario
from .views import admin_dashboard_view


class AdminDashboardTests(SimpleTestCase):
    def test_dashboard_shows_real_delegation_details(self):
        delegacion = SimpleNamespace(nombre='Delegación Norte', ambito='Sector norte')

        periodo_manager = Mock()
        periodo_manager.filter.return_value.order_by.return_value.first.return_value = None

        delegacion_manager = Mock()
        delegacion_manager.filter.return_value.order_by.return_value = [delegacion]

        usuario_manager = Mock()
        usuario_manager.filter.side_effect = [
            Mock(count=Mock(return_value=3)),
            Mock(count=Mock(return_value=7)),
        ]

        compromiso_manager = Mock()
        compromiso_manager.filter.return_value.count.return_value = 5

        alerta_manager = Mock()
        alerta_manager.filter.return_value.count.return_value = 2

        auditoria_manager = Mock()
        auditoria_manager.select_related.return_value.order_by.return_value = []

        with (
            patch.object(Periodo, 'objects', periodo_manager),
            patch.object(Delegacion, 'objects', delegacion_manager),
            patch.object(Usuario, 'objects', usuario_manager),
            patch.object(Compromiso, 'objects', compromiso_manager),
            patch.object(Alerta, 'objects', alerta_manager),
            patch.object(Auditoria, 'objects', auditoria_manager),
            patch('admin_demo_app.views.render', return_value=object()) as render,
        ):
            response = admin_dashboard_view(RequestFactory().get('/admin-demo/'))

        context = render.call_args.args[2]
        self.assertIsNotNone(response)
        self.assertEqual(context['delegaciones_dashboard'], [delegacion])
        self.assertEqual(delegacion.funcionarios_count, 3)
        self.assertEqual(delegacion.compromisos_count, 5)
