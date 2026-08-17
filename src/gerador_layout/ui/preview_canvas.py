"""Canvas 2D nativo do layout — substitui a necessidade de abrir o
CorelDRAW (ou qualquer outro programa externo) só para conferir o desenho.

Usa QGraphicsView/QGraphicsScene, que já resolve zoom e pan de graça e é
o jeito padrão de fazer canvas técnico (estilo CAD) em Qt.

As cores usadas aqui são só para leitura em tela — a exportação real
(fase futura, PDF/SVG) sai tudo em preto, com o tipo de linha (contínua/
tracejada) indicando corte ou vinco, como no sistema original.
"""

from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from ..models import LayoutCaixa, TipoLinha

_ESTILO_POR_TIPO: dict[TipoLinha, tuple[QColor, Qt.PenStyle, float]] = {
    TipoLinha.CORTE: (QColor(20, 20, 25), Qt.PenStyle.SolidLine, 0.6),
    TipoLinha.VINCO: (QColor(40, 100, 220), Qt.PenStyle.DashLine, 0.5),
    TipoLinha.CORTE_SERRA: (QColor(230, 110, 20), Qt.PenStyle.DashDotLine, 0.5),
    TipoLinha.MEIO_CORTE: (QColor(30, 160, 90), Qt.PenStyle.DotLine, 0.5),
    TipoLinha.DOBRA: (QColor(150, 150, 160), Qt.PenStyle.DotLine, 0.4),
}

_NOME_TIPO: dict[TipoLinha, str] = {
    TipoLinha.CORTE: "Corte",
    TipoLinha.VINCO: "Vinco",
    TipoLinha.CORTE_SERRA: "Corte-serra",
    TipoLinha.MEIO_CORTE: "Meio-corte",
}

_ZOOM_MINIMO = 0.05
_ZOOM_MAXIMO = 40.0


class PreviewCanvas(QGraphicsView):
    """Área de desenho do layout com zoom (roda do mouse) e pan (arrastar)."""

    zoom_alterado = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor(250, 250, 255)))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

        self._zoom_atual = 1.0
        self._layout: LayoutCaixa | None = None

    # ── API pública ─────────────────────────────────────────────────
    @property
    def zoom_atual(self) -> float:
        return self._zoom_atual

    def definir_layout(self, layout: LayoutCaixa | None) -> None:
        self._layout = layout
        self._redesenhar()
        self.ajustar_a_tela()

    def ajustar_a_tela(self) -> None:
        if not self._scene.items():
            return
        self.resetTransform()
        self._zoom_atual = 1.0
        margem = 20
        rect = self._scene.itemsBoundingRect().adjusted(-margem, -margem, margem, margem)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_atual = self.transform().m11()
        self.zoom_alterado.emit(self._zoom_atual)

    # ── Zoom com a roda do mouse ───────────────────────────────────
    def wheelEvent(self, event) -> None:  # noqa: N802 (nome exigido pelo Qt)
        fator = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        novo_zoom = self._zoom_atual * fator
        if not (_ZOOM_MINIMO <= novo_zoom <= _ZOOM_MAXIMO):
            return
        self.scale(fator, fator)
        self._zoom_atual = novo_zoom
        self.zoom_alterado.emit(self._zoom_atual)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)
        self.ajustar_a_tela()

    # ── Desenho ─────────────────────────────────────────────────────
    def _redesenhar(self) -> None:
        self._scene.clear()

        if self._layout is None or not self._layout.linhas:
            texto = QGraphicsSimpleTextItem("Informe as medidas para gerar a pré-visualização.")
            texto.setBrush(QBrush(QColor(150, 150, 160)))
            fonte = QFont("Segoe UI", 10)
            fonte.setItalic(True)
            texto.setFont(fonte)
            self._scene.addItem(texto)
            return

        self._desenhar_linhas_tecnicas()
        self._desenhar_cota()
        self._desenhar_legenda_cores()
        self._desenhar_legenda_tipos_de_linha()

    def _desenhar_linhas_tecnicas(self) -> None:
        assert self._layout is not None
        for linha in self._layout.linhas:
            cor, estilo, largura = _ESTILO_POR_TIPO.get(
                linha.tipo, (QColor(0, 0, 0), Qt.PenStyle.SolidLine, 0.5)
            )
            pen = QPen(cor, largura, estilo)
            pen.setCosmetic(True)  # espessura constante independente do zoom
            item = QGraphicsLineItem(QLineF(linha.x1, linha.y1, linha.x2, linha.y2))
            item.setPen(pen)
            self._scene.addItem(item)

    def _desenhar_cota(self) -> None:
        assert self._layout is not None
        texto = f"{self._layout.largura_total:.1f} × {self._layout.altura_total:.1f} mm"
        item = QGraphicsSimpleTextItem(texto)
        item.setBrush(QBrush(QColor(70, 70, 80)))
        fonte = QFont("Segoe UI", 10, QFont.Weight.Bold)
        item.setFont(fonte)
        item.setPos(0, self._layout.altura_total + 6)
        self._scene.addItem(item)

    def _desenhar_legenda_cores(self) -> None:
        assert self._layout is not None
        if not self._layout.cores_legenda:
            return

        x = 0.0
        y = -18.0
        fonte_titulo = QFont("Segoe UI", 8, QFont.Weight.Bold)
        fonte_item = QFont("Segoe UI", 8)

        titulo = QGraphicsSimpleTextItem("CORES:")
        titulo.setFont(fonte_titulo)
        titulo.setBrush(QBrush(QColor(60, 60, 70)))
        titulo.setPos(x, y)
        self._scene.addItem(titulo)
        x += 26

        for cor in self._layout.cores_legenda:
            bolinha = QGraphicsEllipseItem(QRectF(x, y + 2, 6, 6))
            bolinha.setBrush(QBrush(QColor(cor.r, cor.g, cor.b)))
            bolinha.setPen(QPen(QColor(120, 120, 120), 0.3))
            self._scene.addItem(bolinha)
            x += 9

            item = QGraphicsSimpleTextItem(cor.nome)
            item.setFont(fonte_item)
            item.setBrush(QBrush(QColor(60, 60, 70)))
            item.setPos(x, y)
            self._scene.addItem(item)
            x += len(cor.nome) * 4.2 + 10

    def _desenhar_legenda_tipos_de_linha(self) -> None:
        assert self._layout is not None
        fonte = QFont("Segoe UI", 7.5)
        largura_total = self._layout.largura_total
        y = -18.0

        for tipo, nome in _NOME_TIPO.items():
            cor, estilo, largura = _ESTILO_POR_TIPO[tipo]
            x = largura_total - 90
            pen = QPen(cor, largura, estilo)
            pen.setCosmetic(True)
            linha = QGraphicsLineItem(QLineF(x, y + 4, x + 16, y + 4))
            linha.setPen(pen)
            self._scene.addItem(linha)

            texto = QGraphicsSimpleTextItem(nome)
            texto.setFont(fonte)
            texto.setBrush(QBrush(QColor(90, 90, 100)))
            texto.setPos(x + 20, y)
            self._scene.addItem(texto)
            y += 11
