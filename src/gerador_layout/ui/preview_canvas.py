"""Canvas 2D nativo do layout — substitui a necessidade de abrir o
CorelDRAW (ou qualquer outro programa externo) só para conferir o desenho.

Usa QGraphicsView/QGraphicsScene, que já resolve zoom e pan de graça e é
o jeito padrão de fazer canvas técnico (estilo CAD) em Qt.

A cota de dimensões é desenhada como um painel HTML flutuante por cima do
canvas (não faz parte da cena/zoom) — assim o texto tem sempre o mesmo
tamanho em tela, não importa o quão pequena ou grande seja a caixa, e
nunca mais "explode" de tamanho numa caixa minúscula.

A legenda de cores é um widget à parte (`PainelLegendaCores`, ver mais
abaixo), montado por fora do canvas em `main_window.py` — assim ela nunca
sobrepõe o desenho, ao contrário do painel de dimensão (que é pequeno e
fica num canto, sem esse problema).

A pré-visualização segue o mesmo padrão dos arquivos exportados (ver
`exportacao.py`/`corel_bridge.py`): tudo preto, só o vinco tracejado —
assim o que aparece em tela é exatamente o que sai no arquivo final, sem
diferenças pra explicar.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ..models import CorImpressao, LayoutCaixa, TipoLinha
from ..paineis import Painel
from .estilo import Cor
from .mockup_itens import ElementoMockup, GrupoMockup

# Cor das linhas técnicas na pré-visualização: a cor de texto do tema
# (`Cor.TEXTO`), não preto fixo — em tema escuro, "preto" literal
# desapareceria contra o fundo escuro do canvas. `Cor.TEXTO` já é claro
# no tema escuro e escuro no tema claro, então acompanha automaticamente.
_COR_LINHA = QColor(Cor.TEXTO)
_ESTILO_POR_TIPO: dict[TipoLinha, tuple[QColor, Qt.PenStyle, float]] = {
    TipoLinha.CORTE: (_COR_LINHA, Qt.PenStyle.SolidLine, 0.6),
    TipoLinha.VINCO: (_COR_LINHA, Qt.PenStyle.DashLine, 0.5),
    TipoLinha.CORTE_SERRA: (_COR_LINHA, Qt.PenStyle.SolidLine, 0.6),
    TipoLinha.MEIO_CORTE: (_COR_LINHA, Qt.PenStyle.SolidLine, 0.5),
    TipoLinha.DOBRA: (_COR_LINHA, Qt.PenStyle.SolidLine, 0.4),
}

_ZOOM_MINIMO = 0.05
_ZOOM_MAXIMO = 40.0

# Fundo do canvas: um branco liso incomoda a vista numa área grande (era
# a reclamação) e não lê como área de desenho técnico. Uma grade bem sutil
# de 10mm resolve as duas coisas — quebra a monotonia e ainda funciona
# como referência visual de escala. Traço fino/cosmetic (não escala
# espessura com o zoom) e cor quase invisível de propósito: é textura de
# fundo, não pode competir com as linhas do próprio layout. Vem de
# `Cor` (ver estilo.py) pra também inverter certo no tema escuro.
_COR_FUNDO_CANVAS = QColor(*Cor.CANVAS_FUNDO_RGB)
_COR_GRADE = QColor(*Cor.CANVAS_GRADE_RGBA)
_PASSO_GRADE_MM = 10.0

_r, _g, _b, _a = Cor.PAINEL_FLUTUANTE_RGBA
_ESTILO_PAINEL = (
    f"background: rgba({_r}, {_g}, {_b}, {_a});"
    f"border: 1px solid {Cor.BORDA};"
    "border-radius: 6px;"
    "padding: 4px 8px;"
    "font-size: 12px;"
)


def _cor_texto_legivel(r: int, g: int, b: int) -> QColor:
    """Usa a própria cor no texto (pedido do usuário: "vermelho" escrito em
    vermelho), mas escurece cores muito claras (ex.: amarelo) o mínimo
    necessário pra continuar legível sobre o fundo claro do canvas."""
    luminancia = 0.299 * r + 0.587 * g + 0.114 * b
    if luminancia > 200:
        fator = 0.65
        return QColor(int(r * fator), int(g * fator), int(b * fator))
    return QColor(r, g, b)


class PreviewCanvas(QGraphicsView):
    """Área de desenho do layout com zoom (roda do mouse) e pan (arrastar)."""

    zoom_alterado = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(_COR_FUNDO_CANVAS))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._grade_visivel = True

        self._zoom_atual = 1.0
        self._layout: LayoutCaixa | None = None

        # Itens da dieline (linhas calculadas) ficam à parte dos itens de
        # mockup (adicionados/editados pelo usuário) — `_redesenhar` só
        # mexe na primeira lista, senão recalcular as medidas apagaria
        # qualquer elemento de mockup já posicionado na cena.
        self._itens_dieline: list[QGraphicsItem] = []
        self._modo_mockup = False
        self._elementos_mockup: list[ElementoMockup] = []

        # Painéis (faces) da caixa atual — só pra desenhar a grade encaixada
        # em cada face (ver `drawBackground`), não pra recorte/seleção.
        self._paineis: list[Painel] = []

        # Pan com o botão do meio (scroll-click) — funciona nos dois modos
        # (Dieline E Layout), diferente do `ScrollHandDrag` (arrastar com o
        # botão esquerdo), que só existe fora do modo mockup, porque lá o
        # botão esquerdo já é usado pra mover/selecionar elemento.
        self._panorama_ativo = False
        self._panorama_ultimo_ponto = QPointF()

        # Painel fixo (HUD) por cima da cena — não escala com o zoom, então
        # nunca "explode" de tamanho numa caixa pequena.
        self._painel_dimensao = QLabel(self)
        self._painel_dimensao.setObjectName("rotuloTecnico")
        self._painel_dimensao.setStyleSheet(
            _ESTILO_PAINEL + f"color: {Cor.TEXTO}; font-weight: 700; font-size: 13px;"
        )
        self._painel_dimensao.hide()

    # ── API pública ─────────────────────────────────────────────────
    @property
    def zoom_atual(self) -> float:
        return self._zoom_atual

    @property
    def cena(self) -> QGraphicsScene:
        """Exposto para o exportador (SVG/PDF/JPG) renderizar a cena."""
        return self._scene

    @property
    def layout_atual(self) -> LayoutCaixa | None:
        return self._layout

    def definir_layout(self, layout: LayoutCaixa | None) -> None:
        self._layout = layout
        self._redesenhar()
        self.ajustar_a_tela()

    def ajustar_a_tela(self) -> None:
        if not self._scene.items():
            return
        self.resetTransform()
        self._zoom_atual = 1.0
        margem = 20
        rect = self._scene.itemsBoundingRect().adjusted(-margem, -margem, margem, margem)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_atual = self.transform().m11()
        self.zoom_alterado.emit(self._zoom_atual)

    # ── Fundo ───────────────────────────────────────────────────────
    def definir_grade_visivel(self, visivel: bool) -> None:
        self._grade_visivel = visivel
        self.viewport().update()

    def definir_paineis(self, paineis: list[Painel]) -> None:
        """Faces da caixa atual (ver `paineis.py`) — usadas só pra
        encaixar a grade de fundo em cada face (grade própria, alinhada
        ao canto de cada painel, em vez de uma grade só cobrindo o
        canvas inteiro sem relação com onde as faces realmente estão)."""
        self._paineis = list(paineis)
        self.viewport().update()

    def drawBackground(self, painter, rect) -> None:  # noqa: N802
        painter.fillRect(rect, _COR_FUNDO_CANVAS)
        if not self._grade_visivel:
            return

        pen = QPen(_COR_GRADE)
        pen.setCosmetic(True)  # traço de 1px na tela, não 1mm — em qualquer zoom
        painter.setPen(pen)

        if self._paineis:
            self._desenhar_grade_por_painel(painter, rect, pen)
        else:
            self._desenhar_grade_continua(painter, rect)

    def _desenhar_grade_continua(self, painter, rect) -> None:
        """Grade contínua cobrindo todo o canvas — usada só antes de
        calcular qualquer layout (sem painel nenhum ainda pra encaixar
        a grade)."""
        x = math.floor(rect.left() / _PASSO_GRADE_MM) * _PASSO_GRADE_MM
        while x < rect.right():
            painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
            x += _PASSO_GRADE_MM

        y = math.floor(rect.top() / _PASSO_GRADE_MM) * _PASSO_GRADE_MM
        while y < rect.bottom():
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
            y += _PASSO_GRADE_MM

    def _desenhar_grade_por_painel(self, painter, rect, pen) -> None:
        """Uma grade por face, começando do canto de CADA painel (não de
        um (0,0) global) — assim a grade sempre marca "quão longe da
        borda desta face" em vez de uma origem arbitrária do desenho
        inteiro, que é o que realmente ajuda a posicionar arte numa face
        específica."""
        for painel in self._paineis:
            area = QRectF(painel.x1, painel.y1, painel.largura, painel.altura)
            if not area.intersects(rect):
                continue
            painter.save()
            painter.setClipRect(area)
            painter.setPen(pen)
            x = painel.x1
            while x <= painel.x2:
                painter.drawLine(QLineF(x, painel.y1, x, painel.y2))
                x += _PASSO_GRADE_MM
            y = painel.y1
            while y <= painel.y2:
                painter.drawLine(QLineF(painel.x1, y, painel.x2, y))
                y += _PASSO_GRADE_MM
            painter.restore()

    # ── Zoom com a roda do mouse ───────────────────────────────────
    def wheelEvent(self, event) -> None:  # noqa: N802 (nome exigido pelo Qt)
        fator = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        novo_zoom = self._zoom_atual * fator
        if not (_ZOOM_MINIMO <= novo_zoom <= _ZOOM_MAXIMO):
            return
        self.scale(fator, fator)
        self._zoom_atual = novo_zoom
        self.zoom_alterado.emit(self._zoom_atual)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)
        self.ajustar_a_tela()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reposicionar_paineis()

    # ── Pan com o botão do meio ────────────────────────────────────
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panorama_ativo = True
            self._panorama_ultimo_ponto = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._panorama_ativo:
            ponto = event.position()
            delta = ponto - self._panorama_ultimo_ponto
            self._panorama_ultimo_ponto = ponto
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self._panorama_ativo:
            self._panorama_ativo = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ── Painel fixo (HUD) ───────────────────────────────────────────
    def _reposicionar_paineis(self) -> None:
        margem = 8
        if self._painel_dimensao.isVisible():
            self._painel_dimensao.adjustSize()
            self._painel_dimensao.move(margem, self.height() - self._painel_dimensao.height() - margem)

    def _atualizar_painel_dimensao(self) -> None:
        assert self._layout is not None
        self._painel_dimensao.setText(
            f"{self._layout.largura_total:.1f} × {self._layout.altura_total:.1f} mm"
        )
        self._painel_dimensao.show()

    # ── Desenho ─────────────────────────────────────────────────────
    def _redesenhar(self) -> None:
        for item in self._itens_dieline:
            self._scene.removeItem(item)
        self._itens_dieline.clear()

        if self._layout is None or not self._layout.linhas:
            texto = QGraphicsSimpleTextItem("Informe as medidas para gerar a pré-visualização.")
            texto.setBrush(QBrush(QColor(150, 150, 160)))
            self._scene.addItem(texto)
            self._itens_dieline.append(texto)
            self._painel_dimensao.hide()
            return

        self._desenhar_linhas_tecnicas()
        self._atualizar_painel_dimensao()
        self._reposicionar_paineis()

    def _desenhar_linhas_tecnicas(self) -> None:
        assert self._layout is not None
        for linha in self._layout.linhas:
            cor, estilo, largura = _ESTILO_POR_TIPO.get(
                linha.tipo, (QColor(0, 0, 0), Qt.PenStyle.SolidLine, 0.5)
            )
            pen = QPen(cor, largura, estilo)
            pen.setCosmetic(True)  # espessura constante independente do zoom
            item = QGraphicsLineItem(QLineF(linha.x1, linha.y1, linha.x2, linha.y2))
            item.setPen(pen)
            item.setData(0, linha.tipo)  # lido por `_PenasExportacao` em exportacao.py
            self._scene.addItem(item)
            self._itens_dieline.append(item)

    # ── Modo mockup (seleção/edição de elementos, ver mockup_itens.py) ─
    def definir_modo_mockup(self, ativo: bool) -> None:
        """Liga/desliga a edição de mockup. Desligado (padrão): arrastar
        no canvas move a visão (pan), igual sempre foi. Ligado: clicar
        num elemento seleciona/move ELE, e arrastar numa área vazia abre
        uma seleção retangular — troca de `DragMode` resolve os dois
        comportamentos de graça, o Qt já entende a diferença entre
        "clique caiu num item" e "clique caiu vazio"."""
        self._modo_mockup = ativo
        self.setDragMode(
            QGraphicsView.DragMode.RubberBandDrag if ativo else QGraphicsView.DragMode.ScrollHandDrag
        )
        if not ativo:
            for item in self._scene.selectedItems():
                item.setSelected(False)

    @property
    def modo_mockup(self) -> bool:
        return self._modo_mockup

    @property
    def elementos_mockup(self) -> list[ElementoMockup]:
        return list(self._elementos_mockup)

    def adicionar_elemento_mockup(self, elemento: ElementoMockup, pos: QPointF | None = None) -> None:
        self._scene.addItem(elemento)
        if pos is not None:
            elemento.setPos(pos)
        self._elementos_mockup.append(elemento)

    def agrupar_selecionados(self) -> GrupoMockup | None:
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if len(selecionados) < 2:
            return None
        for el in selecionados:
            if el in self._elementos_mockup:
                self._elementos_mockup.remove(el)
        grupo = GrupoMockup(selecionados)
        grupo.setSelected(True)
        self._elementos_mockup.append(grupo)
        return grupo

    def desagrupar_selecionados(self) -> None:
        grupos = [it for it in self._scene.selectedItems() if isinstance(it, GrupoMockup)]
        for grupo in grupos:
            if grupo in self._elementos_mockup:
                self._elementos_mockup.remove(grupo)
            self._elementos_mockup.extend(grupo.desagrupar())

    def remover_selecionados(self) -> None:
        for item in list(self._scene.selectedItems()):
            if isinstance(item, ElementoMockup):
                self._scene.removeItem(item)
                if item in self._elementos_mockup:
                    self._elementos_mockup.remove(item)

    def trazer_para_frente(self) -> None:
        """Ordem de empilhamento — só entre elementos de mockup no nível
        raiz da cena (`self._elementos_mockup`); um elemento dentro de um
        `GrupoMockup` tem `zValue()` relativa só aos irmãos do mesmo
        grupo, não faz sentido comparar com o resto da cena."""
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if not selecionados:
            return
        maior = max((it.zValue() for it in self._elementos_mockup), default=0.0)
        for item in selecionados:
            maior += 1
            item.setZValue(maior)

    def enviar_para_tras(self) -> None:
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if not selecionados:
            return
        menor = min((it.zValue() for it in self._elementos_mockup), default=0.0)
        for item in selecionados:
            menor -= 1
            item.setZValue(menor)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._modo_mockup:
            if event.key() == Qt.Key.Key_Delete:
                self.remover_selecionados()
                return
            eh_ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            eh_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if eh_ctrl and event.key() == Qt.Key.Key_G:
                self.desagrupar_selecionados() if eh_shift else self.agrupar_selecionados()
                return
            if eh_ctrl and event.key() == Qt.Key.Key_Home:
                self.trazer_para_frente()
                return
            if eh_ctrl and event.key() == Qt.Key.Key_End:
                self.enviar_para_tras()
                return
        super().keyPressEvent(event)


class PainelLegendaCores(QWidget):
    """Legenda de cores de impressão, numa linha reta de widgets reais
    (bolinha + nome lado a lado, sem quebra) — colocada acima do canvas
    pelo `main_window.py`, fora da área de desenho, pra nunca sobrepor o
    layout."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 6)
        self._layout.setSpacing(16)
        self.hide()

    def definir_cores(self, cores: list[CorImpressao]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not cores:
            self.hide()
            return

        titulo = QLabel("CORES:")
        titulo.setStyleSheet(f"font-weight: 700; color: {Cor.TEXTO}; font-size: 12px;")
        self._layout.addWidget(titulo)

        for cor in cores:
            self._layout.addWidget(self._criar_item(cor))

        self._layout.addStretch(1)
        self.show()

    def _criar_item(self, cor: CorImpressao) -> QWidget:
        item = QWidget()
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)

        bolinha = QLabel()
        bolinha.setFixedSize(10, 10)
        bolinha.setStyleSheet(
            f"background: rgb({cor.r},{cor.g},{cor.b}); border-radius: 5px; "
            "border: 1px solid rgba(0, 0, 0, 60);"
        )
        item_layout.addWidget(bolinha)

        cor_legivel = _cor_texto_legivel(cor.r, cor.g, cor.b)
        nome = QLabel(cor.nome)
        nome.setStyleSheet(
            f"color: rgb({cor_legivel.red()},{cor_legivel.green()},{cor_legivel.blue()}); "
            "font-weight: 600; font-size: 12px;"
        )
        item_layout.addWidget(nome)

        return item
