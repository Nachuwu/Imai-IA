# Registra una Tarea Programada de Windows que inicia Imai al iniciar sesión
# y la reinicia automáticamente si el proceso termina con error (crash).
#
# Uso: ejecutar este script una vez (no requiere privilegios de administrador).
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_tarea.ps1

$raiz    = (Resolve-Path "$PSScriptRoot\..").Path
$pythonw = Join-Path $raiz "venv\Scripts\pythonw.exe"
$appPy   = Join-Path $raiz "app.py"

$accion     = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$appPy`"" -WorkingDirectory $raiz
$disparador = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$principal  = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

$config = New-ScheduledTaskSettingsSet `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask -TaskName "Imai" `
    -Action $accion -Trigger $disparador -Principal $principal -Settings $config `
    -Force | Out-Null

Write-Host "Tarea 'Imai' registrada: se iniciará al iniciar sesión y se reiniciará si falla (hasta 999 veces, cada 1 min)."
