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

from .dobra_generica import achar_faces
from .models import TIPOS_MALETA as _TIPOS_MALETA
from .models import LinhaDesenho, TipoCaixa


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
    tipo: TipoCaixa,
    segmentos_impressora: list[float],
    segmentos_riscador: list[float],
    faixas_recuadas: tuple[int, ...] = (),
) -> list[Painel]:
    """Recebe os `segmentos_impressora`/`segmentos_riscador` já efetivos
    (ver `LayoutCaixa.segmentos_impressora/segmentos_riscador`, valores
    reais usados no desenho, já com os padrões aplicados). Na cinta,
    `faixas_recuadas` diz quais faixas entram o recuo dos lados."""
    if tipo == TipoCaixa.CINTA:
        return _paineis_cinta(segmentos_impressora, segmentos_riscador, faixas_recuadas)
    if tipo in _TIPOS_MALETA:
        return _paineis_maleta(segmentos_impressora, segmentos_riscador)
    if tipo == TipoCaixa.ENVOLTORIO_CAPA:
        return _paineis_capa(segmentos_impressora, segmentos_riscador)
    com_corte = tipo in (TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE, TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_COM_CORTE)
    return _paineis_envoltorio(segmentos_impressora, segmentos_riscador, com_corte)


def face_no_ponto(paineis: list[Painel], x: float, y: float) -> Painel | None:
    """A face onde o ponto cai (a menor, se houver mais de uma)."""
    dentro = [p for p in paineis if p.contem(x, y)]
    return min(dentro, key=lambda p: p.largura * p.altura) if dentro else None


def deslocamento_na_face(
    x1: float, y1: float, x2: float, y2: float, velha: Painel, nova: Painel, tolerancia: float = 0.5
) -> tuple[float, float]:
    """Quanto mover um objeto (a caixa x1..x2, y1..y2) quando a face muda de
    tamanho: mantém a distância da borda mais próxima, e o que está
    centralizado continua centralizado. O tamanho do objeto não muda."""

    def eixo(a: float, b: float, v1: float, v2: float, n1: float, n2: float) -> float:
        antes, depois = a - v1, v2 - b
        if abs(antes - depois) <= tolerancia:
            return (n1 + n2) / 2 - (v1 + v2) / 2
        return n1 - v1 if antes < depois else n2 - v2

    return eixo(x1, x2, velha.x1, velha.x2, nova.x1, nova.x2), eixo(y1, y2, velha.y1, velha.y2, nova.y1, nova.y2)


def faces_da_faca(linhas: list[LinhaDesenho]) -> list[Painel]:
    """Faca que não vem de um tipo de caixa (Construtor, catálogo, em
    branco): as faces são as regiões que as próprias linhas fecham, numeradas
    de cima pra baixo e da esquerda pra direita. O painel é o retângulo que
    envolve cada região."""
    if not linhas:
        return []
    caixas = []
    for face in achar_faces(linhas).faces:
        xs = [p[0] for p in face.poligono]
        ys = [p[1] for p in face.poligono]
        caixas.append((min(ys), min(xs), max(xs), max(ys)))
    return [
        Painel(f"face{n}", f"Face {n}", x1, y1, x2, y2, eh_aba=False)
        for n, (y1, x1, x2, y2) in enumerate(sorted(caixas), start=1)
    ]


def _paineis_capa(segmentos_impressora: list[float], segmentos_riscador: list[float]) -> list[Painel]:
    xs = _bordas_cumulativas(segmentos_impressora)
    ys = _bordas_cumulativas(segmentos_riscador)
    if len(xs) < 4 or len(ys) < 4:
        return []
    definicoes = [
        ("centro", "Centro", 1, 1),
        ("lateral1", "Lateral 1", 0, 1),
        ("lateral2", "Lateral 2", 2, 1),
        ("parede_sup", "Parede superior", 1, 0),
        ("parede_inf", "Parede inferior", 1, 2),
    ]
    return [
        Painel(id_, nome, xs[col], ys[linha], xs[col + 1], ys[linha + 1], eh_aba=False)
        for id_, nome, col, linha in definicoes
    ]


