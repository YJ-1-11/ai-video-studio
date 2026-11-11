import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import wave

from .workflow import copy_new, die, inside, token

MAX_WAV = 64 * 1024 * 1024

def command(name):
    p = shutil.which(name)
    if not p:
        die(f'{name} not found; load studio/tools/tool-paths.ps1 first')
    return p

def call(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)

def probe(path):
    result = call([command('ffprobe'), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path],
                  stdout=subprocess.PIPE, encoding='utf-8')
    return json.loads(result.stdout)

def duration(info, stream=None):
    value = float((stream or {}).get('duration', info.get('format', {}).get('duration', 0)))
    if not math.isfinite(value) or value <= 0:
        die('Missing or invalid media duration')
    return value

def qa(path, silent_ok=False, timeline=None):
    info = probe(path)
    video = [s for s in info['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')]
    audio = [s for s in info['streams'] if s['codec_type'] == 'audio']
    seconds = duration(info)
    problems = []
    if 'mp4' not in info['format']['format_name'].split(',') or path.suffix.lower() != '.mp4':
        problems.append('expected MP4')
    if len(video) != 1 or video[0]['codec_name'] != 'h264' or video[0]['pix_fmt'] != 'yuv420p':
        problems.append('expected one H.264 yuv420p video stream')
    if (not audio and not silent_ok) or len(audio) > 1 or any(s['codec_name'] != 'aac' for s in audio):
        problems.append('expected one AAC audio stream unless silence is explicitly allowed')
    if timeline and len(video) == 1:
        from fractions import Fraction
        s = video[0]
        if (s['width'], s['height']) != (timeline['width'], timeline['height']):
            problems.append('resolution does not match the timeline')
        if Fraction(s['avg_frame_rate']) != timeline['fps']:
            problems.append('frame rate does not match the timeline')
        if abs(seconds - timeline['duration_frames'] / timeline['fps']) > max(0.06, 1 / timeline['fps']):
            problems.append('duration does not match the timeline')
    if problems:
        die('; '.join(problems))
    call([command('ffmpeg'), '-v', 'error', '-xerror', '-nostdin', '-i', path,
          '-map', '0:v:0', '-map', '0:a:0?', '-f', 'null', '-'])
    return {'duration_seconds': seconds, 'width': video[0]['width'], 'height': video[0]['height'],
            'video': 'h264', 'audio': 'aac' if audio else None,
            'human_review': 'not performed; check intelligibility, sync and visual legibility'}

def own_input(video, relative, *, source=False):
    path = inside(video.project, relative)
    rel = path.relative_to(video.project).as_posix()
    prefix = f'videos/{video.path.name}/'
    if source:
        valid = rel.startswith(prefix + 'source/')
    else:
        valid = rel.startswith((prefix, f'voiceover/{video.path.name}/'))
    if not valid or not path.is_file():
        die(f'Input must be a file in this video scope: {relative}')
    return path

def remotion(video, stage, rev, entry, kind, *, comp=None, name=None, frame=None):
    video.prior(stage)
    if kind == 'still' and stage not in ('sample-stills', *video.steps[4:-1]):
        die('Still output belongs to sample-stills or a production batch')
    if kind != 'still' and stage not in ('sample-motion', *video.steps[4:]):
        die('Motion preview or render is not allowed before sample-motion')
    entry = own_input(video, entry, source=True)
    if entry.suffix.lower() not in ('.ts', '.tsx', '.js', '.jsx'):
        die('Remotion entry must be a JS/TS file')
    tool = video.studio.base / 'tools' / 'remotion'
    cli = tool / 'node_modules' / '@remotion' / 'cli' / 'remotion-cli.js'
    cached_browser = tool / 'node_modules' / '.remotion' / 'chrome-headless-shell' / 'win64' / 'chrome-headless-shell-win64' / 'chrome-headless-shell.exe'
    chrome = Path(os.environ.get('AI_VIDEO_STUDIO_BROWSER') or cached_browser).expanduser()
    if not cli.is_file():
        die('Install Remotion dependencies with npm ci (see README.md)')
    if kind != 'studio' and not chrome.is_file():
        die('Install the Remotion browser or set AI_VIDEO_STUDIO_BROWSER to an existing executable')
    chrome = chrome.resolve()
    if video.version(stage, rev).exists():
        die('Revision has already been submitted; create a new revision')
    run = video.run_dir()
    # Child temp locations are project-specific; this does not mutate the parent process environment.
    env = dict(os.environ, TEMP=str(run), TMP=str(run), TMPDIR=str(run),
               AI_VIDEO_STUDIO_REMOTION_MODULES=str(tool / 'node_modules'))
    for secret in ('AI_VIDEO_TTS_TOKEN', 'AI_VIDEO_TTS_URL'):
        env.pop(secret, None)
    launcher = tool / 'studio-local.cjs' if kind == 'studio' else cli
    public = inside(video.path, 'source/public')
    common = [command('node'), launcher, kind, entry, f'--config={tool / "studio.config.js"}',
              f'--public-dir={public}']
    if kind == 'studio':
        call([*common, '--no-open', '--disable-git-source'], cwd=video.path, env=env)
        return None
    token(comp, r'[A-Za-z0-9-]+', 'composition ID')
    expected = '.png' if kind == 'still' else '.mp4'
    if Path(name).suffix.lower() != expected:
        die(f'Output must use {expected}')
    target = video.destination(stage, rev, name)
    temp = run / ('render' + expected)
    flags = [f'--browser-executable={chrome}']
    if kind == 'still':
        flags += [f'--frame={frame}', '--image-format=png']
    else:
        flags += ['--codec=h264', '--pixel-format=yuv420p']
    call([*common, comp, temp, *flags], cwd=video.path, env=env)
    if not temp.is_file() or not temp.stat().st_size:
        die('Remotion did not produce an output')
    copy_new(temp, target)
    return target

