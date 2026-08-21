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

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

_LARGURA_TRACO_PADRAO_MM = 0.5
_LADOS_POLIGONO_PADRAO = 6
_LADOS_POLIGONO_MINIMO = 3
_LADOS_POLIGONO_MAXIMO = 20


# ── Retângulo ────────────────────────────────────────────────────────


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

    def clonar(self) -> "ElementoRetangulo":
        novo = ElementoRetangulo(
            cor_tinta=self._cor_tinta, preenchido=self._preenchido, largura_traco=self._largura_traco
        )
        self._copiar_geometria_para(novo)
        return novo


# ── Linha ────────────────────────────────────────────────────────────


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

    def clonar(self) -> "ElementoLinha":
        novo = ElementoLinha(cor_tinta=self._cor_tinta, largura_traco=self._largura_traco)
        self._copiar_geometria_para(novo)
        return novo


# ── Elipse ───────────────────────────────────────────────────────────


class ElementoElipse(ElementoMockup):
    """Mesmo princípio do `ElementoRetangulo` (cor/preenchido/traço),
    só troca `drawRect` por `drawEllipse` — "círculo" é só uma elipse
    com largura == altura, igual "quadrado" já é pro retângulo."""

    def __init__(
        self,
        largura: float = 40.0,
        altura: float = 40.0,
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
        margem = self._largura_traco / 2
        painter.drawEllipse(
            QRectF(
                margem, margem, max(0.01, self._largura - self._largura_traco), max(0.01, self._altura - self._largura_traco)
            )
        )

    def clonar(self) -> "ElementoElipse":
        novo = ElementoElipse(
            cor_tinta=self._cor_tinta, preenchido=self._preenchido, largura_traco=self._largura_traco
        )
        self._copiar_geometria_para(novo)
        return novo


# ── Polígono ─────────────────────────────────────────────────────────


class ElementoPoligono(ElementoMockup):
    """Polígono regular de N lados (padrão hexágono) — cobre também a
    ideia de "estrela" como variante (poucos lados = losango/triângulo/
    pentágono, sem precisar de uma ferramenta de estrela à parte). O
    polígono é normalizado (-1..1) e escalado por (largura/2, altura/2)
    ao pintar, então redimensionar largura/altura de forma diferente
    estica ele — mesmo comportamento de qualquer outra forma aqui."""

    def __init__(
        self,
        largura: float = 40.0,
        altura: float = 40.0,
        lados: int = _LADOS_POLIGONO_PADRAO,
        cor_tinta: CorImpressao | None = None,
        preenchido: bool = False,
        largura_traco: float = _LARGURA_TRACO_PADRAO_MM,
        parent=None,
    ) -> None:
        super().__init__(largura, altura, parent)
        self._lados = max(_LADOS_POLIGONO_MINIMO, min(_LADOS_POLIGONO_MAXIMO, lados))
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._preenchido = preenchido
        self._largura_traco = max(0.05, largura_traco)

    @property
    def lados(self) -> int:
        return self._lados

    def definir_lados(self, lados: int) -> None:
        self._lados = max(_LADOS_POLIGONO_MINIMO, min(_LADOS_POLIGONO_MAXIMO, lados))
        self.update()

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

    def _caminho_normalizado(self) -> QPainterPath:
        caminho = QPainterPath()
        for i in range(self._lados):
            angulo = math.radians(-90 + i * 360 / self._lados)  # começa apontando pra cima, igual estrela/logo
            ponto = QPointF(math.cos(angulo), math.sin(angulo))
            caminho.moveTo(ponto) if i == 0 else caminho.lineTo(ponto)
        caminho.closeSubpath()
        return caminho

    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        margem = self._largura_traco / 2
        raio_x = max(0.01, self._largura / 2 - margem)
        raio_y = max(0.01, self._altura / 2 - margem)

        painter.save()
        painter.translate(self._largura / 2, self._altura / 2)
        painter.scale(raio_x, raio_y)
        pen = QPen(cor, self._largura_traco / min(raio_x, raio_y))  # espessura constante apesar do scale não-uniforme
        pen.setCosmetic(False)
        painter.setPen(pen)
        painter.setBrush(QBrush(cor) if self._preenchido else QBrush(Qt.BrushStyle.NoBrush))
        painter.drawPath(self._caminho_normalizado())
        painter.restore()

    def clonar(self) -> "ElementoPoligono":
        novo = ElementoPoligono(
            lados=self._lados, cor_tinta=self._cor_tinta, preenchido=self._preenchido, largura_traco=self._largura_traco
        )
        self._copiar_geometria_para(novo)
        return novo
