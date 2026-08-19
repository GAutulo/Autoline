"""Painéis (faces) da caixa — deriva, a partir dos segmentos já calculados
pelo `ServicoLayoutCaixa` (Impressora nas colunas/X, Riscador nas
linhas/Y), as regiões retangulares que representam cada face física da
caixa aberta (frente, lateral, tampa, fundo, aba de cola...).

Não depende de nada de UI — só de `models.py`, mesmo padrão de
`layout_service.py`. É o que permite um elemento de mockup (texto,
forma, imagem) "pertencer" a uma face específica da caixa: por decisão
do usuário, isso é só uma etiqueta (`ElementoMockup.painel_id`, ver
`ui/mockup_itens.py`) — nenhum recorte acontece, porque às vezes uma
impressão atravessa pra um painel vizinho, e não vale a pena travar o
elemento nisso. Mais adiante, quando a Fase 3 (visualização 3D) existir,
cada painel vira uma face do sólido dobrado.

Escopo deliberadamente conservador: só expõe os painéis que são sempre
os mesmos independente da variação exata do tipo de caixa (ex.: o
envoltório "com corte" recorta os cantos externos da chapa, o "sem
corte" não — em vez de tentar acertar essa diferença painel a painel
aqui, essa função só devolve as faces centrais de verdade, que existem
sempre e são as que realmente recebem arte na prática. Abas de canto e
tiras de cola ficam de fora por ora; dá pra ampliar isso depois se
precisar."""

from __future__ import annotations

from dataclasses import dataclass

from .models import TipoCaixa

_TIPOS_MALETA = {TipoCaixa.MALETA_NORMAL, TipoCaixa.MALETA_TRANSPASSADA}


@dataclass(frozen=True)
class Painel:
    """Uma face (ou aba) da caixa aberta, em coordenadas de mm — mesmo
    sistema de eixos dos `LinhaDesenho` (X = Impressora, Y = Riscador)."""

    id: str
    nome: str
    x1: float
    y1: float
    x2: float
    y2: float
    eh_aba: bool  # aba de cola/estrutural — normalmente não leva arte impressa

    @property
    def largura(self) -> float:
        return self.x2 - self.x1

    @property
    def altura(self) -> float:
        return self.y2 - self.y1

    def contem(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


def calcular_paineis(
    tipo: TipoCaixa, segmentos_impressora: list[float], segmentos_riscador: list[float]
) -> list[Painel]:
    """Recebe os `segmentos_impressora`/`segmentos_riscador` já efetivos
    (ver `LayoutCaixa.segmentos_impressora/segmentos_riscador`, valores
    reais usados no desenho, já com os padrões aplicados)."""
    if tipo in _TIPOS_MALETA:
        return _paineis_maleta(segmentos_impressora, segmentos_riscador)
    return _paineis_envoltorio(segmentos_impressora, segmentos_riscador)


def _bordas_cumulativas(segmentos: list[float]) -> list[float]:
    bordas = [0.0]
    for s in segmentos:
        bordas.append(bordas[-1] + s)
    return bordas


def _paineis_maleta(segmentos_impressora: list[float], segmentos_riscador: list[float]) -> list[Painel]:
    # Impressora (X): Aba | L | C | L | C  → x0..x5
    # Riscador   (Y): Topo | Centro | Inferior → y0..y3
    # A faixa central (y1-y2, a altura real da caixa) é sempre sólida e
    # contínua em toda a largura x0-x5 (confirmado contra a geometria em
    # `layout_service.py::_calc_maleta_normal`) — é a única faixa exposta
    # aqui (ver docstring do módulo).
    xs = _bordas_cumulativas(segmentos_impressora)
    ys = _bordas_cumulativas(segmentos_riscador)
    if len(xs) < 6 or len(ys) < 4:
        return []

    definicoes = [
        ("aba_cola", "Aba de cola", 0, True),
        ("lateral1", "Lateral 1", 1, False),
        ("frente", "Frente", 2, False),
        ("lateral2", "Lateral 2", 3, False),
        ("verso", "Verso", 4, False),
    ]
    return [
        Painel(id_, nome, xs[col], ys[1], xs[col + 1], ys[2], eh_aba)
        for id_, nome, col, eh_aba in definicoes
    ]


def _paineis_envoltorio(segmentos_impressora: list[float], segmentos_riscador: list[float]) -> list[Painel]:
    # Impressora (X): Aba | Altura | Comprimento | Altura | Aba → x0..x5
    # Riscador   (Y): Aba | Altura | Largura | Altura | Aba     → y0..y5
    # A "cruz" central (Frente no meio + Lateral/Tampa/Fundo grudados nas
    # 4 bordas dela) é sempre sólida nas 4 variantes de envoltório — os
    # cantos e as tiras de Aba nas pontas mudam de presença conforme
    # "com corte" ou não, então ficam de fora (ver docstring do módulo).
    xs = _bordas_cumulativas(segmentos_impressora)
    ys = _bordas_cumulativas(segmentos_riscador)
    if len(xs) < 6 or len(ys) < 6:
        return []

    definicoes = [
        ("frente", "Frente", 2, 2),
        ("lateral1", "Lateral 1", 1, 2),
        ("lateral2", "Lateral 2", 3, 2),
        ("tampa", "Tampa", 2, 1),
        ("fundo", "Fundo", 2, 3),
    ]
    return [
        Painel(id_, nome, xs[col], ys[linha], xs[col + 1], ys[linha + 1], eh_aba=False)
        for id_, nome, col, linha in definicoes
    ]
