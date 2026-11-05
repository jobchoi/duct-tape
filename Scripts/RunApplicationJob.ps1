param([guid]$JobId)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$root=Split-Path $PSScriptRoot -Parent
$env:DUCT_JOB_ID=$JobId.ToString()
. (Join-Path $PSScriptRoot 'JobProgress.ps1')
. (Join-Path $PSScriptRoot 'ManagedApplications.ps1')
try {
    $config=Get-Content (Join-Path $root 'Config/Agent.json') -Raw -Encoding UTF8|ConvertFrom-Json
    $headers=if($config.AuthMode -eq 'development'){@{'X-Duct-Tape-Request'='1';'X-Duct-Device-ID'=$config.DeviceId}}else{@{Authorization=('Bearer '+$config.AgentToken)}}
    $url=$config.ServerUrl.TrimEnd('/')
    $plan=Invoke-RestMethod -Uri ($url+'/api/agent/jobs/'+$JobId+'/application-plan') -Headers $headers -TimeoutSec 15 -MaximumRedirection 0
    if($plan.schema_version -ne 2 -or -not $plan.applications){throw 'PLAN_INVALID'}
    foreach($app in $plan.applications){Assert-ManagedAppDefinition $app}
    $resultDir=Join-Path $root 'application-results'
    New-Item -ItemType Directory $resultDir -Force|Out-Null
    foreach($app in $plan.applications){
        $result=Invoke-ManagedApp -Root $root -JobId $JobId -App $app -ServerUrl $url -Headers $headers
        $json=$result|ConvertTo-Json -Compress
        [IO.File]::WriteAllText((Join-Path $resultDir ($JobId.ToString()+'.'+$app.id+'.json')),$json,(New-Object Text.UTF8Encoding($false)))
        # Persist before sending. Never repeat an installer merely because reporting failed.
        $sent=$false
        for($attempt=0;$attempt -lt 3;$attempt++){
            try{
                $null=Invoke-RestMethod -Uri ($url+'/api/agent/jobs/'+$JobId+'/applications/'+$app.id+'/result') -Headers $headers -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($json)) -ContentType 'application/json' -TimeoutSec 15 -MaximumRedirection 0
                $sent=$true;break
            } catch {Start-Sleep -Seconds 2}
        }
        if(-not $sent){throw 'APP_REPORT_PENDING'}
        if(-not $result.verified){exit 1}
    }
    exit 0
} catch {
    # Fixed codes only: exception text can contain paths, credentials or vendor output.
    Write-Host 'APPLICATION_JOB_FAILED: inspect application-results and progress logs'
    Write-JobProgress -Phase error -Status failed
    exit 1
}
