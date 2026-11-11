from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

CORE = ('outline', 'sample-voice', 'sample-stills', 'sample-motion')
REPARSE = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)

def die(message):
    raise ValueError(message)

def token(value, pattern, name):
    if not isinstance(value, str) or not re.fullmatch(pattern, value, re.ASCII):
        die(f'Invalid {name}: {value!r}')
    return value

def project_id(value):
    token(value, r'[A-Za-z][A-Za-z0-9_-]{0,63}', 'project ID')
    if re.fullmatch(r'(?i:con|prn|aux|nul|com[0-9]|lpt[0-9])', value):
        die('Reserved Windows project name')
    return value

def video_id(value):
    return token(value, r'V(?!000)[0-9]{3}', 'video ID')

def revision_id(value):
    return token(value, r'R(?!000)[0-9]{3}', 'revision ID')

def batch_ids(values):
    if not isinstance(values, list) or not values or len(set(values)) != len(values):
        die('Provide at least one distinct batch ID')
    for value in values:
        token(value, r'B(?!000)[0-9]{3}', 'batch ID')
    return values

def inside(root: Path, relative: str) -> Path:
    # No drive, alternate streams, traversal, Windows aliases or reparse points.
    if not isinstance(relative, str):
        die('Expected a relative path')
    parts = relative.replace('\\', '/').split('/')
    for part in parts:
        if (not part or part in ('.', '..') or part[-1] in '. '
            or re.search(r'[<>:"|?*\x00-\x1f]', part)
            or re.fullmatch(r'(?i:(con|prn|aux|nul|com[0-9¹²³]|lpt[0-9¹²³]|conin\$|conout\$)(?:\..*)?)', part)):
            die(f'Unsafe relative path: {relative!r}')
    cursor = root
    for part in parts:
        cursor = cursor / part
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & REPARSE:
            die(f'Links and junctions are not allowed: {cursor}')
    if not cursor.resolve().is_relative_to(root.resolve()):
        die(f'Path outside scope: {relative}')
    return cursor

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write('\n')

def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def copy_new(src, dst):
    with src.open('rb') as source, dst.open('xb') as target:
        shutil.copyfileobj(source, target)

class Studio:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.base = self.root / 'studio'
        self.template = self.base / 'templates'
        self.projects = inside(self.root, 'projects')
        self.runtime = inside(self.root, 'runtime')

    def project(self, pid):
        path = inside(self.projects, project_id(pid))
        data = read(inside(path, 'project.json'))
        if data.get('schema') != 1 or data.get('id', '').casefold() != pid.casefold():
            die('Project manifest does not match directory')
        return path

    def new_project(self, pid, title, vid, batches):
        title = title.strip()
        if not title:
            die('Project title is empty')
        video_id(vid)
        batch_ids(batches)
        p = inside(self.projects, project_id(pid))
        p.mkdir()
        for folder in ('videos', 'voiceover', 'materials'):
            (p / folder).mkdir()
        copy_new(self.template / 'project' / 'AGENTS.md', p / 'AGENTS.md')
        write(p / 'project.json', {'schema': 1, 'id': pid, 'title': title, 'created_at': utc_now()})
        self.add_video(pid, vid, batches)
        return p

    def add_video(self, pid, vid, batches):
        vid = video_id(vid)
        batches = batch_ids(batches)
        project = self.project(pid)
        v = inside(project, f'videos/{vid}')
        v.mkdir()
        for folder in ('drafts', 'review', 'timeline', 'source'):
            (v / folder).mkdir()
        (v / 'source' / 'public').mkdir()
        copy_new(self.template / 'video' / 'timeline-composition.jsx', v / 'source' / 'timeline-composition.jsx')
        copy_new(self.template / 'video' / 'outline.md', v / 'outline-template.md')
        copy_new(self.template / 'video' / 'timeline.json', v / 'timeline' / 'template.json')
        write(v / 'video.json', {'schema': 1, 'id': vid, 'batches': batches})
        inside(project, f'voiceover/{vid}').mkdir()
        inside(self.runtime, f'{project.name}/{vid}').mkdir(parents=True)
        return v

    def video(self, pid, vid):
        project = self.project(pid)
        v = inside(project, f'videos/{video_id(vid)}')
        data = read(inside(v, 'video.json'))
        if data.get('schema') != 1 or data.get('id') != vid:
            die('Video manifest does not match directory')
        return Video(self, project, v, batch_ids(data.get('batches')))

