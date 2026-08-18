<#
driver.ps1 - launch, screenshot (safely), and stop the LayoutCorel app.

Two things this driver fixes, both found by actually running it (see
Gotchas in SKILL.md for the full story):

1. Screenshots go through PrintWindow (reads pixels straight from the
   window's own device context, by HWND) instead of CopyFromScreen
   (reads screen pixels at a rectangle of coordinates). CopyFromScreen
   is what caused three real privacy incidents in the session that
   authored this skill: an unrelated overlapping window (File
   Explorer, CorelDRAW with a real client file open) got captured
   instead of the app, because CopyFromScreen has no idea which window
   is actually there -- it just grabs whatever's on screen at that
   rect at that instant. PrintWindow can't make that mistake: it
   renders the specific HWND you pass it, regardless of what else is
   on screen.

2. The app's window is found via EnumWindows (first visible top-level
   window with a non-empty title owned by the PID we launched, OR one
   of its child PIDs), not .NET's Process.MainWindowHandle.
   MainWindowHandle is unreliable here two different ways: with
   python.exe it returns the console window's handle instead of the Qt
   window (console exists first); with pythonw.exe (no console) it can
   sit at 0 indefinitely. And on top of that, this venv's pythonw.exe
   -m re-execs into a *child* pythonw.exe process that's the one that
   actually owns the window -- the PID Start-Process hands back is a
   stub that never gets a window at all. So the search has to walk
   the process this driver started *and* its children.

Usage (from repo root, PowerShell):
    . .claude\skills\run-gerador-layout-caixas\driver.ps1
    $app = Start-LayoutCorel                      # dev mode (fast)
    Save-AppScreenshot -App $app -Path "$env:TEMP\tela.png"
    Stop-LayoutCorel -App $app

    $app = Start-LayoutCorel -Modo exe            # packaged dist\LayoutCorel.exe

$app is a small object: @{ Proc = <Process>; Hwnd = <IntPtr> }.
#>

