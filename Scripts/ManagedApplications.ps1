# V2 fixed MSI adapter. Never evaluates uploaded commands or enrollment credentials.
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
function Test-ManagedAppInstalled {
    param($App)
    foreach($base in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
                       'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')) {
        $item=Get-ItemProperty -LiteralPath (Join-Path $base $App.product_code) -ErrorAction SilentlyContinue
        $version=$null
        if($item -and [version]::TryParse([string]$item.DisplayVersion,[ref]$version) -and $version -ge [version]$App.version){return $true}
    }
    return $false
}
function Assert-ManagedAppDefinition {
    param($App)
    if($App.adapter -ne 'msi-v1' -or $App.schema_version -ne 2 -or
       $App.id -notmatch '^[a-z][a-z0-9-]{0,47}$' -or
       $App.version -notmatch '^\d{1,5}\.\d{1,5}\.\d{1,5}(\.\d{1,5})?$' -or
       $App.sha256 -notmatch '^[a-f0-9]{64}$' -or
       $App.product_code -notmatch '^\{[A-Fa-f0-9-]{36}\}$' -or
       $App.installer -notmatch '\.msi$' -or
       $App.installer -match '(^/|\\|:|(^|/)\.\.?(/|$)|//)' -or
       $App.enrollment -isnot [bool]){throw 'PACKAGE_INVALID'}
    $null=[guid]$App.product_code
}
function Assert-ManagedMsiIdentity {
    param([string]$Path,$App)
    $installer=$null;$database=$null;$view=$null
    try {
        $installer=New-Object -ComObject WindowsInstaller.Installer
        $database=$installer.OpenDatabase($Path,0)
        $view=$database.OpenView('SELECT `Property`, `Value` FROM `Property`');$view.Execute()
        $code='';$version=''
        while($record=$view.Fetch()){
            if($record.StringData(1) -eq 'ProductCode'){$code=$record.StringData(2)}
            if($record.StringData(1) -eq 'ProductVersion'){$version=$record.StringData(2)}
        }
        if($code -ne $App.product_code -or [version]$version -ne [version]$App.version){throw 'PACKAGE_INVALID'}
    } finally {
        foreach($object in @($view,$database,$installer)){
            if($null -ne $object){[Runtime.InteropServices.Marshal]::FinalReleaseComObject($object)|Out-Null}
        }
    }
}
function Expand-ManagedAppPackage {
    param([string]$Zip,[string]$Destination)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive=[IO.Compression.ZipFile]::OpenRead($Zip)
    try {
        $seen=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        $size=[long]0
        if($archive.Entries.Count -eq 0 -or $archive.Entries.Count -gt 10000){throw 'PACKAGE_INVALID'}
        foreach($entry in $archive.Entries){
            $name=$entry.FullName.TrimEnd('/')
            $size+=$entry.Length
            if(-not $name -or $name -match '(^/|\\|:|(^|/)\.\.?(/|$)|//)' -or
               -not $seen.Add($name) -or $size -gt 2147483648 -or
               (($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960){throw 'PACKAGE_INVALID'}
            if(-not $entry.FullName.EndsWith('/') -and [IO.Path]::GetExtension($name) -notin @('.msi','.exe','.cab','.dll')){throw 'PACKAGE_INVALID'}
        }
        foreach($entry in $archive.Entries){
            $path=Join-Path $Destination $entry.FullName
            if($entry.FullName.EndsWith('/')){New-Item -ItemType Directory $path -Force|Out-Null}
            else{
                New-Item -ItemType Directory (Split-Path $path -Parent) -Force|Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$path,$true)
            }
        }
    } finally {$archive.Dispose()}
}
function Invoke-ManagedMsi {
    param([string]$Path)
    $process=Start-Process msiexec.exe -ArgumentList ('/i "'+$Path+'" /qn /norestart') -PassThru -WindowStyle Hidden
    $null=$process.Handle
    $process.WaitForExit();$process.Refresh()
    if($null -eq $process.ExitCode){throw 'INSTALL_FAILED'}
    return [int]$process.ExitCode
}
function Invoke-ManagedApp {
    param([string]$Root,[guid]$JobId,$App,[string]$ServerUrl,$Headers)
    Assert-ManagedAppDefinition $App
    $result=@{status='failed';exit_code=1;verified=$false;reboot_required=$false;
              enrollment=$(if($App.enrollment){'required'}else{'not_required'});error_code=''}
    $work=Join-Path $Root ('app-stage-'+[guid]::NewGuid().ToString('N'))
    try {
        Write-JobProgress -Phase application -Status started -ApplicationId $App.id
        if(Test-ManagedAppInstalled $App){$result.status='already_installed';$result.exit_code=0;$result.verified=$true;return $result}
        $cache=Join-Path $Root 'packages'
        New-Item -ItemType Directory $cache -Force|Out-Null
        $zip=Join-Path $cache ($App.sha256+'.zip')
        if((Test-Path $zip) -and (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $App.sha256){Remove-Item $zip -Force}
        if(-not(Test-Path $zip)){
            $partial=$zip+'.partial'
            try{
                Receive-AgentMedia -Uri ($ServerUrl+'/api/agent/jobs/'+$JobId+'/applications/'+$App.id+'/package') -Headers $Headers -OutFile $partial
                if((Get-FileHash $partial -Algorithm SHA256).Hash.ToLowerInvariant() -ne $App.sha256){throw 'PACKAGE_INVALID'}
                Move-Item $partial $zip -Force
            } finally {if(Test-Path $partial){Remove-Item $partial -Force}}
        }
        New-Item -ItemType Directory $work -Force|Out-Null
        Write-JobProgress -Phase extract -Status started
        Expand-ManagedAppPackage -Zip $zip -Destination $work
        Write-JobProgress -Phase extract -Status completed
        $msi=Join-Path $work $App.installer
        Assert-ManagedMsiIdentity -Path $msi -App $App
        $code=Invoke-ManagedMsi $msi
        Write-Host ('APP_INSTALL_EXIT: '+$App.id+' '+$code)
        $result.exit_code=if($code -lt 0){1}else{$code}
        if($code -notin @(0,3010)){throw 'INSTALL_FAILED'}
        $result.reboot_required=$code -eq 3010
        if(-not(Test-ManagedAppInstalled $App)){throw 'VERIFY_FAILED'}
        $result.status='installed';$result.verified=$true
    } catch {
        $known=@('INSTALL_FAILED','VERIFY_FAILED','PACKAGE_INVALID')
        $result.error_code=if($_.Exception.Message -in $known){$_.Exception.Message}else{'APP_OPERATION_FAILED'}
        Write-Host ('APP_ERROR: '+$App.id+' '+$result.error_code)
    } finally {
        Write-JobProgress -Phase application -Status $(if($result.verified){'completed'}else{'failed'}) -ApplicationId $App.id
        if(Test-Path $work){Remove-Item $work -Recurse -Force}
    }
    return $result
}
