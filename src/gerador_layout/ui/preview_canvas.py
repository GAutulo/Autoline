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
from enum import Enum, auto

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
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
from .mockup_reguas import GuiaCanvas


class FerramentaMockup(Enum):
    """Ferramenta ativa na tela de Layout — igual a qualquer CAD/vetorial
    de verdade: SELECIONAR é o ponteiro padrão (clicar/arrastar move e
    seleciona, como sempre foi); as outras trocam o que um clique/arrasto
    no canvas vazio faz (ver `PreviewCanvas.mousePressEvent` etc.), pra
    criar o elemento DIRETO no lugar clicado — em vez do fluxo antigo
    (clicar um botão de barra sempre cria no centro da tela, editar
    depois pela barra de propriedades)."""

    SELECIONAR = auto()
    TEXTO = auto()
    RETANGULO = auto()
    LINHA = auto()
    CONTA_GOTAS = auto()
    MEDIR = auto()
    ELIPSE = auto()
    POLIGONO = auto()
    CALLOUT = auto()
    TABELA = auto()
    ACABAMENTO = auto()


# Ferramentas que desenham por clique+arrasto de um retângulo (a forma
# final varia — elipse, polígono, área de acabamento — mas o GESTO de
# criação é sempre o mesmo, então tratamos juntas na hora de decidir
# qual sinal emitir em `_finalizar_criacao`).
_FERRAMENTAS_RETANGULO_ARRASTO = {
    FerramentaMockup.RETANGULO,
    FerramentaMockup.ELIPSE,
    FerramentaMockup.POLIGONO,
    FerramentaMockup.ACABAMENTO,
}
# Ferramentas que nascem com um clique só, sem arrastar (igual TEXTO).
_FERRAMENTAS_CLIQUE_UNICO = {
    FerramentaMockup.TEXTO,
    FerramentaMockup.CONTA_GOTAS,
    FerramentaMockup.CALLOUT,
    FerramentaMockup.TABELA,
}

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

