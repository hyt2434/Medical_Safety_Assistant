"""Project-local relocation of sealed historical evidence paths.

Artifacts retain their original bytes and provenance strings. Only filesystem access
is relocated; aliases cannot escape this project or fall back to the old workspace.
"""
import json
from pathlib import Path as NativePath

_ROOT = NativePath(__file__).resolve().parents[2]
_aliases = None


def resolve_path(value):
    global _aliases
    raw = str(value).replace('\\', '/')
    # The team checkout can have a different directory name from the research
    # project. Its root is already local, not a historical evidence reference.
    if raw == str(_ROOT).replace('\\', '/'):
        return _ROOT
    if _aliases is None:
        manifest = _ROOT/'data/reference/path_aliases.json'
        _aliases = json.loads(manifest.read_text(encoding='utf-8-sig'))['aliases'] if manifest.exists() else {}
    prefix = str(_ROOT).replace('\\', '/')+'/'
    logical = raw
    if raw.startswith(prefix):
        logical = 'Medication-Safety-Assistant/'+raw[len(prefix):]
    elif '/api_quicktests/' in raw:
        logical = raw.split('/api_quicktests/', 1)[1]
    if logical == 'Medication-Safety-Assistant':
        return _ROOT
    if logical.startswith('Medication-Safety-Assistant/data/'):
        return _ROOT/logical[len('Medication-Safety-Assistant/'):]
    for old in sorted(_aliases, key=len, reverse=True):
        if logical == old or logical.startswith(old+'/'):
            result = (_ROOT/_aliases[old]/logical[len(old):].lstrip('/')).resolve()
            if not result.is_relative_to(_ROOT):
                raise ValueError('Evidence alias escapes project')
            return result
    if logical != raw and not raw.startswith(prefix):
        raise FileNotFoundError('Historical evidence has no project-local alias: '+logical)
    if raw.startswith('data/'):
        return _ROOT/raw
    return NativePath(value)


class ProjectPath(type(NativePath())):
    """Path whose constructor resolves registered historical locations."""
    def __new__(cls, *parts):
        return super().__new__(cls, resolve_path(NativePath(*parts)))

    def __init__(self, *parts):
        super().__init__(resolve_path(NativePath(*parts)))


PROJECT_ROOT = ProjectPath(_ROOT)
