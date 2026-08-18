"""Canvas 2D nativo do layout — substitui a necessidade de abrir o
CorelDRAW (ou qualquer outro programa externo) só para conferir o desenho.

Usa QGraphicsView/QGraphicsScene, que já resolve zoom e pan de graça e é
o jeito padrão de fazer canvas técnico (estilo CAD) em Qt.

A cota de dimensões é desenhada como um painel HTML flutuante por cima do
canvas (não faz parte da cena/zoom) — assim o texto tem sempre o mesmo
tamanho em tela, não importa o quão pequena ou grande seja a caixa, e
nunca mais "explode" de tamanho numa caixa minúscula.

A legenda de cores é um widget à parte (`PainelLegendaCores`, ver mais
abaixo), montado por fora do canvas em `main_window.py` — assim ela nunca
sobrepõe o desenho, ao contrário do painel de dimensão (que é pequeno e
fica num canto, sem esse problema).

As cores usadas aqui são só para leitura em tela — a exportação real sai
tudo em preto, com o tipo de linha (contínua/tracejada) indicando corte
ou vinco, como no sistema original.
"""

from __future__ import annotations

from PySide6.QtCore import QLineF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ..models import CorImpressao, LayoutCaixa, TipoLinha

_ESTILO_POR_TIPO: dict[TipoLinha, tuple[QColor, Qt.PenStyle, float]] = {
    TipoLinha.CORTE: (QColor(20, 20, 25), Qt.PenStyle.SolidLine, 0.6),
    TipoLinha.VINCO: (QColor(40, 100, 220), Qt.PenStyle.DashLine, 0.5),
    TipoLinha.CORTE_SERRA: (QColor(230, 110, 20), Qt.PenStyle.DashDotLine, 0.5),
    TipoLinha.MEIO_CORTE: (QColor(30, 160, 90), Qt.PenStyle.DotLine, 0.5),
    TipoLinha.DOBRA: (QColor(150, 150, 160), Qt.PenStyle.DotLine, 0.4),
}

_ZOOM_MINIMO = 0.05
_ZOOM_MAXIMO = 40.0

_ESTILO_PAINEL = (
    "background: rgba(250, 250, 255, 235);"
    "border: 1px solid rgba(0, 0, 0, 30);"
    "border-radius: 4px;"
    "padding: 4px 8px;"
    "font-size: 12px;"
)


def _cor_texto_legivel(r: int, g: int, b: int) -> QColor:
    """Usa a própria cor no texto (pedido do usuário: "vermelho" escrito em
    vermelho), mas escurece cores muito claras (ex.: amarelo) o mínimo
    necessário pra continuar legível sobre o fundo claro do canvas."""
    luminancia = 0.299 * r + 0.587 * g + 0.114 * b
    if luminancia > 200:
        fator = 0.65
        return QColor(int(r * fator), int(g * fator), int(b * fator))
    return QColor(r, g, b)


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

        # Painel fixo (HUD) por cima da cena — não escala com o zoom, então
        # nunca "explode" de tamanho numa caixa pequena.
        self._painel_dimensao = QLabel(self)
        self._painel_dimensao.setStyleSheet(
            _ESTILO_PAINEL + "color: #46505a; font-weight: 700; font-size: 13px;"
        )
        self._painel_dimensao.hide()

    # ── API pública ─────────────────────────────────────────────────
    @property
    def zoom_atual(self) -> float:
        return self._zoom_atual

    @property
    def cena(self) -> QGraphicsScene:
        """Exposto para o exportador (SVG/PDF/JPG) renderizar a cena."""
        return self._scene

    @property
    def layout_atual(self) -> LayoutCaixa | None:
        return self._layout

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

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reposicionar_paineis()

    # ── Painel fixo (HUD) ───────────────────────────────────────────
    def _reposicionar_paineis(self) -> None:
        margem = 8
        if self._painel_dimensao.isVisible():
            self._painel_dimensao.adjustSize()
            self._painel_dimensao.move(margem, self.height() - self._painel_dimensao.height() - margem)

    def _atualizar_painel_dimensao(self) -> None:
        assert self._layout is not None
        self._painel_dimensao.setText(
            f"{self._layout.largura_total:.1f} × {self._layout.altura_total:.1f} mm"
        )
        self._painel_dimensao.show()

    # ── Desenho ─────────────────────────────────────────────────────
    def _redesenhar(self) -> None:
        self._scene.clear()

        if self._layout is None or not self._layout.linhas:
            texto = QGraphicsSimpleTextItem("Informe as medidas para gerar a pré-visualização.")
            texto.setBrush(QBrush(QColor(150, 150, 160)))
            self._scene.addItem(texto)
            self._painel_dimensao.hide()
            return

        self._desenhar_linhas_tecnicas()
        self._atualizar_painel_dimensao()
        self._reposicionar_paineis()

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


class PainelLegendaCores(QWidget):
    """Legenda de cores de impressão, numa linha reta de widgets reais
    (bolinha + nome lado a lado, sem quebra) — colocada acima do canvas
    pelo `main_window.py`, fora da área de desenho, pra nunca sobrepor o
    layout."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 6)
        self._layout.setSpacing(16)
        self.hide()

    def definir_cores(self, cores: list[CorImpressao]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not cores:
            self.hide()
            return

        titulo = QLabel("CORES:")
        titulo.setStyleSheet("font-weight: 700; color: #333; font-size: 12px;")
        self._layout.addWidget(titulo)

        for cor in cores:
            self._layout.addWidget(self._criar_item(cor))

        self._layout.addStretch(1)
        self.show()

    def _criar_item(self, cor: CorImpressao) -> QWidget:
        item = QWidget()
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)

        bolinha = QLabel()
        bolinha.setFixedSize(10, 10)
        bolinha.setStyleSheet(
            f"background: rgb({cor.r},{cor.g},{cor.b}); border-radius: 5px; "
            "border: 1px solid rgba(0, 0, 0, 60);"
        )
        item_layout.addWidget(bolinha)

        cor_legivel = _cor_texto_legivel(cor.r, cor.g, cor.b)
        nome = QLabel(cor.nome)
        nome.setStyleSheet(
            f"color: rgb({cor_legivel.red()},{cor_legivel.green()},{cor_legivel.blue()}); "
            "font-weight: 600; font-size: 12px;"
        )
        item_layout.addWidget(nome)

        return item
