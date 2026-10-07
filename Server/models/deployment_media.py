"""Configured installation source; private media is never in the public agent ZIP."""
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, ZIP_STORED

REQUIRED = ('Office/setup.exe', 'Office/install.xml', 'Office/remove.xml',
            'Hancom/Install/Hwp130.msi', 'Hancom/Install/VC_redist.x86.exe', 'Config/HancomKey.txt')


class DeploymentMedia:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def manifest(self):
        missing = [name for name in REQUIRED if not (self.root/name).is_file() or not os.access(self.root/name, os.R_OK)]
        return {'ready': not missing, 'missing': missing}

    def build(self):
        if not self.manifest()['ready']:
            raise FileNotFoundError('Deployment media is incomplete')
        entries = []
        for folder in ('Office', 'Hancom'):
            for path in (self.root/folder).rglob('*'):
                if path.is_file():
                    if not path.resolve().is_relative_to(self.root):
                        raise ValueError('Media links must remain inside the configured root')
                    entries.append(path)
        key = self.root/'Config/HancomKey.txt'
        if not key.resolve().is_relative_to(self.root):
            raise ValueError('Key must remain inside the configured root')
        entries.append(key)
        with NamedTemporaryFile(prefix='duct-media-', suffix='.zip', delete=False) as temp:
            target = Path(temp.name)
        try:
            with ZipFile(target, 'w', ZIP_STORED, allowZip64=True) as archive:
                for path in entries:
                    archive.write(path, path.relative_to(self.root).as_posix())
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return target
