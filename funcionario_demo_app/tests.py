from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from admin_demo_app.models import (
    Actividad,
    AtencionSocial,
    CatalogoTipo,
    Cargo,
    Compromiso,
    CompromisoEstadoHistorial,
    Delegacion,
    Evidencia,
    ItemMedicion,
    Meta,
    PersonaUsuaria,
    Periodo,
    Usuario,
)
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


class FlujoCompromisosTests(TestCase):
    def setUp(self):
        self.delegado = self.crear_usuario('DEL-001', 'delegado')
        self.delegacion = Delegacion.objects.create(
            nombre='Delegación Centro',
            responsable=self.delegado,
        )
        self.delegado.delegacion = self.delegacion
        self.delegado.save(update_fields=['delegacion'])
        self.funcionario = self.crear_usuario('FUN-001', 'funcionario', self.delegacion)
        self.otra_delegacion = Delegacion.objects.create(nombre='Delegación Norte')
        self.otro_funcionario = self.crear_usuario('FUN-002', 'otro', self.otra_delegacion)
        self.periodo = Periodo.objects.create(
            fecha_inicio=date(2026, 1, 1),
            fecha_termino=date(2026, 12, 31),
            dias_computables=261,
        )
        cargo = Cargo.objects.create(nombre='Gestor territorial')
        item = ItemMedicion.objects.create(cargo=cargo, nombre='Operativo territorial')
        self.actividad = Actividad.objects.create(
            codigo_evidencia='ACT-CENTRO1',
            funcionario=self.funcionario,
            periodo=self.periodo,
            fecha_actividad=date(2026, 10, 1),
            descripcion='Operativo comunitario Centro',
            accion='Atención en terreno',
            item=item,
        )
        self.actividad_ajena = Actividad.objects.create(
            codigo_evidencia='ACT-NORTE1',
            funcionario=self.otro_funcionario,
            periodo=self.periodo,
            fecha_actividad=date(2026, 10, 2),
            descripcion='Operativo comunitario Norte',
            accion='Atención en terreno',
            item=item,
        )
        tipo_atencion = CatalogoTipo.objects.create(
            categoria='atencion',
            nombre='Orientación social',
            codigo='ORI-SOCIAL',
        )
        persona_local = PersonaUsuaria.objects.create(referencia_anonima='CASO-CENTRO')
        persona_ajena = PersonaUsuaria.objects.create(referencia_anonima='CASO-NORTE')
        AtencionSocial.objects.create(
            persona=persona_local,
            actividad=self.actividad,
            catalogo_tipo=tipo_atencion,
            funcionario=self.funcionario,
            orden_gestion=1,
            fecha=date(2026, 10, 1),
            resultado='Derivación local',
        )
        AtencionSocial.objects.create(
            persona=persona_ajena,
            actividad=self.actividad_ajena,
            catalogo_tipo=tipo_atencion,
            funcionario=self.otro_funcionario,
            orden_gestion=1,
            fecha=date(2026, 10, 2),
            resultado='Derivación externa',
        )

    def crear_usuario(self, identificador, nombre, delegacion=None):
        return Usuario.objects.create(
            identificador_inst=identificador,
            nombres=nombre,
            apellidos='Prueba',
            email=f'{identificador.lower()}@muni.test',
            password_hash='hash',
            delegacion=delegacion,
        )

    def iniciar_sesion_rol(self, rol, usuario):
        session = self.client.session
        session['user_role'] = rol
        session['user_id'] = usuario.pk
        session.save()

    def test_delegate_assigns_staff_tracks_and_approves_commitment(self):
        self.iniciar_sesion_rol('DELEGADO', self.delegado)
        response = self.client.post(reverse('delegado_compromiso_nuevo_view'), {
            'accion': 'guardar',
            'fecha_comprometida': '2026-12-15',
            'responsable': self.funcionario.pk,
            'solicitante': 'Junta vecinal',
            'territorio': 'Centro',
            'observacion': 'Coordinar operativo comunitario',
        })

        compromiso = Compromiso.objects.get(solicitante='Junta vecinal')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(compromiso.delegacion, self.delegacion)
        self.assertEqual(compromiso.responsable, self.funcionario)
        self.assertEqual(compromiso.estado, 'ingresado')
        self.assertEqual(CompromisoEstadoHistorial.objects.filter(compromiso=compromiso).count(), 1)

        self.iniciar_sesion_rol('FUNCIONARIO', self.funcionario)
        update_url = reverse('funcionario_compromiso_view', args=[compromiso.pk])
        response = self.client.post(update_url, {'estado': 'revision', 'observacion': 'No puede omitir el avance'})
        self.assertEqual(response.status_code, 200)
        compromiso.refresh_from_db()
        self.assertEqual(compromiso.estado, 'ingresado')

        response = self.client.post(update_url, {'estado': 'en_proceso', 'observacion': 'Gestión iniciada'})
        self.assertEqual(response.status_code, 302)
        compromiso.refresh_from_db()
        self.assertEqual(compromiso.estado, 'en_proceso')

        response = self.client.post(update_url, {'estado': 'revision', 'observacion': 'Trabajo terminado'})
        self.assertEqual(response.status_code, 302)
        compromiso.refresh_from_db()
        self.assertEqual(compromiso.estado, 'revision')

        self.iniciar_sesion_rol('DELEGADO', self.delegado)
        response = self.client.post(
            reverse('delegado_compromiso_view', args=[compromiso.pk]),
            {'accion': 'estado', 'estado': 'realizado', 'observacion': 'Cumplimiento validado'},
        )
        compromiso.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(compromiso.estado, 'realizado')
        self.assertEqual(CompromisoEstadoHistorial.objects.filter(compromiso=compromiso).count(), 4)

    def test_delegate_cannot_assign_commitment_to_staff_from_another_delegation(self):
        self.iniciar_sesion_rol('DELEGADO', self.delegado)
        response = self.client.post(reverse('delegado_compromiso_nuevo_view'), {
            'accion': 'guardar',
            'fecha_comprometida': '2026-12-15',
            'responsable': self.otro_funcionario.pk,
            'solicitante': 'Junta vecinal',
            'territorio': 'Centro',
            'observacion': 'Compromiso fuera del territorio',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Compromiso.objects.filter(solicitante='Junta vecinal').exists())

    def test_delegate_and_staff_cannot_access_another_delegations_commitment(self):
        compromiso = Compromiso.objects.create(
            delegacion=self.otra_delegacion,
            responsable=self.otro_funcionario,
            solicitante='Organización vecinal',
            fecha_comprometida=date(2026, 12, 15),
        )
        self.iniciar_sesion_rol('DELEGADO', self.delegado)

        response = self.client.get(reverse('delegado_compromiso_view', args=[compromiso.pk]))
        self.assertEqual(response.status_code, 404)

        self.iniciar_sesion_rol('FUNCIONARIO', self.funcionario)
        response = self.client.get(reverse('funcionario_compromiso_view', args=[compromiso.pk]))
        self.assertEqual(response.status_code, 404)

    def test_delegate_sees_only_own_delegation_activity_and_social_attention(self):
        self.iniciar_sesion_rol('DELEGADO', self.delegado)

        response = self.client.get(reverse('delegado_demo_view'))
        self.assertContains(response, 'Operativo comunitario Centro')
        self.assertContains(response, 'CASO-CENTRO')
        self.assertNotContains(response, 'Operativo comunitario Norte')
        self.assertNotContains(response, 'CASO-NORTE')

        response = self.client.get(reverse('actividades_view'))
        self.assertContains(response, 'Operativo comunitario Centro')
        self.assertNotContains(response, 'Operativo comunitario Norte')

        response = self.client.get(reverse('atenciones_sociales_view'))
        self.assertContains(response, 'CASO-CENTRO')
        self.assertNotContains(response, 'CASO-NORTE')

    def test_delegate_can_read_own_activity_but_cannot_upload_evidence_as_staff(self):
        self.iniciar_sesion_rol('DELEGADO', self.delegado)
        url = reverse('actividad_detalle_view', args=[self.actividad.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Operativo comunitario Centro')
        self.assertNotContains(response, 'Agregar evidencia')

        response = self.client.get(reverse('actividad_detalle_view', args=[self.actividad_ajena.pk]))
        self.assertEqual(response.status_code, 404)

        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 403)

    def test_delegate_agenda_is_scoped_and_links_to_commitment_review(self):
        local_commitment = Compromiso.objects.create(
            delegacion=self.delegacion,
            responsable=self.funcionario,
            solicitante='Junta de Centro',
            fecha_comprometida=date(2026, 12, 15),
        )
        Compromiso.objects.create(
            delegacion=self.otra_delegacion,
            responsable=self.otro_funcionario,
            solicitante='Junta del Norte',
            fecha_comprometida=date(2026, 12, 15),
        )
        self.iniciar_sesion_rol('DELEGADO', self.delegado)

        response = self.client.get(reverse('agenda_colectiva_view'))
        self.assertContains(response, 'Junta de Centro')
        self.assertNotContains(response, 'Junta del Norte')
        self.assertContains(response, reverse('delegado_compromiso_view', args=[local_commitment.pk]))

    def test_delegate_evidence_endpoint_returns_only_delegation_files(self):
        Evidencia.objects.create(
            actividad=self.actividad,
            archivo='evidencias/centro.jpg',
            formato='jpg',
            tamanio_bytes=100,
            autor=self.funcionario,
        )
        Evidencia.objects.create(
            actividad=self.actividad_ajena,
            archivo='evidencias/norte.jpg',
            formato='jpg',
            tamanio_bytes=100,
            autor=self.otro_funcionario,
        )
        self.iniciar_sesion_rol('DELEGADO', self.delegado)

        response = self.client.get(reverse('evidencias_json_view'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['codigo'] for item in response.json()], ['ACT-CENTRO1'])


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
        request = RequestFactory().get('/atencion-social/')
        request.session = {'user_role': 'FUNCIONARIO', 'user_id': 4}
        usuario_manager = Mock()
        usuario_manager.select_related.return_value.filter.return_value.first.return_value = funcionario
        atencion_query = Mock()
        atencion_query.select_related.return_value.order_by.return_value = [atencion]

        with (
            patch.object(Usuario, 'objects', usuario_manager),
            patch.object(AtencionSocial, 'objects', Mock(filter=Mock(return_value=atencion_query))),
            patch('funcionario_demo_app.views.render', return_value=object()) as render,
        ):
            response = atenciones_sociales_view(request)

        self.assertIsNotNone(response)
        self.assertEqual(render.call_args.args[1], 'funcionario_demo_app/atenciones_sociales.html')
        self.assertEqual(render.call_args.args[2]['atenciones_json'][0]['persona'], 'CASO-001')
        self.assertEqual(render.call_args.args[2]['atenciones_json'][0]['tipo'], 'Orientación familiar')
        self.assertEqual(reverse('atenciones_sociales_view'), '/funcionario/atencion-social/')

    def test_new_attention_post_saves_and_redirects_to_history(self):
        funcionario = SimpleNamespace(pk=4)
        atencion = SimpleNamespace(persona=SimpleNamespace(referencia_anonima='CASO-001'))
        request = RequestFactory().post('/atencion-social/nueva/')
        request.session = {'user_role': 'FUNCIONARIO', 'user_id': 4}
        usuario_manager = Mock()
        usuario_manager.select_related.return_value.filter.return_value.first.return_value = funcionario
        form = Mock()
        form.is_valid.return_value = True
        form.save.return_value = atencion

        with (
            patch.object(Usuario, 'objects', usuario_manager),
            patch('funcionario_demo_app.views.AtencionSocialForm', return_value=form) as form_class,
            patch('funcionario_demo_app.views.transaction.atomic'),
            patch('funcionario_demo_app.views.messages.success'),
            patch('funcionario_demo_app.views.redirect', return_value='redirect') as redirect,
        ):
            response = nueva_atencion_social_view(request)

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


class EvidenciasJsonTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create(
            identificador_inst='FUN-EVI',
            nombres='Elena',
            apellidos='Evidencia',
            email='evidencia@muni.test',
            password_hash='hash',
        )
        self.delegacion = Delegacion.objects.create(nombre='Delegación Evidencias')
        self.usuario.delegacion = self.delegacion
        self.usuario.save(update_fields=['delegacion'])
        periodo = Periodo.objects.create(
            fecha_inicio=date(2026, 1, 1),
            fecha_termino=date(2026, 12, 31),
            dias_computables=261,
        )
        cargo = Cargo.objects.create(nombre='Gestor de evidencias')
        item = ItemMedicion.objects.create(cargo=cargo, nombre='Registro de atenciones')
        actividad = Actividad.objects.create(
            codigo_evidencia='ACT-EVID001',
            funcionario=self.usuario,
            periodo=periodo,
            fecha_actividad=date(2026, 10, 1),
            descripcion='Atención territorial',
            accion='Atención',
            item=item,
        )
        Evidencia.objects.create(
            actividad=actividad,
            archivo='evidencias/atencion.jpg',
            formato='jpg',
            tamanio_bytes=100,
            autor=self.usuario,
        )

    def test_evidencias_json_endpoint_returns_data(self):
        session = self.client.session
        session['user_role'] = 'FUNCIONARIO'
        session['user_id'] = self.usuario.pk
        session.save()

        response = self.client.get(reverse('evidencias_json_view'))

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        self.assertEqual([item['codigo'] for item in response.json()], ['ACT-EVID001'])


class AdminDemoTests(SimpleTestCase):
    def test_admin_demo_page_loads(self):
        response = self.client.get('/admin-demo/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Centro de Administración SGR')

    def test_admin_new_user_page_loads(self):
        response = self.client.get('/admin-demo/nuevo-usuario/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrar Nuevo Usuario')
