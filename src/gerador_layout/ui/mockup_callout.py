"""Callout (linha de chamada com texto) — anotação técnica de revisão,
tipo "aqui precisa de sangria" ou "cor Pantone tal", apontando pra perto
de onde está. A "geometria" (largura × altura, mover/redimensionar/
rotacionar) é sempre só a caixa de texto — a cauda sai sempre do canto
inferior-esquerdo dela numa direção fixa (como um balão de fala), não é
um segundo ponto de controle independente: isso mantém o callout
compatível com o mesmo motor de mover/redimensionar/rotacionar/snap que
todo outro elemento usa, sem precisar de um caso especial.

Edição de texto: mesmo princípio de `ElementoTexto` (campo nativo
sobreposto, escalado pro tamanho do elemento) — ver `iniciar_edicao_inline`.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsProxyWidget, QLineEdit

from ..models import CorImpressao
from .mockup_itens import ElementoMockup, desenhar_texto_escalado

_LARGURA_PADRAO_MM = 45.0
_ALTURA_PADRAO_MM = 16.0
_TAMANHO_FONTE_REFERENCIA_PT = 200.0
_COMPRIMENTO_CAUDA_MM = 9.0
_RAIO_CANTO_MM = 2.0

_LARGURA_EDICAO_PX = 360
_ALTURA_EDICAO_PX = 90


class ElementoCallout(ElementoMockup):
    def __init__(
        self,
        texto: str = "Observação",
        cor_tinta: CorImpressao | None = None,
        parent=None,
    ) -> None:
        super().__init__(largura=_LARGURA_PADRAO_MM, altura=_ALTURA_PADRAO_MM, parent=parent)
        self._texto = texto or " "
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._proxy_edicao: QGraphicsProxyWidget | None = None
        self._campo_edicao: QLineEdit | None = None

    @property
    def texto(self) -> str:
        return self._texto

    def definir_texto(self, texto: str) -> None:
        self._texto = texto or " "
        self.update()

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    # ── Edição direto no canvas — mesmo princípio de ElementoTexto ────
    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.iniciar_edicao_inline()
        super().mouseDoubleClickEvent(event)

    def iniciar_edicao_inline(self) -> None:
        if self._proxy_edicao is not None or self.scene() is None:
            return
        campo = QLineEdit(self._texto.strip())
        fonte = QFont()
        fonte.setPixelSize(28)
        campo.setFont(fonte)
        cor = self._cor_tinta
        campo.setStyleSheet(
            "QLineEdit { background: white; border: 2px dashed rgb(%d,%d,%d); color: rgb(%d,%d,%d); padding: 2px 6px; }"
            % (cor.r, cor.g, cor.b, cor.r, cor.g, cor.b)
        )
        campo.setFixedSize(_LARGURA_EDICAO_PX, _ALTURA_EDICAO_PX)

        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(campo)
        # Ver comentário equivalente em `mockup_texto.py::iniciar_edicao_inline`
        # — sem isso, `self.setOpacity(0.0)` abaixo apaga o proxy junto.
        proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresParentOpacity, True)
        escala = self._altura / _ALTURA_EDICAO_PX if self._altura else 1.0
        proxy.setScale(escala)
        proxy.setPos(0, 0)
        proxy.setZValue(1000)

        self._proxy_edicao = proxy
        self._campo_edicao = campo
        self.setOpacity(0.0)

        campo.selectAll()
        campo.setFocus(Qt.FocusReason.MouseFocusReason)
        campo.editingFinished.connect(self._confirmar_edicao_inline)

    def _confirmar_edicao_inline(self) -> None:
        if self._proxy_edicao is None:
            return
        novo_texto = self._campo_edicao.text() if self._campo_edicao else self._texto
        proxy = self._proxy_edicao
        self._proxy_edicao = None
        self._campo_edicao = None
        self.setOpacity(1.0)
        self.definir_texto(novo_texto)
        if self.scene() is not None:
            self.scene().removeItem(proxy)

    # ── Pintura ──────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        painter.setPen(QPen(cor, 0.4))
        painter.setBrush(QBrush(QColor(255, 255, 255, 235)))

        caminho = QPainterPath()
        caminho.addRoundedRect(QRectF(0, 0, self._largura, self._altura), _RAIO_CANTO_MM, _RAIO_CANTO_MM)
        # Cauda saindo do canto inferior-esquerdo, apontando pra fora —
        # mesmo ângulo (225°, sudoeste) não importa o tamanho da caixa,
        # pra sempre ler como "isso aqui aponta pra baixo-esquerda de
        # onde a caixa está", igual um balão de fala.
        base_x, base_y = self._largura * 0.18, self._altura
        ponta = QPointF(base_x - _COMPRIMENTO_CAUDA_MM * 0.75, base_y + _COMPRIMENTO_CAUDA_MM * 0.75)
        cauda = QPainterPath()
        cauda.moveTo(base_x, base_y)
        cauda.lineTo(ponta)
        cauda.lineTo(base_x + _RAIO_CANTO_MM * 2.2, base_y)
        cauda.closeSubpath()
        caminho = caminho.united(cauda)
        painter.drawPath(caminho)

        # Ponto de referência na ponta da cauda — deixa claro que é ISSO
        # que está sendo apontado, não só uma decoração.
        painter.setBrush(QBrush(cor))
        painter.drawEllipse(ponta, 1.0, 1.0)

        # Texto, mesmo truque de fonte-de-referência-grande do resto do
        # app — evita rasterização ruim em fonte pequena.
        fonte_ref = QFont()
        fonte_ref.setPointSizeF(_TAMANHO_FONTE_REFERENCIA_PT)
        metrica = QFontMetricsF(fonte_ref)
        altura_ref = metrica.capHeight() or metrica.ascent()
        margem = 3.0
        altura_disponivel = max(1.0, self._altura - margem * 2)
        escala = altura_disponivel / altura_ref if altura_ref else 1.0
        largura_texto_ref = metrica.horizontalAdvance(self._texto) or 1.0
        if largura_texto_ref * escala > self._largura - margem * 2:
            escala = max(0.01, (self._largura - margem * 2) / largura_texto_ref)

        painter.save()
        painter.setPen(QPen(cor))
        painter.translate(margem, margem)
        painter.scale(escala, escala)
        desenhar_texto_escalado(painter, QPointF(0, altura_ref), fonte_ref, self._texto)
        painter.restore()

    def clonar(self) -> "ElementoCallout":
        novo = ElementoCallout(texto=self._texto, cor_tinta=self._cor_tinta)
        self._copiar_geometria_para(novo)
        return novo
