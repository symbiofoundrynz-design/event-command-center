#!/usr/bin/env python3
"""Create a new, local-only configuration file; never print or overwrite secrets."""
from pathlib import Path
import secrets
import sys

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    raise SystemExit('STOP: .env already exists; no changes made.')
lines = [
    '# Generated locally. Keep this file private; it is excluded by .gitignore.',
    'DB_PASSWORD=' + secrets.token_hex(32),
    'APP_SECRET_KEY=' + secrets.token_urlsafe(48),
    'OPERATOR_PROXY_KEY=' + secrets.token_urlsafe(48),
    'GUEST_SITE_URL=http://127.0.0.1:8080/',
]
fd = None
try:
    fd = target.open('x', encoding='utf-8')
    fd.write('\n'.join(lines) + '\n')
finally:
    if fd:
        fd.close()
if sys.platform != 'win32':
    target.chmod(0o600)
print('Created a local .env with randomized credentials. Contents not displayed.')
