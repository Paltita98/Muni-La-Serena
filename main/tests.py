from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth.hashers import check_password, make_password
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from admin_demo_app import views as admin_views
from admin_demo_app.models import (
    Actividad,
    AtencionSocial,
    CodigoRecuperacion,
    Compromiso,
    Evidencia,
    Meta,
    Notificacion,
    Periodo,
    Usuario,
)
from funcionario_demo_app import views as funcionario_views
from .context_processors import user_notifications
from .middleware import ForceInitialPasswordChangeMiddleware
from .views import (
    login_view,
    logout_view,
    marcar_notificacion_leida,
    nueva_password,
    organizaciones_comunitarias_dashboard_view,
    primer_cambio_password,
    recuperar_password,
    role_dashboard_view,
)


class LoginSession(dict):
    def cycle_key(self):
        pass

    def flush(self):
        self.clear()
class LoginViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _login(self, role_name, must_change_password=False):
        user = SimpleNamespace(
            pk=17,
            email='funcionario@muni.cl',
            nombres='Ana',
            apellidos='Pérez',
            password_hash=make_password('ClaveSegura123!'),
            debe_cambiar_password=must_change_password,
            roles=SimpleNamespace(all=lambda: [SimpleNamespace(nombre=role_name)]),
        )
        request = self.factory.post('/', {
            'email': user.email,
            'password': 'ClaveSegura123!',
        })
        request.session = LoginSession()
        request._messages = Mock()
        user_query = Mock()
        user_query.filter.return_value.first.return_value = user

        with patch.object(Usuario, 'objects') as manager:
            manager.prefetch_related.return_value = user_query
            response = login_view(request)

        return response, request.session

    def test_admin_login_redirects_to_admin_panel(self):
        with patch('main.views.messages.success') as success:
            response, session = self._login('Administrador')

        self.assertEqual(response.url, '/administrador/panel/')
        self.assertEqual(session['user_role'], 'ADMIN')
        self.assertEqual(session['user_id'], 17)
        self.assertEqual(session['user_name'], 'Ana Pérez')
        self.assertIn('Bienvenido/a, Ana Pérez.', success.call_args.args[1])

    def test_first_login_redirects_to_required_password_change(self):
        response, session = self._login('Administrador', must_change_password=True)

        self.assertEqual(response.url, '/primer-cambio-password/')
        self.assertTrue(session['must_change_password'])

    def test_staff_login_redirects_to_staff_panel(self):
        response, session = self._login('Funcionario')

        self.assertEqual(response.url, '/funcionario/panel/')
        self.assertEqual(session['user_role'], 'FUNCIONARIO')

    def test_delegate_login_redirects_to_delegate_panel(self):
        response, session = self._login('Delegado')

        self.assertEqual(response.url, '/funcionario/delegado/panel/')
        self.assertEqual(session['user_role'], 'DELEGADO')

    def test_community_organizations_login_redirects_to_dashboard(self):
        response, session = self._login('Organizaciones Comunitarias')

        self.assertEqual(response.url, '/organizaciones-comunitarias/panel/')
        self.assertEqual(session['user_role'], 'ORGANIZACIONES_COMUNITARIAS')

    def test_community_organizations_dashboard_renders_for_role(self):
        request = self.factory.get('/organizaciones-comunitarias/panel/')
        request.session = LoginSession(user_role='ORGANIZACIONES_COMUNITARIAS', user_name='Ana Pérez')
        organizaciones = MagicMock()
        organizaciones.count.return_value = 0
        organizaciones.aggregate.return_value = {'total': None}
        organizaciones.exclude.return_value = organizaciones
        organizaciones.values.return_value = organizaciones
        organizaciones.distinct.return_value = organizaciones
        organizaciones.__getitem__.return_value = []

        with patch('main.views.OrganizacionJJVV.objects') as manager:
            manager.order_by.return_value = organizaciones
            response = organizaciones_comunitarias_dashboard_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Organizaciones Comunitarias')
        self.assertContains(response, 'Registro y acompañamiento de OOCC')

    def test_verifier_login_redirects_to_evidence_review(self):
        response, session = self._login('Verificador')

        self.assertEqual(response.url, '/funcionario/verificador/evidencias/')
        self.assertEqual(session['user_role'], 'VERIFICADOR')

    def test_coordinator_login_redirects_to_role_dashboard(self):
        response, session = self._login('Coordinador')

        self.assertEqual(response.url, '/panel-rol/')
        self.assertEqual(session['user_role'], 'COORDINADOR')

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
        request._messages = Mock()
        query = Mock()
        query.filter.return_value.first.return_value = user
        with (
            patch.object(Usuario, 'objects') as manager,
            patch('main.views.messages.success'),
        ):
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
        request._messages = []
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
        request._messages = Mock()

        with patch('main.views.messages.success'):
            response = logout_view(request)

        self.assertEqual(response.url, '/login/')
        self.assertEqual(request.session, {})

    def test_logout_rejects_get_requests(self):
        response = self.client.get('/cerrar-sesion/')

        self.assertEqual(response.status_code, 405)


