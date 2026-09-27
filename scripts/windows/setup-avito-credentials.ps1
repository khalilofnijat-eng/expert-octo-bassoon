#Requires -Version 5.1
<#
.SYNOPSIS
    Avito API kimlik bilgilerini (client_id, client_secret, isteğe bağlı hesap kimliği)
    yalnızca sizin okuyabileceğiniz bir dosyaya yazar.

.DESCRIPTION
    Dosya: %LOCALAPPDATA%\AvitoAssistant\secrets.env
    (Git deposunun ve Obsidian kasasının dışında.)

    - client_id ve client_secret gizli olarak sorulur (Read-Host -AsSecureString):
      yazarken ekranda görünmez, hiçbir yere yazdırılmaz.
    - Hesap kimliği (Avito user_id) isteğe bağlıdır; boş bırakılırsa uygulama onu
      GET /core/v1/accounts/self ile kendisi bulur.
    - Klasörün ve dosyanın izinleri yalnızca Windows'a giriş yapmış olan kullanıcıya verilir
      (devralma kapatılır, başka kimseye izin kalmaz).
    - Yeniden çalıştırılabilir: boş bırakılan değer korunur, yazılan değer güncellenir.
    - -Remove ile dosya silinir.

    Bu betik Avito'ya bağlanmaz. Kurulumdan sonra erişimi denemek için:
        uv run python scripts/avito_access_check.py

.PARAMETER Remove
    Gizli dosyayı siler (onay ister).

.EXAMPLE
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\windows\setup-avito-credentials.ps1

.EXAMPLE
    .\scripts\windows\setup-avito-credentials.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# Dosyaya yazılan anahtar adları (app/config.py bunları okur).
$KeyClientId = 'AVITO_CLIENT_ID'
$KeyClientSecret = 'AVITO_CLIENT_SECRET'
$KeyUserId = 'AVITO_USER_ID'
$OurKeys = @($KeyClientId, $KeyClientSecret, $KeyUserId)
$HeaderLines = @(
    '# Avito Müşteri Asistanı — gizli ayarlar. Git''e eklemeyin, kimseyle paylaşmayın.',
    '# Oluşturan: scripts/windows/setup-avito-credentials.ps1 (yeniden çalıştırarak güncelleyin).'
)

function Get-SecretsLocation {
    # Varsayılan konum: %LOCALAPPDATA%\AvitoAssistant\secrets.env
    if ($env:OS -ne 'Windows_NT') {
        throw 'Bu betik yalnızca Windows içindir.'
    }
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw 'LOCALAPPDATA ortam değişkeni bulunamadı; gizli dosyanın yeri belirlenemedi.'
    }
    $dir = Join-Path $env:LOCALAPPDATA 'AvitoAssistant'
    return New-Object PSObject -Property @{
        Dir  = $dir
        File = (Join-Path $dir 'secrets.env')
    }
}

function Get-CurrentUserSid {
    return [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
}

function Invoke-Icacls {
    # icacls çıktısı gösterilmez (yalnızca izin satırları içerir); hata kodu kontrol edilir.
    param([string[]]$Arguments)
    & icacls.exe @Arguments | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "icacls başarısız oldu (çıkış kodu $LASTEXITCODE)."
    }
}

function Get-RuleSid {
    param($Rule)
    try {
        return $Rule.IdentityReference.Translate(
            [System.Security.Principal.SecurityIdentifier]).Value
    } catch {
        return $null
    }
}

function Set-OwnerOnlyAcl {
    # Devralmayı kapatır ve yalnızca geçerli kullanıcıya tam denetim verir.
    param(
        [string]$Path,
        [switch]$Directory
    )
    $sid = Get-CurrentUserSid
    $grant = if ($Directory) { "*${sid}:(OI)(CI)F" } else { "*${sid}:F" }
    # Önce kendimize açık izin (kendimizi dışarıda bırakmamak için), sonra devralmayı kaldır.
    Invoke-Icacls @($Path, '/grant:r', $grant)
    Invoke-Icacls @($Path, '/inheritance:r')
    # Başka hesaplara ait açık izin kaldıysa onları da kaldır.
    foreach ($rule in (Get-Acl -LiteralPath $Path).Access) {
        $ruleSid = Get-RuleSid $rule
        if ($ruleSid -ne $sid) {
            $target = if ($ruleSid) { "*$ruleSid" } else { $rule.IdentityReference.Value }
            Invoke-Icacls @($Path, '/remove', $target)
        }
    }
    # Doğrula: devralma kapalı ve tek sahip biz.
    $acl = Get-Acl -LiteralPath $Path
    if (-not $acl.AreAccessRulesProtected) {
        throw "İzinler kısıtlanamadı (devralma hâlâ açık): $Path"
    }
    foreach ($rule in $acl.Access) {
        if ((Get-RuleSid $rule) -ne $sid) {
            throw "İzinler kısıtlanamadı (başka bir hesabın izni var): $Path"
        }
    }
}

