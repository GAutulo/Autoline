---
name: run-gerador-layout-caixas
description: Build, run, and drive the Gerador de Layout de Caixas desktop app (PySide6/Qt, Windows-only). Use when asked to start the app, launch it, take a screenshot of its UI, verify a UI/design change, or check that it opens without errors.
---

Windows desktop app (PySide6/Qt). Drive it via
`.claude\skills\run-gerador-layout-caixas\driver.ps1` — a PowerShell
module with `Start-LayoutCorel` / `Save-AppScreenshot` /
`Stop-LayoutCorel`. All paths below are relative to the repo root.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -r requirements-build.txt   # only needed for Build below
```

## Build (packaged .exe — optional, dev mode below doesn't need this)

```powershell
.venv\Scripts\pyinstaller.exe --noconfirm LayoutCorel.spec
```

Produces `dist\LayoutCorel.exe`. Dev mode (below) is faster to iterate
with; build this when you specifically need to verify the packaged exe.

## Run (agent path)

```powershell
. .claude\skills\run-gerador-layout-caixas\driver.ps1
$app = Start-LayoutCorel               # dev mode — launches via .venv's pythonw.exe
Save-AppScreenshot -App $app -Path "$env:TEMP\tela.png"
Stop-LayoutCorel -App $app
```

Use `Start-LayoutCorel -Modo exe` instead to drive `dist\LayoutCorel.exe`
(build it first — see above).

`$app` is `@{ Proc = <Process>; Hwnd = <IntPtr>; LauncherPid = <int> }` —
the actual window-owning process, not necessarily the one you launched
(see Gotchas). Always go through these three functions; don't call
`Start-Process`/screenshot APIs yourself — see Gotchas for exactly why
each one exists.

| command | what it does |
|---|---|
| `Start-LayoutCorel [-Modo dev\|exe]` | Launches the app, waits up to 15s for its window, returns `$app`. Throws with a specific message if the process dies first or the window never appears. |
| `Save-AppScreenshot -App $app -Path <file>` | Screenshots exactly that window (via `PrintWindow`, not screen coordinates — see Gotchas) to a PNG file. |
| `Stop-LayoutCorel -App $app` | Kills the window-owning process and the launcher stub, if they're different PIDs. |

Screenshots land wherever `-Path` says; nothing writes anywhere on its
own.

## Run (human path)

Double-click `dist\LayoutCorel.exe`, or from repo root:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m gerador_layout.main
```

(`python.exe`, not `pythonw.exe`, so a crash traceback prints to the
console — that's the whole reason the human path uses it and the agent
path doesn't, see Gotchas.)

## Test

```powershell
.venv\Scripts\python.exe -m pytest tests\ -q
```

5 tests, all pass, no GUI involved (pure `layout_service.py` logic).

---

## Gotchas

- **Screenshot via `CopyFromScreen` is unsafe on this machine — use
  `PrintWindow` instead, always.** `CopyFromScreen` reads screen
  *pixels at a rectangle of coordinates*, not "the app's window" — if
  any other window (a File Explorer folder, CorelDRAW with a real
  client file open) is on top of that rectangle at the instant of the
  call, you capture *that*, not the app. This happened three times
  while authoring this skill, each time exposing real client file
  names from a totally unrelated window, even though the window
  handle had just been verified to have the right title a moment
  earlier — the overlap can happen in the gap between the check and
  the actual pixel copy. `Save-AppScreenshot` instead uses
  `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)`, which renders the
  specific HWND you pass it directly from its own buffer — it cannot
  pick up a different window by accident, regardless of what's on top
  of it on screen. If you ever add another way to grab a picture of
  this app, make it go through `PrintWindow` on a PID-verified HWND,
  never screen coordinates.

- **`Process.MainWindowHandle` doesn't reliably find the Qt window —
  that's why the driver uses `EnumWindows` by PID instead.** Two
  separate failures, both reproduced while building this: (1) launching
  via `python.exe` (console subsystem) — `MainWindowHandle` returns the
  *console* window's handle, not the Qt window, because the console
  exists first; (2) launching via `pythonw.exe` (no console) —
  `MainWindowHandle` can sit at `0` indefinitely even though the Qt
  window is visible and the process is `Responding: True`. `driver.ps1`
  finds the window by walking `EnumWindows` for the first visible
  top-level window with a non-empty title owned by the target PID —
  see `FindWindowForProcess` in the driver.

- **`pythonw.exe -m gerador_layout.main` in this venv re-execs into a
  *child* process — the PID `Start-Process` hands back never gets a
  window at all.** Confirmed with `Get-CimInstance Win32_Process
  -Filter "ParentProcessId=..."`: the process you launch is a stub;
  a *child* `pythonw.exe` with the same command line is the one that
  actually owns the Qt window. `Start-LayoutCorel` searches the
  launched PID *and* its direct children for a window, and
  `Stop-LayoutCorel` kills both PIDs (the child is usually already
  gone by the time the launcher is asked to stop, hence
  `-ErrorAction SilentlyContinue` there). The packaged exe
  (`-Modo exe`) does the same thing for a different reason — PyInstaller
  onefile's bootloader stub re-execs the real app as a child too — so
  the fix covers both modes.

- **`.ps1` files with accented Portuguese text (á, ç, ã, —) need a
  UTF-8 BOM, or Windows PowerShell 5.1 mangles them into text that
  fails to parse** — not just renders wrong, the script won't load at
  all (`Token '...' unexpected`). Hit this authoring `driver.ps1`
  itself. Fixed two ways: (1) `driver.ps1` avoids accented characters
  and em-dashes entirely (uses "nao"/"--"), so this can't recur in that
  file no matter how it gets saved; (2) if you write a *different* `.ps1`
  with accented text, save it with a BOM:
  `Get-Content $path -Raw -Encoding UTF8 | Set-Content $path -Encoding UTF8`
  (Windows PowerShell 5.1's `Set-Content -Encoding UTF8` writes a BOM;
  plain UTF-8-without-BOM, which is what most editors/tools default to,
  is what breaks).

- **First screenshot after launch can show unpainted blank space at
  the bottom of the window.** Observed in both `-Modo dev` and
  `-Modo exe` runs, ~200ms after the window was detected: the bottom
  "Medidas geradas / ajustáveis" section is visible but doesn't reach
  the window's bottom edge, leaving plain background below it. Looks
  like a first-show layout/paint timing issue rather than anything
  `PrintWindow`-specific. Workaround if it matters for what you're
  checking: `Save-AppScreenshot` twice a beat apart and use the second
  one, or resize the window by 1px (triggers a real layout pass) before
  capturing.

## Troubleshooting

- **`Janela principal nao apareceu em 15s`**: either the app crashed on
  startup (run the human path with `python.exe`, not `pythonw.exe`, to
  see the traceback) or `.venv` doesn't have PySide6 installed (rerun
  Setup).
- **`dist\LayoutCorel.exe nao existe`** (from `-Modo exe`): run Build
  first.
- **`.venv nao existe`** (from `-Modo dev`): run Setup first.
- **PowerShell throws a parser error pointing at what looks like
  garbled text inside a string** in a `.ps1` you're editing: that file
  is missing its UTF-8 BOM — see the Gotchas entry above.

## Possible future extension

No interaction beyond launch/screenshot/stop today — no
click/type harness. `pywinauto` (not currently installed; would need
`.venv\Scripts\pip install pywinauto`) would let a driver actually
change field values and confirm the canvas redraws, not just that the
window opens and looks right. Not built now because nothing in this
skill's authoring session needed to script the GUI's a click or a
keypress — only launch and look — but worth knowing if a future task
needs that.
