from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from admin_demo_app.models import Actividad, AtencionSocial, CatalogoTipo, Meta, PersonaUsuaria, Usuario
from .forms import AtencionSocialForm
from .views import _calcular_metricas_funcionario, atenciones_sociales_view, nueva_atencion_social_view


class MetricasFuncionarioTests(SimpleTestCase):
    def calcular_metricas(self, avance):
        funcionario = SimpleNamespace(pk=1, cargo_id=2, cargo=SimpleNamespace(pk=2))
        periodo = SimpleNamespace(
            fecha_inicio=date(2026, 1, 1),
            fecha_termino=date(2026, 1, 30),
            dias_computables=22,
        )
        item = SimpleNamespace(pk=3)
        meta = SimpleNamespace(
            item_id=item.pk,
            item=item,
            ponderador_pct=Decimal('100'),
            valor_objetivo=Decimal('10'),
            maximo_computable_pct=Decimal('150'),
            umbral_minimo_pct=Decimal('80'),
        )
        meta_query = Mock()
        meta_query.filter.return_value = meta_query
        meta_query.select_related.return_value = meta_query
        meta_query.order_by.return_value = [meta]
        actividad_query = Mock()
        actividad_query.values_list.return_value.annotate.return_value = [(item.pk, avance)]
        actividad_manager = Mock(filter=Mock(return_value=actividad_query))

        with (
            patch.object(Meta, 'objects', Mock(filter=Mock(return_value=meta_query))),
            patch.object(Actividad, 'objects', actividad_manager),
        ):
            metricas = _calcular_metricas_funcionario(
                funcionario,
                periodo,
                fecha_actual=date(2026, 1, 15),
            )
        self.assertEqual(
            actividad_manager.filter.call_args.kwargs['fecha_actividad__range'],
            (periodo.fecha_inicio, date(2026, 1, 15)),
        )
        return metricas

    def test_calculates_expected_progress_and_red_semaphore(self):
        metricas = self.calcular_metricas(avance=2)

        self.assertEqual(metricas['avance_real_pct'], Decimal('20.00'))
        self.assertEqual(metricas['meta_esperada_pct'], Decimal('50.00'))
        self.assertEqual(metricas['semaforo'], 'rojo')

    def test_green_semaphore_when_progress_reaches_daily_expectation(self):
        metricas = self.calcular_metricas(avance=6)

        self.assertEqual(metricas['avance_real_pct'], Decimal('60.00'))
        self.assertEqual(metricas['semaforo'], 'verde')


class ActividadesTemplateTests(SimpleTestCase):
    def test_history_renders_validated_activities(self):
        template_path = Path(__file__).parent / 'templates' / 'funcionario_demo_app' / 'actividades.html'
        template = template_path.read_text(encoding='utf-8')

        self.assertIn('<option value="validada">Validada</option>', template)
        self.assertIn("validada: { label: 'Validada', className: 'success' }", template)


class AgendaTemplateTests(SimpleTestCase):
    def test_history_renders_new_commitments(self):
        template_path = Path(__file__).parent / 'templates' / 'funcionario_demo_app' / 'agenda_colectiva.html'
        template = template_path.read_text(encoding='utf-8')

        self.assertIn('<option value="ingresado">Ingresado</option>', template)
        self.assertIn("ingresado: { label: 'Ingresado', className: 'info' }", template)


