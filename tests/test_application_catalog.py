from pathlib import Path
from zipfile import ZipFile
import pytest
from Server.models.application_catalog import load, Application
from Server.models.deployment_media import DeploymentMedia, REQUIRED


def prepare(root,folder,app):
    for name in app.required_files:
        path=root/folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
    if app.key_file:
        key=root/app.key_file;key.parent.mkdir(parents=True,exist_ok=True);key.write_bytes(b'fixture-key')


def test_reference_layout_is_resolved_and_archive_remains_portable(tmp_path):
    apps=load()
    for app in apps:prepare(tmp_path,'Tools/'+app.media_folder,app)
    media=DeploymentMedia(tmp_path)
    assert media.manifest()['ready']
    assert all(app.resolve(tmp_path)==tmp_path/'Tools'/app.media_folder for app in apps)
    archive=media.build()
    try:
        with ZipFile(archive) as z:
            assert set(REQUIRED)<=set(z.namelist())
            assert not any(name.startswith('Tools/') for name in z.namelist())
    finally:archive.unlink()


def test_complete_candidate_wins_over_partial_directory(tmp_path):
    app=load()[0]
    partial=tmp_path/'Office';partial.mkdir();(partial/'README.md').write_text('guide')
    prepare(tmp_path,'Tools/Office',app)
    assert app.resolve(tmp_path)==tmp_path/'Tools/Office'


def test_another_application_does_not_require_office_hancom_branches(tmp_path):
    extra=Application('sample','Sample app','Sample',('sources/Sample',),('setup.exe',),None,('Modules/07_Sample.ps1',))
    prepare(tmp_path,'sources/Sample',extra)
    media=DeploymentMedia(tmp_path,applications=[extra])
    assert media.manifest()['ready']
    archive=media.build()
    try:
        with ZipFile(archive) as z:assert z.namelist()==['Sample/setup.exe']
    finally:archive.unlink()


def test_invalid_catalogue_path_rejected(tmp_path):
    import json
    data={'applications':[{'id':'bad','name':'Bad','media_folder':'Bad','source_candidates':['../private'],'required_files':['setup.exe'],'modules':[]}]}
    path=tmp_path/'catalog.json';path.write_text(json.dumps(data))
    with pytest.raises(ValueError):load(path)

def test_agent_package_includes_registered_extra_module_only(tmp_path):
    import json
    from io import BytesIO
    from Server.models.agent_package import FILES, build
    repo=Path(__file__).resolve().parents[1]
    for name in FILES:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((repo/name).read_bytes())
    descriptor=tmp_path/'Config/Applications.json'
    data=json.loads(descriptor.read_text())
    data['applications'].append({'id':'sample','name':'Sample','media_folder':'Sample','source_candidates':['Sample'],'required_files':['setup.exe'],'key_file':None,'modules':['Modules/07_Sample.ps1']})
    descriptor.write_text(json.dumps(data))
    (tmp_path/'Modules/07_Sample.ps1').write_text('# reviewed module fixture')
    (tmp_path/'Config/OfficeKey.txt').write_text('private-fixture')
    with ZipFile(BytesIO(build(tmp_path,'https://server.example'))) as z:
        assert 'duct-tape-agent/Modules/07_Sample.ps1' in z.namelist()
        assert 'duct-tape-agent/Config/OfficeKey.txt' not in z.namelist()
