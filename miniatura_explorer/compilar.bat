@echo off
rem Compila a prévia do Explorer (AutolineMiniatura.dll) com o csc do .NET
rem Framework 4 que vem no Windows. A DLL vai pra assets\ e entra no exe
rem (Autoline.spec). Rodar de novo só se MiniaturaAutoline.cs mudar.
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
"%CSC%" /nologo /target:library /platform:x64 /optimize+ /reference:System.Drawing.dll ^
  /out:"%~dp0..\assets\AutolineMiniatura.dll" "%~dp0MiniaturaAutoline.cs"
