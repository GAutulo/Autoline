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

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QGraphicsProxyWidget, QLineEdit

from ..models import CorImpressao
from .mockup_itens import ElementoMockup, desenhar_texto_escalado

_TAMANHO_FONTE_REFERENCIA_PT = 200.0
_ALTURA_PADRAO_MM = 8.0

# Tamanho NATIVO (pixels reais) do campo de edição embutido no canvas —
# não tem relação com largura/altura do elemento em mm. Dar um tamanho
# generoso aqui (em vez de tentar forçar o QLineEdit pro tamanho em mm
# do elemento, que pode ser menor que a altura mínima de um campo nativo
# do Qt e sair cortado/ilegível) e depois ESCALAR o widget inteiro pra
# caber no elemento é o mesmo truque de fonte-de-referência-grande já
# usado no resto do módulo (`_TAMANHO_FONTE_REFERENCIA_PT`), só que
# aplicado ao widget, não ao `QPainter.scale()`.
_LARGURA_EDICAO_PX = 320
_ALTURA_EDICAO_PX = 64


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
        self._proxy_edicao: QGraphicsProxyWidget | None = None
        self._campo_edicao: QLineEdit | None = None

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

    def clonar(self) -> "ElementoTexto":
        novo = ElementoTexto(
            texto=self._texto, fonte_familia=self._fonte_familia, negrito=self._negrito, cor_tinta=self._cor_tinta
        )
        self._copiar_geometria_para(novo)
        return novo

    # ── Edição direto no canvas (clique duplo, ou logo após criar com a
    # ferramenta Texto — ver `main_window.py::_criar_texto_por_clique`) ──
    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.iniciar_edicao_inline()
        super().mouseDoubleClickEvent(event)

    def iniciar_edicao_inline(self) -> None:
        """Sobrepõe um `QLineEdit` de verdade em cima do texto pintado —
        digitar vai direto pro canvas, no lugar onde o texto vai ficar,
        em vez de precisar editar pelo campo da barra de propriedades
        (pedido explícito do usuário). Não tenta casar a métrica exata
        da fonte pintada (ver docstring do módulo — o texto real usa o
        truque de fonte-de-referência-grande); o campo de edição é só
        uma aproximação visual suficiente pra digitar no lugar certo — o
        tamanho final de verdade vem de `definir_texto` ao confirmar."""
        if self._proxy_edicao is not None or self.scene() is None:
            return

        campo = QLineEdit(self._texto.strip())
        fonte = QFont(self._fonte_familia)
        fonte.setPixelSize(40)
        fonte.setBold(self._negrito)
        campo.setFont(fonte)
        cor = self._cor_tinta
        campo.setStyleSheet(
            "QLineEdit { background: white; border: 2px dashed rgb(%d,%d,%d); color: rgb(%d,%d,%d); padding: 2px 6px; }"
            % (cor.r, cor.g, cor.b, cor.r, cor.g, cor.b)
        )
        campo.setFixedSize(_LARGURA_EDICAO_PX, _ALTURA_EDICAO_PX)

        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(campo)
        # Escala uniforme baseada na ALTURA (mesmo eixo que define
        # "tamanho de fonte" no resto do app) — a largura do campo pode
        # sobrar/faltar um pouco em relação ao texto final, sem problema,
        # já que `definir_texto` recalcula a largura real ao confirmar.
        escala = self._altura / _ALTURA_EDICAO_PX if self._altura else 1.0
        proxy.setScale(escala)
        proxy.setPos(0, 0)
        proxy.setZValue(1000)

        self._proxy_edicao = proxy
        self._campo_edicao = campo
        self.setOpacity(0.0)  # esconde o texto pintado normal enquanto edita, evita duplicar

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
        altura_ref, largura_ref = self._metrica_referencia()
        escala_y = self._altura / altura_ref if altura_ref else 1.0
        escala_x = self._largura / largura_ref if largura_ref else escala_y

        painter.save()
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        painter.setPen(QPen(cor))
        painter.setBrush(QBrush(cor))
        painter.scale(escala_x, escala_y)
        # `desenhar_texto_escalado` (não `painter.drawText` direto) —
        # ver docstring dela em mockup_itens.py pro bug real de
        # exportação SVG que essa troca evita.
        desenhar_texto_escalado(painter, QPointF(0, altura_ref), self._fonte_referencia(), self._texto)
        painter.restore()
