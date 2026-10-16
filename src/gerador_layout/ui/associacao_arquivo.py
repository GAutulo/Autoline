"""Abrir os projetos ``.autoline`` com dois cliques no Windows: registra a
extensão no registro DO USUÁRIO (HKEY_CURRENT_USER\\Software\\Classes — não
precisa de administrador nem mexe nos outros usuários) apontando pro
Autoline.exe que está rodando. Só faz algo quando o usuário clica no botão
das Configurações."""

from __future__ import annotations

import sys

_PROGID = "Autoline.Projeto"


class ErroAssociacao(RuntimeError):
    pass


def comando_de_abrir() -> str:
    if not getattr(sys, "frozen", False):
        raise ErroAssociacao("Isso funciona no Autoline.exe (o programa instalado), não rodando pelo código-fonte.")
    return f'"{sys.executable}" "%1"'


def chaves(comando: str) -> list[tuple[str, str]]:
    """(caminho da chave em HKCU, valor padrão) a gravar."""
    return [
        (r"Software\Classes\.autoline", _PROGID),
        (rf"Software\Classes\{_PROGID}", "Projeto do Autoline"),
        (rf"Software\Classes\{_PROGID}\DefaultIcon", comando.split('" "')[0].strip('"') + ",0"),
        (rf"Software\Classes\{_PROGID}\shell\open\command", comando),
    ]


def associar() -> None:
    if sys.platform != "win32":
        raise ErroAssociacao("Só no Windows.")
    import ctypes
    import winreg

    for chave, valor in chaves(comando_de_abrir()):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chave) as k:
            winreg.SetValue(k, "", winreg.REG_SZ, valor)
    # Avisa o Explorer pra atualizar os ícones/associações.
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
