"""Application source adapters; archive layout is independent of source location."""
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, ZIP_STORED
from Server.models.application_catalog import load

REQUIRED = tuple(name for app in load() for name in (
    *(app.media_folder+'/'+name for name in app.required_files), *((app.key_file,) if app.key_file else ())))


class DeploymentMedia:
    def __init__(self, root, applications=None):
        self.licenses = None
        self.root = Path(root).resolve()
        self.applications = tuple(applications) if applications is not None else load()

    def manifest(self):
        missing=[]
        managed = self.licenses.snapshot() if self.licenses else {}
        for app in self.applications:
            source=app.resolve(self.root)
            if app.key_file and app.id in managed and managed[app.id] is None:
                missing.append(app.key_file)
            for path in [*(source/name for name in app.required_files), *((self.root/app.key_file,) if app.key_file and app.id not in managed else ())]:
                if not path.is_file() or not os.access(path, os.R_OK):
                    missing.append(path.relative_to(self.root).as_posix())
        return {'ready':not missing, 'missing':missing}

    def build(self):
        if not self.manifest()['ready']:
            raise FileNotFoundError('Deployment media is incomplete')
        entries=[]
        managed = self.licenses.snapshot() if self.licenses else {}
        if any(value is None for value in managed.values()):
            raise FileNotFoundError("Managed product key unavailable")
        managed_entries=[]
        for app in self.applications:
            source=app.resolve(self.root)
            for path in source.rglob('*'):
                if path.is_file():
                    if not path.resolve().is_relative_to(self.root):
                        raise ValueError('Media links must remain inside the configured root')
                    entries.append((path, app.media_folder+'/'+path.relative_to(source).as_posix()))
            if app.key_file and app.id in managed:
                managed_entries.append((app.key_file, managed[app.id]))
            elif app.key_file:
                key=self.root/app.key_file
                if not key.resolve().is_relative_to(self.root):
                    raise ValueError('Key must remain inside the configured root')
                entries.append((key, app.key_file))
        with NamedTemporaryFile(prefix='duct-media-',suffix='.zip',delete=False) as temp:
            target=Path(temp.name)
        try:
            with ZipFile(target,'w',ZIP_STORED,allowZip64=True) as archive:
                for path,name in entries:archive.write(path,name)
                for name,value in managed_entries:archive.writestr(name,value)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return target
