"""One bounded location request. Never write Google credentials into source files."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor'))


def finish(payload, code=0):
    print(json.dumps(payload), flush=True)
    os._exit(code)  # FCM owns background threads; terminate this request's child only.


def main():
    timer = threading.Timer(48, lambda: finish({'error': 'Google did not return a report in time. Please try again.'}, 2))
    timer.daemon = True
    timer.start()
    try:
        cached = json.loads(base64.b64decode(os.environ['FINDMY_SECRETS_B64'], validate=True))
        for field in ('username', 'aas_token', 'owner_key', 'fcm_credentials'):
            if not cached.get(field):
                raise ValueError('Incomplete desktop session')
        with tempfile.TemporaryDirectory(prefix='find-session-') as directory:
            secret_file = Path(directory) / 'secrets.json'
            secret_file.write_text(json.dumps(cached), encoding='utf-8')
            secret_file.chmod(0o600)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                import Auth.token_cache as cache
                cache._get_secrets_file = lambda: str(secret_file)
                from NovaApi.ListDevices.nbe_list_devices import request_device_list
                from ProtoDecoders.decoder import parse_device_list_protobuf
                from SpotApi.UploadPrecomputedPublicKeyIds.upload_precomputed_public_key_ids import refresh_custom_trackers
                import NovaApi.ExecuteAction.LocateTracker.decrypt_locations as decrypt_module
                from NovaApi.ExecuteAction.LocateTracker.location_request import get_location_data_for_device
                from ProtoDecoders import DeviceUpdate_pb2, Common_pb2
                device_id = os.environ['TRACKER_DEVICE_ID']
                devices = parse_device_list_protobuf(request_device_list())
                selected = [d for d in devices.deviceMetadata
                            if any(c.id == device_id for c in d.identifierInformation.canonicIds.canonicId)]
                if not selected:
                    raise ValueError('Tracker registration not found')
                # Renew this selected custom tracker's advertised IDs, as upstream requires.
                one = DeviceUpdate_pb2.DevicesList()
                one.deviceMetadata.add().CopyFrom(selected[0])
                refresh_custom_trackers(one)
                collected = []
                original = decrypt_module.WrappedLocation
                def collect(*args, **kwargs):
                    loc = original(*args, **kwargs)
                    collected.append(loc)
                    return loc
                decrypt_module.WrappedLocation = collect
                get_location_data_for_device(device_id, os.environ.get('TRACKER_NAME', 'My tracker'))
                reports = []
                for loc in collected:
                    if loc.status == Common_pb2.Status.SEMANTIC:
                        continue
                    point = DeviceUpdate_pb2.Location()
                    point.ParseFromString(loc.decrypted_location)
                    lat, lon = point.latitude / 1e7, point.longitude / 1e7
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        reports.append({'latitude': lat, 'longitude': lon, 'timestamp': loc.time,
                                        'accuracy': loc.accuracy, 'ownReport': loc.is_own_report})
            result = {'name': os.environ.get('TRACKER_NAME', 'My tracker'),
                      'location': max(reports, key=lambda p: p['timestamp']) if reports else None}
        finish(result)
    except Exception:
        finish({'error': 'Unable to retrieve location. Check your saved Google session and tracker registration, then retry.'}, 1)


if __name__ == '__main__':
    main()
