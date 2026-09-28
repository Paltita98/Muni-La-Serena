from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.hashers import make_password
from django.test import RequestFactory, SimpleTestCase

from admin_demo_app import views as admin_views
from admin_demo_app.models import Usuario
from funcionario_demo_app import views as funcionario_views
from .views import login_view


class LoginSession(dict):
    def cycle_key(self):
        pass


class LoginViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _login(self, role_name):
        user = SimpleNamespace(
            pk=17,
            email='funcionario@muni.cl',
            nombres='Ana',
            apellidos='Pérez',
            password_hash=make_password('ClaveSegura123!'),
            roles=SimpleNamespace(all=lambda: [SimpleNamespace(nombre=role_name)]),
        )
        request = self.factory.post('/', {
            'email': user.email,
            'password': 'ClaveSegura123!',
        })
        request.session = LoginSession()
        user_query = Mock()
        user_query.filter.return_value.first.return_value = user

        with patch.object(Usuario, 'objects') as manager:
            manager.prefetch_related.return_value = user_query
            response = login_view(request)

        return response, request.session

    def test_admin_login_redirects_to_admin_panel(self):
        response, session = self._login('Administrador')

        self.assertEqual(response.url, '/administrador/panel/')
        self.assertEqual(session['user_role'], 'ADMIN')
        self.assertEqual(session['user_id'], 17)
        self.assertEqual(session['user_name'], 'Ana Pérez')

    def test_staff_login_redirects_to_staff_panel(self):
        response, session = self._login('Funcionario')

        self.assertEqual(response.url, '/funcionario/panel/')
        self.assertEqual(session['user_role'], 'FUNCIONARIO')

    def test_invalid_password_does_not_create_authenticated_session(self):
        user = SimpleNamespace(
            password_hash=make_password('OtraClave123!'),
            roles=SimpleNamespace(all=lambda: [SimpleNamespace(nombre='Funcionario')]),
        )
        request = self.factory.post('/', {
            'email': 'funcionario@muni.cl',
            'password': 'incorrecta',
        })
        request.session = LoginSession()
        user_query = Mock()
        user_query.filter.return_value.first.return_value = user

        with (
            patch.object(Usuario, 'objects') as manager,
            patch('main.views.messages.error'),
        ):
            manager.prefetch_related.return_value = user_query
            response = login_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('user_role', request.session)


class FuncionarioPanelTests(SimpleTestCase):
    def test_panel_uses_the_logged_in_staff_account(self):
        funcionario = SimpleNamespace(pk=23, cargo=None, cargo_id=None)
        request = RequestFactory().get('/funcionario/panel/')
        request.session = LoginSession(user_role='FUNCIONARIO', user_id=23)
        user_query = Mock()
        user_query.filter.return_value.first.return_value = funcionario
        activity_query = Mock()
        activity_query.order_by.return_value = []
        commitment_query = Mock()
        commitment_query.order_by.return_value = []

        with (
            patch.object(Usuario, 'objects') as user_manager,
            patch.object(funcionario_views.Actividad, 'objects') as activity_manager,
            patch.object(funcionario_views.Compromiso, 'objects') as commitment_manager,
            patch.object(funcionario_views, '_periodo_actual', return_value=None),
            patch.object(funcionario_views, 'render', return_value='rendered') as render,
        ):
            user_manager.select_related.return_value = user_query
            activity_manager.filter.return_value = activity_query
            commitment_manager.filter.return_value = commitment_query
            response = funcionario_views.funcionario_demo_view(request)

        self.assertEqual(response, 'rendered')
        user_query.filter.assert_called_once_with(pk=23, estado='activo')
        self.assertIs(render.call_args.args[2]['funcionario'], funcionario)

    def test_wrong_role_is_sent_back_to_login(self):
        request = RequestFactory().get('/funcionario/panel/')
        request.session = LoginSession(user_role='ADMIN', user_id=23)

        response = funcionario_views.funcionario_demo_view(request)

        self.assertEqual(response.url, '/login/')


class AdminPanelTests(SimpleTestCase):
    def test_staff_role_is_sent_back_to_login(self):
        request = RequestFactory().get('/administrador/panel/')
        request.session = LoginSession(user_role='FUNCIONARIO', user_id=23)

        response = admin_views.admin_demo_view(request)

        self.assertEqual(response.url, '/login/')