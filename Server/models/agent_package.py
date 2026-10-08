"""Build a small public agent archive from a fixed, secret-free allowlist."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from Server.models.application_catalog import module_paths

FILES = (
    'InstallAgent.bat', 'Main.bat', 'Config/Applications.json', 'Scripts/ApplicationMedia.ps1', 'Scripts/InvokeApplications.ps1',
    'Scripts/Agent.ps1', 'Scripts/AgentRegistration.ps1', 'Scripts/AgentActions.ps1', 'Scripts/ClientSetup.ps1',
    'Scripts/Common.ps1', 'Scripts/OfficeConfiguration.ps1', 'Scripts/InstallAgent.ps1', 'Scripts/ReportStatus.ps1',
    'Scripts/RunAgentJob.ps1', 'Scripts/PrepareAgentMedia.ps1', 'Scripts/Test-DeploymentPrerequisites.ps1',
    'Modules/01_GetInfo.ps1', 'Modules/02_CheckOffice.ps1', 'Modules/03_RemoveOffice.ps1',
    'Modules/04_InstallOffice.ps1', 'Modules/05_CheckHancom.ps1', 'Modules/06_InstallHancom.ps1',
)


def build(root, origin):
    stream = BytesIO()
    with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        files = tuple(dict.fromkeys((*FILES, *module_paths(root/'Config/Applications.json'))))
        for name in files:
            archive.writestr('duct-tape-agent/'+name, (root/name).read_bytes())
        archive.writestr('duct-tape-agent/Config/ServerUrl.txt', origin)
        archive.writestr('duct-tape-agent/시작 안내.txt', 'InstallAgent.bat을 실행하세요. 설치 후 바탕화면 바로가기가 생성됩니다.\nOffice/한컴 매체와 라이선스는 별도로 준비하세요.\n')
    return stream.getvalue()
