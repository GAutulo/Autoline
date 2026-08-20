"""Indicador de acabamento de produção — marca uma área da caixa que
recebe um processo especial (verniz localizado, laminação, hot stamping),
não um efeito de transparência de design. Convenção de pré-impressão de
verdade: área de acabamento se marca com uma hachura + rótulo do
processo, numa cor de MARCAÇÃO técnica (magenta), separada das tintas
reais de impressão — a gráfica não confunde isso com uma cor que vai
para a chapa de cor, é uma instrução à parte pro processo de pós-
impressão. Por isso este elemento NÃO usa `CorImpressao`/cor de tinta
como os outros — a cor de marcação é sempre a mesma, de propósito.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen

from .mockup_itens import ElementoMockup, desenhar_texto_escalado

_LARGURA_PADRAO_MM = 40.0
_ALTURA_PADRAO_MM = 25.0
_COR_MARCACAO = QColor(236, 0, 140)  # magenta de marcação técnica — nunca confundir com tinta real
_PASSO_HACHURA_MM = 3.0
_TAMANHO_FONTE_REFERENCIA_PT = 80.0


class TipoAcabamento(Enum):
    VERNIZ_LOCALIZADO = "Verniz localizado"
    LAMINACAO_FOSCA = "Laminação fosca"
    LAMINACAO_BRILHO = "Laminação brilho"
    HOT_STAMPING = "Hot stamping"


class ElementoAcabamento(ElementoMockup):
    def __init__(
        self,
        tipo: TipoAcabamento = TipoAcabamento.VERNIZ_LOCALIZADO,
        largura: float = _LARGURA_PADRAO_MM,
        altura: float = _ALTURA_PADRAO_MM,
        parent=None,
    ) -> None:
        super().__init__(largura=largura, altura=altura, parent=parent)
        self._tipo = tipo

    @property
    def tipo(self) -> TipoAcabamento:
        return self._tipo

    def definir_tipo(self, tipo: TipoAcabamento) -> None:
        self._tipo = tipo
        self.update()

    def _pintar_conteudo(self, painter: QPainter) -> None:
        painter.setPen(QPen(_COR_MARCACAO, 0.4))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawRect(QRectF(0, 0, self._largura, self._altura))

        # Hachura diagonal — o mesmo glyph universal de "área especial,
        # não é a arte final" que qualquer software de pré-impressão usa
        # (a hachura em si nunca vai pra chapa, é só indicação visual no
        # arquivo de referência).
        painter.save()
        painter.setClipRect(QRectF(0, 0, self._largura, self._altura))
        caneta_hachura = QPen(QColor(_COR_MARCACAO.red(), _COR_MARCACAO.green(), _COR_MARCACAO.blue(), 130), 0.3)
        painter.setPen(caneta_hachura)
        diagonal = self._largura + self._altura
        x = -self._altura
        while x < self._largura:
            painter.drawLine(QPointF(x, 0), QPointF(x + self._altura, self._altura))
            x += _PASSO_HACHURA_MM
        painter.restore()

        # Rótulo do tipo de processo — sem isso, uma hachura sozinha não
        # diz QUAL acabamento é (verniz? laminação? hot stamping?).
        fonte_ref = QFont()
        fonte_ref.setPointSizeF(_TAMANHO_FONTE_REFERENCIA_PT)
        fonte_ref.setBold(True)
        metrica = QFontMetricsF(fonte_ref)
        altura_ref = metrica.capHeight() or metrica.ascent()
        margem = 2.0
        altura_disponivel = max(1.0, min(self._altura * 0.3, 6.0))
        escala = altura_disponivel / altura_ref if altura_ref else 1.0
        texto = self._tipo.value
        largura_texto_ref = metrica.horizontalAdvance(texto) or 1.0
        if largura_texto_ref * escala > self._largura - margem * 2:
            escala = max(0.01, (self._largura - margem * 2) / largura_texto_ref)

        painter.save()
        painter.setPen(QPen(_COR_MARCACAO))
        painter.setBrush(QBrush(QColor(255, 255, 255, 210)))
        largura_fundo = min(self._largura - margem, largura_texto_ref * escala + margem * 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(margem, margem, largura_fundo, altura_disponivel + margem))
        painter.setPen(QPen(_COR_MARCACAO))
        painter.setBrush(QBrush(_COR_MARCACAO))  # desenhar_texto_escalado preenche com o brush, não o pen
        painter.translate(margem * 1.5, margem)
        painter.scale(escala, escala)
        desenhar_texto_escalado(painter, QPointF(0, altura_ref), fonte_ref, texto)
        painter.restore()

    def clonar(self) -> "ElementoAcabamento":
        novo = ElementoAcabamento(tipo=self._tipo, largura=self._largura, altura=self._altura)
        self._copiar_geometria_para(novo)
        return novo
