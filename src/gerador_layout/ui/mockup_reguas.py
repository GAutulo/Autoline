"""Réguas (topo/esquerda do canvas) + guias arrastáveis — mesmo par de
ferramentas que qualquer editor vetorial de verdade (CorelDRAW,
Illustrator, Photoshop): arrastar a partir da régua de cima solta uma
guia VERTICAL (marca uma posição X); arrastar a partir da régua da
esquerda solta uma guia HORIZONTAL (marca uma posição Y). Guia nasce já
arrastável — a própria régua move ela ao vivo enquanto o botão do mouse
está apertado (ver `mousePressEvent`/`mouseMoveEvent` abaixo), sem
precisar simular arrasto entre dois widgets diferentes.

Guias participam do encaixe (snap, ver `preview_canvas.py::_calcular_snap`)
como mais um tipo de alvo, junto da grade/bordas de outros elementos/face.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QWidget

from .estilo import Cor

_ESPESSURA_REGUA = 22
_EXTENSAO_GUIA_MM = 1_000_000.0  # bem maior que qualquer caixa real — a guia sempre "atravessa" a cena inteira
_COR_GUIA = QColor(0, 172, 163, 200)
_COR_GUIA_SELECIONADA = QColor(0, 206, 196, 255)
_PASSOS_REGUA_MM = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)
_ESPACO_MINIMO_ENTRE_TICKS_PX = 45


class GuiaCanvas(QGraphicsObject):
    """Uma guia — reta "infinita" (bem mais longa que qualquer caixa
    real) travada num eixo só. Igual a qualquer `ElementoMockup` no que
    diz respeito a seleção/remoção (Delete), mas não é um elemento de
    mockup — não aparece na exportação nem no CorelDRAW, é só referência
    visual/de encaixe dentro do app."""

    guia_alterada = Signal()

    def __init__(self, orientacao: str, posicao_mm: float, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._orientacao = orientacao  # "h" (horizontal, trava em Y) ou "v" (vertical, trava em X)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(5000)  # sempre por cima dos elementos de mockup, nunca escondida atrás de um
        cursor = Qt.CursorShape.SizeVerCursor if orientacao == "h" else Qt.CursorShape.SizeHorCursor
        self.setCursor(cursor)
        if orientacao == "h":
            self.setPos(0, posicao_mm)
        else:
            self.setPos(posicao_mm, 0)

    @property
    def orientacao(self) -> str:
        return self._orientacao

    @property
    def posicao(self) -> float:
        return self.pos().y() if self._orientacao == "h" else self.pos().x()

    def boundingRect(self) -> QRectF:
        margem = 1.5  # área de clique um pouco maior que o traço de 1px, mais fácil de selecionar/arrastar
        if self._orientacao == "h":
            return QRectF(-_EXTENSAO_GUIA_MM, -margem, 2 * _EXTENSAO_GUIA_MM, margem * 2)
        return QRectF(-margem, -_EXTENSAO_GUIA_MM, margem * 2, 2 * _EXTENSAO_GUIA_MM)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        cor = _COR_GUIA_SELECIONADA if self.isSelected() else _COR_GUIA
        pen = QPen(cor, 1.4 if self.isSelected() else 1.0, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)  # 1px de tela em qualquer zoom, igual à grade
        painter.setPen(pen)
        if self._orientacao == "h":
            painter.drawLine(QPointF(-_EXTENSAO_GUIA_MM, 0), QPointF(_EXTENSAO_GUIA_MM, 0))
        else:
            painter.drawLine(QPointF(0, -_EXTENSAO_GUIA_MM), QPointF(0, _EXTENSAO_GUIA_MM))

    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Trava no eixo perpendicular ao próprio — uma guia horizontal
            # só sobe/desce (Y muda, X sempre 0), uma vertical só anda pro
            # lado. Arrastar puxando ela na diagonal não faz sentido pra
            # uma reta que representa "uma posição só" num eixo.
            return QPointF(0, value.y()) if self._orientacao == "h" else QPointF(value.x(), 0)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.guia_alterada.emit()
        return super().itemChange(change, value)


def _passo_regua(pixels_por_mm: float) -> float:
    """Maior passo "redondo" (1/2/5/10/20/50mm...) que ainda cabe pelo
    menos `_ESPACO_MINIMO_ENTRE_TICKS_PX` na tela — mesma lógica de
    qualquer régua de CAD: menos ticks quando afastado, mais quando
    aproxima, sempre múltiplo "de gente ler", nunca um valor arbitrário."""
    for passo in _PASSOS_REGUA_MM:
        if passo * pixels_por_mm >= _ESPACO_MINIMO_ENTRE_TICKS_PX:
            return float(passo)
    return float(_PASSOS_REGUA_MM[-1])


class _ReguaBase(QWidget):
    """Comum às duas réguas: desenha ticks/números a partir da transform
    atual do canvas (`canvas.mapToScene`/`mapFromScene`) — nunca guarda
    zoom/posição por conta própria, só espelha o que o canvas já sabe,
    então nunca desalinha."""

    def __init__(self, canvas, orientacao: str, parent=None) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self._orientacao = orientacao
        self._guia_em_arrasto: GuiaCanvas | None = None
        # Régua "h" fica deitada no topo (fina em altura, comprida em
        # largura) e solta guia VERTICAL — arrastar dela é um gesto
        # horizontal, daí o cursor `SizeHorCursor`. Régua "v" é o
        # espelho disso, em pé na esquerda.
        self.setCursor(Qt.CursorShape.SizeHorCursor if orientacao == "h" else Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Arraste pra criar uma guia" if canvas is not None else "")
        if orientacao == "h":
            self.setFixedHeight(_ESPESSURA_REGUA)
        else:
            self.setFixedWidth(_ESPESSURA_REGUA)
        canvas.zoom_alterado.connect(lambda _z: self.update())
        canvas.horizontalScrollBar().valueChanged.connect(lambda _v: self.update())
        canvas.verticalScrollBar().valueChanged.connect(lambda _v: self.update())

    # ── Pintura ──────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(Cor.CARTAO))
        pen = QPen(QColor(Cor.TEXTO_TERCIARIO))
        painter.setPen(pen)
        painter.setFont(self.font())
        metrica = QFontMetrics(self.font())

        if self._orientacao == "h":
            p0 = self._canvas.mapToScene(QPoint(0, 0)).x()
            p1 = self._canvas.mapToScene(QPoint(self.width(), 0)).x()
        else:
            p0 = self._canvas.mapToScene(QPoint(0, 0)).y()
            p1 = self._canvas.mapToScene(QPoint(0, self.height())).y()
        if p1 == p0:
            return
        pixels_por_mm = (self.width() if self._orientacao == "h" else self.height()) / (p1 - p0)
        passo = _passo_regua(abs(pixels_por_mm))

        inicio = math.floor(min(p0, p1) / passo) * passo
        valor = inicio
        while valor <= max(p0, p1):
            if self._orientacao == "h":
                px = self._canvas.mapFromScene(QPointF(valor, 0)).x()
                painter.drawLine(px, self.height() - 7, px, self.height())
                texto = f"{valor:g}"
                painter.drawText(px + 3, self.height() - 8, texto)
            else:
                py = self._canvas.mapFromScene(QPointF(0, valor)).y()
                painter.drawLine(self.width() - 7, py, self.width(), py)
                texto = f"{valor:g}"
                # Texto vertical: gira -90° em torno do próprio ponto —
                # mesmo truque de qualquer régua vertical de CAD, senão os
                # números não cabem na faixa estreita.
                painter.save()
                painter.translate(self.width() - 9, py - 3)
                painter.rotate(-90)
                painter.drawText(0, 0, texto)
                painter.restore()
            valor += passo

        # Linha fina separando a régua do canvas — mesmo espírito do
        # `border-bottom`/`border-right` que o resto do app usa em barra.
        painter.setPen(QPen(QColor(Cor.BORDA)))
        if self._orientacao == "h":
            painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

    # ── Arrastar pra criar/mover uma guia ──────────────────────────────
    def _posicao_mm(self, pos_widget) -> float:
        if self._orientacao == "h":
            return self._canvas.mapToScene(QPoint(int(pos_widget.x()), 0)).x()
        return self._canvas.mapToScene(QPoint(0, int(pos_widget.y()))).y()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # Guia é um conceito do modo Layout (mockup) — na tela Dieline a
        # régua ainda serve de referência visual de escala, mas não faz
        # sentido criar uma guia que não vai ser usada pra nada lá.
        if not self._canvas.modo_mockup:
            return
        orientacao_guia = "v" if self._orientacao == "h" else "h"
        posicao = self._posicao_mm(event.position())
        for it in self._canvas.cena.selectedItems():
            it.setSelected(False)
        guia = self._canvas.adicionar_guia(orientacao_guia, posicao)
        guia.setSelected(True)
        self._guia_em_arrasto = guia
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._guia_em_arrasto is None:
            return
        posicao = self._posicao_mm(event.position())
        if self._guia_em_arrasto.orientacao == "h":
            self._guia_em_arrasto.setPos(0, posicao)
        else:
            self._guia_em_arrasto.setPos(posicao, 0)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._guia_em_arrasto = None
        event.accept()


class ReguaHorizontal(_ReguaBase):
    def __init__(self, canvas, parent=None) -> None:
        super().__init__(canvas, "h", parent)


class ReguaVertical(_ReguaBase):
    def __init__(self, canvas, parent=None) -> None:
        super().__init__(canvas, "v", parent)
