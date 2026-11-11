import base64
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import execute, parser
from tools.tts import doubao

def stream(*records):
    return io.BytesIO(b''.join(json.dumps(record).encode() + b'\n' for record in records))

class DoubaoTests(unittest.TestCase):
    def test_vivi_defaults_and_missing_key(self):
        status = doubao.config_status({})
        self.assertFalse(status['ready'])
        self.assertEqual(status['speaker'], 'zh_female_vv_uranus_bigtts')
        self.assertEqual(status['resource_id'], 'seed-tts-2.0')

    def test_api_key_request_only_uses_new_auth(self):
        req = doubao.request_for({'DOUBAO_API_KEY': 'fixture-key', 'DOUBAO_APP_ID': 'fixture-id',
                                   'DOUBAO_ACCESS_TOKEN': 'fixture-token'}, 'Hello.', {'language': 'en'})
        headers = {k.lower(): v for k, v in req.header_items()}
        self.assertEqual(req.full_url, doubao.ENDPOINT)
        self.assertEqual(headers['x-api-key'], 'fixture-key')
        self.assertNotIn('x-api-access-key', headers)
        params = json.loads(req.data)['req_params']
        self.assertEqual(params['speaker'], doubao.SPEAKER)
        self.assertEqual(params['audio_params']['format'], 'mp3')
        self.assertEqual(json.loads(params['additions'])['explicit_language'], 'en')

    def test_legacy_requires_both_fields(self):
        values = {'DOUBAO_APP_ID': 'fixture-id'}
        self.assertEqual(doubao.config_status(values)['missing'], ['DOUBAO_ACCESS_TOKEN'])
        req = doubao.request_for({**values, 'DOUBAO_ACCESS_TOKEN': 'fixture-token'}, 'Hello.', {})
        headers = {k.lower(): v for k, v in req.header_items()}
        self.assertEqual(headers['x-api-app-id'], 'fixture-id')
        self.assertEqual(headers['x-api-access-key'], 'fixture-token')

    def test_voice_direction_is_context_and_not_spoken_text(self):
        config = {'DOUBAO_API_KEY': 'fixture-key'}
        req = doubao.request_for(config, 'Hello.', {'voice_direction': '  语速自然。  '})
        params = json.loads(req.data)['req_params']
        self.assertEqual(params['text'], 'Hello.')
        self.assertEqual(json.loads(params['additions']), {'context_texts': ['语速自然。']})
        for invalid in ('  ', 'x' * 501, ['direction']):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'voice_direction'):
                doubao.request_for(config, 'Hello.', {'voice_direction': invalid})

    def test_ipa_markup_keeps_plain_text_and_disables_markdown_filter(self):
        config = {'DOUBAO_API_KEY': 'fixture-key'}
        text = '<speak>看，<phoneme alphabet="ipa" ph="ən">un</phoneme>。</speak>'
        params = json.loads(doubao.request_for(config, text, {'ipa_ssml': True}).data)['req_params']
        self.assertEqual(params['text'], '看，un。')
        self.assertEqual(params['ssml'], text)
        self.assertFalse(json.loads(params['additions'])['disable_markdown_filter'])
        with self.assertRaisesRegex(ValueError, 'Only speak'):
            doubao.request_for(config, '<speak><audio src="https://example.com/a"/></speak>', {'ipa_ssml': True})

    def test_offline_status_never_calls_api_or_displays_key(self):
        with patch.object(doubao, 'read_config', return_value={'DOUBAO_API_KEY': 'fixture-secret'}), \
                patch.object(doubao, 'fetch_mp3') as fetch:
            result = execute(parser().parse_args(['tts-config']), None)
            self.assertTrue(result['ready'])
            self.assertNotIn('fixture-secret', json.dumps(result))
            fetch.assert_not_called()

    def test_stream_assembles_complete_audio_only(self):
        out = io.BytesIO()
        self.assertEqual(doubao.write_audio(stream(
            {'code': 0, 'data': base64.b64encode(b'fixture-').decode()},
            {'code': 0, 'data': None}, {'code': 0, 'data': base64.b64encode(b'bytes').decode()},
            {'code': 20000000, 'data': None}), out), len(b'fixture-bytes'))
        self.assertEqual(out.getvalue(), b'fixture-bytes')
        for packet, message in (({'code': 0, 'data': 'YQ=='}, 'without a completion'),
                                ({'code': 20000000}, 'no audio'),
                                ({'code': 45000000, 'message': 'fixture-secret'}, '45000000'),
                                ({'code': 0, 'data': '!'}, 'Invalid Doubao audio')):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message) as raised:
                doubao.write_audio(stream(packet), io.BytesIO())
            self.assertNotIn('fixture-secret', str(raised.exception))

    def test_unapproved_synthesis_does_not_load_credentials(self):
        class Video:
            steps = ('outline', 'sample-voice', 'sample-stills', 'sample-motion', 'B001', 'final')
            def prior(self, stage):
                return None
        from lib import media
        with patch.object(doubao, 'read_config') as config:
            with self.assertRaisesRegex(ValueError, 'allow-network'):
                media.tts(Video(), 'sample-voice', 'R001', 'script.txt', 'voice.wav', {}, False, provider='doubao')
            config.assert_not_called()
