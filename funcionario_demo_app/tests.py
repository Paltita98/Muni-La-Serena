from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.urls import reverse
from PIL import Image

from admin_demo_app.models import Actividad, AtencionSocial, CatalogoTipo, Evidencia, Meta, PersonaUsuaria, Usuario, Validacion
from .forms import ActividadForm, AtencionSocialForm, EvidenciaForm, ImageEvidenceField, VerificacionEvidenciaForm
from .views import _calcular_metricas_funcionario, _es_imagen_previsualizable, actividades_view, agenda_colectiva_view, atenciones_sociales_view, evidencia_previsualizacion_view, nueva_atencion_social_view, validar_evidencia_view, verificador_evidencias_view


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

        with (
            patch('funcionario_demo_app.views._funcionario_actual', return_value=funcionario),
            patch.object(Actividad, 'objects', actividad_manager),
            patch('funcionario_demo_app.views.render', return_value=object()),
        ):
            response = actividades_view(RequestFactory().get('/funcionario/actividades/'))

        self.assertIsNotNone(response)
        actividad_manager.filter.assert_called_once_with(funcionario=funcionario)

    def test_collective_agenda_is_scoped_to_the_active_staff_member(self):
        funcionario = SimpleNamespace(pk=4)
        compromiso_query = Mock()
        compromiso_query.select_related.return_value.order_by.return_value = []
        compromiso_manager = Mock(filter=Mock(return_value=compromiso_query))

        with (
            patch('funcionario_demo_app.views._funcionario_actual', return_value=funcionario),
            patch('funcionario_demo_app.views.Compromiso.objects', compromiso_manager),
            patch('funcionario_demo_app.views.render', return_value=object()),
        ):
            response = agenda_colectiva_view(RequestFactory().get('/funcionario/agenda-colectiva/'))

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
            'solicitante': 'María Pérez',
            'referencia_anonima': ' CASO-001 ',
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
        person_manager.get_or_create.assert_called_once_with(referencia_anonima='CASO-001')
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
