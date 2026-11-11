"""Doubao Speech v3 HTTP streaming adapter (standard library only)."""
import base64
import binascii
import http.client
import json
import re
from pathlib import Path
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4
from xml.etree import ElementTree

ENDPOINT = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'
CONFIG = Path(__file__).with_name('.env')
RESOURCE = 'seed-tts-2.0'
SPEAKER = 'zh_female_vv_uranus_bigtts'
CONFIG_KEYS = {'DOUBAO_API_KEY', 'DOUBAO_APP_ID', 'DOUBAO_ACCESS_TOKEN',
               'DOUBAO_RESOURCE_ID', 'DOUBAO_SPEAKER_ID'}
MAX_RECORD = 4 * 1024 * 1024
MAX_STREAM = 64 * 1024 * 1024

def read_config(path=CONFIG):
    values = {}
    try:
        with path.open(encoding='utf-8-sig') as source:
            raw = source.read(16385)
    except FileNotFoundError:
        return values
    except UnicodeError:
        raise ValueError('Save the Doubao .env file as UTF-8') from None
    if len(raw) > 16384:
        raise ValueError('The Doubao .env file is too large')
    for number, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        name = name.strip()
        if not separator or name not in CONFIG_KEYS or name in values:
            raise ValueError(f'Unexpected or duplicate field in Doubao .env (line {number})')
        value = value.strip()
        if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
            value = value[1:-1]
        if len(value) > 2048 or (value and not re.fullmatch(r'[!-~]+', value)):
            raise ValueError(f'Invalid value for {name} in Doubao .env')
        values[name] = value
    return values

def config_status(values):
    key, app_id, token = (values.get(k, '') for k in
                          ('DOUBAO_API_KEY', 'DOUBAO_APP_ID', 'DOUBAO_ACCESS_TOKEN'))
    resource = values.get('DOUBAO_RESOURCE_ID') or RESOURCE
    speaker = values.get('DOUBAO_SPEAKER_ID') or SPEAKER
    if resource != RESOURCE:
        raise ValueError('Vivi 2.0 uses DOUBAO_RESOURCE_ID=seed-tts-2.0')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', speaker):
        raise ValueError('Invalid DOUBAO_SPEAKER_ID')
    auth = 'api_key' if key else 'legacy' if app_id and token else None
    missing = ([] if auth else ['DOUBAO_API_KEY'] if not (app_id or token) else
               [name for name, value in (('DOUBAO_APP_ID', app_id), ('DOUBAO_ACCESS_TOKEN', token)) if not value])
    return {'provider': 'doubao', 'ready': bool(auth), 'auth': auth, 'missing': missing,
            'resource_id': resource, 'speaker': speaker, 'checked_online': False}

def request_for(values, narration, options):
    status = config_status(values)
    if not status['ready']:
        raise ValueError('Fill the Doubao .env: ' + ', '.join(status['missing']))
    if not isinstance(options, dict) or options.keys() - {'speech_rate', 'language', 'voice_direction', 'ipa_ssml'}:
        raise ValueError('Doubao options: speech_rate, language, voice_direction, ipa_ssml')
    speed = options.get('speech_rate', 0)
    if type(speed) is not int or not -50 <= speed <= 100:
        raise ValueError('Doubao speech_rate must be an integer between -50 and 100')
    language = options.get('language')
    if language not in (None, 'en', 'zh-cn'):
        raise ValueError('Doubao language must be en or zh-cn')
    direction = options.get('voice_direction')
    if direction is not None and (not isinstance(direction, str) or not 0 < len(direction.strip()) <= 500):
        raise ValueError('Doubao voice_direction must be a nonempty string of up to 500 characters')
    ssml = options.get('ipa_ssml', False)
    if type(ssml) is not bool:
        raise ValueError('Doubao ipa_ssml must be a boolean')
    params = {'speaker': status['speaker'], 'text': narration,
              'audio_params': {'format': 'mp3', 'sample_rate': 24000, 'speech_rate': speed}}
    additions = {}
    if ssml:
        # Scope this mode to local pronunciation markup, not SSML media or DTDs.
        if '<!' in narration or '<?' in narration:
            raise ValueError('Unsupported Doubao IPA markup')
        try:
            root = ElementTree.fromstring(narration)
        except ElementTree.ParseError:
            raise ValueError('Invalid Doubao IPA markup') from None
        if root.tag != 'speak' or root.attrib or not len(root) or any(
            tag.tag != 'phoneme' or len(tag) or set(tag.attrib) != {'alphabet', 'ph'}
            or tag.get('alphabet') != 'ipa' or not re.fullmatch(r'[a-zɪɛæɑɔʊʌəɜθðʃʒŋˈˌː]{1,32}', tag.get('ph', ''))
            or not re.fullmatch(r'[A-Za-z]+(?: [A-Za-z]+)*', tag.text or '') for tag in root
        ):
            raise ValueError('Only speak and IPA phoneme tags are accepted')
        params['text'] = ''.join(root.itertext())
        params['ssml'] = narration
        additions['disable_markdown_filter'] = False
    if language:
        additions['explicit_language'] = language
    if direction is not None:
        additions['context_texts'] = [direction.strip()]
    if additions:
        params['additions'] = json.dumps(additions, ensure_ascii=False)
    headers = {'Content-Type': 'application/json', 'X-Api-Resource-Id': status['resource_id'],
               'X-Api-Request-Id': str(uuid4())}
    if status['auth'] == 'api_key':
        headers['X-Api-Key'] = values['DOUBAO_API_KEY']
    else:
        headers['X-Api-App-Id'] = values['DOUBAO_APP_ID']
        headers['X-Api-Access-Key'] = values['DOUBAO_ACCESS_TOKEN']
    return Request(ENDPOINT, method='POST', headers=headers,
                   data=json.dumps({'req_params': params}, ensure_ascii=False).encode('utf-8'))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def write_audio(stream, out):
    deadline = monotonic() + 180
    total = count = 0
    while monotonic() < deadline:
        line = stream.readline(MAX_RECORD + 1)
        if not line:
            break
        total += len(line)
        if len(line) > MAX_RECORD or total > MAX_STREAM:
            raise ValueError('Doubao response is too large')
        if not line.strip():
            continue
        try:
            packet = json.loads(line)
        except (ValueError, UnicodeError):
            raise ValueError('Invalid Doubao response record') from None
        code = packet.get('code') if isinstance(packet, dict) else None
        if type(code) is not int:
            raise ValueError('Invalid Doubao response code')
        if code == 20000000:
            if not count:
                raise ValueError('Doubao returned no audio')
            return count
        if code != 0:
            raise ValueError(f'Doubao synthesis failed (provider code {code})')
        chunk = packet.get('data')
        if chunk is None or chunk == '':
            continue
        try:
            decoded = base64.b64decode(chunk, validate=True)
        except (binascii.Error, ValueError, TypeError):
            raise ValueError('Invalid Doubao audio data') from None
        out.write(decoded)
        count += len(decoded)
    raise ValueError('Doubao response ended without a completion record')

def fetch_mp3(request, destination):
    try:
        with build_opener(NoRedirect).open(request, timeout=60) as response:
            with destination.open('xb') as out:
                write_audio(response, out)
    except HTTPError as exc:
        raise ValueError(f'Doubao returned HTTP {exc.code}; check key, service and voice access') from None
    except (URLError, TimeoutError, http.client.HTTPException):
        raise ValueError('Doubao network request failed or timed out; no automatic retry') from None
