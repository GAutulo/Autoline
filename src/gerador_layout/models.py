"""Modelos de dados do gerador de layout de caixas.

Porta direta dos modelos originais em C# (BoxMeasures.cs / DrawLine.cs),
sem nenhuma dependência de UI — podem ser usados tanto pela interface
gráfica quanto por testes automatizados ou por um futuro exportador
(PDF/SVG) sem alteração nenhuma.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

# ── Enums ─────────────────────────────────────────────────────────────


class TipoLinha(Enum):
    """Tipo de linha técnica no layout de corte."""

    CORTE = auto()        # Corte externo (contínuo)
    VINCO = auto()         # Vinco/dobra (tracejado)
    CORTE_SERRA = auto()   # Corte de separação de abas ("serra")
    MEIO_CORTE = auto()    # Meio corte
    DOBRA = auto()          # Auxiliar


class TipoCaixa(Enum):
    """Tipos de caixa suportados pelo sistema."""

    ENVOLTORIO_FECHAMENTO_MEIO_SEM_CORTE = auto()
    ENVOLTORIO_FECHAMENTO_MEIO_COM_CORTE = auto()
    ENVOLTORIO_FECHAMENTO_NORMAL_SEM_CORTE = auto()
    ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE = auto()
    MALETA_NORMAL = auto()
    MALETA_TRANSPASSADA = auto()
    # Meia caixa: só Aba | L | C na impressora (caixa grande feita em duas
    # metades coladas depois).
    MALETA_NORMAL_MEIA = auto()
    MALETA_TRANSPASSADA_MEIA = auto()
    # Capa / bandeja: envoltório só com A | C | A na impressora e A | L | A
    # no riscador (fundo, 4 paredes e cantos, sem tampa).
    ENVOLTORIO_CAPA = auto()


# Nomes curtos (cabem na lista sem cortar) e agrupados por família.
NOME_EXIBICAO_TIPO_CAIXA: dict[TipoCaixa, str] = {
    TipoCaixa.MALETA_NORMAL: "Maleta normal",
    TipoCaixa.MALETA_NORMAL_MEIA: "Maleta normal · meia caixa",
    TipoCaixa.MALETA_TRANSPASSADA: "Maleta transpassada",
    TipoCaixa.MALETA_TRANSPASSADA_MEIA: "Maleta transpassada · meia caixa",
    TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_SEM_CORTE: "Envoltório normal · sem corte",
    TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE: "Envoltório normal · com corte",
    TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_SEM_CORTE: "Envoltório fecha no meio · sem corte",
    TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_COM_CORTE: "Envoltório fecha no meio · com corte",
    TipoCaixa.ENVOLTORIO_CAPA: "Envoltório capa (bandeja)",
}

# Ordem da lista de tipos na tela (a do dicionário acima).
ORDEM_TIPOS_CAIXA: list[TipoCaixa] = list(NOME_EXIBICAO_TIPO_CAIXA)

# Explicação de cada tipo (dica da lista).
DESCRICAO_TIPO_CAIXA: dict[TipoCaixa, str] = {
    TipoCaixa.MALETA_NORMAL: "Aba | L | C | L | C — abas de cima e de baixo se encontram no meio (L/2).",
    TipoCaixa.MALETA_NORMAL_MEIA: "Metade da maleta normal: Aba | L | C. Pra caixa grande, feita em duas metades coladas.",
    TipoCaixa.MALETA_TRANSPASSADA: "Aba | L | C | L | C — abas de cima e de baixo inteiras (L), uma por cima da outra.",
    TipoCaixa.MALETA_TRANSPASSADA_MEIA: "Metade da maleta transpassada: Aba | L | C.",
    TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_SEM_CORTE: "Tampa inteira (L) + aba de fechamento; chapa inteira.",
    TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE: "Tampa inteira (L) + aba de fechamento; cantos externos recortados.",
    TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_SEM_CORTE: "Duas meias tampas (L/2) que se encontram no meio; chapa inteira.",
    TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_COM_CORTE: "Duas meias tampas (L/2); cantos externos recortados.",
    TipoCaixa.ENVOLTORIO_CAPA: "Bandeja: A | C | A na impressora e A | L | A no riscador — fundo, 4 paredes e cantos, sem tampa.",
}

TIPOS_MALETA = {
    TipoCaixa.MALETA_NORMAL,
    TipoCaixa.MALETA_TRANSPASSADA,
    TipoCaixa.MALETA_NORMAL_MEIA,
    TipoCaixa.MALETA_TRANSPASSADA_MEIA,
}
TIPOS_MEIA_CAIXA = {TipoCaixa.MALETA_NORMAL_MEIA, TipoCaixa.MALETA_TRANSPASSADA_MEIA}
TIPOS_TRANSPASSADA = {TipoCaixa.MALETA_TRANSPASSADA, TipoCaixa.MALETA_TRANSPASSADA_MEIA}


# ── Dataclasses ───────────────────────────────────────────────────────


@dataclass
class LinhaDesenho:
    """Um segmento de linha a ser desenhado (em milímetros).

    `bojo` diferente de zero faz dela um ARCO de (x1, y1) a (x2, y2) — a
    convenção "bulge" do DXF, bojo = tan(θ/4). Ver `geometria_faca.py`."""

    x1: float
    y1: float
    x2: float
    y2: float
    tipo: TipoLinha
    bojo: float = 0.0


@dataclass
class CorImpressao:
    """Cor que aparece na legenda de impressão do layout.

    Não altera as linhas técnicas da faca — é só informação visual/
    de produção (quais tintas serão usadas na impressão).
    """

    nome: str
    r: int
    g: int
    b: int


@dataclass
class MedidasCaixa:
    """Medidas fornecidas pelo operador para geração do layout."""

    tipo: TipoCaixa = TipoCaixa.MALETA_NORMAL

    # ── Medidas finais da caixa ──────────────────────────────────────
    comprimento: float = 0.0
    largura: float = 0.0
    altura: float = 0.0

    # ── Compatibilidade / outros tipos ───────────────────────────────
    sangria_top: float = 0.0
    sangria_bottom: float = 0.0
    aba: float = 4.0

    # ── Medidas geradas/editáveis por trecho — Impressora (X) ────────
    # Aba × L × C × L × C
    impressora_aba: float = 4.0
    impressora_largura_1: float = 0.0
    impressora_comprimento_1: float = 0.0
    impressora_largura_2: float = 0.0
    impressora_comprimento_2: float = 0.0

    # ── Riscador (Y) ──────────────────────────────────────────────────
    riscador_superior: float = 0.0
    riscador_centro: float = 0.0
    riscador_inferior: float = 0.0
    riscador_parte_4: float = 0.0
    riscador_parte_5: float = 0.0

    # ── Legenda de cores de impressão ────────────────────────────────
    cores_legenda: list[CorImpressao] = field(default_factory=list)

    # ── Geral ─────────────────────────────────────────────────────────
    espessura_papelao: float = 3.0


@dataclass
class LayoutCaixa:
    """Conjunto de linhas que formam o layout completo de uma caixa."""

    linhas: list[LinhaDesenho] = field(default_factory=list)
    cores_legenda: list[CorImpressao] = field(default_factory=list)
    largura_total: float = 0.0
    altura_total: float = 0.0
    descricao: str = ""

    # Valores efetivos (já com os padrões aplicados) de cada trecho — usados
    # pela UI para mostrar o número real que está sendo usado no desenho,
    # mesmo quando o campo foi deixado em "automático".
    segmentos_impressora: list[float] = field(default_factory=list)
    segmentos_riscador: list[float] = field(default_factory=list)
