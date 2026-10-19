from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase

from .forms import MetaForm, UsuarioForm
from .models import Alerta, Auditoria, Cargo, Compromiso, Delegacion, Periodo, Usuario
from .validators import validate_chilean_rut
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
        form.cleaned_data = {'item': item, 'funcionario': funcionario}
        form._errors = {}

        form.clean()

        self.assertEqual(form.instance.cargo, item_cargo)
        self.assertIn('funcionario', form.errors)
