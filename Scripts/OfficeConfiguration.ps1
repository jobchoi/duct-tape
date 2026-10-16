function Get-OfficeProductKey {
    param([string]$KeyPath)
    if (-not (Test-Path -LiteralPath $KeyPath -PathType Leaf)) { throw 'OFFICE_KEY_MISSING' }
    try { $key = (Get-Content -LiteralPath $KeyPath -Raw -Encoding UTF8).Trim().ToUpperInvariant() }
    catch { throw 'OFFICE_KEY_UNREADABLE' }
    if ($key -notmatch '^[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4}$' -or $key -eq 'XXXXX-XXXXX-XXXXX-XXXXX-XXXXX') { throw 'OFFICE_KEY_INVALID' }
    return $key
}

function Invoke-WithOfficeConfiguration {
    param([string]$TemplatePath, [string]$KeyPath, [scriptblock]$Install)
    $key = Get-OfficeProductKey -KeyPath $KeyPath
    $settings = New-Object System.Xml.XmlReaderSettings
    $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
    $settings.XmlResolver = $null
    $reader = $null
    try {
        $reader = [Xml.XmlReader]::Create($TemplatePath, $settings)
        $xml = New-Object System.Xml.XmlDocument
        $xml.PreserveWhitespace = $true
        $xml.XmlResolver = $null
        $xml.Load($reader)
        $products = @($xml.SelectNodes('/Configuration/Add/Product'))
        if ($products.Count -ne 1 -or $products[0].GetAttribute('ID') -ne 'ProPlus2024Volume') { throw 'invalid' }
        $products[0].SetAttribute('PIDKEY', $key)
    } catch { throw 'OFFICE_CONFIG_INVALID' }
    finally { if ($null -ne $reader) { $reader.Dispose() } }
    $temporary = Join-Path ([IO.Path]::GetTempPath()) ('duct-office-'+[guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory $temporary | Out-Null
        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            $acl = New-Object Security.AccessControl.DirectorySecurity
            $acl.SetAccessRuleProtection($true, $false)
            $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
            foreach ($identity in @($sid, (New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
                $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
                $acl.AddAccessRule($rule)
            }
            Set-Acl -LiteralPath $temporary -AclObject $acl
        } else {
            [IO.File]::SetUnixFileMode($temporary, [IO.UnixFileMode]'UserRead,UserWrite,UserExecute')
        }
        $path = Join-Path $temporary 'install.xml'
        $xml.Save($path)
        & $Install $path
    } finally {
        $key = $null
        $xml = $null
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    }
}
