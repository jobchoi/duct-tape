"""Build a small public agent archive from a fixed, secret-free allowlist."""
from io import BytesIO
import hashlib
from datetime import datetime, timezone, timedelta
from zipfile import ZipFile, ZIP_DEFLATED
from Server.models.application_catalog import module_paths

FILES = (
    'CollectDiagnostics.bat', 'Scripts/diagnostics/Collect-ClientDiagnostics.ps1',
    'Scripts/RunApplicationJob.ps1', 'Scripts/ManagedApplications.ps1',
    'InstallAgent.bat', 'Scripts/RunSetup.bat', 'Config/Applications.json', 'Scripts/ApplicationMedia.ps1', 'Scripts/InvokeApplications.ps1',
    'Scripts/Agent.ps1', 'Scripts/JobProgress.ps1', 'Scripts/ProgressDelivery.ps1', 'Scripts/AgentRegistration.ps1', 'Scripts/AgentActions.ps1', 'Scripts/ClientSetup.ps1',
    'Scripts/LicenseKeys.ps1', 'Scripts/Common.ps1', 'Scripts/OfficeConfiguration.ps1', 'Scripts/InstallAgent.ps1', 'Scripts/ReportStatus.ps1',
    'Scripts/RunAgentJob.ps1', 'Scripts/PrepareAgentMedia.ps1', 'Scripts/Test-DeploymentPrerequisites.ps1',
    'Modules/01_GetInfo.ps1', 'Modules/02_CheckOffice.ps1', 'Modules/03_RemoveOffice.ps1',
    'Modules/04_InstallOffice.ps1', 'Modules/05_CheckHancom.ps1', 'Modules/06_InstallHancom.ps1',
)


def package_version(root):
    files = tuple(dict.fromkeys((*FILES, *module_paths(root / "Config/Applications.json"))))
    digest = hashlib.sha256()
    for name in files:
        data = (root / name).read_bytes()
        digest.update(name.encode() + b"\0" + len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()

def build(root, origin):
    stream = BytesIO()
    with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        files = tuple(dict.fromkeys((*FILES, *module_paths(root/'Config/Applications.json'))))
        for name in files:
            archive.writestr('duct-tape-agent/'+name, (root/name).read_bytes())
        archive.writestr('duct-tape-agent/Config/ServerUrl.txt', origin)
        version = package_version(root)
        archive.writestr('duct-tape-agent/Config/PackageVersion.txt', version)
        archive.writestr('duct-tape-agent/시작 안내.txt', f'패키지 버전: {version[:12]}\n전체 버전: Config/PackageVersion.txt 참조\n생성일: {datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")}\n이전에 받은 ZIP은 폐기하세요.\nInstallAgent.bat을 실행하세요. 설치 후 바탕화면 바로가기가 생성됩니다.\nOffice/한컴 설치 매체와 제품 키는 서버에서 준비하고 관리합니다. 에이전트가 셋업 시 동기화합니다.\n설치 없이 점검하려면 CollectDiagnostics.bat을 관리자 권한으로 실행하세요.\n')
    return stream.getvalue()