class AtencionesSocialesViewTests(SimpleTestCase):
    def test_view_lists_social_attention_for_active_staff_member(self):
        funcionario = SimpleNamespace(pk=4)
        catalogo_tipo = SimpleNamespace(
            nombre='Orientación familiar',
            categoria='atencion',
            get_categoria_display=lambda: 'Atención',
        )
        actividad = SimpleNamespace(pk=12, descripcion='Acompañamiento social')
        atencion = SimpleNamespace(
            persona=SimpleNamespace(referencia_anonima='CASO-001'),
            catalogo_tipo=catalogo_tipo,
            orden_gestion=1,
            fecha=date(2026, 9, 25),
            resultado='Derivación realizada',
            actividad=actividad,
            actividad_id=actividad.pk,
        )
        usuario_query = Mock()
        usuario_query.order_by.return_value.first.return_value = funcionario
        atencion_query = Mock()
        atencion_query.select_related.return_value.order_by.return_value = [atencion]

        with (
            patch.object(Usuario, 'objects', Mock(filter=Mock(return_value=usuario_query))),
            patch.object(AtencionSocial, 'objects', Mock(filter=Mock(return_value=atencion_query))),
            patch('funcionario_demo_app.views.render', return_value=object()) as render,
        ):
            response = atenciones_sociales_view(RequestFactory().get('/atencion-social/'))

        self.assertIsNotNone(response)
        self.assertEqual(render.call_args.args[1], 'funcionario_demo_app/atenciones_sociales.html')
        self.assertEqual(render.call_args.args[2]['atenciones_json'][0]['persona'], 'CASO-001')
        self.assertEqual(render.call_args.args[2]['atenciones_json'][0]['tipo'], 'Orientación familiar')
        self.assertEqual(reverse('atenciones_sociales_view'), '/atencion-social/')

    def test_new_attention_post_saves_and_redirects_to_history(self):
        funcionario = SimpleNamespace(pk=4)
        atencion = SimpleNamespace(persona=SimpleNamespace(referencia_anonima='CASO-001'))
        usuario_query = Mock()
        usuario_query.order_by.return_value.first.return_value = funcionario
        form = Mock()
        form.is_valid.return_value = True
        form.save.return_value = atencion

        with (
            patch.object(Usuario, 'objects', Mock(filter=Mock(return_value=usuario_query))),
            patch('funcionario_demo_app.views.AtencionSocialForm', return_value=form) as form_class,
            patch('funcionario_demo_app.views.transaction.atomic'),
            patch('funcionario_demo_app.views.messages.success'),
            patch('funcionario_demo_app.views.redirect', return_value='redirect') as redirect,
        ):
            response = nueva_atencion_social_view(RequestFactory().post('/atencion-social/nueva/'))

        self.assertEqual(response, 'redirect')
        form_class.assert_called_once_with({}, funcionario=funcionario)
        form.save.assert_called_once_with()
        redirect.assert_called_once_with('atenciones_sociales_view')

    def test_form_save_reuses_anonymous_person_and_creates_attention(self):
        persona = SimpleNamespace(pk=9)
        funcionario = SimpleNamespace(pk=4)
        tipo = SimpleNamespace(pk=3)
        actividad = SimpleNamespace(pk=12)
        activity_query = Mock()
        activity_query.all.return_value = activity_query
        activity_query.order_by.return_value = activity_query
        catalog_query = Mock()
        catalog_query.all.return_value = catalog_query
        catalog_query.order_by.return_value = catalog_query
        with (
            patch.object(Actividad, 'objects', Mock(filter=Mock(return_value=activity_query))),
            patch.object(CatalogoTipo, 'objects', Mock(filter=Mock(return_value=catalog_query))),
        ):
            form = AtencionSocialForm(funcionario=funcionario)
        form.cleaned_data = {
            'referencia_anonima': ' CASO-001 ',
            'catalogo_tipo': tipo,
            'orden_gestion': 2,
            'fecha': date(2026, 9, 25),
            'resultado': 'Derivación realizada',
            'actividad': actividad,
        }
        person_manager = Mock()
        person_manager.get_or_create.return_value = (persona, False)
        attention_manager = Mock()
        attention_manager.create.return_value = 'saved-attention'

        with (
            patch.object(PersonaUsuaria, 'objects', person_manager),
            patch.object(AtencionSocial, 'objects', attention_manager),
        ):
            saved = form.save()

        self.assertEqual(saved, 'saved-attention')
        person_manager.get_or_create.assert_called_once_with(referencia_anonima='CASO-001')
        attention_manager.create.assert_called_once_with(
            persona=persona,
            catalogo_tipo=tipo,
            funcionario=funcionario,
            orden_gestion=2,
            fecha=date(2026, 9, 25),
            resultado='Derivación realizada',
            actividad=actividad,
        )


class EvidenciasJsonTests(SimpleTestCase):
    def test_evidencias_json_endpoint_returns_data(self):
        response = self.client.get(reverse('evidencias_json_view'))

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        self.assertGreater(len(response.json()), 0)


class AdminDemoTests(SimpleTestCase):
    def test_admin_demo_page_loads(self):
        response = self.client.get('/admin-demo/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Centro de Administración SGR')

    def test_admin_new_user_page_loads(self):
        response = self.client.get('/admin-demo/nuevo-usuario/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrar Nuevo Usuario')