def _paineis_cinta(
    segmentos_impressora: list[float], segmentos_riscador: list[float], faixas_recuadas: tuple[int, ...]
) -> list[Painel]:
    # Impressora: largura total | recuo. Cada faixa do riscador é uma face.
    if not segmentos_impressora or not segmentos_riscador:
        return []
    largura = segmentos_impressora[0]
    recuo = segmentos_impressora[1] if len(segmentos_impressora) > 1 else 0.0
    ys = _bordas_cumulativas(segmentos_riscador)
    paineis = []
    for i, altura in enumerate(segmentos_riscador):
        if altura <= 0:  # campo vazio no meio: as outras faixas mantêm o número
            continue
        x1 = recuo if i + 1 in faixas_recuadas else 0.0
        paineis.append(Painel(f"faixa{i + 1}", f"Faixa {i + 1}", x1, ys[i], largura - x1, ys[i + 1], eh_aba=False))
    return paineis


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
    if len(xs) < 4 or len(ys) < 4:
        return []

    definicoes = [
        ("aba_cola", "Aba de cola", 0, True),
        ("lateral1", "Lateral 1", 1, False),
        ("frente", "Frente", 2, False),
        ("lateral2", "Lateral 2", 3, False),
        ("verso", "Verso", 4, False),
    ]
    # Meia caixa (Aba | L | C) só tem as três primeiras.
    paineis = [
        Painel(id_, nome, xs[col], ys[1], xs[col + 1], ys[2], eh_aba)
        for id_, nome, col, eh_aba in definicoes
        if col + 1 < len(xs)
    ]
    # Abas de tampa (em cima) e de fundo (embaixo) de cada coluna: também
    # recebem arte (logo, símbolo) — sem elas a malha e as medidas até a
    # borda da face sumiam ali.
    for id_, nome, col, _eh_aba in definicoes[1:]:
        if col + 1 < len(xs):
            paineis.append(Painel(f"tampa_{id_}", f"Tampa — {nome}", xs[col], ys[0], xs[col + 1], ys[1], False))
            paineis.append(Painel(f"fundo_{id_}", f"Fundo — {nome}", xs[col], ys[2], xs[col + 1], ys[3], False))
    return paineis


def _paineis_envoltorio(
    segmentos_impressora: list[float], segmentos_riscador: list[float], com_corte: bool = True
) -> list[Painel]:
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
    paineis = [
        Painel(id_, nome, xs[col], ys[linha], xs[col + 1], ys[linha + 1], eh_aba=False)
        for id_, nome, col, linha in definicoes
    ]
    # O resto da chapa, que também é caixa (malha, medidas, alinhar na face):
    # o fechamento de cima e o de baixo (as linhas do Riscador nas pontas),
    # os cantos (prolongamento da coluna da lateral) e as abas laterais.
    # "Sem corte": os cantos de fora também ficam na chapa.
    paineis += [
        Painel("fechamento_sup", "Fechamento superior", xs[2], ys[0], xs[3], ys[1], eh_aba=False),
        Painel("fechamento_inf", "Fechamento inferior", xs[2], ys[4], xs[3], ys[5], eh_aba=False),
    ]
    for col, lado in ((1, "1"), (3, "2")):
        for linha, onde in ((0, "sup"), (1, "sup_parede"), (3, "inf_parede"), (4, "inf")):
            paineis.append(Painel(f"canto_{lado}_{onde}", f"Canto {lado}", xs[col], ys[linha], xs[col + 1], ys[linha + 1], eh_aba=True))
    for col, lado in ((0, "1"), (4, "2")):
        for linha in ((2,) if com_corte else (0, 1, 2, 3, 4)):
            sufixo = "" if linha == 2 else f"_{linha}"
            paineis.append(Painel(f"aba_lateral_{lado}{sufixo}", f"Aba lateral {lado}", xs[col], ys[linha], xs[col + 1], ys[linha + 1], eh_aba=True))
    return paineis
