import copy
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from lib import media, timeline
from lib.workflow import Studio, inside
from studio import execute, parser

def timing():
    return {'schema': 1, 'fps': 30, 'width': 1920, 'height': 1080, 'duration_frames': 90,
            'scenes': [{'id': 'S01', 'purpose': 'test clock only', 'start_frame': 0, 'end_frame': 90}],
            'captions': [{'id': 'C01', 'text': 'Fixture only.', 'start_frame': 15, 'end_frame': 60}]}

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workspace = os.environ.get('AI_VIDEO_STUDIO_TEST_WORK')
        if not workspace:
            raise RuntimeError('Set AI_VIDEO_STUDIO_TEST_WORK to an approved scratch directory (not projects).')
        p = Path(workspace).resolve()
        studio_root = BASE.parent
        if p == studio_root or p.is_relative_to(studio_root / 'projects'):
            raise RuntimeError('Do not use the live projects directory for fixtures.')
        cls.scratch = p / ('framework-test-' + uuid4().hex[:12])
        cls.scratch.mkdir(parents=True)
        shutil.copytree(BASE / 'templates', cls.scratch / 'studio' / 'templates')
        (cls.scratch / 'projects').mkdir()
        (cls.scratch / 'runtime').mkdir()

    def setUp(self):
        self.studio = Studio(self.scratch)
        self.pid = 'Test_' + uuid4().hex[:10]
        self.p = self.studio.new_project(self.pid, 'Fixture (no media)', 'V001', ['B001', 'B002'])
        self.v = self.studio.video(self.pid, 'V001')

    def cli(self, *args):
        return execute(parser().parse_args(args), self.studio)

    def draft(self, stage, rev='R001', voice=False, name='check.txt'):
        p = self.v.destination(stage, rev, name, voice=voice)
        p.write_text('Text fixture; not a production asset.', encoding='utf-8')
        return p.relative_to(self.p).as_posix()

    def accept(self, stage, rev='R001'):
        folder = self.v.submit(stage, rev, [self.draft(stage, rev, stage == 'sample-voice')])
        self.v.approve(stage, rev, True, 'TEST FIXTURE — not a user approval')
        return folder

    def test_project_template_and_independent_video(self):
        self.assertTrue((self.p / 'AGENTS.md').is_file())
        self.assertTrue((self.v.path / 'source' / 'timeline-composition.jsx').is_file())
        self.assertTrue((self.p / 'voiceover' / 'V001').is_dir())
        self.studio.add_video(self.pid, 'V002', ['B001'])
        second = self.studio.video(self.pid, 'V002')
        self.accept('outline')
        self.assertEqual(second.status()[0]['state'], 'awaiting approval')
        self.assertNotEqual(self.v.run_dir().parent, second.run_dir().parent)
        with self.assertRaises(FileExistsError):
            self.studio.new_project(self.pid, 'duplicate', 'V001', ['B001'])

    def test_path_escape_and_other_video_input(self):
        for invalid in ('../other', 'D:/elsewhere', 'test:stream', 'a/../b', 'folder/NUL.txt', 'file.'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                inside(self.p, invalid)
        self.studio.add_video(self.pid, 'V002', ['B001'])
        second = self.studio.video(self.pid, 'V002')
        path = self.draft('outline')
        with self.assertRaises(ValueError):
            second.submit('outline', 'R001', [path])
        with self.assertRaises(ValueError):
            media.own_input(second, path)

    def test_requires_user_approval_not_submission(self):
        self.v.submit('outline', 'R001', [self.draft('outline')])
        with self.assertRaisesRegex(ValueError, 'confirmed-by-user'):
            self.v.approve('outline', 'R001', False, 'not confirmed')
        with self.assertRaisesRegex(ValueError, 'outline'):
            self.v.prior('sample-voice')
        with self.assertRaises(ValueError):
            self.v.approve('outline', 'R001', True, '   ')

    def test_full_chain_and_batch_order(self):
        for stage in self.v.steps:
            position = self.v.steps.index(stage)
            self.assertEqual(self.v.status()[position]['state'], 'awaiting approval')
            if position + 1 < len(self.v.steps):
                next_stage = self.v.steps[position + 1]
                self.assertEqual(self.v.status()[position + 1]['state'], 'blocked')
                with self.assertRaisesRegex(ValueError, 'waiting for user approval'):
                    self.v.prior(next_stage)
            self.accept(stage)
        self.assertTrue(all(s['state'] == 'approved' for s in self.v.status()))

    def test_immutable_snapshots_and_updated_upstream(self):
        approved = self.accept('outline')
        old_data = (approved / 'artifacts' / 'check.txt').read_bytes()
        self.accept('sample-voice')
        self.assertFalse((approved / 'artifacts' / 'check.txt').stat().st_mode & stat.S_IWRITE)
        with self.assertRaises(FileExistsError):
            self.v.submit('outline', 'R001', ['videos/V001/drafts/outline/R001/check.txt'])
        with self.assertRaisesRegex(ValueError, 'already'):
            self.v.approve('outline', 'R001', True, 'TEST')
        with self.assertRaisesRegex(ValueError, 'already'):
            self.v.destination('outline', 'R001', 'another.txt')
        self.accept('outline', 'R002')
        self.assertEqual((approved / 'artifacts' / 'check.txt').read_bytes(), old_data)
        with self.assertRaisesRegex(ValueError, 'sample-voice'):
            self.v.prior('sample-stills')
        self.accept('sample-voice', 'R002')
        self.assertIn('sample-voice', self.v.prior('sample-stills'))

    def test_detects_tampering(self):
        approved = self.accept('outline') / 'artifacts' / 'check.txt'
        approved.chmod(stat.S_IREAD | stat.S_IWRITE)  # intentionally corrupt a scratch fixture only
        approved.write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.v.prior('sample-voice')

    def test_media_entry_points_respect_gates_without_spawning(self):
        with patch.object(media, 'call') as call:
            with self.assertRaisesRegex(ValueError, 'outline'):
                self.cli('render', self.pid, 'V001', 'sample-motion', 'R001', 'missing.jsx', 'Lesson', 'test.mp4')
            with self.assertRaisesRegex(ValueError, 'Motion preview'):
                self.cli('preview', self.pid, 'V001', 'outline', 'R001', 'missing.jsx')
            self.accept('outline')
            with self.assertRaisesRegex(ValueError, 'sample-voice'):
                self.cli('still', self.pid, 'V001', 'sample-stills', 'R001', 'missing.jsx', 'Lesson', 'test.png')
            call.assert_not_called()

    def test_tts_opt_in_before_network(self):
        self.accept('outline')
        with patch.object(media, 'fetch_wav') as fetch:
            with self.assertRaisesRegex(ValueError, 'allow-network'):
                self.cli('tts', self.pid, 'V001', 'sample-voice', 'R001', 'not-sent.txt', 'test.wav')
            fetch.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            media.fetch_wav('http://example.invalid', 'not-a-token', {}, self.p / 'no.wav')

    def test_cli_srt_stays_in_revision_and_no_overwrite(self):
        data = self.v.path / 'timeline' / 'fixture.json'
        data.write_text(json.dumps(timing()), encoding='utf-8')
        args = ('captions', self.pid, 'V001', 'sample-stills', 'R001', 'videos/V001/timeline/fixture.json')
        with self.assertRaises(ValueError):
            self.cli(*args)
        for stage in ('outline', 'sample-voice'):
            self.accept(stage)
        path = Path(self.cli(*args)['output'])
        self.assertEqual(path, self.v.path / 'drafts' / 'sample-stills' / 'R001' / 'captions.srt')
        self.assertIn('00:00:00,500 --> 00:00:02,000', path.read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.cli(*args)

class TimelineTests(unittest.TestCase):
    def test_exact_frame_conversion(self):
        self.assertEqual(timeline.millis(1, 30), 33)
        self.assertEqual(timeline.millis(2, 30), 67)
        self.assertEqual(timeline.srt(timing()), '1\n00:00:00,500 --> 00:00:02,000\nFixture only.\n\n')

    def test_rejects_overlap_gap_and_out_of_range(self):
        for field, edit in (
            ('scenes', {'start_frame': 1}),
            ('scenes', {'end_frame': 89}),
            ('captions', {'end_frame': 91}),
            ('captions', {'start_frame': True}),
        ):
            data = timing()
            data[field][0].update(edit)
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                timeline.validate(data)
        data = timing()
        data['captions'].append(dict(data['captions'][0], id='C02', start_frame=55, end_frame=80))
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            timeline.validate(data)

    def test_caption_legibility_warning_does_not_rewrite(self):
        data = timing()
        data['captions'][0]['text'] = 'x' * 75
        original = copy.deepcopy(data)
        self.assertTrue(timeline.validate(data))
        self.assertEqual(original, data)
