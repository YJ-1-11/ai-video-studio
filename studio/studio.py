"""Local AI Video Studio command line. No network or rendering on import."""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

from lib import media, timeline
from tools.tts import doubao
from lib.workflow import Studio, die, inside, read

ROOT = Path(__file__).resolve().parents[1]

def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    def args(command, *, project=False, video=False, stage=False, rev=False):
        a = sub.add_parser(command)
        if project or video or stage or rev:
            a.add_argument('project')
        if video or stage or rev:
            a.add_argument('video')
        if stage or rev:
            a.add_argument('stage')
        if rev:
            a.add_argument('revision')
        return a
    n = args('new', project=True)
    n.add_argument('--title', required=True)
    n.add_argument('--video', default='V001')
    n.add_argument('--batches', nargs='+', default=['B001'])
    n = args('add-video', video=True)
    n.add_argument('--batches', nargs='+', default=['B001'])
    args('status', video=True)
    args('require', stage=True)
    args('prepare', rev=True).add_argument('--voice', action='store_true')
    args('submit', rev=True).add_argument('files', nargs='+')
    a = args('approve', rev=True)
    a.add_argument('--confirmed-by-user', action='store_true')
    a.add_argument('--note', required=True)
    args('check-timeline', video=True).add_argument('timeline')
    a = args('captions', rev=True)
    a.add_argument('timeline')
    a.add_argument('--out', default='captions.srt')
    a = args('preview', rev=True)
    a.add_argument('entry')
    for kind in ('still', 'render'):
        a = args(kind, rev=True)
        a.add_argument('entry')
        a.add_argument('composition')
        a.add_argument('output')
        if kind == 'still':
            a.add_argument('--frame', type=int, default=0)
    a = args('mux', rev=True)
    a.add_argument('picture')
    a.add_argument('speech')
    a.add_argument('output')
    a.add_argument('--srt')
    a = args('qa', video=True)
    a.add_argument('media')
    a.add_argument('--timeline')
    a.add_argument('--silent-ok', action='store_true')
    args('tts-config')
    a = args('tts', rev=True)
    a.add_argument('--provider', choices=('generic', 'doubao'), default='generic')
    a.add_argument('script')
    a.add_argument('output')
    a.add_argument('--options', default='{}', help='Provider-specific JSON; do not pass secrets')
    a.add_argument('--allow-network', action='store_true')
    return p

def execute(a, studio):
    if a.cmd == 'new':
        return studio.new_project(a.project, a.title, a.video, a.batches)
    if a.cmd == 'add-video':
        return studio.add_video(a.project, a.video, a.batches)
    if a.cmd == 'tts-config':
        return doubao.config_status(doubao.read_config())
    v = studio.video(a.project, a.video)
    if a.cmd == 'status':
        return v.status()
    if a.cmd == 'require':
        return v.prior(a.stage)
    if a.cmd == 'prepare':
        if a.voice and a.stage not in ('sample-voice', *v.steps[4:-1]):
            die('Voiceover only belongs to sample-voice or a production batch')
        return v.destination(a.stage, a.revision, 'work-placeholder', voice=a.voice).parent
    if a.cmd == 'submit':
        return v.submit(a.stage, a.revision, a.files)
    if a.cmd == 'approve':
        return v.approve(a.stage, a.revision, a.confirmed_by_user, a.note)
    if a.cmd in ('captions', 'check-timeline'):
        data = read(media.own_input(v, a.timeline))
        warnings = timeline.validate(data)
        if a.cmd == 'check-timeline':
            return {'valid': True, 'warnings': warnings}
        if a.stage not in ('sample-stills', 'sample-motion', *v.steps[4:]):
            die('Subtitle export is not allowed before sample-stills')
        if not a.out.lower().endswith('.srt'):
            die('Subtitle output must use .srt')
        if not data['captions']:
            die('No subtitle cues to export')
        output = v.destination(a.stage, a.revision, a.out)
        with output.open('x', encoding='utf-8', newline='\n') as out:
            out.write(timeline.srt(data))
        return {'output': str(output), 'warnings': warnings}
    if a.cmd in ('still', 'render', 'preview'):
        if a.cmd == 'still' and a.frame < 0:
            die('Frame must be non-negative')
        return media.remotion(v, a.stage, a.revision, a.entry,
                              'studio' if a.cmd == 'preview' else a.cmd,
                              comp=getattr(a, 'composition', None),
                              name=getattr(a, 'output', None), frame=getattr(a, 'frame', None))
    if a.cmd == 'mux':
        return media.mux(v, a.stage, a.revision, a.picture, a.speech, a.srt, a.output)
    if a.cmd == 'tts':
        return media.tts(v, a.stage, a.revision, a.script, a.output, json.loads(a.options),
                         a.allow_network, provider=a.provider)
    if a.cmd == 'qa':
        data = read(media.own_input(v, a.timeline)) if a.timeline else None
        if data is not None:
            timeline.validate(data)
        return media.qa(media.own_input(v, a.media), a.silent_ok, data)

def main(argv=None):
    try:
        result = execute(parser().parse_args(argv), Studio(ROOT))
    except (ValueError, OSError, KeyError, TypeError, AttributeError, EOFError,
            subprocess.CalledProcessError, wave.Error) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, (dict, list)) else result)
    return 0

if __name__ == '__main__':
    sys.exit(main())
