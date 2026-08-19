"""Motor de seleção/edição dos elementos de mockup (texto, formas, imagens
que o usuário posiciona sobre a dieline) — a base de tudo que a Fase 2 do
programa precisa: mover, redimensionar, rotacionar e agrupar/desagrupar.
Item #1 do plano da Fase 2 (ver conversa) — as ferramentas de verdade
(texto, forma, imagem, logotipo) vêm depois, todas construídas em cima
desta base.

Cada elemento guarda sua própria largura/altura "lógica" (independente da
`QTransform` do Qt) em coordenadas locais começando em (0,0) — é o que
permite redimensionar sem distorcer o conteúdo desenhado por cima (texto
não pode esticar tipo um balão; cada subclasse decide como reagir a um
novo tamanho). Rotação usa a rotação nativa do Qt (`setRotation`), sempre
em torno do centro do elemento (`setTransformOriginPoint`).

Alças de edição (8 de redimensionar + 1 de rotacionar) só aparecem quando
o elemento está selecionado, com tamanho fixo em milímetros de CENA (não
em pixels de tela) — mais simples que escalar com o zoom, e como os
elementos de mockup tendem a ser pequenos (dezenas de mm) perto do
tamanho da caixa (centenas de mm), o usuário natural mente dá zoom pra
editar de perto, o que já deixa as alças confortáveis.

O cálculo de redimensionar/rotacionar usa só o ângulo e a posição
capturados no início do arrasto (`mousePressEvent`) — nunca reconsulta
`mapToScene`/`mapFromScene` a cada frame do arrasto, porque isso
reintroduziria o próprio ponto de referência (origem da rotação) que
está mudando durante o gesto, causando deriva. Em vez disso, a posição
final de cada frame é recalculada do zero a partir do estado inicial
congelado, usando só `QTransform` pra rotação — sem acumular erro.
"""

from __future__ import annotations

import math
from enum import Enum, auto

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget

_TAMANHO_ALCA_MM = 3.0
_TAMANHO_ALCA_ROTACAO_MM = 4.0
_DISTANCIA_ALCA_ROTACAO_MM = 10.0
_LARGURA_MINIMA_MM = 4.0
_ALTURA_MINIMA_MM = 4.0
_MARGEM_CLIQUE_ALCA = 1.7  # área de clique um pouco maior que o desenho da alça, mais fácil de acertar

_COR_SELECAO = QColor("#2f6fed")
_COR_ALCA_PREENCHIMENTO = QColor("#ffffff")


class Alca(Enum):
    NENHUMA = auto()
    SUPERIOR_ESQUERDA = auto()
    SUPERIOR = auto()
    SUPERIOR_DIREITA = auto()
    DIREITA = auto()
    INFERIOR_DIREITA = auto()
    INFERIOR = auto()
    INFERIOR_ESQUERDA = auto()
    ESQUERDA = auto()
    ROTACAO = auto()
    CORPO = auto()  # clicou dentro do elemento, fora de qualquer alça


# Pra cada alça de redimensionar, sua posição relativa (0..1, 0..1) dentro
# do retângulo largura×altura. O ponto OPOSTO (1-x, 1-y) é o que fica
# fixo na tela durante o arrasto dessa alça.
_PONTO_RELATIVO_ALCA: dict[Alca, tuple[float, float]] = {
    Alca.SUPERIOR_ESQUERDA: (0.0, 0.0),
    Alca.SUPERIOR: (0.5, 0.0),
    Alca.SUPERIOR_DIREITA: (1.0, 0.0),
    Alca.DIREITA: (1.0, 0.5),
    Alca.INFERIOR_DIREITA: (1.0, 1.0),
    Alca.INFERIOR: (0.5, 1.0),
    Alca.INFERIOR_ESQUERDA: (0.0, 1.0),
    Alca.ESQUERDA: (0.0, 0.5),
}

_CURSOR_POR_ALCA = {
    Alca.SUPERIOR_ESQUERDA: Qt.CursorShape.SizeFDiagCursor,
    Alca.INFERIOR_DIREITA: Qt.CursorShape.SizeFDiagCursor,
    Alca.SUPERIOR_DIREITA: Qt.CursorShape.SizeBDiagCursor,
    Alca.INFERIOR_ESQUERDA: Qt.CursorShape.SizeBDiagCursor,
    Alca.SUPERIOR: Qt.CursorShape.SizeVerCursor,
    Alca.INFERIOR: Qt.CursorShape.SizeVerCursor,
    Alca.ESQUERDA: Qt.CursorShape.SizeHorCursor,
    Alca.DIREITA: Qt.CursorShape.SizeHorCursor,
    Alca.ROTACAO: Qt.CursorShape.CrossCursor,
    Alca.CORPO: Qt.CursorShape.SizeAllCursor,
    Alca.NENHUMA: Qt.CursorShape.ArrowCursor,
}


