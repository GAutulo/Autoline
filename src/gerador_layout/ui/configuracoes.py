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

# Parâmetros de ferramenta do modo Layout — todos eram constante fixa no
# código até virarem preferência (ver `DialogoConfiguracoes`, aba
# "Ferramentas"); os valores aqui são exatamente os que já estavam
# hard-coded antes, preservados como padrão pra ninguém sentir a telinha
# mudar sozinha na primeira vez que abrir a versão nova.
_PADRAO_SNAP_ATIVO = True
_PADRAO_LIMIAR_SNAP_MM = 3.0
_PADRAO_PASSO_GRADE_MM = 10.0
_PADRAO_PASSO_NUDGE_MM = 1.0
_PADRAO_PASSO_NUDGE_SHIFT_MM = 10.0
_PADRAO_PASSO_DUPLICAR_MM = 6.0
_PADRAO_FONTE_TEXTO = "Arial"


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


# ── Parâmetros de ferramenta (modo Layout) ─────────────────────────────
# Mesmo princípio do traço do vinco/legenda acima: lidos ao vivo (sem
# cache) no ponto de uso — ver `preview_canvas.py` — então uma mudança
# aqui já vale na próxima vez que a ferramenta for usada, sem reiniciar.


def espessura_papelao_mm() -> float:
    """Papelão do 3D (mm) — lembrado entre as sessões. 0 = folha fina."""
    return float(_settings().value("espessura_papelao_mm", 0.0, type=float))


def definir_espessura_papelao_mm(valor: float) -> None:
    _settings().setValue("espessura_papelao_mm", float(valor))


def giro_automatico_3d() -> bool:
    """Se a caixa montada fica girando sozinha no 3D (desligado: gastava o
    processador o tempo todo com a aba 3D aberta)."""
    return bool(_settings().value("giro_automatico_3d", False, type=bool))


def definir_giro_automatico_3d(ativo: bool) -> None:
    _settings().setValue("giro_automatico_3d", bool(ativo))


def snap_ativo_padrao() -> bool:
    """Se o encaixe (snap) começa LIGADO quando o app abre — só o estado
    inicial; o usuário ainda pode ligar/desligar na hora pelo menu Exibir
    (isso não fica salvo, é por sessão de propósito, igual a grade)."""
    return bool(_settings().value("snap_ativo_padrao", _PADRAO_SNAP_ATIVO, type=bool))


def definir_snap_ativo_padrao(ativo: bool) -> None:
    _settings().setValue("snap_ativo_padrao", ativo)


def limiar_snap_mm() -> float:
    """Distância (mm) dentro da qual uma borda/centro "gruda" num alvo de
    encaixe ao soltar o arrasto — maior valor gruda mais fácil (bom pra
    trabalho rápido/impreciso no mouse), menor valor exige chegar mais
    perto (bom pra ajuste fino sem grudar à toa)."""
    return float(_settings().value("limiar_snap_mm", _PADRAO_LIMIAR_SNAP_MM, type=float))


def definir_limiar_snap_mm(valor: float) -> None:
    _settings().setValue("limiar_snap_mm", valor)


def passo_grade_mm() -> float:
    """Espaçamento (mm) da grade de fundo do canvas — também um alvo de
    encaixe quando a grade está visível (ver menu Exibir)."""
    return float(_settings().value("passo_grade_mm", _PADRAO_PASSO_GRADE_MM, type=float))


def definir_passo_grade_mm(valor: float) -> None:
    _settings().setValue("passo_grade_mm", valor)


def passo_nudge_mm() -> tuple[float, float]:
    """(passo normal, passo com Shift) pra mover elemento selecionado
    pelas setas do teclado — o "ajuste fino" de precisão que complementa
    o arrasto com o mouse."""
    s = _settings()
    normal = float(s.value("passo_nudge_mm", _PADRAO_PASSO_NUDGE_MM, type=float))
    com_shift = float(s.value("passo_nudge_shift_mm", _PADRAO_PASSO_NUDGE_SHIFT_MM, type=float))
    return normal, com_shift


def definir_passo_nudge_mm(normal: float, com_shift: float) -> None:
    s = _settings()
    s.setValue("passo_nudge_mm", normal)
    s.setValue("passo_nudge_shift_mm", com_shift)


def passo_duplicar_mm() -> float:
    """Deslocamento (mm, nos 2 eixos) de cada cópia feita com Ctrl+D —
    efeito "cascata" pra não empilhar as cópias exatamente uma em cima
    da outra."""
    return float(_settings().value("passo_duplicar_mm", _PADRAO_PASSO_DUPLICAR_MM, type=float))


def definir_passo_duplicar_mm(valor: float) -> None:
    _settings().setValue("passo_duplicar_mm", valor)


def fonte_padrao_texto() -> str:
    """Família de fonte usada quando um elemento de Texto/Callout novo é
    criado — o usuário ainda troca por elemento depois, na barra de
    propriedades; isso só define o ponto de partida."""
    return str(_settings().value("fonte_padrao_texto", _PADRAO_FONTE_TEXTO, type=str))


def definir_fonte_padrao_texto(nome: str) -> None:
    _settings().setValue("fonte_padrao_texto", nome)


def restaurar_padroes() -> None:
    s = _settings()
    s.setValue("dpi_exportacao_jpg", _PADRAO_DPI_JPG)
    s.setValue("traco_vinco_mm", _PADRAO_TRACO_VINCO_MM)
    s.setValue("espaco_vinco_mm", _PADRAO_ESPACO_VINCO_MM)
    s.setValue("altura_legenda_mm", _PADRAO_ALTURA_LEGENDA_MM)
    s.setValue("snap_ativo_padrao", _PADRAO_SNAP_ATIVO)
    s.setValue("limiar_snap_mm", _PADRAO_LIMIAR_SNAP_MM)
    s.setValue("passo_grade_mm", _PADRAO_PASSO_GRADE_MM)
    s.setValue("passo_nudge_mm", _PADRAO_PASSO_NUDGE_MM)
    s.setValue("passo_nudge_shift_mm", _PADRAO_PASSO_NUDGE_SHIFT_MM)
    s.setValue("passo_duplicar_mm", _PADRAO_PASSO_DUPLICAR_MM)
    s.setValue("fonte_padrao_texto", _PADRAO_FONTE_TEXTO)