_DELTA_SETA_NUDGE: dict[Qt.Key, QPointF] = {
    Qt.Key.Key_Left: QPointF(-1, 0),
    Qt.Key.Key_Right: QPointF(1, 0),
    Qt.Key.Key_Up: QPointF(0, -1),
    Qt.Key.Key_Down: QPointF(0, 1),
}

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
    # Emitidos quando uma ferramenta de criação termina um gesto de
    # clique/arrasto no canvas vazio (ver `_finalizar_criacao` abaixo) —
    # o canvas só sabe a GEOMETRIA (onde/tamanho); quem monta o elemento
    # de verdade (cor de tinta padrão etc.) é `main_window.py`.
    retangulo_desenhado = Signal(QRectF)
    linha_desenhada = Signal(QPointF, QPointF)
    texto_solicitado = Signal(QPointF)
    cor_amostrada = Signal(QColor)  # conta-gotas: cor de verdade sob o cursor no clique
    elipse_desenhada = Signal(QRectF)
    poligono_desenhado = Signal(QRectF)
    acabamento_desenhado = Signal(QRectF)
    callout_solicitado = Signal(QPointF)
    tabela_solicitada = Signal(QPointF)
    ferramenta_alterada = Signal(object)  # FerramentaMockup

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

        # Ferramenta ativa (ver `FerramentaMockup`) + estado do gesto de
        # criação em andamento (clique/arrasto pra desenhar um retângulo/
        # linha novos, ou clique único pra texto).
        self._ferramenta = FerramentaMockup.SELECIONAR
        self._criando = False
        self._ponto_inicial_criacao = QPointF()
        self._item_preview_criacao: QGraphicsItem | None = None

        # Área de transferência interna do app (Ctrl+C/Ctrl+V) — guarda
        # clones desconectados da cena, não referências aos itens de
        # verdade (ver `copiar_selecionados`).
        self._area_transferencia: list[ElementoMockup] = []

        # Encaixe (snap) — grade, bordas/centro de outros elementos, da
        # face e das guias (ver `_calcular_snap`).
        self._snap_ativo = True
        # Guias de verdade (réguas, ver `mockup_reguas.py`) — cada uma é
        # um `GuiaCanvas` na cena (arrastável/selecionável/removível como
        # qualquer item), não só um número numa lista.
        self._guias: list[GuiaCanvas] = []

        # Painel fixo (HUD) por cima da cena — não escala com o zoom, então
        # nunca "explode" de tamanho numa caixa pequena.
        self._painel_dimensao = QLabel(self)
        self._painel_dimensao.setObjectName("rotuloTecnico")
        self._painel_dimensao.setStyleSheet(
            _ESTILO_PAINEL + f"color: {Cor.TEXTO}; font-weight: 700; font-size: 13px;"
        )
        self._painel_dimensao.hide()

        # Leitura ao vivo da ferramenta de medida (ver `FerramentaMockup.MEDIR`)
        # — segue o cursor durante o arrasto, mesmo estilo do painel de
        # dimensão (fonte fixa em tela, não escala com o zoom).
        self._rotulo_medida = QLabel(self)
        self._rotulo_medida.setObjectName("rotuloTecnico")
        self._rotulo_medida.setStyleSheet(_ESTILO_PAINEL + f"color: {Cor.TEXTO}; font-weight: 700; font-size: 12px;")
        self._rotulo_medida.hide()

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
        # Duplo-clique num elemento (ex.: texto, ver `mockup_texto.py`)
        # tem tratamento próprio no item (editar inline) — só cai pro
        # "ajustar à tela" de conveniência quando o clique foi em área
        # vazia do canvas, senão os dois efeitos brigavam (editar texto
        # E mudar o zoom no mesmo clique).
        item = self.itemAt(event.pos())
        super().mouseDoubleClickEvent(event)
        if self._modo_mockup and item is not None:
            return
        self.ajustar_a_tela()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reposicionar_paineis()

    # ── Ferramenta ativa (ver `FerramentaMockup`) ──────────────────────
    @property
    def ferramenta_ativa(self) -> FerramentaMockup:
        return self._ferramenta

    def definir_ferramenta(self, ferramenta: FerramentaMockup) -> None:
        if self._criando:
            self._cancelar_criacao()
        if self._ferramenta == FerramentaMockup.MEDIR and ferramenta != FerramentaMockup.MEDIR:
            # Sair da ferramenta de medida limpa a última leitura — ela é
            # uma resposta pontual ("quanto é isso aqui?"), não uma
            # anotação permanente que devesse sobreviver à troca de
            # ferramenta.
            self._rotulo_medida.hide()
            if self._item_preview_criacao is not None:
                self._scene.removeItem(self._item_preview_criacao)
                self._item_preview_criacao = None
        self._ferramenta = ferramenta
        cursores = {
            FerramentaMockup.SELECIONAR: Qt.CursorShape.ArrowCursor,
            FerramentaMockup.TEXTO: Qt.CursorShape.IBeamCursor,
            FerramentaMockup.RETANGULO: Qt.CursorShape.CrossCursor,
            FerramentaMockup.LINHA: Qt.CursorShape.CrossCursor,
            FerramentaMockup.CONTA_GOTAS: Qt.CursorShape.PointingHandCursor,
            FerramentaMockup.MEDIR: Qt.CursorShape.CrossCursor,
            FerramentaMockup.ELIPSE: Qt.CursorShape.CrossCursor,
            FerramentaMockup.POLIGONO: Qt.CursorShape.CrossCursor,
            FerramentaMockup.ACABAMENTO: Qt.CursorShape.CrossCursor,
            FerramentaMockup.CALLOUT: Qt.CursorShape.IBeamCursor,
            FerramentaMockup.TABELA: Qt.CursorShape.CrossCursor,
        }
        self.setCursor(cursores[ferramenta])
        # Enquanto uma ferramenta de criação está ativa, arrastar no
        # canvas vazio desenha a forma nova, não seleciona por retângulo
        # nem move a visão — `NoDrag` evita que o `QGraphicsView` tente
        # fazer as duas coisas ao mesmo tempo.
        if ferramenta == FerramentaMockup.SELECIONAR:
            self.setDragMode(
                QGraphicsView.DragMode.RubberBandDrag if self._modo_mockup else QGraphicsView.DragMode.ScrollHandDrag
            )
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.ferramenta_alterada.emit(ferramenta)

    # ── Pan com o botão do meio + ferramentas de criação ───────────────
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panorama_ativo = True
            self._panorama_ultimo_ponto = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if (
            self._modo_mockup
            and self._ferramenta != FerramentaMockup.SELECIONAR
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._iniciar_criacao(event.pos())
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
        if self._criando:
            self._atualizar_criacao(event.pos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self._panorama_ativo:
            self._panorama_ativo = False
            self.unsetCursor()
            event.accept()
            return
        if self._criando and event.button() == Qt.MouseButton.LeftButton:
            self._finalizar_criacao(event.pos())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ── Gesto de criação (clique/arrasto com uma ferramenta ativa) ─────
    def _caneta_preview(self) -> QPen:
        caneta = QPen(QColor(Cor.PRIMARIA), 0.6, Qt.PenStyle.DashLine)
        caneta.setCosmetic(True)
        return caneta

    def _iniciar_criacao(self, pos_viewport) -> None:
        self._ponto_inicial_criacao = self.mapToScene(pos_viewport)
        if self._ferramenta == FerramentaMockup.CONTA_GOTAS:
            # Não precisa de arrasto — amostra na hora do clique.
            cor = self._amostrar_cor(pos_viewport)
            if cor.isValid():
                self.cor_amostrada.emit(cor)
            return
        if self._ferramenta in _FERRAMENTAS_CLIQUE_UNICO:
            # Texto/Callout/Tabela: um clique já basta pra nascer no
            # lugar certo (Texto/Callout entram direto em edição).
            sinais_clique_unico = {
                FerramentaMockup.TEXTO: self.texto_solicitado,
                FerramentaMockup.CALLOUT: self.callout_solicitado,
                FerramentaMockup.TABELA: self.tabela_solicitada,
            }
            sinais_clique_unico[self._ferramenta].emit(self._ponto_inicial_criacao)
            return
        if self._ferramenta == FerramentaMockup.MEDIR and self._item_preview_criacao is not None:
            # Começando uma medida nova por cima de uma anterior ainda
            # visível — limpa a antiga primeiro.
            self._scene.removeItem(self._item_preview_criacao)
            self._item_preview_criacao = None

        self._criando = True
        if self._ferramenta in _FERRAMENTAS_RETANGULO_ARRASTO:
            self._item_preview_criacao = QGraphicsRectItem()
        elif self._ferramenta in (FerramentaMockup.LINHA, FerramentaMockup.MEDIR):
            self._item_preview_criacao = QGraphicsLineItem()
        else:
            self._criando = False
            return
        self._item_preview_criacao.setPen(self._caneta_preview())
        self._scene.addItem(self._item_preview_criacao)

        if self._ferramenta == FerramentaMockup.MEDIR:
            self._rotulo_medida.setText("0,0 mm")
            self._rotulo_medida.adjustSize()
            self._rotulo_medida.move(pos_viewport.x() + 14, pos_viewport.y() - self._rotulo_medida.height() - 10)
            self._rotulo_medida.show()

    def _atualizar_criacao(self, pos_viewport) -> None:
        atual = self.mapToScene(pos_viewport)
        if self._ferramenta in _FERRAMENTAS_RETANGULO_ARRASTO and isinstance(self._item_preview_criacao, QGraphicsRectItem):
            self._item_preview_criacao.setRect(QRectF(self._ponto_inicial_criacao, atual).normalized())
        elif isinstance(self._item_preview_criacao, QGraphicsLineItem):
            linha = QLineF(self._ponto_inicial_criacao, atual)
            self._item_preview_criacao.setLine(linha)
            if self._ferramenta == FerramentaMockup.MEDIR:
                self._rotulo_medida.setText(f"{linha.length():.1f} mm")
                self._rotulo_medida.adjustSize()
                self._rotulo_medida.move(pos_viewport.x() + 14, pos_viewport.y() - self._rotulo_medida.height() - 10)

    def _finalizar_criacao(self, pos_viewport) -> None:
        self._criando = False
        if self._ferramenta == FerramentaMockup.MEDIR:
            # Fica visível como leitura até a próxima medida ou trocar de
            # ferramenta (ver `definir_ferramenta`) — não é um elemento
            # criado, só uma resposta pontual, não precisa confirmação.
            return
        if self._item_preview_criacao is not None:
            self._scene.removeItem(self._item_preview_criacao)
            self._item_preview_criacao = None

        atual = self.mapToScene(pos_viewport)
        # Arrasto mínimo pra não criar uma forma de 0×0 num clique seco
        # sem querer arrastar de verdade (o gesto mais comum de quem
        # ainda tá aprendendo a ferramenta).
        if self._ferramenta in _FERRAMENTAS_RETANGULO_ARRASTO:
            rect = QRectF(self._ponto_inicial_criacao, atual).normalized()
            if rect.width() < 2.0 or rect.height() < 2.0:
                return
            sinais_arrasto = {
                FerramentaMockup.RETANGULO: self.retangulo_desenhado,
                FerramentaMockup.ELIPSE: self.elipse_desenhada,
                FerramentaMockup.POLIGONO: self.poligono_desenhado,
                FerramentaMockup.ACABAMENTO: self.acabamento_desenhado,
            }
            sinais_arrasto[self._ferramenta].emit(rect)
        elif self._ferramenta == FerramentaMockup.LINHA:
            if QLineF(self._ponto_inicial_criacao, atual).length() >= 2.0:
                self.linha_desenhada.emit(self._ponto_inicial_criacao, atual)

    def _cancelar_criacao(self) -> None:
        self._criando = False
        if self._item_preview_criacao is not None:
            self._scene.removeItem(self._item_preview_criacao)
            self._item_preview_criacao = None
        self._rotulo_medida.hide()

    def _amostrar_cor(self, pos_viewport) -> QColor:
        """Cor de verdade sob o cursor, lida do que está renderizado na
        tela (não do modelo/dado) — inclui imagem/logo importado, texto,
        qualquer coisa visível. `viewport().grab()` é exatamente o mesmo
        pixel que a pessoa está olhando, então a coordenada do clique bate
        direto sem nenhuma conta de transform."""
        imagem = self.viewport().grab().toImage()
        if 0 <= pos_viewport.x() < imagem.width() and 0 <= pos_viewport.y() < imagem.height():
            return imagem.pixelColor(pos_viewport.x(), pos_viewport.y())
        return QColor()

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
        # Sempre volta pro ponteiro ao trocar de tela — solta qualquer
        # ferramenta de criação que tivesse ficado ativa (e já ajusta o
        # `DragMode`/cursor certo pro modo novo, ver `definir_ferramenta`).
        self.definir_ferramenta(FerramentaMockup.SELECIONAR)
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
        self._registrar_elemento_mockup(elemento)

    def _registrar_elemento_mockup(self, elemento: ElementoMockup) -> None:
        """Cadastra o elemento em `_elementos_mockup` E liga o snap nele
        — ponto único pra isso, senão é fácil esquecer de ligar o snap
        num caminho de criação novo (duplicar, colar, desagrupar...) e o
        elemento ficar "mudo" pro encaixe sem ninguém notar na hora."""
        self._elementos_mockup.append(elemento)
        elemento.definir_calculador_snap(self._calcular_snap)

    def definir_snap_ativo(self, ativo: bool) -> None:
        self._snap_ativo = ativo

    def adicionar_guia(self, orientacao: str, posicao_mm: float) -> GuiaCanvas:
        guia = GuiaCanvas(orientacao, posicao_mm)
        self._scene.addItem(guia)
        self._guias.append(guia)
        return guia

    def remover_guia(self, guia: GuiaCanvas) -> None:
        if guia in self._guias:
            self._guias.remove(guia)
        self._scene.removeItem(guia)

    _LIMIAR_SNAP_MM = 3.0

    def _calcular_snap(self, elemento: ElementoMockup, pos_proposta: QPointF) -> QPointF:
        """Chamado pelo `mouseReleaseEvent` do elemento (ver
        `mockup_itens.py`) assim que um arrasto pelo corpo termina — testa
        a borda esquerda, o centro e a borda direita do elemento (na
        posição onde ele acabou de ser largado) contra grade/outros
        elementos/face/guias, e "gruda" no alvo mais próximo dentro do
        limiar; fora do limiar, a posição passa sem alteração. Eixos X e Y
        são independentes — pode grudar só num, só no outro, nos dois, ou
        em nenhum. Só no soltar (não durante o arrasto) de propósito — ver
        o comentário em `ElementoMockup.mouseReleaseEvent`."""
        if not self._snap_ativo:
            return pos_proposta

        largura, altura = elemento.largura, elemento.altura
        bordas_x = (pos_proposta.x(), pos_proposta.x() + largura / 2, pos_proposta.x() + largura)
        bordas_y = (pos_proposta.y(), pos_proposta.y() + altura / 2, pos_proposta.y() + altura)

        ajuste_x = self._melhor_ajuste_snap(bordas_x, self._alvos_snap_x(elemento))
        ajuste_y = self._melhor_ajuste_snap(bordas_y, self._alvos_snap_y(elemento))
        return QPointF(pos_proposta.x() + ajuste_x, pos_proposta.y() + ajuste_y)

    def _melhor_ajuste_snap(self, bordas: tuple[float, float, float], alvos: list[float]) -> float:
        candidatos = list(alvos)
        if self._grade_visivel:
            # Grade só participa do encaixe se estiver visível — senão a
            # peça "gruda" numa referência que a pessoa nem está vendo,
            # o que pareceria um bug ("por que não solta exatamente onde
            # eu larguei o mouse?").
            candidatos.extend(round(borda / _PASSO_GRADE_MM) * _PASSO_GRADE_MM for borda in bordas)

        melhor_ajuste = 0.0
        menor_distancia = self._LIMIAR_SNAP_MM
        for borda in bordas:
            for alvo in candidatos:
                distancia = abs(borda - alvo)
                if distancia < menor_distancia:
                    menor_distancia = distancia
                    melhor_ajuste = alvo - borda
        return melhor_ajuste

    def _alvos_snap_x(self, elemento: ElementoMockup) -> list[float]:
        alvos = [g.posicao for g in self._guias if g.orientacao == "v"]
        for outro in self._elementos_mockup:
            if outro is elemento:
                continue
            alvos.extend((outro.pos().x(), outro.pos().x() + outro.largura / 2, outro.pos().x() + outro.largura))
        painel = self._painel_do_elemento(elemento)
        if painel is not None:
            alvos.extend((painel.x1, (painel.x1 + painel.x2) / 2, painel.x2))
        return alvos

    def _alvos_snap_y(self, elemento: ElementoMockup) -> list[float]:
        alvos = [g.posicao for g in self._guias if g.orientacao == "h"]
        for outro in self._elementos_mockup:
            if outro is elemento:
                continue
            alvos.extend((outro.pos().y(), outro.pos().y() + outro.altura / 2, outro.pos().y() + outro.altura))
        painel = self._painel_do_elemento(elemento)
        if painel is not None:
            alvos.extend((painel.y1, (painel.y1 + painel.y2) / 2, painel.y2))
        return alvos

    def _painel_do_elemento(self, elemento: ElementoMockup) -> Painel | None:
        if elemento.painel_id is None:
            return None
        return next((p for p in self._paineis if p.id == elemento.painel_id), None)

    def agrupar_selecionados(self) -> GrupoMockup | None:
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if len(selecionados) < 2:
            return None
        for el in selecionados:
            if el in self._elementos_mockup:
                self._elementos_mockup.remove(el)
        grupo = GrupoMockup(selecionados)
        grupo.setSelected(True)
        self._registrar_elemento_mockup(grupo)
        return grupo

    def desagrupar_selecionados(self) -> None:
        grupos = [it for it in self._scene.selectedItems() if isinstance(it, GrupoMockup)]
        for grupo in grupos:
            if grupo in self._elementos_mockup:
                self._elementos_mockup.remove(grupo)
            for filho in grupo.desagrupar():
                self._registrar_elemento_mockup(filho)

    def remover_selecionados(self) -> None:
        for item in list(self._scene.selectedItems()):
            if isinstance(item, ElementoMockup):
                self._scene.removeItem(item)
                if item in self._elementos_mockup:
                    self._elementos_mockup.remove(item)
            elif isinstance(item, GuiaCanvas):
                self.remover_guia(item)

    # ── Duplicar / copiar-colar (Ctrl+D, Ctrl+C, Ctrl+V) ────────────────
    _PASSO_DUPLICAR_MM = 6.0

    def duplicar_selecionados(self) -> list[ElementoMockup]:
        """Ctrl+D — clona e desloca na hora, já selecionando o clone (não
        o original), pra continuar arrastando/ajustando ele direto. Sem
        passar pela área de transferência: Ctrl+D é "mais um igual, aqui
        do lado", não "guardar pra colar depois em outro lugar/momento"
        (isso é o que Ctrl+C/V fazem, ver abaixo)."""
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if not selecionados:
            return []
        clones = []
        for it in selecionados:
            it.setSelected(False)
            clone = it.clonar()
            clone.setPos(clone.pos() + QPointF(self._PASSO_DUPLICAR_MM, self._PASSO_DUPLICAR_MM))
            self._scene.addItem(clone)
            self._registrar_elemento_mockup(clone)
            clone.setSelected(True)
            clones.append(clone)
        return clones

    def copiar_selecionados(self) -> None:
        """Ctrl+C — tira uma "foto" (clone desconectado da cena) de cada
        selecionado agora; Ctrl+V mais tarde parte sempre desse instante,
        não do que aconteceu com o elemento original depois (mesmo
        princípio de copiar/colar de qualquer editor: colar não deveria
        refletir edições feitas DEPOIS da cópia)."""
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if selecionados:
            self._area_transferencia = [it.clonar() for it in selecionados]

    def colar(self) -> list[ElementoMockup]:
        if not self._area_transferencia:
            return []
        for it in self._scene.selectedItems():
            it.setSelected(False)
        clones = []
        for original in self._area_transferencia:
            clone = original.clonar()
            clone.setPos(clone.pos() + QPointF(self._PASSO_DUPLICAR_MM, self._PASSO_DUPLICAR_MM))
            self._scene.addItem(clone)
            self._registrar_elemento_mockup(clone)
            clone.setSelected(True)
            clones.append(clone)
        # Um Ctrl+V repetido parte do último colado, não sempre do mesmo
        # ponto — cada colagem em cascata fica um pouco mais deslocada da
        # anterior, igual Word/Illustrator, em vez de empilhar tudo exatamente
        # no mesmo lugar toda vez que aperta de novo.
        self._area_transferencia = clones
        return clones

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
            if event.key() == Qt.Key.Key_Escape:
                # Mesma tecla resolve os 2 casos de "sair do que eu tava
                # fazendo": cancela um desenho em andamento (arrastando
                # um retângulo/linha), ou solta a ferramenta e volta pro
                # ponteiro — igual qualquer CAD/vetorial.
                if self._criando:
                    self._cancelar_criacao()
                else:
                    self.definir_ferramenta(FerramentaMockup.SELECIONAR)
                return
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
            if eh_ctrl and event.key() == Qt.Key.Key_D:
                self.duplicar_selecionados()
                return
            if eh_ctrl and event.key() == Qt.Key.Key_C:
                self.copiar_selecionados()
                return
            if eh_ctrl and event.key() == Qt.Key.Key_V:
                self.colar()
                return
            if not eh_ctrl and event.key() in _DELTA_SETA_NUDGE:
                # Mover fino pelo teclado — 1mm por toque, 10mm com Shift
                # (mesmo padrão de qualquer CAD: mouse pro grosso, seta
                # pro ajuste fino de precisão). Só intercepta a seta
                # quando tem elemento selecionado — sem seleção, a seta
                # continua rolando a view (comportamento nativo de
                # QGraphicsView, não mexi nisso).
                selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
                if selecionados:
                    passo = 10.0 if eh_shift else 1.0
                    delta = _DELTA_SETA_NUDGE[event.key()] * passo
                    for item in selecionados:
                        item.setPos(item.pos() + delta)
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
