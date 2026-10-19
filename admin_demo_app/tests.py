from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase

from .forms import MetaForm, UsuarioForm
from .models import Alerta, Auditoria, Cargo, Compromiso, Delegacion, Periodo, Usuario
from .validators import validate_chilean_rut
from .views import admin_dashboard_view, gestionar_meta_view


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


class UserInputValidationTests(SimpleTestCase):
    def test_valid_chilean_rut_is_accepted(self):
        validate_chilean_rut('19864005-0')

    def test_invalid_rut_check_digit_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_chilean_rut('19864005-1')

    def test_user_form_exposes_rut_format_hint(self):
        form = UsuarioForm()

        self.assertEqual(form.fields['identificador_inst'].widget.attrs['pattern'], '[0-9]{7,8}-[0-9kK]')
        self.assertEqual(form.fields['email'].widget.input_type, 'email')

    def test_password_requires_minimum_length_uppercase_and_special_character(self):
        validate_password('Clave123!')

        for password in ('Corta1!', 'clave123!', 'Clave1234'):
            with self.subTest(password=password), self.assertRaises(ValidationError):
                validate_password(password)


class MetaFormTests(SimpleTestCase):
    def test_cargo_and_unit_are_not_editable_meta_fields(self):
        form = MetaForm()

        self.assertNotIn('cargo', form.fields)
        self.assertNotIn('unidad', form.fields)
        self.assertIn('cargo_mostrado', form.fields)
        self.assertIn('unidad_mostrada', form.fields)
        self.assertTrue(form.fields['cargo_mostrado'].disabled)
        self.assertTrue(form.fields['unidad_mostrada'].disabled)

    def test_meta_inherits_item_cargo_and_rejects_other_cargo_official(self):
        item_cargo = Cargo(pk=3)
        item = SimpleNamespace(cargo=item_cargo, cargo_id=3)
        funcionario = SimpleNamespace(cargo_id=8)
        form = MetaForm()
        form.cleaned_data = {'item': item, 'funcionarios': [funcionario]}
        form._errors = {}

        form.clean()

        self.assertEqual(form.instance.cargo, item_cargo)
        self.assertIn('funcionarios', form.errors)