param()

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class LayoutCorelDriver {
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }

    // First visible top-level window with a non-empty title owned by
    // this PID. Zero if none exists yet.
    public static IntPtr FindWindowForProcess(uint pid) {
        IntPtr found = IntPtr.Zero;
        EnumWindows(delegate (IntPtr hWnd, IntPtr lParam) {
            uint windowPid;
            GetWindowThreadProcessId(hWnd, out windowPid);
            if (windowPid == pid && IsWindowVisible(hWnd) && GetWindowTextLength(hWnd) > 0) {
                found = hWnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
"@ -ErrorAction SilentlyContinue

function Start-LayoutCorel {
    <#
    .SYNOPSIS
    Launches the app and returns @{ Proc = <Process>; Hwnd = <IntPtr> }
    once its window exists. Always launch through this function (not
    your own Start-Process) -- the window is located by the PID this
    function started, via EnumWindows, never by title (a title match
    can hit an unrelated already-open window) and never via
    Process.MainWindowHandle (unreliable for this app, see file header).
    #>
    param(
        [ValidateSet("dev", "exe")]
        [string]$Modo = "dev",
        [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..\..").Path
    )

    if ($Modo -eq "exe") {
        $exe = Join-Path $RepoRoot "dist\LayoutCorel.exe"
        if (-not (Test-Path $exe)) {
            throw "dist\LayoutCorel.exe nao existe. Rode primeiro: .venv\Scripts\pyinstaller.exe --noconfirm LayoutCorel.spec"
        }
        $proc = Start-Process -FilePath $exe -PassThru
    } else {
        # pythonw.exe, nao python.exe -- ver o cabecalho do arquivo:
        # python.exe traz uma janela de console que confunde a deteccao
        # de janela: nao evita o problema, so troca de forma.
        $python = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
        if (-not (Test-Path $python)) {
            throw ".venv nao existe. Rode primeiro: python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt"
        }
        $env:PYTHONPATH = Join-Path $RepoRoot "src"
        $proc = Start-Process -FilePath $python -ArgumentList "-m", "gerador_layout.main" `
            -WorkingDirectory $RepoRoot -PassThru
    }

    $launcherPid = $proc.Id
    for ($i = 0; $i -lt 75; $i++) {
        Start-Sleep -Milliseconds 200
        $proc.Refresh()
        if ($proc.HasExited -and $Modo -eq "exe") {
            throw "O processo (PID $launcherPid) encerrou antes de abrir janela."
        }

        # -Modo dev: pythonw.exe -m re-execa num processo FILHO nesta venv
        # -- o filho e' quem acaba com a janela, o PID original vira um
        # stub que nunca abre nada (ver cabecalho do arquivo). Procura no
        # PID original e em todo filho direto dele.
        $candidatos = @($launcherPid)
        $filhos = Get-CimInstance Win32_Process -Filter "ParentProcessId=$launcherPid" -ErrorAction SilentlyContinue
        foreach ($f in $filhos) { $candidatos += $f.ProcessId }

        foreach ($pidCandidato in $candidatos) {
            $hwnd = [LayoutCorelDriver]::FindWindowForProcess([uint32]$pidCandidato)
            if ($hwnd -ne [IntPtr]::Zero) {
                $procJanela = Get-Process -Id $pidCandidato
                return @{ Proc = $procJanela; Hwnd = $hwnd; LauncherPid = $launcherPid }
            }
        }
    }
    throw "Janela principal nao apareceu em 15s (PID $launcherPid nem filhos)."
}

function Save-AppScreenshot {
    <#
    .SYNOPSIS
    Screenshots exactly the window in $App.Hwnd -- never the screen --
    via PrintWindow. Safe to call even if another window is on top of
    it, or it's on a monitor that isn't currently displayed.
    #>
    param(
        [Parameter(Mandatory)]
        [hashtable]$App,
        [Parameter(Mandatory)]
        [string]$Path
    )
    $App.Proc.Refresh()
    if ($App.Proc.HasExited) { throw "Processo (PID $($App.Proc.Id)) ja encerrou." }
    $hwnd = $App.Hwnd

    [LayoutCorelDriver]::ShowWindow($hwnd, 9) | Out-Null  # SW_RESTORE, caso esteja minimizada
    Start-Sleep -Milliseconds 200

    $rect = New-Object LayoutCorelDriver+RECT
    [LayoutCorelDriver]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
    $largura = $rect.Right - $rect.Left
    $altura = $rect.Bottom - $rect.Top
    if ($largura -le 0 -or $altura -le 0) {
        throw "Retangulo da janela invalido ($largura x $altura) -- PID $($App.Proc.Id)."
    }

    Add-Type -AssemblyName System.Drawing -ErrorAction SilentlyContinue
    $bmp = New-Object System.Drawing.Bitmap $largura, $altura
    $gr = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $gr.GetHdc()
    try {
        $ok = [LayoutCorelDriver]::PrintWindow($hwnd, $hdc, 2)  # PW_RENDERFULLCONTENT
    } finally {
        $gr.ReleaseHdc($hdc)
    }
    if (-not $ok) { throw "PrintWindow falhou pro HWND $hwnd." }

    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $gr.Dispose()
    $bmp.Dispose()
    Write-Output "Screenshot salvo: $Path ($largura x $altura)"
}

function Stop-LayoutCorel {
    param([Parameter(Mandatory)][hashtable]$App)
    $App.Proc.Refresh()
    if (-not $App.Proc.HasExited) {
        Stop-Process -Id $App.Proc.Id -Force
    }
    # Mata tambem o stub lancador (-Modo dev), se for um PID diferente --
    # ver Start-LayoutCorel. Ignora erro: normalmente ja saiu junto com o filho.
    if ($App.LauncherPid -and $App.LauncherPid -ne $App.Proc.Id) {
        Stop-Process -Id $App.LauncherPid -Force -ErrorAction SilentlyContinue
    }
}
