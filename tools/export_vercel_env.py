"""Run locally after GoogleFindMyTools setup. The generated file must stay private."""
import argparse
import base64
import json
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument('--google-secrets', type=Path, required=True)
parser.add_argument('--registration', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
destination = root / 'vercel-secrets.env'
if destination.exists():
    raise SystemExit('vercel-secrets.env already exists; preserving the existing website password.')
cached = json.loads(args.google_secrets.read_text())
for key in ('username', 'aas_token', 'owner_key', 'fcm_credentials'):
    if not cached.get(key):
        raise SystemExit(f'Missing {key}. Complete desktop GoogleFindMyTools setup first.')
registration = json.loads(args.registration.read_text())
values = {
    'TRACKER_PASSWORD': secrets.token_urlsafe(24),
    'SESSION_SECRET': secrets.token_urlsafe(48),
    'FINDMY_SECRETS_B64': base64.b64encode(json.dumps(cached).encode()).decode(),
    'TRACKER_DEVICE_ID': registration['id'],
    'TRACKER_NAME': registration['name'],
}
destination.write_text('\n'.join(f'{key}="{value}"' for key, value in values.items()) + '\n')
print('Created private vercel-secrets.env. Import it into Vercel Environment Variables; never commit or share this file.')