class CoordinatorDashboardTests(SimpleTestCase):
    def test_coordinator_receives_cross_functional_metrics_and_goal_progress(self):
        request = RequestFactory().get('/panel-rol/')
        request.session = LoginSession(user_role='COORDINADOR', user_id=17)
        user = SimpleNamespace(nombres='Ana', apellidos='Pérez')
        active_period = SimpleNamespace(
            fecha_inicio=timezone.localdate().replace(day=1),
            fecha_termino=timezone.localdate(),
        )
        item = SimpleNamespace(
            nombre='Casos sociales',
            unidad='casos',
            cargo=SimpleNamespace(nombre='Atención Social'),
        )
        meta = SimpleNamespace(
            item_id=3,
            item=item,
            valor_objetivo=10,
            ponderador_pct=40,
        )

        user_lookup = Mock()
        user_lookup.first.return_value = user
        active_staff = Mock()
        active_staff.count.return_value = 12
        user_manager = Mock()
        user_manager.filter.side_effect = [user_lookup, active_staff]

        period_manager = Mock()
        period_manager.filter.return_value.order_by.return_value.first.return_value = active_period

        activities_for_period = Mock()
        activities_for_period.count.return_value = 8
        activities_for_period.filter.return_value.count.return_value = 2
        activities_for_period.filter.return_value.select_related.return_value.order_by.return_value = [SimpleNamespace(
            descripcion='Operativo de limpieza pendiente',
            accion='Limpieza comunitaria',
            funcionario=SimpleNamespace(
                nombres='Ana',
                apellidos='Soto',
                delegacion_id=9,
                delegacion=SimpleNamespace(nombre='Las Compañías'),
            ),
            fecha_registro=timezone.now(),
        )]
        validated_activities = Mock()
        validated_activities.values.return_value.annotate.return_value.values_list.return_value = [(3, 6)]
        activity_manager = Mock()
        activity_manager.filter.side_effect = [activities_for_period, validated_activities]

        attention_manager = Mock()
        attention_manager.filter.return_value.count.return_value = 5
        attention_manager.all.return_value.select_related.return_value.order_by.return_value = []
        attention_manager.aggregate.return_value = {'realizado': 4, 'pendiente': 5}

        open_commitments = Mock()
        open_commitments.count.return_value = 4
        overdue = Mock(count=Mock(return_value=1))
        overdue.select_related.return_value.order_by.return_value = [SimpleNamespace(
            observacion='Reparar luminaria',
            solicitante='Junta de Vecinos Centro',
            delegacion=SimpleNamespace(nombre='Centro'),
            responsable=SimpleNamespace(nombres='Luis', apellidos='Pérez'),
            fecha_comprometida=date(2026, 11, 1),
        )]
        due_soon = Mock(count=Mock(return_value=2))
        open_commitments.filter.side_effect = [overdue, due_soon]
        commitment_manager = Mock()
        commitment_manager.all.return_value.exclude.return_value = open_commitments
        commitment_manager.all.return_value.select_related.return_value.order_by.return_value = []
        commitment_manager.none.return_value = []
        commitment_manager.values.return_value.annotate.return_value.values_list.return_value = [
            ('realizado', 1), ('en_proceso', 2), ('revision', 1),
        ]

        activity_manager.all.return_value.select_related.return_value.order_by.return_value = []
        activity_manager.none.return_value = []
        activity_manager.values.return_value.annotate.return_value.values_list.return_value = [
            ('validada', 2), ('en_correccion', 1), ('pendiente', 3),
        ]

        evidence_manager = Mock()
        evidence_manager.filter.return_value.count.return_value = 3
        evidence_manager.filter.return_value.select_related.return_value.order_by.return_value = [SimpleNamespace(
            actividad=SimpleNamespace(
                descripcion='Reunión vecinal',
                codigo_evidencia='ACT-0001',
                funcionario=SimpleNamespace(nombres='Ana', apellidos='Soto'),
            ),
            autor=SimpleNamespace(nombres='Ana', apellidos='Soto'),
            fecha_carga=timezone.now(),
        )]

        metas_query = Mock()
        metas_query.select_related.return_value.order_by.return_value = [meta]
        meta_manager = Mock()
        meta_manager.filter.return_value = metas_query

        with (
            patch.object(Usuario, 'objects', user_manager),
            patch.object(Periodo, 'objects', period_manager),
            patch.object(Actividad, 'objects', activity_manager),
            patch.object(AtencionSocial, 'objects', attention_manager),
            patch.object(Compromiso, 'objects', commitment_manager),
            patch.object(Evidencia, 'objects', evidence_manager),
            patch.object(Meta, 'objects', meta_manager),
            patch('main.views.render', return_value='rendered') as render,
        ):
            response = role_dashboard_view(request)

        self.assertEqual(response, 'rendered')
        self.assertEqual(render.call_args.args[1], 'main/coordinador_dashboard.html')
        context = render.call_args.args[2]
        self.assertEqual(context['active_staff'], 12)
        self.assertEqual(context['activity_total'], 8)
        self.assertEqual(context['attention_total'], 5)
        self.assertEqual(context['commitment_overdue'], 1)
        self.assertEqual(context['evidence_pending'], 3)
        self.assertEqual(context['indicator_rows'][0]['progress_label'], '60%')
        self.assertEqual(context['alerts'][0]['items'][0]['name'], 'Reparar luminaria')
        self.assertEqual(context['alerts'][1]['items'][0]['name'], 'Operativo de limpieza pendiente')
        self.assertEqual(context['alerts'][2]['items'][0]['name'], 'Reunión vecinal')
        self.assertEqual(context['backlog_total'], 0)
        self.assertEqual(context['backlog_summary'], {
            'realizado': 7,
            'en_proceso': 3,
            'pendiente': 9,
            'total': 19,
        })

    def test_other_roles_cannot_open_coordinator_dashboard(self):
        request = RequestFactory().get('/panel-rol/')
        request.session = LoginSession(user_role='FUNCIONARIO', user_id=17)

        response = role_dashboard_view(request)

        self.assertEqual(response.url, '/login/')


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


