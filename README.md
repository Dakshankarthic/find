# Find — private ESP32 tracker website

A phone-friendly, password-protected website for the existing GoogleFindMyTools
tracker. It retrieves and decrypts actual network location reports on demand.
This is an independent website, not Google's official Find Hub application.

## Deploy to Vercel

1. In Vercel, choose **Add New → Project**, and import `Dakshankarthic/find`.
2. Use **FastAPI** as the framework and the repository root as the root directory.
   There is no frontend build command. Python dependencies are in requirements.txt.
3. Before deployment, import the locally generated **vercel-secrets.env** into
   the project's Environment Variables. Select only the Production environment
   for the real Google session; do not expose it to untrusted preview branches.
4. Deploy. If you add environment variables after a deployment, redeploy.
5. Open the Vercel URL on your phone. Sign in using TRACKER_PASSWORD from your
   private local environment file, then tap **Refresh location**.

The generated file contains sensitive Google login tokens. Do not upload it to
GitHub, attach it to chat, or place it under `public`. Base64 is encoding, not
encryption. Vercel stores the values as server-side environment variables.

### Generate the private environment file locally

After completing GoogleFindMyTools sign-in and registering your tracker:

```powershell
python tools/export_vercel_env.py --google-secrets "I:\android find my tag\Auth\secrets.json" --registration "I:\android find my tag\firmware_platformio\registration.json"
```

The exporter refuses to overwrite existing settings. To intentionally rotate the
website password or update an expired Google session, make a private backup and
remove the generated file, run it again, replace the Vercel variables, and redeploy.

Required variables:

| Variable | Purpose |
| --- | --- |
| TRACKER_PASSWORD | Unique password for this website, not a Google password |
| SESSION_SECRET | Random secret signing one-day login cookies |
| FINDMY_SECRETS_B64 | Base64-encoded desktop Auth/secrets.json |
| TRACKER_DEVICE_ID | Existing Google tracker registration ID |
| TRACKER_NAME | Display name |

## Local development

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
# Load the private environment variables into your shell first.
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. Without the variables, the page displays a setup message
and will not allow login. No sample location is presented as real data.

## Behavior and limits

- Refresh renews the selected custom tracker's announced advertisements and
  requests location reports. It never registers another tracker.
- The newest geographic report is shown with its actual report timestamp.
  A successful refresh may return an older position; it does not guarantee live GPS.
- Google authentication and cryptographic keys remain server-side. No credentials
  are sent to the browser. Google Maps receives the displayed coordinates when the
  signed-in viewer loads the embedded map or opens the Maps link.
- The worker is bounded to 48 seconds; the request timeout is 54 seconds and the
  Vercel function duration is configured to 60 seconds. There is no persistent
  background server or automatic polling. Cache/cooldown is per warm instance.
- The location path requires outbound HTTPS and Firebase messaging TCP connections.
  It is tested locally; its first live refresh still needs verification on Vercel.
  If the hosting environment blocks Firebase connections, a persistent Python
  backend will be needed. An error is shown instead of invented data.
- Browser-based Google sign-in cannot run in Vercel. If tokens or encryption keys
  expire, repeat setup on your PC and replace the environment variable.
- Protect the deployment further using Vercel Firewall/rate limiting where
  available. The built-in password is for a single private owner, not multi-user
  account management. No cloud database or location history is retained.

## Validation

```powershell
python -m pytest tests
node --check public/app.js
```

## Attribution

This project includes a source snapshot of
[GoogleFindMyTools](https://github.com/leonboe1/GoogleFindMyTools),
commit `660be5395702ff7f1a6174f4ec4c865a57c7b527`, by Leon Böttger and contributors.
Vendored code is under `vendor`. Browser-authentication entrypoints are replaced
with explicit server-safe errors; the original credentials and tracker keys are
not included. Original copyright notices are retained. Distributed under GPL-3.0;
see LICENSE. Some vendored components retain their own license notices.
