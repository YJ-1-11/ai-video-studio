import re
from .workflow import die

def number(value, name, maximum=None, minimum=1):
    if type(value) is not int or value < minimum or (maximum and value > maximum):
        die(f'Invalid {name}: {value!r}')
    return value

def millis(frame, fps):
    return (frame * 2000 + fps) // (2 * fps)

def stamp(ms):
    sec, ms = divmod(ms, 1000)
    minute, sec = divmod(sec, 60)
    hour, minute = divmod(minute, 60)
    return f'{hour:02}:{minute:02}:{sec:02},{ms:03}'

def validate(data):
    if data.get('schema') != 1:
        die('Unsupported timeline schema')
    fps = number(data['fps'], 'fps', 120)
    frames = number(data['duration_frames'], 'duration_frames', fps * 3600 * 24)
    for name in ('width', 'height'):
        if number(data[name], name, 8192) % 2:
            die(f'{name} must be even for H.264')
    warnings = []
    for track in ('scenes', 'captions'):
        items = data.get(track)
        if not isinstance(items, list) or (track == 'scenes' and not items):
            die(f'{track} must be a list (at least one scene)')
        prev, ids = 0, set()
        for item in items:
            ident = item['id']
            if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', ident) or ident in ids:
                die(f'{track}: invalid or duplicate ID: {ident!r}')
            ids.add(ident)
            start = number(item['start_frame'], 'start frame', frames, 0)
            end = number(item['end_frame'], 'end frame', frames)
            if not prev <= start < end <= frames:
                die(f'{track}/{ident}: invalid, overlapping or out-of-order interval')
            if track == 'scenes':
                if start != prev or not isinstance(item.get('purpose'), str) or not item['purpose'].strip():
                    die(f'{track}/{ident}: scenes need a purpose and contiguous coverage')
            else:
                text = item['text']
                if (not isinstance(text, str) or not text.strip() or '\r' in text
                    or any(not line.strip() for line in text.split('\n')) or '-->' in text):
                    die(f'Invalid subtitle text: {ident}')
                seconds = (end - start) / fps
                if len(text.split('\n')) > 2 or max(map(len, text.split('\n'))) > 42 or seconds < 0.8 or len(text) / seconds > 20:
                    warnings.append(f'{ident}: review reading time or line breaks')
            prev = end
        if track == 'scenes' and prev != frames:
            die('Scenes must cover the entire timeline')
    return warnings

def srt(data):
    validate(data)
    fps = data['fps']
    return ''.join(f"{i}\n{stamp(millis(c['start_frame'], fps))} --> {stamp(millis(c['end_frame'], fps))}\n{c['text']}\n\n"
                   for i, c in enumerate(data['captions'], 1))
