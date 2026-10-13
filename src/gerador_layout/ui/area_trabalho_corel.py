"""Peças da área de trabalho no estilo CorelDRAW (ver REFERENCIA_CORELDRAW.md,
seção 1): botão de ferramenta com *flyout*, paleta de cores vertical e o
painel da barra de status (posição do cursor, objeto selecionado e
amostras de preenchimento/contorno).

Só o comportamento e a disposição seguem o CorelDRAW — os ícones e o
desenho dos controles são do Autoline.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QToolButton, QVBoxLayout, QWidget

from .estilo import FONTE_MONO, Cor

_TAMANHO_AMOSTRA = 18


class BotaoFlyout(QToolButton):
    """Botão da caixa de ferramentas que agrupa ferramentas irmãs, como os
    *flyouts* do CorelDRAW: clicar usa a ferramenta mostrada; segurar o
    clique (ou clicar no triângulo do canto) abre as outras, e a escolhida
    passa a ser a mostrada no botão."""

    def __init__(self, acoes: list[QAction], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._acoes = list(acoes)
        self.setDefaultAction(self._acoes[0])
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setAutoRaise(True)
        if len(self._acoes) > 1:
            menu = QMenu(self)
            for acao in self._acoes:
                menu.addAction(acao)
            menu.triggered.connect(self.mostrar)
            self.setMenu(menu)
            self.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)

    @property
    def acoes(self) -> list[QAction]:
        return list(self._acoes)

    def mostrar(self, acao: QAction) -> None:
        """Passa `acao` a ser a ferramenta visível no botão."""
        if acao in self._acoes and self.defaultAction() is not acao:
            self.setDefaultAction(acao)

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        # Clique no triângulo do canto abre o flyout na hora.
        if len(self._acoes) > 1 and evento.position().x() > self.width() - 10 and evento.position().y() > self.height() - 10:
            self.showMenu()
            return
        super().mousePressEvent(evento)

    def paintEvent(self, evento) -> None:  # noqa: N802
        super().paintEvent(evento)
        if len(self._acoes) <= 1:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Cor.TEXTO_SECUNDARIO))
        w, h = self.width(), self.height()
        p.drawPolygon(QPolygonF([QPointF(w - 3, h - 8), QPointF(w - 3, h - 3), QPointF(w - 8, h - 3)]))
        p.end()


class _Amostra(QToolButton):
    """Quadradinho de cor da paleta. Clique esquerdo e direito viram sinais
    separados (preenchimento e contorno, como no CorelDRAW)."""

    clique_esquerdo = Signal()
    clique_direito = Signal()

    def __init__(self, rgb: tuple[int, int, int] | None, dica: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rgb = rgb
        self.setToolTip(dica)
        self.setFixedSize(QSize(_TAMANHO_AMOSTRA + 4, _TAMANHO_AMOSTRA + 4))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.RightButton:
            self.clique_direito.emit()
        elif evento.button() == Qt.MouseButton.LeftButton:
            self.clique_esquerdo.emit()

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(2, 2, -3, -3)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        if self._rgb is None:
            p.setBrush(QColor(255, 255, 255))
            p.drawRect(r)
            p.setPen(QPen(QColor(0, 0, 0), 1.4))
            p.drawLine(r.topLeft(), r.bottomRight())
            p.drawLine(r.topRight(), r.bottomLeft())
        else:
            p.setBrush(QColor(*self._rgb))
            p.drawRect(r)
        p.end()


class PaletaCores(QWidget):
    """Paleta vertical da borda direita. Clique esquerdo = preenchimento,
    clique direito = contorno; o quadrado com X = nenhum. Os sinais levam
    `(nome, rgb)` ou `None` pro X."""

    preenchimento_escolhido = Signal(object)
    contorno_escolhido = Signal(object)

    def __init__(self, cores: list[tuple[str, tuple[int, int, int]]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(2, 4, 2, 4)
        vbox.setSpacing(2)
        nenhuma = _Amostra(None, "Nenhum — esquerdo tira o preenchimento")
        nenhuma.clique_esquerdo.connect(lambda: self.preenchimento_escolhido.emit(None))
        nenhuma.clique_direito.connect(lambda: self.contorno_escolhido.emit(None))
        vbox.addWidget(nenhuma)
        for nome, rgb in cores:
            amostra = _Amostra(rgb, f"{nome} — clique: preenchimento · botão direito: contorno")
            amostra.clique_esquerdo.connect(lambda n=nome, c=rgb: self.preenchimento_escolhido.emit((n, c)))
            amostra.clique_direito.connect(lambda n=nome, c=rgb: self.contorno_escolhido.emit((n, c)))
            vbox.addWidget(amostra)
        vbox.addStretch(1)


class _AmostraStatus(QWidget):
    """Amostra de preenchimento (quadrado cheio) ou contorno (moldura) da
    barra de status."""

    def __init__(self, contorno: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._contorno = contorno
        self._cor: QColor | None = None
        self.setFixedSize(_TAMANHO_AMOSTRA, _TAMANHO_AMOSTRA)

    def definir_cor(self, cor: QColor | None) -> None:
        self._cor = cor
        self.update()

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -2, -2)
        if self._cor is None:
            p.setPen(QPen(QColor(Cor.TEXTO_TERCIARIO), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
            p.drawLine(r.topLeft(), r.bottomRight())
        elif self._contorno:
            p.setPen(QPen(self._cor, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(1, 1, -1, -1))
        else:
            p.setPen(QPen(QColor(0, 0, 0, 90), 1))
            p.setBrush(self._cor)
            p.drawRect(r)
        p.end()


class PainelStatus(QWidget):
    """Lado permanente da barra de status: posição do cursor em mm, o que
    está selecionado e as amostras de preenchimento/contorno."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rotulo_posicao = QLabel("")
        self.rotulo_posicao.setStyleSheet(f'font-family: "{FONTE_MONO}"; color: {Cor.TEXTO_SECUNDARIO};')
        self.rotulo_posicao.setMinimumWidth(170)
        self.rotulo_objeto = QLabel("")
        self.rotulo_objeto.setMinimumWidth(220)
        self.amostra_preenchimento = _AmostraStatus(contorno=False)
        self.amostra_preenchimento.setToolTip("Preenchimento do objeto selecionado")
        self.amostra_contorno = _AmostraStatus(contorno=True)
        self.amostra_contorno.setToolTip("Contorno do objeto selecionado")

        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 8, 0)
        hbox.setSpacing(10)
        hbox.addWidget(self.rotulo_posicao)
        hbox.addWidget(self.rotulo_objeto)
        hbox.addWidget(self.amostra_preenchimento)
        hbox.addWidget(self.amostra_contorno)

    def definir_posicao(self, ponto: QPointF | None) -> None:
        if ponto is None:
            self.rotulo_posicao.setText("")
            return
        self.rotulo_posicao.setText(f"X {ponto.x():8.1f}   Y {ponto.y():8.1f} mm".replace(".", ","))

    def definir_objeto(self, descricao: str, preenchimento: QColor | None, contorno: QColor | None, mostrar_amostras: bool) -> None:
        self.rotulo_objeto.setText(descricao)
        self.amostra_preenchimento.setVisible(mostrar_amostras)
        self.amostra_contorno.setVisible(mostrar_amostras)
        self.amostra_preenchimento.definir_cor(preenchimento)
        self.amostra_contorno.definir_cor(contorno)