class InitialPasswordChangeTests(SimpleTestCase):
    def test_middleware_blocks_routes_until_password_change(self):
        request = RequestFactory().get('/administrador/panel/')
        request.session = LoginSession(must_change_password=True)
        get_response = Mock(return_value='view response')

        response = ForceInitialPasswordChangeMiddleware(get_response)(request)

        self.assertEqual(response.url, '/primer-cambio-password/')
        get_response.assert_not_called()

    def test_password_change_updates_hash_and_releases_session(self):
        user = SimpleNamespace(
            debe_cambiar_password=True,
            password_hash=make_password('Temporal123!'),
            save=Mock(),
        )
        request = RequestFactory().post('/primer-cambio-password/', {
            'nueva_password': 'PersonalSegura456!',
            'confirmar_password': 'PersonalSegura456!',
        })
        request.session = LoginSession(
            user_id=17,
            user_role='ADMIN',
            must_change_password=True,
        )
        request._messages = Mock()

        with (
            patch('main.views._usuario_sesion_activo', return_value=user),
            patch('main.views.messages.success'),
        ):
            response = primer_cambio_password(request)

        self.assertEqual(response.url, '/administrador/panel/')
        self.assertTrue(check_password('PersonalSegura456!', user.password_hash))
        self.assertFalse(user.debe_cambiar_password)
        self.assertNotIn('must_change_password', request.session)

    def test_password_change_rejects_the_temporary_password(self):
        temporary_password = 'Temporal123!'
        user = SimpleNamespace(
            debe_cambiar_password=True,
            password_hash=make_password(temporary_password),
            save=Mock(),
        )
        request = RequestFactory().post('/primer-cambio-password/', {
            'nueva_password': temporary_password,
            'confirmar_password': temporary_password,
        })
        request.session = LoginSession(user_id=17, user_role='ADMIN', must_change_password=True)
        request._messages = Mock()

        with (
            patch('main.views._usuario_sesion_activo', return_value=user),
            patch('main.views.messages.error') as error,
            patch('main.views.render', return_value='rendered'),
        ):
            response = primer_cambio_password(request)

        self.assertEqual(response, 'rendered')
        user.save.assert_not_called()
        self.assertTrue(request.session['must_change_password'])
        error.assert_called_once()

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
        user = SimpleNamespace(password_hash='', debe_cambiar_password=False, save=Mock())
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
        user.save.assert_called_once_with(update_fields=['password_hash', 'debe_cambiar_password'])
        challenge.delete.assert_called_once_with()
        self.assertNotIn('reset_user_id', request.session)


class NotificationTests(SimpleTestCase):
    def test_staff_notification_context_hides_admin_changes_and_unread_count(self):
        operational_notification = SimpleNamespace(tipo='evidencia')
        notifications_query = MagicMock()
        notifications_query.exclude.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [
            operational_notification,
        ]
        unread_query = Mock()
        unread_query.exclude.return_value.count.return_value = 1
        manager = Mock()
        manager.filter.side_effect = [notifications_query, unread_query]
        request = RequestFactory().get('/')
        request.session = {'user_id': 17, 'user_role': 'FUNCIONARIO'}

        with patch.object(Notificacion, 'objects', manager):
            context = user_notifications(request)

        notifications_query.exclude.assert_called_once_with(tipo='administracion')
        unread_query.exclude.assert_called_once_with(tipo='administracion')
        self.assertEqual(context['user_notifications'], [operational_notification])
        self.assertEqual(context['unread_notifications_count'], 1)

    def test_admin_notification_context_keeps_admin_changes(self):
        notifications_query = MagicMock()
        notifications_query.select_related.return_value.order_by.return_value.__getitem__.return_value = []
        unread_query = Mock()
        unread_query.count.return_value = 0
        manager = Mock()
        manager.filter.side_effect = [notifications_query, unread_query]
        request = RequestFactory().get('/')
        request.session = {'user_id': 1, 'user_role': 'ADMIN'}

        with patch.object(Notificacion, 'objects', manager):
            user_notifications(request)

        notifications_query.exclude.assert_not_called()
        unread_query.exclude.assert_not_called()

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