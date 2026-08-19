"""Formas básicas do mockup — retângulo/quadrado e linha — com cor de
tinta (mesmo `CorImpressao` usado no texto e na legenda). Mover,
redimensionar e rotacionar vêm do motor em `mockup_itens.py`; "quadrado"
não é uma classe à parte, é só um `ElementoRetangulo` criado com
largura == altura.

`ElementoLinha` desenha um traço horizontal no meio vertical da própria
caixa, não a diagonal dela — uma linha reta não devia inclinar sozinha só
porque a caixa (que o motor sempre mantém com uma altura mínima, pra ter
onde clicar) não é perfeitamente achatada. Redimensionar pela largura
muda o comprimento da linha; a altura da caixa é só a "faixa de clique",
sem efeito visual — mesmo princípio de uma ferramenta de linha em
qualquer editor vetorial (a régua de seleção nunca é a própria linha).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

_LARGURA_TRACO_PADRAO_MM = 0.5


class ElementoRetangulo(ElementoMockup):
    def __init__(
        self,
        largura: float = 40.0,
        altura: float = 25.0,
        cor_tinta: CorImpressao | None = None,
        preenchido: bool = False,
        largura_traco: float = _LARGURA_TRACO_PADRAO_MM,
        parent=None,
    ) -> None:
        super().__init__(largura, altura, parent)
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._preenchido = preenchido
        self._largura_traco = max(0.05, largura_traco)

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    @property
    def preenchido(self) -> bool:
        return self._preenchido

    def definir_preenchido(self, preenchido: bool) -> None:
        self._preenchido = preenchido
        self.update()

    @property
    def largura_traco(self) -> float:
        return self._largura_traco

    def definir_largura_traco(self, mm: float) -> None:
        self._largura_traco = max(0.05, mm)
        self.update()

    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        painter.setPen(QPen(cor, self._largura_traco))
        painter.setBrush(QBrush(cor) if self._preenchido else QBrush(Qt.BrushStyle.NoBrush))
        # Encolhe meio traço pra dentro — senão a linha do contorno fica
        # cortada pela metade nos limites da caixa/alças de seleção.
        margem = self._largura_traco / 2
        painter.drawRect(
            margem, margem, max(0.01, self._largura - self._largura_traco), max(0.01, self._altura - self._largura_traco)
        )


class ElementoLinha(ElementoMockup):
    def __init__(
        self,
        largura: float = 40.0,
        cor_tinta: CorImpressao | None = None,
        largura_traco: float = _LARGURA_TRACO_PADRAO_MM,
        parent=None,
    ) -> None:
        # Altura vem do mínimo do próprio motor (só "faixa de clique",
        # ver docstring do módulo) — não representa espessura do traço.
        super().__init__(largura=largura, altura=0.0, parent=parent)
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._largura_traco = max(0.05, largura_traco)

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    @property
    def largura_traco(self) -> float:
        return self._largura_traco

    def definir_largura_traco(self, mm: float) -> None:
        self._largura_traco = max(0.05, mm)
        self.update()

    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        pen = QPen(cor, self._largura_traco)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        meio = self._altura / 2
        painter.drawLine(QPointF(0, meio), QPointF(self._largura, meio))
