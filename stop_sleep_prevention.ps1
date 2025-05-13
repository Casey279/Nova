# Stop any PowerShell processes that might be preventing sleep by sending F15 keystrokes
Write-Host "Searching for sleep prevention PowerShell processes..."

# Find and kill any PowerShell processes that contain F15 in their command line
$processes = Get-Process powershell -ErrorAction SilentlyContinue | 
    Where-Object { $_.MainWindowTitle -eq '' }

if ($processes.Count -gt 0) {
    Write-Host "Found $($processes.Count) background PowerShell processes. Stopping them..."
    $processes | ForEach-Object {
        Write-Host "  Stopping process ID $($_.Id)"
        Stop-Process -Id $_.Id -Force
    }
    Write-Host "All background PowerShell processes stopped."
} else {
    Write-Host "No background PowerShell processes found."
}

# Also, reset the system power state to allow sleep
try {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Sleep {
    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
    public static void AllowSleep() {
        // ES_CONTINUOUS only, which resets to default behavior
        SetThreadExecutionState(0x80000000);
    }
}
"@
    [Sleep]::AllowSleep()
    Write-Host "System power state reset to allow sleep."
} catch {
    Write-Host "Failed to reset system power state: $_"
}

Write-Host "Done."
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')