class Video:
    def __init__(self, studio, project, path, batches):
        self.studio, self.project, self.path = studio, project, path
        self.steps = (*CORE, *batches, 'final')

    def prior(self, stage):
        if stage not in self.steps:
            die(f'Unknown stage: {stage}; expected {", ".join(self.steps)}')
        result = {}
        for step in self.steps[:self.steps.index(stage)]:
            receipt = self.current(step, result)
            if receipt is None:
                die(f'{stage} is waiting for user approval: {step}')
            result[step] = receipt
        return result

    def version(self, stage, rev):
        return inside(self.path, f'review/{stage}/{revision_id(rev)}')

    def current(self, stage, deps):
        base = inside(self.path, f'review/{stage}')
        if not base.is_dir():
            return None
        candidates = sorted((p.name for p in base.iterdir() if re.fullmatch(r'R(?!000)\d{3}', p.name, re.ASCII)), reverse=True)
        for rev in candidates:
            folder = self.version(stage, rev)
            approval = inside(folder, 'approval.json')
            if not approval.exists():
                continue
            submission = self.check_submission(stage, rev)
            receipt = read(approval)
            if (receipt.get('schema') != 1 or receipt.get('stage') != stage or receipt.get('revision') != rev
                or receipt.get('submission_sha256') != sha(inside(folder, 'submission.json'))):
                die(f'Approval integrity failure: {stage}/{rev}')
            if submission.get('prerequisites') != deps:
                return None
            return {'revision': rev, 'approval_sha256': sha(approval)}
        return None

    def check_submission(self, stage, rev):
        folder = self.version(stage, rev)
        item = read(inside(folder, 'submission.json'))
        if item.get('schema') != 1 or item.get('stage') != stage or item.get('revision') != rev or not item.get('files'):
            die(f'Invalid submission: {stage}/{rev}')
        for name, digest in item['files'].items():
            file = inside(folder, f'artifacts/{name}')
            if not file.is_file() or sha(file) != digest:
                die(f'Submission integrity failure: {file}')
        return item

    def submit(self, stage, rev, paths):
        deps = self.prior(stage)
        dst = self.version(stage, rev)
        if not paths:
            die('No review files supplied')
        files, seen = {}, set()
        for name in paths:
            src = inside(self.project, name)
            canonical = src.relative_to(self.project).as_posix()
            allowed = (f'videos/{self.path.name}/drafts/{stage}/{rev}/',
                       f'voiceover/{self.path.name}/{stage}/{rev}/')
            if not canonical.startswith(allowed):
                die(f'File must belong to this video, stage and revision: {canonical}')
            if not src.is_file() or src.stat().st_size == 0:
                die(f'Review artifact is missing or empty: {src}')
            if src.name.casefold() in seen:
                die(f'Duplicate review filename: {src.name}')
            files[src.name] = src
            seen.add(src.name.casefold())
        dst.mkdir(parents=True)
        (dst / 'artifacts').mkdir()
        hashes = {}
        for name, src in files.items():
            file = inside(dst, f'artifacts/{name}')
            copy_new(src, file)
            hashes[name] = sha(file)
            file.chmod(stat.S_IREAD)
        item = {'schema': 1, 'stage': stage, 'revision': rev,
                'submitted_at': utc_now(), 'prerequisites': deps, 'files': hashes}
        metadata = inside(dst, 'submission.json')
        write(metadata, item)
        metadata.chmod(stat.S_IREAD)
        return dst

    def approve(self, stage, rev, confirmed, note):
        if not confirmed or not note.strip():
            die('Record only explicit user approval: --confirmed-by-user and --note required')
        deps = self.prior(stage)
        submission = self.check_submission(stage, rev)
        if submission.get('prerequisites') != deps:
            die('Prerequisites changed since submission; submit a new revision')
        active = self.current(stage, deps)
        if active and active['revision'] >= rev:
            die('This revision is already approved or older than the active approval')
        folder = self.version(stage, rev)
        path = inside(folder, 'approval.json')
        write(path, {'schema': 1, 'stage': stage, 'revision': rev, 'approved_at': utc_now(),
                     'user_confirmation': note.strip(),
                     'submission_sha256': sha(inside(folder, 'submission.json'))})
        path.chmod(stat.S_IREAD)
        return path

    def status(self):
        result, chain, blocked = [], {}, False
        for stage in self.steps:
            receipt = None if blocked else self.current(stage, chain)
            state = 'blocked' if blocked else ('approved' if receipt else 'awaiting approval')
            result.append({'stage': stage, 'state': state, **(receipt or {})})
            if receipt:
                chain[stage] = receipt
            else:
                blocked = True
        return result

    def destination(self, stage, rev, name, *, voice=False):
        self.prior(stage)
        revision_id(rev)
        if self.version(stage, rev).exists():
            die('Revision has already been submitted; create a new revision')
        base = f'voiceover/{self.path.name}' if voice else f'videos/{self.path.name}/drafts'
        target = inside(self.project, f'{base}/{stage}/{rev}/{name}')
        if target.exists():
            die(f'Output already exists; choose a new name or revision: {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def run_dir(self):
        from uuid import uuid4
        p = inside(self.studio.runtime, f'{self.project.name}/{self.path.name}/{uuid4().hex}')
        p.mkdir()
        return p