def mux(video, stage, rev, picture, speech, subtitle, name):
    video.prior(stage)
    if stage not in ('sample-motion', *video.steps[4:]):
        die('Mux is not allowed before sample-motion')
    if Path(name).suffix.lower() != '.mp4':
        die('Mux output must be MP4')
    picture, speech = [own_input(video, p) for p in (picture, speech)]
    picture_info, voice_info = probe(picture), probe(speech)
    tracks = [s for s in picture_info['streams'] if s['codec_type'] == 'video']
    if not tracks:
        die('Missing picture track')
    audios = [s for s in voice_info['streams'] if s['codec_type'] == 'audio']
    if not audios or duration(voice_info, audios[0]) > duration(picture_info, tracks[0]) + 0.001:
        die('Narration is missing or longer than the picture; adjust the timeline rather than trimming speech')
    target = video.destination(stage, rev, name)
    temp = video.run_dir() / 'mux.mp4'
    args = [command('ffmpeg'), '-v', 'error', '-nostdin', '-n', '-i', picture, '-i', speech]
    maps = ['-map', '0:v:0', '-map', '1:a:0']
    if subtitle:
        path = own_input(video, subtitle)
        if path.suffix.lower() != '.srt':
            die('Selectable subtitles must be an SRT file')
        args.extend(['-i', path])
        maps.extend(['-map', '2:s:0', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng'])
    call([*args, *maps, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000',
          '-af', 'apad', '-shortest', '-movflags', '+faststart', temp])
    qa(temp)
    copy_new(temp, target)
    return target

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch_wav(endpoint, key, payload, dest):
    url = urlsplit(endpoint)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment or url.query:
        die('TTS endpoint must be HTTPS without credentials, a query or fragment')
    req = Request(endpoint, data=json.dumps(payload).encode('utf-8'), method='POST',
                  headers={'Content-Type': 'application/json', 'Accept': 'audio/wav',
                           'Authorization': 'Bearer ' + key})
    try:
        with build_opener(NoRedirect).open(req, timeout=90) as response, dest.open('xb') as out:
            count = 0
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > MAX_WAV:
                    die('TTS audio exceeds the maximum size')
                out.write(chunk)
    except HTTPError as exc:
        raise ValueError(f'TTS server returned HTTP {exc.code}; response not recorded') from None

def tts(video, stage, rev, script, name, config, online, *, provider='generic'):
    video.prior(stage)
    if stage not in ('sample-voice', *video.steps[4:-1]):
        die('TTS belongs to sample-voice or a production batch')
    if not online:
        die('Network call requires --allow-network after user approval')
    revision_root = f'voiceover/{video.path.name}/{stage}/{rev}/'
    source = own_input(video, script)
    if not source.relative_to(video.project).as_posix().startswith(revision_root) or source.suffix.lower() != '.txt':
        die('Narration must be a .txt file in this voiceover stage/revision directory')
    narration = source.read_text(encoding='utf-8-sig').strip()
    if not 0 < len(narration) <= 20_000 or Path(name).suffix.lower() != '.wav':
        die('TTS needs 1–20,000 text characters and a .wav output')
    if provider == 'doubao':
        from tools.tts import doubao
        request = doubao.request_for(doubao.read_config(), narration, config)
        ffmpeg = command('ffmpeg')  # Verify local dependency before the paid request.
    elif provider == 'generic':
        endpoint, key = os.environ.get('AI_VIDEO_TTS_URL'), os.environ.get('AI_VIDEO_TTS_TOKEN')
        if not endpoint or not key:
            die('Set AI_VIDEO_TTS_URL and AI_VIDEO_TTS_TOKEN for the selected provider')
        if not isinstance(config, dict) or 'input' in config:
            die('TTS options must be a JSON object without the input field')
    else:
        die('Unknown TTS provider')
    target = video.destination(stage, rev, name, voice=True)
    run = video.run_dir()
    temp = run / 'tts.wav'
    if provider == 'doubao':
        mp3 = run / 'tts.mp3'
        doubao.fetch_mp3(request, mp3)
        call([ffmpeg, '-v', 'error', '-xerror', '-nostdin', '-n', '-i', mp3,
              '-map', '0:a:0', '-c:a', 'pcm_s16le', temp])
    else:
        fetch_wav(endpoint, key, {**config, 'input': narration}, temp)
    with wave.open(str(temp)) as audio:
        if not audio.getnframes() or not audio.getframerate() or not audio.readframes(1):
            die('TTS provider did not return readable PCM audio')
    copy_new(temp, target)
    return target
