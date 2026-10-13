"""Modelagem do CorelDRAW (Objeto > Modelar): Soldar, Aparar, Interseção,
Frente menos atrás e Atrás menos frente — ver REFERENCIA_CORELDRAW.md.

Funções puras sobre `QPainterPath` (coordenadas da cena). Quem decide
quais objetos entram e quem vira o resultado é o canvas
(`PreviewCanvas.modelar_selecionados`).

As operações booleanas do Qt devolvem os trechos curvos já achatados em
segmentos retos curtos (desvio da curva original de centésimos de
milímetro, invisível e irrelevante pra impressão); `_limpar_colineares`
tira os nós que sobram no meio de trechos retos.
"""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QPainterPath

OPERACOES = {
    "soldar": "Soldar",
    "aparar": "Aparar",
    "intersecao": "Interseção",
    "frente_menos_atras": "Frente menos atrás",
    "atras_menos_frente": "Atrás menos frente",
}

_TOLERANCIA_COLINEAR_MM = 0.005


def _preparar(caminho: QPainterPath) -> QPainterPath:
    copia = QPainterPath(caminho)
    copia.setFillRule(Qt.FillRule.WindingFill)
    return copia.simplified()


def _limpar_colineares(caminho: QPainterPath) -> QPainterPath:
    """Remove pontos que estão (praticamente) na reta entre os vizinhos."""
    limpo = QPainterPath()
    limpo.setFillRule(Qt.FillRule.OddEvenFill)
    for poligono in caminho.toSubpathPolygons():
        pontos = [poligono.at(i) for i in range(poligono.count())]
        fechado = len(pontos) > 2 and QLineF(pontos[0], pontos[-1]).length() < 1e-6
        if fechado:
            pontos = pontos[:-1]
        mudou = True
        while mudou and len(pontos) > 3:
            mudou = False
            for i in range(len(pontos)):
                if not fechado and (i == 0 or i == len(pontos) - 1):
                    continue
                a, p, b = pontos[i - 1], pontos[i], pontos[(i + 1) % len(pontos)]
                base = QLineF(a, b).length()
                if base < 1e-9:
                    continue
                distancia = abs((b.x() - a.x()) * (a.y() - p.y()) - (a.x() - p.x()) * (b.y() - a.y())) / base
                if distancia < _TOLERANCIA_COLINEAR_MM:
                    del pontos[i]
                    mudou = True
                    break
        if len(pontos) < 2:
            continue
        limpo.moveTo(pontos[0])
        for q in pontos[1:]:
            limpo.lineTo(q)
        if fechado:
            limpo.closeSubpath()
    return limpo


def modelar(operacao: str, caminhos_de_baixo_pra_cima: list[QPainterPath]) -> QPainterPath:
    """Resultado de `operacao` sobre os caminhos, na ordem da pilha (o 1º é
    o de baixo, o "alvo" do CorelDRAW quando a seleção é por área)."""
    caminhos = [_preparar(c) for c in caminhos_de_baixo_pra_cima]
    if len(caminhos) < 2:
        raise ValueError("modelar precisa de pelo menos 2 objetos")
    baixo, cima = caminhos[0], caminhos[-1]
    if operacao == "soldar":
        resultado = caminhos[0]
        for c in caminhos[1:]:
            resultado = resultado.united(c)
    elif operacao in ("aparar", "atras_menos_frente"):
        resultado = baixo
        for c in caminhos[1:]:
            resultado = resultado.subtracted(c)
    elif operacao == "intersecao":
        resultado = caminhos[0]
        for c in caminhos[1:]:
            resultado = resultado.intersected(c)
    elif operacao == "frente_menos_atras":
        resultado = cima
        for c in caminhos[:-1]:
            resultado = resultado.subtracted(c)
    else:
        raise ValueError(f"operação desconhecida: {operacao}")
    return _limpar_colineares(resultado)


def objetos_afetados(operacao: str, quantidade: int) -> tuple[list[int], int]:
    """(índices removidos, índice de quem empresta a aparência) — índices na
    ordem de baixo pra cima. Segue o CorelDRAW: Aparar e Interseção mantêm
    os objetos de origem; as outras substituem todos."""
    todos = list(range(quantidade))
    if operacao == "aparar":
        return [0], 0
    if operacao == "intersecao":
        return [], 0
    if operacao == "frente_menos_atras":
        return todos, quantidade - 1
    return todos, 0
