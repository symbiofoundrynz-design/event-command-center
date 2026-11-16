"""Source-only checks which need no running services or database."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StaticReleaseChecks(unittest.TestCase):
    def test_python_compiles(self):
        for path in [ROOT / 'app' / 'app.py', ROOT / 'scripts' / 'init_env.py']:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

    def test_guest_nginx_explicitly_denies_all_unlisted_paths(self):
        conf = (ROOT / 'deploy' / 'nginx' / 'default.conf.template').read_text(encoding='utf-8')
        guest_server = conf.split('server {', 2)[1]
        self.assertIn('listen 8080;', guest_server)
        self.assertIn('location / { return 404; }', guest_server)
        self.assertNotIn('location = /dashboard', guest_server)
        self.assertNotIn('location = /api/dashboard/state', guest_server)
        self.assertIn('X-ECC-Operator-Key ""', guest_server)
        admin_server = conf.split('server {', 2)[2]
        self.assertIn('listen 8081;', admin_server)
        self.assertIn('X-ECC-Operator-Key "${OPERATOR_PROXY_KEY}"', admin_server)

    def test_host_ports_are_loopback_only(self):
        config = (ROOT / 'compose.yaml').read_text(encoding='utf-8')
        self.assertIn("'127.0.0.1:8080:8080'", config)
        self.assertIn("'127.0.0.1:8081:8081'", config)
        self.assertNotIn('8082:8082', config)
        self.assertNotIn('5432:5432', config)

    def test_no_client_event_assets_or_operational_deployment_script(self):
        self.assertFalse((ROOT / 'app' / 'static' / 'assets').exists())
        self.assertEqual(sorted(p.name for p in (ROOT / 'app' / 'static' / 'demo').glob('*')), sorted([
            'ecc-demo-hero.webp', 'ecc-demo-gallery-venue.webp', 'ecc-demo-gallery-tables.webp',
            'ecc-demo-gallery-presentation.webp', 'ecc-demo-gallery-details.webp']))
        self.assertFalse((ROOT / 'wheels').exists())
        self.assertEqual(list(ROOT.glob('install-*.sh')), [])
        self.assertFalse((ROOT / '.env').exists())
        self.assertIn('.env', (ROOT / '.gitignore').read_text())

    def test_fictional_demo_images_and_narrow_guest_proxy_rule(self):
        from hashlib import sha256
        from PIL import Image
        expected = {
            'ecc-demo-hero.webp': ('d94065bf16eafff6a2d50fc0e726b1c2b953be795364e99ee3a0191b7879cc06', (1920,1080)),
            'ecc-demo-gallery-venue.webp': ('5bfa6bf229718877d7cfb8e89af8362bc65a43e995f0f2cfc3eff3a03fc6e9fc', (1600,1200)),
            'ecc-demo-gallery-tables.webp': ('76bd7b678bc8def5662798cc81cefc602d5b878b6fa4e565695dce865f8ff1dd', (1600,1200)),
            'ecc-demo-gallery-presentation.webp': ('3fb5ab139ffd5e931ac4e212a7bb4d747db1579776fff9e7742cf243bc54dc91', (1600,1200)),
            'ecc-demo-gallery-details.webp': ('25cba3d4619e001a7fdb41e9eca19d92f696edc36520cfff86f2237e753fa4df', (1600,1200)),
        }
        for name, (digest, dimensions) in expected.items():
            path = ROOT / 'app' / 'static' / 'demo' / name
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), digest)
            with Image.open(path) as img:
                self.assertEqual(img.format, 'WEBP')
                self.assertEqual(img.size, dimensions)
        conf = (ROOT / 'deploy' / 'nginx' / 'default.conf.template').read_text(encoding='utf-8')
        public = conf.split('server {',2)[1]
        self.assertIn('location ^~ /static/demo/',public)
        self.assertNotIn('location ^~ /static/',public.replace('location ^~ /static/demo/', ''))
        self.assertIn('X-ECC-Operator-Key ""',public)

    def test_demo_gallery_fallback_only_when_no_published_images(self):
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(ROOT / 'app' / 'templates')), autoescape=True)
        env.globals['url_for'] = lambda endpoint, filename: '/static/' + filename
        template = env.get_template('guest-site.html')
        kwargs = dict(content={'event_title':'Example Community Gathering'}, initial_view='gallery',
                      preview_mode=False, rsvp_result={})
        empty = template.render(**kwargs, gallery=[])
        self.assertEqual(empty.count('class="gallery-card"'), 4)
        self.assertEqual(empty.count('data-full="/static/demo/'), 4)
        self.assertIn('Fictional demonstration gallery', empty)
        actual = template.render(**kwargs, gallery=[dict(
            display_url='/media/gallery/display/test.webp',thumbnail_url='/media/gallery/thumbnails/test.webp',
            alt_text='Test upload',caption='Test upload')])
        self.assertEqual(actual.count('class="gallery-card"'), 1)
        self.assertNotIn('demo-gallery', actual)

    def test_root_license(self):
        license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
        self.assertTrue(license_text.startswith('MIT License\n'))
        self.assertIn('Copyright (c) 2026 SymbioFoundry', license_text)


if __name__ == '__main__':
    unittest.main()
