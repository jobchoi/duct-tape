"""Trusted application descriptions shared with Windows media resolution."""
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath

DEFAULT = Path(__file__).resolve().parents[2]/'Config/Applications.json'


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Invalid application path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Application paths must be relative')
    return value


@dataclass(frozen=True)
class Application:
    id: str
    name: str
    media_folder: str
    source_candidates: tuple[str, ...]
    required_files: tuple[str, ...]
    key_file: str | None
    modules: tuple[str, ...]

    def resolve(self, root):
        candidates = [root/path for path in self.source_candidates]
        for path in candidates:
            if all((path/name).is_file() for name in self.required_files):
                return path
        for path in candidates:
            if any((path/name).is_file() for name in self.required_files):
                return path
        return candidates[0]


def load(path=DEFAULT):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if set(data)-{'applications','common_modules'}:
        raise ValueError('Unexpected catalogue fields')
    apps = []
    for item in data['applications']:
        if set(item)-{'id','name','media_folder','source_candidates','required_files','key_file','modules'}:
            raise ValueError('Unexpected application fields')
        folder=relative(item['media_folder'])
        if '/' in folder or not item['source_candidates'] or not item['required_files'] or not item['modules']:
            raise ValueError('Invalid application media definition')
        apps.append(Application(item['id'], item['name'], folder,
            tuple(relative(p) for p in item['source_candidates']),
            tuple(relative(p) for p in item['required_files']), relative(item['key_file']) if item.get('key_file') else None,
            tuple(relative(p) for p in item['modules'])))
    if not apps or len({a.id for a in apps}) != len(apps) or len({a.media_folder for a in apps}) != len(apps):
        raise ValueError('Duplicate or empty application catalogue')
    return tuple(apps)


def module_paths(path=DEFAULT):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    modules = list(data.get('common_modules', []))
    modules.extend(module for app in load(path) for module in app.modules)
    for module in modules:
        relative(module)
        if not module.startswith('Modules/') or not module.endswith('.ps1') or len(PurePosixPath(module).parts) != 2:
            raise ValueError('Application modules must be reviewed Modules scripts')
    return tuple(dict.fromkeys(modules))
