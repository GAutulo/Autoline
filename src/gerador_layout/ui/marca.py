"""Logotipo do Autoline — opção 3 "Dobra" (REDESIGN.md, seção 3).

O símbolo é o A formado por duas faces dobradas de uma caixa: a de dentro
clara, a de fora âmbar (kraft), com a travessa tracejada como um vinco. Em
tamanho pequeno (abaixo de 64 px) o tracejado some e a travessa vira um
traço cheio, mais grosso, pra continuar legível.

Desenhado com QPainter a partir das mesmas coordenadas do SVG de
referência (viewBox 0 0 120 120) — sai nítido em qualquer tamanho e
escala de tela, sem depender de arquivo.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

# SVG de referência (o mesmo do REDESIGN.md), pra documentação e quem
# precisar do arquivo (ex.: impressos).
SIMBOLO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
  <polygon points="12,106 48,14 60,14 60,44 34,106" fill="#E7E9EB"/>
  <polygon points="108,106 72,14 60,14 60,44 86,106" fill="#F0A04B"/>
  <line x1="45" y1="80" x2="75" y2="80" stroke="#E7E9EB" stroke-width="7" stroke-dasharray="8 3"/>
</svg>"""

_FACE_ESQUERDA = ((12, 106), (48, 14), (60, 14), (60, 44), (34, 106))
_FACE_DIREITA = ((108, 106), (72, 14), (60, 14), (60, 44), (86, 106))

# (face esquerda / travessa, face direita): escuro = tela; claro = impressos.
_CORES_ESCURO = ("#E7E9EB", "#F0A04B")
_CORES_CLARO = ("#15181B", "#B4630F")

TAMANHO_SIMPLIFICADO = 64  # abaixo disso a travessa vira traço cheio


def desenhar_simbolo(p: QPainter, area: QRectF, claro: bool = False, lado_px: float | None = None) -> None:
    """O símbolo dentro de `area` (quadrado, centralizado). `lado_px` = o
    tamanho real em pixels na tela (decide a versão simplificada); por
    padrão, o lado da área."""
    clara, ambar = _CORES_CLARO if claro else _CORES_ESCURO
    lado = min(area.width(), area.height())
    lado_px = lado if lado_px is None else lado_px
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(area.center().x() - lado / 2, area.center().y() - lado / 2)
    p.scale(lado / 120.0, lado / 120.0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(clara))
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in _FACE_ESQUERDA]))
    p.setBrush(QColor(ambar))
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in _FACE_DIREITA]))
    if lado_px >= TAMANHO_SIMPLIFICADO:
        caneta = QPen(QColor(clara), 7.0)
        caneta.setCapStyle(Qt.PenCapStyle.FlatCap)
        caneta.setDashPattern([8 / 7, 3 / 7])  # "8 3" do SVG, em unidades da espessura
        p.setPen(caneta)
        p.drawLine(QPointF(45, 80), QPointF(75, 80))
    else:
        # 9 a 12 de espessura: quanto menor o ícone, mais grossa.
        espessura = 12.0 if lado_px <= 20 else (10.0 if lado_px <= 40 else 9.0)
        caneta = QPen(QColor(clara), espessura)
        caneta.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(caneta)
        p.drawLine(QPointF(44, 80), QPointF(76, 80))
    p.restore()


def pixmap_simbolo(lado: int, claro: bool = False, razao_pixels: float = 1.0) -> QPixmap:
    """O símbolo num pixmap transparente de `lado` × `lado` (pontos lógicos)."""
    reais = max(1, round(lado * razao_pixels))
    pixmap = QPixmap(reais, reais)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    desenhar_simbolo(p, QRectF(0, 0, reais, reais), claro, lado_px=reais)
    p.end()
    pixmap.setDevicePixelRatio(razao_pixels)
    return pixmap


def fonte_marca(tamanho_px: float) -> QFont:
    """Archivo 700, semi-expandida (eixo de largura 112) — marca e títulos de tela."""
    fonte = QFont("Archivo")
    fonte.setPixelSize(max(1, round(tamanho_px)))
    fonte.setWeight(QFont.Weight.Bold)
    if hasattr(fonte, "setVariableAxis"):
        fonte.setVariableAxis(QFont.Tag("wdth"), 112.0)
    else:  # Qt antigo: a instância mais próxima
        fonte.setStretch(112)
    fonte.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 98.5)  # -0,015em, como na referência
    return fonte


class AssinaturaMarca(QWidget):
    """Símbolo + "autoline" em caixa baixa. `so_simbolo` pra barra de título."""

    def __init__(self, altura: int = 28, so_simbolo: bool = False, claro: bool | None = None, parent=None) -> None:
        super().__init__(parent)
        self._altura = altura
        self._so_simbolo = so_simbolo
        if claro is None:  # na tela: a versão clara (face escura) no tema claro
            from . import configuracoes

            claro = configuracoes.tema() == configuracoes.TEMA_CLARO
        self._claro = claro
        self._fonte = fonte_marca(altura * 0.78)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip("Autoline")
        self.setAccessibleName("Autoline")

    def _largura_texto(self) -> float:
        return 0.0 if self._so_simbolo else QFontMetricsF(self._fonte).horizontalAdvance("autoline")

    def sizeHint(self) -> QSize:  # noqa: N802
        espaco = 0 if self._so_simbolo else round(self._altura * 0.27)
        return QSize(self._altura + espaco + round(self._largura_texto()) + 2, self._altura)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        y = (self.height() - self._altura) / 2
        desenhar_simbolo(
            p, QRectF(0, y, self._altura, self._altura), self._claro, lado_px=self._altura * self.devicePixelRatioF()
        )
        if not self._so_simbolo:
            p.setFont(self._fonte)
            # Impresso: o preto da versão clara; na tela, a cor de texto do tema.
            p.setPen(QColor(_CORES_CLARO[0]) if self._claro else self.palette().windowText().color())
            metrica = QFontMetricsF(self._fonte)
            base = y + (self._altura + metrica.capHeight()) / 2
            p.drawText(QPointF(self._altura + self._altura * 0.27, base), "autoline")
        p.end()