class ElementoMockup(QGraphicsObject):
    """Base de qualquer objeto que o usuário posiciona sobre a dieline no
    mockup — texto, forma, imagem, ou um grupo desses. Subclasses só
    precisam implementar `_pintar_conteudo`; toda a interação (mover,
    redimensionar, rotacionar, seleção) já vem daqui."""

    geometria_alterada = Signal()

    def __init__(self, largura: float = 40.0, altura: float = 24.0, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._largura = max(_LARGURA_MINIMA_MM, largura)
        self._altura = max(_ALTURA_MINIMA_MM, altura)
        self.setTransformOriginPoint(self._largura / 2, self._altura / 2)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)

        # Painel "dono" do elemento (frente, lateral, tampa...) — pura
        # etiqueta informativa, sem nenhum recorte/trava associada: o
        # usuário confirmou que às vezes uma impressão atravessa pra um
        # painel vizinho, então travar nisso atrapalharia mais do que
        # ajudaria. Serve pra Fase 3 (3D) saber em qual face colar o quê.
        self._painel_id: str | None = None

        self._alca_ativa = Alca.NENHUMA
        self._arrastando = False
        # Estado congelado no início do arrasto (mousePressEvent) — o
        # cálculo de cada frame do arrasto parte sempre daqui, nunca do
        # frame anterior (ver docstring do módulo).
        self._arrasto_oposto_cena = QPointF()
        self._arrasto_largura_inicial = 0.0
        self._arrasto_altura_inicial = 0.0
        self._arrasto_angulo_inicial = 0.0
        self._arrasto_centro_cena = QPointF()
        self._arrasto_angulo_mouse_inicial = 0.0

    # ── Propriedades geométricas ────────────────────────────────────
    @property
    def largura(self) -> float:
        return self._largura

    @property
    def altura(self) -> float:
        return self._altura

    @property
    def painel_id(self) -> str | None:
        return self._painel_id

    def definir_painel(self, painel_id: str | None) -> None:
        self._painel_id = painel_id

    def definir_tamanho(self, largura: float, altura: float) -> None:
        self.prepareGeometryChange()
        self._largura = max(_LARGURA_MINIMA_MM, largura)
        self._altura = max(_ALTURA_MINIMA_MM, altura)
        self.setTransformOriginPoint(self._largura / 2, self._altura / 2)
        self.update()
        self.geometria_alterada.emit()

    # ── QGraphicsItem ────────────────────────────────────────────────
    def boundingRect(self) -> QRectF:
        margem = _DISTANCIA_ALCA_ROTACAO_MM + _TAMANHO_ALCA_ROTACAO_MM
        return QRectF(0, 0, self._largura, self._altura).adjusted(-margem, -margem, margem, margem)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        self._pintar_conteudo(painter)
        if self.isSelected():
            self._pintar_selecao(painter)

    def _pintar_conteudo(self, painter: QPainter) -> None:
        """Subclasses sobrescrevem pra desenhar o conteúdo real (texto,
        forma, imagem) dentro do retângulo `(0, 0, largura, altura)`."""
        raise NotImplementedError

    def _pintar_selecao(self, painter: QPainter) -> None:
        raio = (_TAMANHO_ALCA_MM / 2.0)

        pen_contorno = QPen(_COR_SELECAO, 0.3)
        painter.setPen(pen_contorno)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, self._largura, self._altura))

        centro_x = self._largura / 2
        painter.drawLine(QPointF(centro_x, 0), QPointF(centro_x, -_DISTANCIA_ALCA_ROTACAO_MM))

        painter.setBrush(QBrush(_COR_ALCA_PREENCHIMENTO))
        painter.setPen(QPen(_COR_SELECAO, 0.4))
        for _alca, (rel_x, rel_y) in _PONTO_RELATIVO_ALCA.items():
            centro = QPointF(rel_x * self._largura, rel_y * self._altura)
            painter.drawRect(QRectF(centro.x() - raio, centro.y() - raio, raio * 2, raio * 2))

        raio_rotacao = _TAMANHO_ALCA_ROTACAO_MM / 2.0
        centro_rotacao = QPointF(centro_x, -_DISTANCIA_ALCA_ROTACAO_MM)
        painter.drawEllipse(centro_rotacao, raio_rotacao, raio_rotacao)

    # ── Detecção de alça sob o cursor ────────────────────────────────
    def _alca_em(self, ponto_local: QPointF) -> Alca:
        if not self.isSelected():
            return Alca.CORPO if self._contem_corpo(ponto_local) else Alca.NENHUMA

        centro_x = self._largura / 2
        centro_rotacao = QPointF(centro_x, -_DISTANCIA_ALCA_ROTACAO_MM)
        raio_rotacao = (_TAMANHO_ALCA_ROTACAO_MM / 2.0) * _MARGEM_CLIQUE_ALCA
        if _distancia(ponto_local, centro_rotacao) <= raio_rotacao:
            return Alca.ROTACAO

        raio = (_TAMANHO_ALCA_MM / 2.0) * _MARGEM_CLIQUE_ALCA
        for alca, (rel_x, rel_y) in _PONTO_RELATIVO_ALCA.items():
            centro = QPointF(rel_x * self._largura, rel_y * self._altura)
            if abs(ponto_local.x() - centro.x()) <= raio and abs(ponto_local.y() - centro.y()) <= raio:
                return alca

        return Alca.CORPO if self._contem_corpo(ponto_local) else Alca.NENHUMA

    def _contem_corpo(self, ponto_local: QPointF) -> bool:
        return QRectF(0, 0, self._largura, self._altura).contains(ponto_local)

    # ── Interação de mouse ───────────────────────────────────────────
    def hoverMoveEvent(self, event) -> None:  # noqa: N802
        alca = self._alca_em(event.pos())
        self.setCursor(_CURSOR_POR_ALCA.get(alca, Qt.CursorShape.ArrowCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        alca = self._alca_em(event.pos())

        if alca == Alca.NENHUMA:
            event.ignore()
            return

        if alca == Alca.CORPO:
            super().mousePressEvent(event)  # seleção + mover: comportamento nativo do Qt (flags já habilitam)
            return

        # Alça de redimensionar ou rotação — só aparece quando já
        # selecionado, então não precisa re-selecionar aqui.
        self._alca_ativa = alca
        self._arrastando = True
        self._arrasto_largura_inicial = self._largura
        self._arrasto_altura_inicial = self._altura
        self._arrasto_angulo_inicial = self.rotation()

        if alca == Alca.ROTACAO:
            self._arrasto_centro_cena = self.mapToScene(QPointF(self._largura / 2, self._altura / 2))
            delta = event.scenePos() - self._arrasto_centro_cena
            self._arrasto_angulo_mouse_inicial = math.degrees(math.atan2(delta.y(), delta.x()))
        else:
            rel_x, rel_y = _PONTO_RELATIVO_ALCA[alca]
            oposto_local = QPointF((1 - rel_x) * self._largura, (1 - rel_y) * self._altura)
            self._arrasto_oposto_cena = self.mapToScene(oposto_local)

        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._arrastando and self._alca_ativa == Alca.ROTACAO:
            self._girar_para(event.scenePos())
            return
        if self._arrastando and self._alca_ativa not in (Alca.NENHUMA, Alca.CORPO):
            self._redimensionar_para(event.scenePos())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._arrastando:
            self._arrastando = False
            self._alca_ativa = Alca.NENHUMA
            self.geometria_alterada.emit()
            return
        super().mouseReleaseEvent(event)

    # ── Redimensionar ────────────────────────────────────────────────
    def _redimensionar_para(self, ponto_cena: QPointF) -> None:
        rel_x, rel_y = _PONTO_RELATIVO_ALCA[self._alca_ativa]

        rotacao_inversa = QTransform().rotate(-self._arrasto_angulo_inicial)
        diff_cena = ponto_cena - self._arrasto_oposto_cena
        diff_local = rotacao_inversa.map(diff_cena)

        nova_largura = self._arrasto_largura_inicial
        nova_altura = self._arrasto_altura_inicial
        if rel_x != 0.5:
            nova_largura = max(_LARGURA_MINIMA_MM, abs(diff_local.x()))
        if rel_y != 0.5:
            nova_altura = max(_ALTURA_MINIMA_MM, abs(diff_local.y()))

        origem_nova = QPointF(nova_largura / 2, nova_altura / 2)
        ponto_local_novo = QPointF((1 - rel_x) * nova_largura, (1 - rel_y) * nova_altura)
        rotacao = QTransform().rotate(self._arrasto_angulo_inicial)
        nova_pos = self._arrasto_oposto_cena - origem_nova - rotacao.map(ponto_local_novo - origem_nova)

        self.prepareGeometryChange()
        self._largura = nova_largura
        self._altura = nova_altura
        self.setTransformOriginPoint(origem_nova)
        self.setPos(nova_pos)
        self.update()
        self.geometria_alterada.emit()

    # ── Rotacionar ───────────────────────────────────────────────────
    def _girar_para(self, ponto_cena: QPointF) -> None:
        delta = ponto_cena - self._arrasto_centro_cena
        angulo_atual = math.degrees(math.atan2(delta.y(), delta.x()))
        variacao = angulo_atual - self._arrasto_angulo_mouse_inicial
        self.setRotation(self._arrasto_angulo_inicial + variacao)
        self.geometria_alterada.emit()


def _distancia(a: QPointF, b: QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())


class GrupoMockup(ElementoMockup):
    """Contêiner de elementos agrupados — se comporta como um elemento
    normal (mover/redimensionar/rotacionar tudo junto, ver
    `_redimensionar_para` sobrescrito abaixo pra também escalar os
    filhos), mas o conteúdo visível são os próprios elementos-filho
    (viram filhos deste item via `setParentItem`, o Qt já desenha e
    transforma eles automaticamente dentro do grupo)."""

    def __init__(self, elementos: list[ElementoMockup], parent: QGraphicsItem | None = None) -> None:
        super().__init__(largura=_LARGURA_MINIMA_MM, altura=_ALTURA_MINIMA_MM, parent=parent)
        self._elementos: list[ElementoMockup] = []
        if elementos:
            self._agrupar(elementos)

    @property
    def elementos(self) -> list[ElementoMockup]:
        return list(self._elementos)

    def _agrupar(self, elementos: list[ElementoMockup]) -> None:
        cena = elementos[0].scene()
        rect_cena = elementos[0].sceneBoundingRect()
        for el in elementos[1:]:
            rect_cena = rect_cena.united(el.sceneBoundingRect())

        self.setRotation(0)
        self.prepareGeometryChange()
        self._largura = max(_LARGURA_MINIMA_MM, rect_cena.width())
        self._altura = max(_ALTURA_MINIMA_MM, rect_cena.height())
        self.setTransformOriginPoint(self._largura / 2, self._altura / 2)
        if cena is not None:
            cena.addItem(self)
        self.setPos(rect_cena.topLeft())

        for el in elementos:
            pos_relativa = el.scenePos() - rect_cena.topLeft()
            el.setSelected(False)
            el.setParentItem(self)
            el.setPos(pos_relativa)
            self._elementos.append(el)

    def desagrupar(self) -> list[ElementoMockup]:
        """Devolve os filhos pro nível da cena, preservando posição/
        rotação absolutas, e remove este grupo (vazio) da cena."""
        cena = self.scene()
        elementos = list(self._elementos)
        for el in elementos:
            pos_absoluta = el.scenePos()
            rotacao_absoluta = el.rotation() + self.rotation()
            el.setParentItem(None)
            if cena is not None:
                cena.addItem(el)
            el.setPos(pos_absoluta)
            el.setRotation(rotacao_absoluta)
            el.setSelected(True)
        self._elementos.clear()
        if cena is not None:
            cena.removeItem(self)
        return elementos

    def _redimensionar_para(self, ponto_cena: QPointF) -> None:
        largura_antes = self._largura
        altura_antes = self._altura
        super()._redimensionar_para(ponto_cena)
        fator_x = self._largura / largura_antes if largura_antes else 1.0
        fator_y = self._altura / altura_antes if altura_antes else 1.0
        if fator_x == 1.0 and fator_y == 1.0:
            return
        for el in self._elementos:
            el.setPos(el.pos().x() * fator_x, el.pos().y() * fator_y)
            el.definir_tamanho(el.largura * fator_x, el.altura * fator_y)

    def _pintar_conteudo(self, painter: QPainter) -> None:
        pass  # o conteúdo visível são os próprios filhos — o Qt já desenha eles
