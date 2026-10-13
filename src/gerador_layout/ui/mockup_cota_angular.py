"""Cota angular (CorelDRAW): mede o ângulo entre dois braços que saem de
um vértice — ver REFERENCIA_CORELDRAW.md.

Três cliques: vértice, um ponto no 1º braço, um ponto no 2º braço. Fica
no desenho como as outras cotas (`mockup_cota.py`) e sai na exportação.

Os três pontos ficam em coordenadas "base" dentro do elemento; a pintura
escala da base pro tamanho atual. Por isso, se a cota for esticada pelas
alças, os braços mudam de direção e o valor em graus acompanha — mesma
ideia da cota linear, em que a largura é a medida.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

_ALTURA_TEXTO_PADRAO_MM = 3.5
_TRACO_MM = 0.25
_SETA_MM = 2.5
_TAMANHO_FONTE_REFERENCIA = 100.0
_FOLGA_MM = 2.0


def _angulo_graus(v: QPointF) -> float:
    """Ângulo de `v` em graus, no sentido anti-horário da TELA (y pra baixo)."""
    return math.degrees(math.atan2(-v.y(), v.x()))


def _ponto_no_arco(centro: QPointF, raio: float, graus: float) -> QPointF:
    r = math.radians(graus)
    return QPointF(centro.x() + raio * math.cos(r), centro.y() - raio * math.sin(r))


def geometria_arco(v: QPointF, a: QPointF, b: QPointF) -> tuple[float, float]:
    """(ângulo inicial, varredura) do arco do menor ângulo entre VA e VB,
    em graus — varredura sempre entre 0 e 180."""
    inicio = _angulo_graus(a - v)
    varredura = (_angulo_graus(b - v) - inicio) % 360.0
    if varredura > 180.0:
        inicio, varredura = _angulo_graus(b - v), 360.0 - varredura
    return inicio, varredura


class ElementoCotaAngular(ElementoMockup):
    _largura_minima_mm = 1.0
    _altura_minima_mm = 1.0

    def __init__(
        self,
        vertice: QPointF,
        ponto_a: QPointF,
        ponto_b: QPointF,
        raio: float | None = None,
        cor_tinta: CorImpressao | None = None,
        altura_texto: float = _ALTURA_TEXTO_PADRAO_MM,
        parent=None,
    ) -> None:
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._altura_texto = max(0.5, altura_texto)
        braco = min(math.hypot(*(ponto_a - vertice).toTuple()), math.hypot(*(ponto_b - vertice).toTuple()))
        self._raio = raio if raio is not None else max(6.0, braco * 0.5)
        # Recebe os pontos na cena; guarda relativos ao canto da caixa (base).
        self._v, self._a, self._b = QPointF(vertice), QPointF(ponto_a), QPointF(ponto_b)
        caixa = self._caixa(self._v, self._a, self._b)
        self._v, self._a, self._b = (q - caixa.topLeft() for q in (self._v, self._a, self._b))
        self._base_l, self._base_a = max(caixa.width(), 1.0), max(caixa.height(), 1.0)
        self._origem_cena = caixa.topLeft()
        super().__init__(largura=self._base_l, altura=self._base_a, parent=parent)

    # ── Geometria ───────────────────────────────────────────────────
    def _caixa(self, v: QPointF, a: QPointF, b: QPointF) -> QRectF:
        inicio, varredura = geometria_arco(v, a, b)
        pontos = [v, a, b]
        for i in range(9):
            pontos.append(_ponto_no_arco(v, self._raio, inicio + varredura * i / 8))
        texto = self._retangulo_texto(v, inicio, varredura)
        pontos.extend((texto.topLeft(), texto.bottomRight()))
        xs = [p.x() for p in pontos]
        ys = [p.y() for p in pontos]
        return QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys))).adjusted(-_FOLGA_MM, -_FOLGA_MM, _FOLGA_MM, _FOLGA_MM)

    def _retangulo_texto(self, v: QPointF, inicio: float, varredura: float) -> QRectF:
        meio = _ponto_no_arco(v, self._raio + self._altura_texto * 1.4, inicio + varredura / 2)
        largura = self._altura_texto * 4.6
        return QRectF(meio.x() - largura / 2, meio.y() - self._altura_texto * 0.75, largura, self._altura_texto * 1.5)

    def pontos_locais(self) -> tuple[QPointF, QPointF, QPointF]:
        sx = self._largura / self._base_l
        sy = self._altura / self._base_a
        return tuple(QPointF(q.x() * sx, q.y() * sy) for q in (self._v, self._a, self._b))  # type: ignore[return-value]

    @property
    def posicao_inicial_cena(self) -> QPointF:
        """Onde o elemento deve ficar na cena logo após criado (sem rotação)."""
        return QPointF(self._origem_cena)

    @property
    def valor_graus(self) -> float:
        v, a, b = self.pontos_locais()
        return geometria_arco(v, a, b)[1]

    def texto_valor(self) -> str:
        return f"{self.valor_graus:.1f}°".replace(".", ",")

    @property
    def raio(self) -> float:
        return self._raio

    def definir_raio(self, mm: float) -> None:
        self._raio = max(2.0, mm)
        self.update()

    @property
    def altura_texto(self) -> float:
        return self._altura_texto

    def definir_altura_texto(self, mm: float) -> None:
        self._altura_texto = max(0.5, mm)
        self.update()

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802
        # O arco/texto pode sair da caixa quando o raio cresce depois de criada.
        base = super().boundingRect()
        v, a, b = self.pontos_locais()
        return base.united(self._caixa(v, a, b))

    def primitivas_locais(self) -> tuple[list[tuple[QPointF, QPointF]], list[QPointF], list[QPolygonF], QRectF]:
        """(linhas dos braços, pontos do arco, setas, retângulo do texto) —
        a mesma geometria da pintura, usada também pela ponte do CorelDRAW."""
        v, a, b = self.pontos_locais()
        inicio, varredura = geometria_arco(v, a, b)
        r = self._raio

        def braco(p: QPointF) -> QPointF:
            d = p - v
            n = math.hypot(d.x(), d.y()) or 1.0
            alcance = max(n, r + _SETA_MM)
            return v + d * (alcance / n)

        linhas = [(v, braco(a)), (v, braco(b))]
        passos = max(8, int(varredura / 4))
        arco = [_ponto_no_arco(v, r, inicio + varredura * i / passos) for i in range(passos + 1)]
        s = min(_SETA_MM, r * math.radians(varredura) / 3) if varredura > 0 else 0.0
        setas = []
        if s > 0:
            for graus, sentido in ((inicio, 1), (inicio + varredura, -1)):
                ponta = _ponto_no_arco(v, r, graus)
                passo = math.degrees(s / r) * sentido
                atras = _ponto_no_arco(v, r, graus + passo)
                direcao = ponta - atras
                n = math.hypot(direcao.x(), direcao.y()) or 1.0
                perp = QPointF(-direcao.y() / n, direcao.x() / n) * (s * 0.35)
                setas.append(QPolygonF([ponta, atras + perp, atras - perp]))
        return linhas, arco, setas, self._retangulo_texto(v, inicio, varredura)

    # ── Pintura ─────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        linhas, arco, setas, rect = self.primitivas_locais()
        painter.setPen(QPen(cor, _TRACO_MM))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for p, q in linhas:
            painter.drawLine(p, q)
        caminho = QPainterPath(arco[0])
        for q in arco[1:]:
            caminho.lineTo(q)
        painter.drawPath(caminho)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        for seta in setas:
            painter.drawPolygon(seta)

        fonte = QFont("Arial")
        fonte.setPixelSize(int(_TAMANHO_FONTE_REFERENCIA))
        metricas = QFontMetricsF(fonte)
        escala = self._altura_texto / metricas.capHeight()
        texto = self.texto_valor()
        painter.save()
        painter.translate(rect.center())
        painter.scale(escala, escala)
        caminho_texto = QPainterPath()
        caminho_texto.addText(QPointF(-metricas.horizontalAdvance(texto) / 2, metricas.capHeight() / 2), fonte, texto)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        painter.drawPath(caminho_texto)
        painter.restore()

    def clonar(self) -> "ElementoCotaAngular":
        novo = ElementoCotaAngular(self._v, self._a, self._b, self._raio, self._cor_tinta, self._altura_texto)
        # Mesma base do original (recalcular a caixa deslocaria a cópia).
        novo._v, novo._a, novo._b = QPointF(self._v), QPointF(self._a), QPointF(self._b)
        novo._base_l, novo._base_a = self._base_l, self._base_a
        self._copiar_geometria_para(novo)
        return novo
