from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.urls import reverse

from admin_demo_app.models import Actividad, Meta
from .views import _calcular_metricas_funcionario


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

        with (
            patch.object(Meta, 'objects', Mock(filter=Mock(return_value=meta_query))),
            patch.object(Actividad, 'objects', Mock(filter=Mock(return_value=actividad_query))),
        ):
            return _calcular_metricas_funcionario(
                funcionario,
                periodo,
                fecha_actual=date(2026, 1, 15),
            )

    def test_calculates_expected_progress_and_red_semaphore(self):
        metricas = self.calcular_metricas(avance=2)

        self.assertEqual(metricas['avance_real_pct'], Decimal('20.00'))
        self.assertEqual(metricas['meta_esperada_pct'], Decimal('50.00'))
        self.assertEqual(metricas['semaforo'], 'rojo')

    def test_green_semaphore_when_progress_reaches_daily_expectation(self):
        metricas = self.calcular_metricas(avance=6)

        self.assertEqual(metricas['avance_real_pct'], Decimal('60.00'))
        self.assertEqual(metricas['semaforo'], 'verde')


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
