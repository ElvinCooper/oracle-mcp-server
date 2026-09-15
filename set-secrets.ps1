#Requires -Version 5.1
<#
.SYNOPSIS
  Fija o elimina las credenciales (USER/PASSWORD) de una conexion Oracle
  como variables de entorno de usuario (scope "User"), evitando guardarlas
  en texto plano en el .env.

.DESCRIPTION
  Define las variables ORACLE_CONN_<NOMBRE>_USER y ORACLE_CONN_<NOMBRE>_PASSWORD
  a nivel de usuario de Windows. Estas variables tienen prioridad sobre las
  del .env (python-dotenv no sobrescribe variables ya definidas).

.PARAMETER Name
  Nombre de la conexion tal como aparece en ORACLE_CONNECTIONS (ej. facturacion).

.PARAMETER User
  Usuario de Oracle. Si se omite, se solicita de forma interactiva.

.PARAMETER Password
  Password de Oracle. Si se omite, se solicita de forma interactiva (enmascarado).

.PARAMETER Unset
  Elimina las variables de la conexion en lugar de crearlas.

.EXAMPLE
  .\set-secrets.ps1 -Name facturacion

.EXAMPLE
  .\set-secrets.ps1 -Name facturacion -User your_user

.EXAMPLE
  .\set-secrets.ps1 -Name facturacion -Unset
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Name,

    [string]$User,

    [string]$Password,

    [switch]$Unset
)

$ErrorActionPreference = "Stop"

$connVar = "ORACLE_CONN_" + $Name.ToUpper()
$userVar = "${connVar}_USER"
$passVar = "${connVar}_PASSWORD"

if ($Unset) {
    [Environment]::SetEnvironmentVariable($userVar, $null, "User")
    [Environment]::SetEnvironmentVariable($passVar, $null, "User")
    Write-Host "[OK] Credenciales de '$Name' eliminadas (scope User)." -ForegroundColor Green
    exit 0
}

if (-not $User) {
    $User = Read-Host "Usuario para '$Name'"
}

if (-not $Password) {
    $secure = Read-Host "Password para '$Name'" -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringUni($bstr)
    }
    finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if (-not $User -or -not $Password) {
    Write-Host "Error: usuario y password son obligatorios." -ForegroundColor Red
    exit 1
}

[Environment]::SetEnvironmentVariable($userVar, $User, "User")
[Environment]::SetEnvironmentVariable($passVar, $Password, "User")

Write-Host "[OK] Credenciales de '$Name' guardadas como variables de usuario:" -ForegroundColor Green
Write-Host "  $userVar = $User"
Write-Host "  $passVar = (oculta)"
Write-Host ""
Write-Host "Reinicia la terminal y el cliente MCP para que el servidor las herede." -ForegroundColor Yellow
