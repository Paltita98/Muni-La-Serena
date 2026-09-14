from django.test import SimpleTestCase
from django.urls import reverse


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
