"""Preferências do usuário, persistidas via QSettings (Windows: registro
em HKEY_CURRENT_USER — não precisa de arquivo de configuração próprio).

Módulo propositalmente sem dependência de nenhum outro módulo da UI
(`estilo.py` importa daqui, não o contrário) — evita import circular,
já que a paleta de cores em `estilo.py` precisa ler o tema salvo aqui
antes mesmo da UI existir.

Tema exige reiniciar o app pra valer (ver `estilo.py`): a paleta vira
literais de cor dentro de várias strings de QSS montadas na hora que
cada tela é construída — trocar o tema em tempo real exigiria reaplicar
isso tudo de novo em cada widget já criado, então mais simples e mais
confiável salvar a escolha e aplicar no próximo início."""

from __future__ import annotations

from PySide6.QtCore import QSettings

# Muda a chave de registro onde as preferências ficam salvas (rebranding
# Autoline) — quem já tinha aberto o app antes vai ver as preferências
# (tema, DPI, traço do vinco) voltarem ao padrão uma vez, não é bug: é
# uma chave nova, a antiga (sob "LayoutCorel") só fica órfã no registro.
_ORGANIZACAO = "Autoline"
_APLICATIVO = "Autoline"

TEMA_CLARO = "claro"
TEMA_ESCURO = "escuro"

_PADRAO_DPI_JPG = 300
# Mesmo valor que já estava fixo no código (DashLength=2/GapLength=3 a
# 1,0pt de espessura de linha — o padrão real confirmado pelo usuário
# comparando direto no CorelDRAW), só que agora em mm e editável.
_PADRAO_TRACO_VINCO_MM = 0.71
_PADRAO_ESPACO_VINCO_MM = 1.06
_PADRAO_ALTURA_LEGENDA_MM = 1.5


def _settings() -> QSettings:
    return QSettings(_ORGANIZACAO, _APLICATIVO)


def tema() -> str:
    return _settings().value("tema", TEMA_CLARO, type=str)


def definir_tema(nome: str) -> None:
    _settings().setValue("tema", nome)


def dpi_exportacao_jpg() -> int:
    return int(_settings().value("dpi_exportacao_jpg", _PADRAO_DPI_JPG, type=int))


def definir_dpi_exportacao_jpg(valor: int) -> None:
    _settings().setValue("dpi_exportacao_jpg", valor)


def traco_vinco_mm() -> tuple[float, float]:
    """(comprimento do traço, comprimento do espaço), em mm."""
    s = _settings()
    traco = float(s.value("traco_vinco_mm", _PADRAO_TRACO_VINCO_MM, type=float))
    espaco = float(s.value("espaco_vinco_mm", _PADRAO_ESPACO_VINCO_MM, type=float))
    return traco, espaco


def definir_traco_vinco_mm(traco: float, espaco: float) -> None:
    s = _settings()
    s.setValue("traco_vinco_mm", traco)
    s.setValue("espaco_vinco_mm", espaco)


def altura_legenda_mm() -> float:
    return float(_settings().value("altura_legenda_mm", _PADRAO_ALTURA_LEGENDA_MM, type=float))


def definir_altura_legenda_mm(valor: float) -> None:
    _settings().setValue("altura_legenda_mm", valor)


def restaurar_padroes() -> None:
    s = _settings()
    s.setValue("dpi_exportacao_jpg", _PADRAO_DPI_JPG)
    s.setValue("traco_vinco_mm", _PADRAO_TRACO_VINCO_MM)
    s.setValue("espaco_vinco_mm", _PADRAO_ESPACO_VINCO_MM)
    s.setValue("altura_legenda_mm", _PADRAO_ALTURA_LEGENDA_MM)
