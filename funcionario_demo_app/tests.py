import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.urls import reverse
from PIL import Image

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
    OrganizacionJJVV,
    PersonaUsuaria,
    Periodo,
    Usuario,
    Validacion,
)
from .forms import (
    ActividadForm,
    AtencionSocialForm,
    EvidenciaForm,
    ImageEvidenceField,
    VerificacionEvidenciaForm,
)
from .views import (
    _calcular_metricas_funcionario,
    _es_imagen_previsualizable,
    actividades_view,
    agenda_colectiva_view,
    atenciones_sociales_view,
    buscar_personas_view,
    evidencia_previsualizacion_view,
    nueva_atencion_social_view,
    validar_evidencia_view,
    verificador_evidencias_view,
)


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

        response = self.client.get(reverse('delegado_actividades_view'))
        self.assertContains(response, 'Operativo comunitario Centro')
        self.assertNotContains(response, 'Operativo comunitario Norte')

        response = self.client.get(reverse('delegado_atenciones_view'))
        self.assertContains(response, 'CASO-CENTRO')
        self.assertNotContains(response, 'CASO-NORTE')

        response = self.client.get(reverse('delegado_equipo_view'))
        self.assertContains(response, 'funcionario Prueba')
        self.assertNotContains(response, 'otro Prueba')
        self.assertContains(response, reverse('delegado_actividades_view'))
        self.assertContains(response, reverse('delegado_atenciones_view'))
        self.assertContains(response, reverse('delegado_compromisos_view'))
        self.assertContains(response, reverse('delegado_equipo_view'))

    def test_delegate_tube_and_filters_are_limited_to_own_delegation(self):
        Compromiso.objects.create(
            delegacion=self.delegacion,
            responsable=self.funcionario,
            solicitante='Junta local',
            territorio='Centro',
            observacion='Solicitud local del TUBO',
            fecha_comprometida=date(2026, 12, 15),
        )
        Compromiso.objects.create(
            delegacion=self.otra_delegacion,
            responsable=self.otro_funcionario,
            solicitante='Junta del Norte',
            territorio='Norte',
            observacion='Solicitud externa del TUBO',
            fecha_comprometida=date(2026, 12, 15),
        )
        self.iniciar_sesion_rol('DELEGADO', self.delegado)

        response = self.client.get(reverse('delegado_demo_view'), {'panel': 'tubo'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Solicitud local del TUBO')
        self.assertContains(response, 'Operativo comunitario Centro')
        self.assertContains(response, 'CASO-CENTRO')
        self.assertNotContains(response, 'Solicitud externa del TUBO')
        self.assertNotContains(response, 'Operativo comunitario Norte')
        self.assertNotContains(response, 'CASO-NORTE')
        self.assertEqual(response.context['backlog_summary']['total'], 3)

        filtered_response = self.client.get(reverse('delegado_demo_view'), {
            'panel': 'tubo',
            'q': 'Norte',
        })
        self.assertEqual(filtered_response.context['backlog_total'], 0)
        self.assertNotContains(filtered_response, 'Solicitud externa del TUBO')

    def test_delegate_can_read_own_activity_but_cannot_upload_evidence_as_staff(self):
        self.iniciar_sesion_rol('DELEGADO', self.delegado)
        url = reverse('actividad_detalle_view', args=[self.actividad.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Operativo comunitario Centro')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'Actividades')
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

    def test_delegate_compromise_date_is_read_only_in_list_and_edit(self):
        compromiso = Compromiso.objects.create(
            delegacion=self.delegacion,
            responsable=self.funcionario,
            solicitante='Junta de Centro',
            territorio='Centro',
            fecha_comprometida=date(2026, 12, 15),
            observacion='Mantener fecha comprometida',
        )
        self.iniciar_sesion_rol('DELEGADO', self.delegado)
        list_url = reverse('delegado_compromisos_view')
        detail_url = reverse('delegado_compromiso_view', args=[compromiso.pk])

        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, '15/12/2026')
        self.assertNotContains(list_response, 'name="fecha_comprometida"')

        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, '15/12/2026')
        self.assertNotContains(detail_response, 'name="fecha_comprometida"')

        response = self.client.post(detail_url, {
            'accion': 'guardar',
            'fecha_comprometida': '2027-01-20',
            'responsable': self.funcionario.pk,
            'solicitante': compromiso.solicitante,
            'territorio': compromiso.territorio,
            'observacion': compromiso.observacion,
        })
        compromiso.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(compromiso.fecha_comprometida, date(2026, 12, 15))

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
class ImageEvidenceFieldTests(SimpleTestCase):
    def png_upload(self, filename='evidence.png'):
        content = BytesIO()
        Image.new('RGB', (1, 1), 'red').save(content, format='PNG')
        return SimpleUploadedFile(filename, content.getvalue(), content_type='image/png')

    def test_accepts_valid_image_and_limits_browser_picker(self):
        form = EvidenciaForm()

        self.assertEqual(form.fields['archivo'].clean(self.png_upload()).name, 'evidence.png')
        self.assertEqual(
            form.fields['archivo'].widget.attrs['accept'],
            'image/jpeg,image/png,image/gif,image/webp,image/bmp',
        )

    def test_rejects_pdf_and_word_even_when_renamed_as_image(self):
        field = ImageEvidenceField()
        uploads = (
            SimpleUploadedFile('document.pdf', b'%PDF-1.4 fake', content_type='application/pdf'),
            SimpleUploadedFile('document.docx', b'PK\x03\x04fake', content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            SimpleUploadedFile('renamed.jpg', b'%PDF-1.4 fake', content_type='image/jpeg'),
        )

        for upload in uploads:
            with self.subTest(filename=upload.name), self.assertRaises(ValidationError):
                field.clean(upload)

    def test_optional_activity_evidence_uses_same_image_validation(self):
        field = ActividadForm.base_fields['evidencia']

        with self.assertRaises(ValidationError):
            field.clean(SimpleUploadedFile('document.pdf', b'%PDF-1.4 fake'))


class FuncionarioListadoTests(SimpleTestCase):
    def test_activities_are_scoped_to_the_active_staff_member(self):
        funcionario = SimpleNamespace(pk=4)
        actividad_query = Mock()
        actividad_query.select_related.return_value.order_by.return_value = []
        actividad_manager = Mock(filter=Mock(return_value=actividad_query))
        request = RequestFactory().get('/funcionario/actividades/')
        request.session = {'user_role': 'FUNCIONARIO'}

        with (
            patch('funcionario_demo_app.views._funcionario_actual', return_value=funcionario),
            patch.object(Actividad, 'objects', actividad_manager),
            patch('funcionario_demo_app.views.render', return_value=object()),
        ):
            response = actividades_view(request)

        self.assertIsNotNone(response)
        actividad_manager.filter.assert_called_once_with(funcionario=funcionario)

    def test_collective_agenda_is_scoped_to_the_active_staff_member(self):
        funcionario = SimpleNamespace(pk=4)
        compromiso_query = Mock()
        compromiso_query.select_related.return_value.order_by.return_value = []
        compromiso_manager = Mock(filter=Mock(return_value=compromiso_query))
        request = RequestFactory().get('/funcionario/agenda-colectiva/')
        request.session = {'user_role': 'FUNCIONARIO'}

        with (
            patch('funcionario_demo_app.views._funcionario_actual', return_value=funcionario),
            patch('funcionario_demo_app.views.Compromiso.objects', compromiso_manager),
            patch('funcionario_demo_app.views.render', return_value=object()),
        ):
            response = agenda_colectiva_view(request)

        self.assertIsNotNone(response)
        compromiso_manager.filter.assert_called_once_with(responsable=funcionario)


class AtencionesSocialesViewTests(SimpleTestCase):
    def test_view_lists_social_attention_for_active_staff_member(self):
        funcionario = SimpleNamespace(pk=4)
        catalogo_tipo = SimpleNamespace(
            nombre='Orientación familiar',
            categoria='atencion',
            get_categoria_display=lambda: 'Atención',
        )
        catalogo_subtipo = SimpleNamespace(nombre='Orientación jurídica')
        delegacion = SimpleNamespace(nombre='Delegación Norte')
        actividad = SimpleNamespace(pk=12, descripcion='Acompañamiento social')
        atencion = SimpleNamespace(
            persona=SimpleNamespace(referencia_anonima='CASO-001'),
            solicitante='María Pérez',
            descripcion='Consulta por apoyo familiar',
            delegacion=delegacion,
            catalogo_tipo=catalogo_tipo,
            catalogo_subtipo=catalogo_subtipo,
            catalogo_subtipo_id=5,
            delegacion_id=8,
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
        self.assertEqual(render.call_args.args[2]['atenciones_json'][0]['subatencion'], 'Orientación jurídica')
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
            patch('funcionario_demo_app.views.notificar_accion_funcionario') as notify,
            patch('funcionario_demo_app.views.redirect', return_value='redirect') as redirect,
        ):
            response = nueva_atencion_social_view(request)

        self.assertEqual(response, 'redirect')
        form_class.assert_called_once_with({}, funcionario=funcionario)
        form.save.assert_called_once_with()
        notify.assert_called_once()
        redirect.assert_called_once_with('atenciones_sociales_view')

    def test_form_save_reuses_selected_person_and_creates_attention(self):
        persona = SimpleNamespace(pk=9, nombre='María Pérez', referencia_anonima='CASO-001')
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
            'solicitante': 'María Pérez',
            'persona': persona,
            'nuevo_rut': '',
            'nuevo_nombre': '',
            'nuevo_telefono': '',
            'catalogo_tipo': tipo,
            'catalogo_subtipo': None,
            'delegacion': SimpleNamespace(pk=8),
            'descripcion': 'Consulta de apoyo',
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
        person_manager.create.assert_not_called()
        attention_manager.create.assert_called_once_with(
            persona=persona,
            solicitante='María Pérez',
            descripcion='Consulta de apoyo',
            delegacion=form.cleaned_data['delegacion'],
            catalogo_tipo=tipo,
            catalogo_subtipo=None,
            funcionario=funcionario,
            orden_gestion=2,
            fecha=date(2026, 9, 25),
            resultado='Derivación realizada',
            actividad=actividad,
        )

    def test_form_save_generates_code_for_new_person(self):
        persona = SimpleNamespace(pk=9, nombre='María Pérez', referencia_anonima='CASO-004')
        funcionario = SimpleNamespace(pk=4)
        tipo = SimpleNamespace(pk=3)
        with (
            patch.object(Actividad, 'objects', Mock()),
            patch.object(CatalogoTipo, 'objects', Mock()),
        ):
            form = AtencionSocialForm(funcionario=funcionario)
        form.cleaned_data = {
            'solicitante': 'María Pérez',
            'persona': None,
            'nuevo_rut': '19864005-0',
            'nuevo_nombre': 'María Pérez',
            'nuevo_telefono': '+56912345678',
            'catalogo_tipo': tipo,
            'catalogo_subtipo': None,
            'delegacion': SimpleNamespace(pk=8),
            'descripcion': 'Primera consulta',
            'orden_gestion': 1,
            'fecha': date(2026, 9, 25),
            'resultado': '',
            'actividad': None,
        }
        person_manager = Mock()
        person_manager.create.return_value = persona
        attention_manager = Mock()
        attention_manager.create.return_value = 'saved-attention'

        with (
            patch.object(PersonaUsuaria, 'crear_con_referencia_incremental', return_value=persona) as create_person,
            patch.object(PersonaUsuaria, 'objects', person_manager),
            patch.object(AtencionSocial, 'objects', attention_manager),
        ):
            saved = form.save()

        self.assertEqual(saved, 'saved-attention')
        create_person.assert_called_once_with(
            rut='19864005-0', nombre='María Pérez', telefono='+56912345678',
        )
        person_manager.create.assert_not_called()

    def test_persona_creation_increments_after_highest_existing_case(self):
        manager = Mock()
        manager.select_for_update.return_value.values_list.return_value = [
            'CASO-001', 'CASO-008', 'LEGADO-42', 'CASO-X',
        ]
        persona = SimpleNamespace(pk=11)
        manager.create.return_value = persona

        with (
            patch('admin_demo_app.models.transaction.atomic'),
            patch.object(PersonaUsuaria, 'objects', manager),
        ):
            created = PersonaUsuaria.crear_con_referencia_incremental()

        self.assertIs(created, persona)
        manager.create.assert_called_once_with(
            referencia_anonima='CASO-009', rut=None, nombre='', telefono='',
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


class BuscarPersonasTests(SimpleTestCase):
    def test_search_requires_an_active_staff_member(self):
        request = RequestFactory().get('/funcionario/personas/buscar/?q=Maria')
        with patch('funcionario_demo_app.views._funcionario_actual', return_value=None):
            response = buscar_personas_view(request)

        self.assertEqual(response.status_code, 403)

    def test_search_returns_matching_person_contact(self):
        request = RequestFactory().get('/funcionario/personas/buscar/?q=Maria')
        persona = SimpleNamespace(
            pk=7,
            nombre='María Pérez',
            rut='19864005-0',
            telefono='+56912345678',
            referencia_anonima='CASO-007',
        )
        people_query = Mock()
        people_query.order_by.return_value = [persona]
        manager = Mock(filter=Mock(return_value=people_query))
        with (
            patch('funcionario_demo_app.views._funcionario_actual', return_value=SimpleNamespace(pk=4)),
            patch.object(PersonaUsuaria, 'objects', manager),
        ):
            response = buscar_personas_view(request)

        self.assertEqual(response.status_code, 200)
        results = json.loads(response.content)['results']
        self.assertEqual(results[0]['rut'], '19864005-0')
        self.assertEqual(results[0]['telefono'], '+56912345678')


class AdminDemoTests(SimpleTestCase):
    def test_admin_demo_page_loads(self):
        response = self.client.get('/admin-demo/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Centro de Administración SGR')

    def test_admin_new_user_page_loads(self):
        response = self.client.get('/admin-demo/nuevo-usuario/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrar Nuevo Usuario')


class VerificacionEvidenciaTests(SimpleTestCase):
    def test_rejection_requires_a_correction_description(self):
        form = VerificacionEvidenciaForm({'decision': 'rechazada', 'observacion': '   '})

        self.assertFalse(form.is_valid())
        self.assertIn('observacion', form.errors)

    def test_approval_records_validation_and_updates_evidence_and_activity(self):
        verifier = SimpleNamespace(pk=9, nombres='Víctor', apellidos='Validador')
        activity = SimpleNamespace(
            codigo_evidencia='ACT-TEST',
            funcionario_id=21,
            estado='pendiente',
            evidencias=Mock(),
            save=Mock(),
        )
        activity.evidencias.exclude.return_value.filter.return_value.exists.return_value = False
        evidence = SimpleNamespace(pk=4, estado='pendiente', actividad=activity, save=Mock())
        user_manager = Mock()
        user_manager.prefetch_related.return_value.filter.return_value.first.return_value = verifier
        request = RequestFactory().post('/verificador/evidencias/4/validar/', {
            'decision': 'aprobada',
            'observacion': '',
        })
        request.session = {'user_role': 'VERIFICADOR', 'user_id': 9}

        with (
            patch.object(Usuario, 'objects', user_manager),
            patch.object(Evidencia, 'objects') as evidence_manager,
            patch.object(Validacion, 'objects') as validation_manager,
            patch('funcionario_demo_app.views.transaction.atomic'),
            patch('funcionario_demo_app.views.get_object_or_404', return_value=evidence),
            patch('funcionario_demo_app.views.messages.success'),
            patch('funcionario_demo_app.views.notificar') as notify_user,
            patch('funcionario_demo_app.views.notificar_administradores'),
        ):
            response = validar_evidencia_view(request, 4)

        self.assertEqual(response.url, reverse('verificador_evidencias_view'))
        self.assertEqual(evidence.estado, 'aprobada')
        self.assertEqual(activity.estado, 'validada')
        evidence_manager.select_for_update.assert_called_once()
        validation_manager.create.assert_called_once_with(
            evidencia=evidence,
            verificador=verifier,
            decision='aprobada',
            observacion=None,
        )
        self.assertIn('aprobada por', notify_user.call_args.args[1])

    def test_non_verifier_cannot_open_review_queue(self):
        request = RequestFactory().get('/verificador/evidencias/')
        request.session = {'user_role': 'FUNCIONARIO', 'user_id': 9}

        response = verificador_evidencias_view(request)

        self.assertEqual(response.url, '/login/')

    def test_rejection_records_feedback_and_returns_activity_for_correction(self):
        verifier = SimpleNamespace(pk=9, nombres='Víctor', apellidos='Validador')
        activity = SimpleNamespace(
            codigo_evidencia='ACT-TEST',
            funcionario_id=21,
            estado='pendiente',
            evidencias=Mock(),
            save=Mock(),
        )
        evidence = SimpleNamespace(pk=4, estado='pendiente', actividad=activity, save=Mock())
        user_manager = Mock()
        user_manager.prefetch_related.return_value.filter.return_value.first.return_value = verifier
        request = RequestFactory().post('/verificador/evidencias/4/validar/', {
            'decision': 'rechazada',
            'observacion': 'Adjunta el respaldo firmado.',
        })
        request.session = {'user_role': 'VERIFICADOR', 'user_id': 9}

        with (
            patch.object(Usuario, 'objects', user_manager),
            patch.object(Evidencia, 'objects'),
            patch.object(Validacion, 'objects') as validation_manager,
            patch('funcionario_demo_app.views.transaction.atomic'),
            patch('funcionario_demo_app.views.get_object_or_404', return_value=evidence),
            patch('funcionario_demo_app.views.messages.success'),
            patch('funcionario_demo_app.views.notificar') as notify_user,
            patch('funcionario_demo_app.views.notificar_administradores'),
        ):
            response = validar_evidencia_view(request, 4)

        self.assertEqual(response.url, reverse('verificador_evidencias_view'))
        self.assertEqual(evidence.estado, 'en_correccion')
        self.assertEqual(activity.estado, 'en_correccion')
        validation_manager.create.assert_called_once_with(
            evidencia=evidence,
            verificador=verifier,
            decision='rechazada',
            observacion='Adjunta el respaldo firmado.',
        )
        self.assertIn('Víctor Validador', notify_user.call_args.args[1])
        self.assertIn('Adjunta el respaldo firmado.', notify_user.call_args.args[1])


class EvidenceImagePreviewTests(SimpleTestCase):
    def test_preview_accepts_only_raster_image_extensions(self):
        for filename in ('foto.jpg', 'foto.JPEG', 'foto.png', 'foto.webp', 'foto.gif', 'foto.bmp'):
            with self.subTest(filename=filename):
                self.assertTrue(_es_imagen_previsualizable(filename))

        for filename in ('documento.pdf', 'script.svg', 'foto.exe'):
            with self.subTest(filename=filename):
                self.assertFalse(_es_imagen_previsualizable(filename))

    def test_owner_receives_inline_preview_with_safe_content_type(self):
        evidence_file = SimpleNamespace(name='uploads/foto.JPG', open=lambda mode: BytesIO(b'image-data'))
        evidence = SimpleNamespace(
            archivo=evidence_file,
            actividad=SimpleNamespace(funcionario_id=12),
        )
        request = RequestFactory().get('/funcionario/evidencias/5/preview/')
        request.session = {'user_role': 'FUNCIONARIO', 'user_id': 12}

        with patch('funcionario_demo_app.views.get_object_or_404', return_value=evidence):
            response = evidencia_previsualizacion_view(request, 5)

        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertIn('inline', response['Content-Disposition'])

    def test_non_owner_without_verifier_role_cannot_preview(self):
        evidence = SimpleNamespace(
            archivo=SimpleNamespace(name='foto.png'),
            actividad=SimpleNamespace(funcionario_id=12),
        )
        request = RequestFactory().get('/funcionario/evidencias/5/preview/')
        request.session = {'user_role': 'ADMIN', 'user_id': 3}

        with (
            patch('funcionario_demo_app.views.get_object_or_404', return_value=evidence),
            self.assertRaises(Http404),
        ):
            evidencia_previsualizacion_view(request, 5)


class OrganizacionesJJVVCrudTests(TestCase):
    def iniciar_sesion_organizaciones(self):
        session = self.client.session
        session['user_role'] = 'ORGANIZACIONES_COMUNITARIAS'
        session['user_id'] = 1
        session['user_name'] = 'Ana Pérez'
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def test_create_search_update_and_delete_organization(self):
        self.iniciar_sesion_organizaciones()
        datos = {
            'organizaciones': 'Junta de Vecinos El Faro',
            'domicilio_legal': 'Av. del Mar 100',
            'territorio_deleg': 'Las Compañías',
            'socios_activos': '35',
            'fecha_constitucion': '2020-05-10',
            'n_reg_pj': 'PJ-104',
            'fecha_inscripcion_reg': '2020-05-20',
            'reg_dir_n': 'DIR-31',
        }

        response = self.client.post(reverse('main:nueva_organizacion_jjvv_view'), datos)
        self.assertRedirects(response, reverse('main:organizaciones_jjvv_list_view'))
        organizacion = OrganizacionJJVV.objects.get(organizaciones='Junta de Vecinos El Faro')

        response = self.client.get(reverse('main:organizaciones_jjvv_list_view'), {'q': 'Las Compañías'})
        self.assertContains(response, 'Junta de Vecinos El Faro')
        self.assertEqual(len(response.context['organizaciones']), 1)

        datos['organizaciones'] = 'Junta de Vecinos El Faro Norte'
        response = self.client.post(
            reverse('main:editar_organizacion_jjvv_view', args=[organizacion.pk]),
            datos,
        )
        self.assertRedirects(response, reverse('main:organizaciones_jjvv_list_view'))
        organizacion.refresh_from_db()
        self.assertEqual(organizacion.organizaciones, 'Junta de Vecinos El Faro Norte')

        delete_url = reverse('main:eliminar_organizacion_jjvv_view', args=[organizacion.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse('main:organizaciones_jjvv_list_view'))
        self.assertFalse(OrganizacionJJVV.objects.filter(pk=organizacion.pk).exists())

    def test_registration_date_cannot_precede_constitution(self):
        self.iniciar_sesion_organizaciones()
        response = self.client.post(reverse('main:nueva_organizacion_jjvv_view'), {
            'organizaciones': 'Agrupación Costera',
            'fecha_constitucion': '2022-05-10',
            'fecha_inscripcion_reg': '2022-05-01',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La inscripción no puede ser anterior a la constitución.')
        self.assertFalse(OrganizacionJJVV.objects.exists())

    def test_dashboard_uses_registered_organization_data(self):
        self.iniciar_sesion_organizaciones()
        OrganizacionJJVV.objects.create(
            organizaciones='Junta Vecinal Costanera',
            territorio_deleg='Coquimbo',
            socios_activos=42,
        )

        response = self.client.get(reverse('main:organizaciones_comunitarias_dashboard_view'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['organizaciones_total'], 1)
        self.assertEqual(response.context['socios_activos_total'], 42)
        self.assertEqual(response.context['territorios_total'], 1)

    def test_crud_redirects_when_role_is_not_authorized(self):
        response = self.client.get(reverse('main:organizaciones_jjvv_list_view'))

        self.assertRedirects(response, reverse('main:login_view'))