class AdminExportTemplateTests(SimpleTestCase):
    def test_each_admin_listing_exports_visible_data_without_actions(self):
        template_path = Path(__file__).parent / 'templates' / 'admin_demo_app' / 'admin_listado.html'
        template = template_path.read_text(encoding='utf-8')

        self.assertIn('data-export-table="table-', template)
        self.assertIn('data-has-actions=', template)
        self.assertIn("tr[data-filter-row]:not([hidden])", template)
        self.assertIn('XLSX.writeFile', template)

    def test_meta_form_supports_multiple_officials(self):
        form = MetaForm()

        self.assertIsInstance(form.fields['funcionarios'], forms.ModelMultipleChoiceField)
        self.assertNotIn('funcionario', form.fields)

    def test_editing_existing_meta_rejects_multiple_officials(self):
        form = MetaForm()
        form.instance.pk = 12
        form.cleaned_data = {
            'item': SimpleNamespace(cargo=Cargo(pk=3), cargo_id=3),
            'funcionarios': [SimpleNamespace(cargo_id=3), SimpleNamespace(cargo_id=3)],
        }
        form._errors = {}

        form.clean()

        self.assertIn('funcionarios', form.errors)

    def test_duplicate_active_meta_for_official_is_rejected(self):
        cargo = Cargo(pk=3)
        item = SimpleNamespace(cargo=cargo, cargo_id=3)
        official = SimpleNamespace(pk=5, cargo_id=3, __str__=lambda self: 'Ana Pérez')
        form = MetaForm()
        form.cleaned_data = {
            'item': item,
            'periodo': SimpleNamespace(pk=1),
            'funcionarios': [official],
        }
        form._errors = {}
        duplicate_query = Mock()
        duplicate_query.exists.return_value = True

        with patch('admin_demo_app.forms.Meta.objects.filter', return_value=duplicate_query):
            form.clean()

        self.assertIn('funcionarios', form.errors)

    def test_creating_meta_assigns_individual_copy_to_each_selected_official(self):
        cargo = Cargo(pk=3)
        item = SimpleNamespace(nombre='Visitas', cargo=cargo)
        officials = [
            SimpleNamespace(pk=5, cargo_id=3),
            SimpleNamespace(pk=6, cargo_id=3),
        ]
        period = SimpleNamespace(pk=1)
        meta_base = SimpleNamespace(
            pk=None,
            item=item,
            periodo=period,
            valor_objetivo=10,
            ponderador_pct=100,
            umbral_minimo_pct=80,
            maximo_computable_pct=150,
            vigente=True,
            save=Mock(),
        )
        form = Mock()
        form.is_valid.return_value = True
        form.cleaned_data = {'funcionarios': officials}
        form.save.return_value = meta_base
        request = RequestFactory().post('/administrador/metas/nueva/')
        request.session = {'user_role': 'ADMIN', 'user_id': 1}
        copies = []

        def create_meta(**kwargs):
            copy = SimpleNamespace(item=kwargs['item'], funcionario=kwargs['funcionario'])
            copies.append(copy)
            return copy

        with (
            patch('admin_demo_app.views._admin_access', return_value=None),
            patch('admin_demo_app.views.MetaForm', return_value=form),
            patch('admin_demo_app.views.get_object_or_404', return_value=SimpleNamespace(pk=1)),
            patch('admin_demo_app.views.Meta.objects') as meta_manager,
            patch('admin_demo_app.views.transaction.atomic'),
            patch('admin_demo_app.views.notificar_administradores'),
            patch('admin_demo_app.views.notificar_asignados_meta'),
            patch('admin_demo_app.views.messages.success') as success,
            patch('admin_demo_app.views.redirect', return_value='redirect'),
        ):
            meta_manager.create.side_effect = create_meta
            response = gestionar_meta_view(request)

        self.assertEqual(response, 'redirect')
        self.assertEqual(meta_base.funcionario, officials[0])
        self.assertEqual([copy.funcionario for copy in copies], [officials[1]])
        self.assertEqual(meta_manager.create.call_count, 1)
        self.assertIn('2 funcionarios', success.call_args.args[1])

    def test_invalid_meta_does_not_report_success(self):
        form = Mock()
        form.is_valid.return_value = False
        request = RequestFactory().post('/administrador/metas/nueva/')
        request.session = {'user_role': 'ADMIN', 'user_id': 1}

        with (
            patch('admin_demo_app.views._admin_access', return_value=None),
            patch('admin_demo_app.views.MetaForm', return_value=form),
            patch('admin_demo_app.views.messages.success') as success,
            patch('admin_demo_app.views.render', return_value=object()),
        ):
            gestionar_meta_view(request)

        success.assert_not_called()

    def test_meta_database_failure_does_not_report_success(self):
        meta_base = SimpleNamespace(
            pk=None,
            item=SimpleNamespace(cargo=SimpleNamespace(pk=3)),
            save=Mock(side_effect=RuntimeError('database unavailable')),
        )
        form = Mock()
        form.is_valid.return_value = True
        form.cleaned_data = {'funcionarios': []}
        form.save.return_value = meta_base
        request = RequestFactory().post('/administrador/metas/nueva/')
        request.session = {'user_role': 'ADMIN', 'user_id': 1}

        with (
            patch('admin_demo_app.views._admin_access', return_value=None),
            patch('admin_demo_app.views.MetaForm', return_value=form),
            patch('admin_demo_app.views.get_object_or_404', return_value=SimpleNamespace(pk=1)),
            patch('admin_demo_app.views.transaction.atomic'),
            patch('admin_demo_app.views.messages.success') as success,
            self.assertRaisesRegex(RuntimeError, 'database unavailable'),
        ):
            gestionar_meta_view(request)

        success.assert_not_called()
