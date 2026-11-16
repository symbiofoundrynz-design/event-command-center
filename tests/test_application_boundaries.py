"""Dependency-light Flask route tests. Require the project Python packages to be installed."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault('ECC_SKIP_SCHEMA', '1')
os.environ.setdefault('DB_NAME', 'test_database_no_connection')
os.environ.setdefault('DB_USER', 'test_user')
os.environ.setdefault('DB_PASSWORD', 'test_password_not_real')
os.environ.setdefault('APP_SECRET_KEY', 'test-secret-' * 5)
os.environ.setdefault('OPERATOR_PROXY_KEY', 'operator-proxy-secret-' * 3)

spec = importlib.util.spec_from_file_location('event_command_center', ROOT / 'app' / 'app.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class OperatorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = module.app.test_client()
        self.auth = {'X-ECC-Operator-Key': module.OPERATOR_PROXY_KEY}

    def test_guest_pages_and_static_assets_are_available_without_operator_key(self):
        with mock.patch.object(module, 'read_content', return_value=module.CONTENT_DEFAULTS), \
             mock.patch.object(module, 'read_gallery', return_value=[]):
            for path in ['/', '/guest-info', '/rsvp', '/gallery', '/contact']:
                with self.subTest(path=path):
                    result = self.client.get(path)
                    self.assertEqual(result.status_code, 200)
                    self.assertIn(b'Example Community Gathering', result.data)
        self.assertEqual(self.client.get('/static/guest-site.css').status_code, 200)
        self.assertEqual(self.client.get('/static/guest-site.js').status_code, 200)

    def test_guest_cannot_open_operator_routes(self):
        for path in ['/dashboard', '/preview', '/api/dashboard/state', '/api/parties/import-template.csv', '/health']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post('/api/content/draft', json={'fields': {}}).status_code, 403)

    def test_operator_key_unlocks_dashboard_template(self):
        response = self.client.get('/dashboard', headers=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Event Command Center', response.data)

    def test_operator_mutation_rejects_external_browser_origins(self):
        with mock.patch.object(module, 'database_connection', side_effect=AssertionError('DB should not be used')):
            response = self.client.post('/api/content/draft', json={'fields': {}}, headers={
                **self.auth,
                'Origin': 'https://malicious.example',
            })
            self.assertEqual(response.status_code, 403)
            response = self.client.post('/api/content/draft', json={'fields': {}}, headers={
                **self.auth,
                'Sec-Fetch-Site': 'cross-site',
            })
            self.assertEqual(response.status_code, 403)

    def test_private_media_is_not_visible_to_guest_even_with_known_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(module, 'PHOTO_DATA_ROOT', Path(tmp)):
                path = Path(tmp) / 'thumbnails' / 'example.webp'
                path.parent.mkdir(parents=True)
                path.write_bytes(b'not-a-real-image')
                with mock.patch.object(module, 'fetch_one', return_value=None):
                    self.assertEqual(self.client.get('/media/gallery/thumbnails/example.webp').status_code, 404)
                result = self.client.get('/media/gallery/thumbnails/example.webp', headers=self.auth)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.data, b'not-a-real-image')
                result.close()
                with mock.patch.object(module, 'fetch_one', return_value={'allowed': 1}):
                    self.assertEqual(self.client.get('/media/gallery/thumbnails/example.webp').status_code, 200)
                self.assertEqual(self.client.get('/media/gallery/originals/test.jpg').status_code, 404)

    def test_public_api_never_reveals_admin_state(self):
        with mock.patch.object(module, 'read_content', return_value={'event_title': 'Example Community Gathering'}), \
             mock.patch.object(module, 'read_gallery', return_value=[]):
            result = self.client.get('/api/content')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['event_title'], 'Example Community Gathering')
            self.assertEqual(self.client.get('/api/gallery').status_code, 200)


if __name__ == '__main__':
    unittest.main()
