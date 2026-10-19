"""Abrir os projetos ``.autoline`` com dois cliques no Windows e mostrar a
prévia do projeto no ícone do Explorer: registra a extensão e o gerador de
miniaturas (AutolineMiniatura.dll, ver miniatura_explorer/) no registro DO
USUÁRIO (HKEY_CURRENT_USER\\Software\\Classes — não precisa de administrador
nem mexe nos outros usuários). Só faz algo quando o usuário clica no botão
das Configurações."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_PROGID = "Autoline.Projeto"
# Gerador de miniaturas: o CLSID é o da classe em MiniaturaAutoline.cs; a outra
# chave é a interface IThumbnailProvider do Windows (fixa).
CLSID_MINIATURA = "{7A3E2C51-9B4D-4F60-8C2E-5D1B0A6F4E21}"
_SHELLEX_MINIATURA = "{e357fccd-a995-4576-b01f-234630154e96}"
_CLASSE = "AutolineMiniatura.MiniaturaAutoline"
_ASSEMBLY = "AutolineMiniatura, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"


class ErroAssociacao(RuntimeError):
    pass


def comando_de_abrir() -> str:
    if not getattr(sys, "frozen", False):
        raise ErroAssociacao("Isso funciona no Autoline.exe (o programa instalado), não rodando pelo código-fonte.")
    return f'"{sys.executable}" "%1"'


def chaves(comando: str) -> list[tuple[str, str]]:
    """(caminho da chave em HKCU, valor padrão) a gravar pra abrir com dois cliques."""
    return [
        (r"Software\Classes\.autoline", _PROGID),
        (rf"Software\Classes\{_PROGID}", "Projeto do Autoline"),
        (rf"Software\Classes\{_PROGID}\DefaultIcon", comando.split('" "')[0].strip('"') + ",0"),
        (rf"Software\Classes\{_PROGID}\shell\open\command", comando),
    ]


def dll_miniatura_embutida() -> Path:
    """A DLL que vem com o app (no exe: dentro do pacote; no código: assets/)."""
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "assets" / "AutolineMiniatura.dll"
    return Path(__file__).resolve().parents[3] / "assets" / "AutolineMiniatura.dll"


def pasta_instalacao() -> Path:
    import os

    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Autoline"


def instalar_dll_miniatura(origem: Path | None = None, pasta: Path | None = None) -> Path:
    """Copia a DLL pra um lugar fixo (o exe extrai tudo numa pasta temporária
    que some ao fechar). Se a cópia antiga estiver em uso pelo Explorer, grava
    com outro nome."""
    origem = origem or dll_miniatura_embutida()
    if not origem.is_file():
        raise ErroAssociacao("Não achei o componente da prévia (AutolineMiniatura.dll).")
    pasta = pasta or pasta_instalacao()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "AutolineMiniatura.dll"
    try:
        if not destino.exists() or destino.read_bytes() != origem.read_bytes():
            shutil.copyfile(origem, destino)
    except PermissionError:
        n = 2
        while (pasta / f"AutolineMiniatura{n}.dll").exists():
            n += 1
        destino = pasta / f"AutolineMiniatura{n}.dll"
        shutil.copyfile(origem, destino)
    return destino


def valores_miniatura(dll: Path) -> list[tuple[str, str | None, str]]:
    """(chave em HKCU, nome do valor — None = padrão, valor) do gerador de miniaturas."""
    base = rf"Software\Classes\CLSID\{CLSID_MINIATURA}"
    codigo = dll.resolve().as_uri()
    inproc = {
        None: "mscoree.dll",
        "ThreadingModel": "Both",
        "Class": _CLASSE,
        "Assembly": _ASSEMBLY,
        "RuntimeVersion": "v4.0.30319",
        "CodeBase": codigo,
    }
    valores: list[tuple[str, str | None, str]] = [(base, None, "Autoline — prévia do projeto")]
    for chave in (rf"{base}\InprocServer32", rf"{base}\InprocServer32\1.0.0.0"):
        valores += [(chave, nome, valor) for nome, valor in inproc.items() if not (nome is None and chave.endswith("1.0.0.0"))]
    valores.append((rf"Software\Classes\.autoline\ShellEx\{_SHELLEX_MINIATURA}", None, CLSID_MINIATURA))
    return valores


def _gravar(valores: list[tuple[str, str | None, str]]) -> None:
    import winreg

    for chave, nome, valor in valores:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chave) as k:
            winreg.SetValueEx(k, nome or "", 0, winreg.REG_SZ, valor)


def registrar_miniatura(dll: Path | None = None) -> Path:
    """Prévia do projeto no ícone dos .autoline no Explorer."""
    if sys.platform != "win32":
        raise ErroAssociacao("Só no Windows.")
    destino = instalar_dll_miniatura(dll)
    _gravar(valores_miniatura(destino))
    _avisar_explorer()
    return destino


def associar() -> None:
    if sys.platform != "win32":
        raise ErroAssociacao("Só no Windows.")
    _gravar([(chave, None, valor) for chave, valor in chaves(comando_de_abrir())])
    registrar_miniatura()
    _avisar_explorer()


def _avisar_explorer() -> None:
    import ctypes

    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
