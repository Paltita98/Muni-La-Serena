from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.hashers import check_password, make_password
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from admin_demo_app import views as admin_views
from admin_demo_app.models import CodigoRecuperacion, Notificacion, Usuario
from funcionario_demo_app import views as funcionario_views
from .context_processors import user_notifications
from .views import login_view, marcar_notificacion_leida, nueva_password, recuperar_password


class LoginSession(dict):
    def cycle_key(self):
        pass

    def flush(self):
        self.clear()
from .views import login_view, logout_view, nueva_password, recuperar_password


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

    def test_verifier_login_redirects_to_evidence_review(self):
        response, session = self._login('Verificador')

        self.assertEqual(response.url, '/funcionario/verificador/evidencias/')
        self.assertEqual(session['user_role'], 'VERIFICADOR')

    def test_login_accepts_institutional_identifier(self):
        user = SimpleNamespace(
            pk=29,
            email='admin@muni.cl',
            identificador_inst='ADMIN-029',
            nombres='Ana',
            apellidos='Pérez',
            password_hash=make_password('ClaveSegura123!'),
            roles=SimpleNamespace(all=lambda: [SimpleNamespace(nombre='Administrador')]),
        )
        request = self.factory.post('/', {'username': user.identificador_inst, 'password': 'ClaveSegura123!'})
        request.session = LoginSession()
        query = Mock()
        query.filter.return_value.first.return_value = user
        with patch.object(Usuario, 'objects') as manager:
            manager.prefetch_related.return_value = query
            response = login_view(request)
        self.assertEqual(response.url, '/administrador/panel/')

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

    def test_logout_flushes_session_and_redirects_to_login(self):
        request = self.factory.post('/cerrar-sesion/')
        request.session = LoginSession(user_id=4, user_role='ADMIN')

        response = logout_view(request)

        self.assertEqual(response.url, '/login/')
        self.assertEqual(request.session, {})

    def test_logout_rejects_get_requests(self):
        response = self.client.get('/cerrar-sesion/')

        self.assertEqual(response.status_code, 405)


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


class PasswordResetTests(SimpleTestCase):
    def test_recovery_for_unknown_email_uses_generic_verification_step(self):
        request = RequestFactory().post('/recuperar-password/', {'email': 'persona@ejemplo.com'})
        request.session = LoginSession()
        manager = Mock()
        manager.filter.return_value.first.return_value = None

        with (
            patch.object(Usuario, 'objects', manager),
            patch('main.views.messages.success') as success,
        ):
            response = recuperar_password(request)

        self.assertEqual(response.url, '/validar-codigo/')
        self.assertEqual(request.session['reset_email_mask'], 'p****@ejemplo.com')
        self.assertNotIn('persona@ejemplo.com', success.call_args.args[1])

    def test_recovery_for_known_email_uses_same_verification_step(self):
        user = SimpleNamespace(pk=3, email='persona@ejemplo.com')
        manager = Mock()
        manager.filter.return_value.first.return_value = user
        request = RequestFactory().post('/recuperar-password/', {'email': user.email})
        request.session = LoginSession()

        with (
            patch.object(Usuario, 'objects', manager),
            patch('main.views._emitir_codigo_recuperacion') as emit,
            patch('main.views.messages.success'),
        ):
            response = recuperar_password(request)

        self.assertEqual(response.url, '/validar-codigo/')
        emit.assert_called_once_with(request, user)
        self.assertEqual(request.session['reset_email_mask'], 'p****@ejemplo.com')

    def test_validated_reset_persists_a_hashed_password_and_consumes_code(self):
        user = SimpleNamespace(password_hash='', save=Mock())
        challenge = SimpleNamespace(
            usuario=user,
            expira=timezone.now() + timedelta(minutes=5),
            delete=Mock(),
        )
        manager = Mock()
        manager.filter.return_value.order_by.return_value.first.return_value = challenge
        request = RequestFactory().post('/nueva-password/', {
            'nueva_password': 'MuySeguraClave482!',
            'confirmar_password': 'MuySeguraClave482!',
        })
        request.session = LoginSession(reset_user_id=12, codigo_validado=True)

        with (
            patch.object(CodigoRecuperacion, 'objects', manager),
            patch('main.views.messages.success'),
        ):
            response = nueva_password(request)

        self.assertEqual(response.url, '/login/')
        self.assertTrue(check_password('MuySeguraClave482!', user.password_hash))
        user.save.assert_called_once_with(update_fields=['password_hash'])
        challenge.delete.assert_called_once_with()
        self.assertNotIn('reset_user_id', request.session)


class NotificationTests(SimpleTestCase):
    def test_marking_notification_read_only_loads_the_current_recipients_record(self):
        user = SimpleNamespace(pk=17)
        notification = SimpleNamespace(leida=None, url='/funcionario/evidencias/', save=Mock())
        user_manager = Mock()
        user_manager.filter.return_value.first.return_value = user
        request = RequestFactory().post('/notificaciones/5/leer/', HTTP_HOST='testserver')
        request.session = LoginSession(user_id=17)

        with (
            patch.object(Usuario, 'objects', user_manager),
            patch('main.views.get_object_or_404', return_value=notification) as get_notification,
        ):
            response = marcar_notificacion_leida(request, 5)

        self.assertEqual(response.url, notification.url)
        self.assertIsNotNone(notification.leida)
        notification.save.assert_called_once_with(update_fields=['leida'])
        get_notification.assert_called_once_with(Notificacion, pk=5, destinatario=user)

    def test_anonymous_request_gets_empty_notification_context(self):
        request = RequestFactory().get('/')
        request.session = {}

        self.assertEqual(
            user_notifications(request),
            {'user_notifications': [], 'unread_notifications_count': 0},
        )