function ConvertFrom-SecureStringToPlain {
    param([System.Security.SecureString]$Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Test-SafeValue {
    # Yalnızca görünür ASCII karakterler; boşluk, tırnak ve ters eğik çizgi yok.
    # (Dosya biçimi: ANAHTAR='değer'. Bu karakterler değeri bozabilirdi.)
    param([string]$Value)
    return ($Value -cmatch '^[\x21-\x7E]+$') -and ($Value -cnotmatch "['""\\]")
}

function Read-SecretValue {
    # Değeri gizli okur. Boş bırakılırsa: mevcut değer varsa $null (korunur), yoksa tekrar sorar.
    param(
        [string]$Label,
        [bool]$HasExisting
    )
    for ($try = 1; $try -le 3; $try++) {
        $hint = if ($HasExisting) { ' (boş bırakırsanız mevcut değer korunur)' } else { '' }
        $secure = Read-Host -Prompt "$Label$hint" -AsSecureString
        $plain = ConvertFrom-SecureStringToPlain $secure
        $secure.Dispose()
        $plain = $plain.Trim()
        if ($plain.Length -eq 0) {
            if ($HasExisting) { return $null }
            Write-Host "  $Label boş olamaz." -ForegroundColor Yellow
            continue
        }
        if (-not (Test-SafeValue $plain)) {
            $plain = $null
            Write-Host "  Geçersiz karakter var (boşluk, tırnak veya ters eğik çizgi). Tekrar deneyin." `
                -ForegroundColor Yellow
            continue
        }
        return $plain
    }
    throw "$Label alınamadı; betik durduruldu. Hiçbir şey değiştirilmedi."
}

function Read-UserId {
    # Hesap kimliği gizli değildir; normal okunur. '' = değiştirme, '-' = sil.
    param([bool]$HasExisting)
    for ($try = 1; $try -le 3; $try++) {
        if ($HasExisting) {
            $prompt = 'Avito hesap kimliği (isteğe bağlı; boş = koru, - = sil)'
        } else {
            $prompt = 'Avito hesap kimliği (isteğe bağlı; bilmiyorsanız boş bırakın)'
        }
        $value = (Read-Host -Prompt $prompt).Trim()
        if ($value.Length -eq 0) { return $null }
        if ($value -eq '-') { return '-' }
        if ($value -cmatch '^[0-9]{1,19}$' -and $value -cnotmatch '^0+$') { return $value }
        Write-Host '  Hesap kimliği yalnızca rakamlardan oluşmalı.' -ForegroundColor Yellow
    }
    throw 'Hesap kimliği alınamadı; betik durduruldu. Hiçbir şey değiştirilmedi.'
}

function Read-ExistingFile {
    # Mevcut dosyadaki bizim anahtarlarımızı ve diğer satırları ayırır (değerler gösterilmez).
    param([string]$File)
    $values = @{}
    $others = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) {
        return New-Object PSObject -Property @{ Values = $values; Others = $others }
    }
    foreach ($line in (Get-Content -LiteralPath $File -Encoding UTF8)) {
        if ($line -cmatch '^\s*(AVITO_CLIENT_ID|AVITO_CLIENT_SECRET|AVITO_USER_ID)\s*=(.*)$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and $value.StartsWith("'") -and $value.EndsWith("'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            if ($value.Length -gt 0) { $values[$key] = $value }
        } elseif ($HeaderLines -contains $line) {
            continue
        } elseif ($line.Trim().Length -gt 0) {
            # Elle eklenmiş başka ayarlar korunur.
            $others.Add($line)
        }
    }
    return New-Object PSObject -Property @{ Values = $values; Others = $others }
}

function Write-SecretsFile {
    param(
        [string]$File,
        [hashtable]$Values,
        [System.Collections.Generic.List[string]]$Others
    )
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($h in $HeaderLines) { $lines.Add($h) }
    foreach ($key in $OurKeys) {
        if ($Values.ContainsKey($key)) { $lines.Add("$key='" + $Values[$key] + "'") }
    }
    foreach ($o in $Others) { $lines.Add($o) }
    $content = ($lines -join "`r`n") + "`r`n"
    # UTF-8, BOM olmadan (Python tarafı BOM'u da tolere eder).
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($File, $content, $encoding)
    $content = $null
}

# --- Ana akış -----------------------------------------------------------------------------

$location = Get-SecretsLocation

if (-not [string]::IsNullOrWhiteSpace($env:ASSISTANT_SECRETS_FILE)) {
    Write-Host ('Uyarı: ASSISTANT_SECRETS_FILE ortam değişkeni ayarlı. Uygulama o dosyayı ' +
        'kullanır; bu betiğin yazdığı dosyayı değil.') -ForegroundColor Yellow
}

if ($Remove) {
    if (-not (Test-Path -LiteralPath $location.File -PathType Leaf)) {
        Write-Host "Silinecek dosya yok: $($location.File)"
        return
    }
    $answer = Read-Host -Prompt "Gizli dosya silinsin mi? Onaylamak için EVET yazın"
    if ($answer -cne 'EVET') {
        Write-Host 'İptal edildi; hiçbir şey silinmedi.'
        return
    }
    Remove-Item -LiteralPath $location.File -Force
    if (-not (Get-ChildItem -LiteralPath $location.Dir -Force)) {
        Remove-Item -LiteralPath $location.Dir -Force
    }
    Write-Host 'Gizli dosya silindi.' -ForegroundColor Green
    Write-Host ('Anahtarın sızdığından şüpheleniyorsanız Avito kişisel kabinetinde (API ' +
        'ayarları) anahtarı iptal edip yenisini oluşturun.')
    return
}

Write-Host 'Avito API kimlik bilgileri kurulumu'
Write-Host "Dosya: $($location.File)"
Write-Host ('client_id ve client_secret yazarken ekranda görünmez. Yapıştırmak için ' +
    'Ctrl+V veya farenin sağ tuşunu kullanabilirsiniz; ardından Enter.')
Write-Host 'Bu değerleri sohbete, e-postaya veya başka bir dosyaya asla yapıştırmayın.'
Write-Host ''

# Klasörü oluştur ve dosya yazılmadan ÖNCE izinlerini kısıtla.
if (-not (Test-Path -LiteralPath $location.Dir -PathType Container)) {
    New-Item -ItemType Directory -Path $location.Dir | Out-Null
}
Set-OwnerOnlyAcl -Path $location.Dir -Directory
if (Test-Path -LiteralPath $location.File -PathType Leaf) {
    Set-OwnerOnlyAcl -Path $location.File
}

$existing = Read-ExistingFile $location.File
$values = $existing.Values
if ($values.Count -gt 0) {
    Write-Host ('Mevcut dosyada ayarlı olanlar: ' + (($OurKeys | Where-Object {
        $values.ContainsKey($_) }) -join ', ') + ' (değerler gösterilmez).')
}

$clientId = Read-SecretValue -Label 'client_id' -HasExisting ($values.ContainsKey($KeyClientId))
$clientSecret = Read-SecretValue -Label 'client_secret' `
    -HasExisting ($values.ContainsKey($KeyClientSecret))
$userId = Read-UserId -HasExisting ($values.ContainsKey($KeyUserId))

if ($null -ne $clientId) { $values[$KeyClientId] = $clientId }
if ($null -ne $clientSecret) { $values[$KeyClientSecret] = $clientSecret }
if ($userId -eq '-') {
    $values.Remove($KeyUserId)
} elseif ($null -ne $userId) {
    $values[$KeyUserId] = $userId
}
$clientId = $null
$clientSecret = $null

try {
    Write-SecretsFile -File $location.File -Values $values -Others $existing.Others
    Set-OwnerOnlyAcl -Path $location.File
} catch {
    # İzinler kısıtlanamadıysa gizli değerler diskte bırakılmaz.
    if (Test-Path -LiteralPath $location.File -PathType Leaf) {
        Remove-Item -LiteralPath $location.File -Force
    }
    throw
} finally {
    $values = $null
    $existing = $null
}

Write-Host ''
Write-Host "Kaydedildi: $($location.File)" -ForegroundColor Green
Write-Host "Erişim izni yalnızca bu Windows kullanıcısında: $env:USERNAME"
Write-Host 'Sonraki adım (proje klasöründe): uv run python scripts/avito_access_check.py'
