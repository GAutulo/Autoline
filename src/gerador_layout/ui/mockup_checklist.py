"""Checklist de cores do produto — lista de "quadradinho + nome" pra
empresa marcar na própria caixa qual variação do produto foi embalada
ali (ex.: uma mesa que existe em preto/branco/cinza). Usa o mesmo
princípio de medição de texto do resto do mockup (fonte de referência
grande + escala, ver mockup_texto.py), mas como um elemento só — não um
`GrupoMockup` de elementos soltos — porque a lista inteira se comporta
como uma unidade (mover/redimensionar/rotacionar tudo junto é o
comportamento esperado, não cada linha por si).

Redimensionar escala a lista inteira (quadradinhos + texto, dois eixos
independentes — mesmo espírito de ElementoTexto/ElementoRetangulo).
Adicionar/remover uma variante reajusta a caixa pro tamanho "natural"
de novo (mesmo princípio de `ElementoTexto.definir_texto`): o que
importa é sempre caber exatamente o conteúdo atual, não preservar um
redimensionamento manual anterior ao mudar a lista.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

_TAMANHO_FONTE_REFERENCIA_PT = 200.0
_ALTURA_LINHA_MM = 6.0  # base de referência — a caixa toda escala a partir daqui
_ESPACO_ENTRE_LINHAS_FATOR = 0.6  # relativo à altura da linha
_ESPACO_CAIXA_TEXTO_FATOR = 0.5  # relativo à altura da linha
_ESPESSURA_TRACO_FATOR = 0.08  # relativo à altura da linha


class ElementoChecklistCores(ElementoMockup):
    def __init__(
        self,
        variantes: list[str] | None = None,
        fonte_familia: str = "Arial",
        cor_tinta: CorImpressao | None = None,
        parent=None,
    ) -> None:
        super().__init__(largura=30.0, altura=_ALTURA_LINHA_MM, parent=parent)
        self._variantes = list(variantes) if variantes else ["Cor 1", "Cor 2"]
        self._fonte_familia = fonte_familia
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._reajustar_caixa()

    # ── Propriedades ────────────────────────────────────────────────
    @property
    def variantes(self) -> list[str]:
        return list(self._variantes)

    def definir_variantes(self, variantes: list[str]) -> None:
        self._variantes = list(variantes) if variantes else ["Cor 1"]
        self._reajustar_caixa()

    def adicionar_variante(self, nome: str) -> None:
        self._variantes.append(nome)
        self._reajustar_caixa()

    def remover_variante(self, indice: int) -> None:
        if len(self._variantes) > 1 and 0 <= indice < len(self._variantes):
            self._variantes.pop(indice)
            self._reajustar_caixa()

    @property
    def fonte_familia(self) -> str:
        return self._fonte_familia

    def definir_fonte(self, familia: str) -> None:
        self._fonte_familia = familia
        self._reajustar_caixa()

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    # ── Medição / layout natural (fonte de referência grande) ────────
    def _fonte_referencia(self) -> QFont:
        fonte = QFont(self._fonte_familia)
        fonte.setPointSizeF(_TAMANHO_FONTE_REFERENCIA_PT)
        return fonte

    def _metrica_referencia(self) -> tuple[QFontMetricsF, float]:
        metrica = QFontMetricsF(self._fonte_referencia())
        altura_ref = metrica.capHeight() or metrica.ascent()
        return metrica, altura_ref

    def _layout_natural(self) -> tuple[float, float]:
        """(largura, altura) que a lista ocuparia com cada linha em
        `_ALTURA_LINHA_MM` — a base sobre a qual o redimensionamento
        (herdado do motor) escala pra caber na caixa real."""
        metrica, altura_ref = self._metrica_referencia()
        escala_fonte = _ALTURA_LINHA_MM / altura_ref if altura_ref else 1.0
        espaco_linhas = _ALTURA_LINHA_MM * _ESPACO_ENTRE_LINHAS_FATOR
        espaco_caixa_texto = _ALTURA_LINHA_MM * _ESPACO_CAIXA_TEXTO_FATOR

        largura = 0.0
        for variante in self._variantes:
            largura_texto = metrica.horizontalAdvance(variante) * escala_fonte
            largura = max(largura, _ALTURA_LINHA_MM + espaco_caixa_texto + largura_texto)

        n = len(self._variantes)
        altura = n * _ALTURA_LINHA_MM + max(0, n - 1) * espaco_linhas
        return largura or 4.0, altura or 4.0

    def _reajustar_caixa(self) -> None:
        largura, altura = self._layout_natural()
        self.definir_tamanho(largura, altura)

    # ── Pintura ──────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        if not self._variantes:
            return

        metrica, altura_ref = self._metrica_referencia()
        escala_fonte = _ALTURA_LINHA_MM / altura_ref if altura_ref else 1.0
        espaco_linhas = _ALTURA_LINHA_MM * _ESPACO_ENTRE_LINHAS_FATOR
        espaco_caixa_texto = _ALTURA_LINHA_MM * _ESPACO_CAIXA_TEXTO_FATOR
        espessura_traco = _ALTURA_LINHA_MM * _ESPESSURA_TRACO_FATOR

        largura_natural, altura_natural = self._layout_natural()
        escala_x = self._largura / largura_natural if largura_natural else 1.0
        escala_y = self._altura / altura_natural if altura_natural else 1.0

        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)

        painter.save()
        painter.scale(escala_x, escala_y)

        y = 0.0
        for variante in self._variantes:
            painter.setPen(QPen(cor, espessura_traco))
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawRect(QRectF(0, y, _ALTURA_LINHA_MM, _ALTURA_LINHA_MM))

            painter.save()
            painter.setPen(QPen(cor))
            painter.setBrush(QBrush(cor))
            painter.translate(_ALTURA_LINHA_MM + espaco_caixa_texto, y)
            painter.scale(escala_fonte, escala_fonte)
            painter.setFont(self._fonte_referencia())
            painter.drawText(QPointF(0, altura_ref), variante)
            painter.restore()

            y += _ALTURA_LINHA_MM + espaco_linhas

        painter.restore()
