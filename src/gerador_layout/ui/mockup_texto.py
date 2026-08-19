"""Elemento de texto do mockup — nome do produto, textos livres, etc.
Fonte, negrito e cor de tinta (reaproveitando o mesmo `CorImpressao` já
usado na legenda de cores de impressão) são editáveis; mover, redimensionar
e rotacionar vêm de graça do motor em `mockup_itens.py`.

Redimensionar aqui NÃO troca de tamanho de fonte por um valor em pt nem
faz wrap de texto — escala o desenho do texto pra caber exatamente na
caixa atual (largura × altura), igual "texto artístico" no CorelDRAW:
arrastar um canto escala os dois eixos, arrastar só um lado estica só
aquele eixo (e distorce o texto de propósito — é o mesmo comportamento
que o CorelDRAW tem por padrão, o usuário já espera isso de lá).

O tamanho da fonte não é guardado em pt: a fonte de referência é
renderizada bem grande (`_TAMANHO_FONTE_REFERENCIA_PT`) e escalada via
`QPainter.scale()` até caber na caixa — evita o mesmo bug de
rasterização/kerning em fontes pequenas que já foi corrigido antes na
legenda de exportação (ver `_fonte_e_escala_legenda` em exportacao.py);
aqui é o mesmo truque, só que reaplicado a cada pintura em vez de uma
vez só, porque o tamanho da caixa pode mudar a qualquer momento.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

_TAMANHO_FONTE_REFERENCIA_PT = 200.0
_ALTURA_PADRAO_MM = 8.0


class ElementoTexto(ElementoMockup):
    def __init__(
        self,
        texto: str = "Texto",
        fonte_familia: str = "Arial",
        negrito: bool = False,
        cor_tinta: CorImpressao | None = None,
        parent=None,
    ) -> None:
        super().__init__(largura=10.0, altura=_ALTURA_PADRAO_MM, parent=parent)
        self._texto = texto or " "
        self._fonte_familia = fonte_familia
        self._negrito = negrito
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._reajustar_largura()

    # ── Propriedades ────────────────────────────────────────────────
    @property
    def texto(self) -> str:
        return self._texto

    def definir_texto(self, texto: str) -> None:
        self._texto = texto or " "
        self._reajustar_largura()

    @property
    def fonte_familia(self) -> str:
        return self._fonte_familia

    def definir_fonte(self, familia: str) -> None:
        self._fonte_familia = familia
        self._reajustar_largura()

    @property
    def negrito(self) -> bool:
        return self._negrito

    def definir_negrito(self, negrito: bool) -> None:
        self._negrito = negrito
        self._reajustar_largura()

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    # ── Medição (fonte de referência grande, nunca a fonte pequena) ──
    def _fonte_referencia(self) -> QFont:
        fonte = QFont(self._fonte_familia)
        fonte.setPointSizeF(_TAMANHO_FONTE_REFERENCIA_PT)
        fonte.setBold(self._negrito)
        return fonte

    def _metrica_referencia(self) -> tuple[float, float]:
        """(altura_de_referencia, largura_de_referencia) — mesma unidade
        arbitrária (pt de referência), só a RAZÃO entre elas e o tamanho
        real da caixa importa."""
        metrica = QFontMetricsF(self._fonte_referencia())
        altura_ref = metrica.capHeight() or metrica.ascent()
        largura_ref = metrica.horizontalAdvance(self._texto) or 1.0
        return altura_ref, largura_ref

    def _reajustar_largura(self) -> None:
        """Só a largura acompanha texto/fonte/negrito novos — a altura
        (= tamanho da fonte, ver docstring do módulo) fica como o
        usuário deixou; editar o texto não deve mudar o tamanho da letra."""
        altura_ref, largura_ref = self._metrica_referencia()
        escala = self._altura / altura_ref if altura_ref else 1.0
        self.definir_tamanho(largura_ref * escala, self._altura)

    # ── Pintura ──────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        altura_ref, largura_ref = self._metrica_referencia()
        escala_y = self._altura / altura_ref if altura_ref else 1.0
        escala_x = self._largura / largura_ref if largura_ref else escala_y

        painter.save()
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        painter.setPen(QPen(cor))
        painter.setBrush(QBrush(cor))
        painter.scale(escala_x, escala_y)
        painter.setFont(self._fonte_referencia())
        painter.drawText(QPointF(0, altura_ref), self._texto)
        painter.restore()
