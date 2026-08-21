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
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
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
from .mockup_itens import ElementoMockup, GrupoMockup, _estado_recursivo
from .mockup_reguas import GuiaCanvas
from .painel_propriedades_mockup import NOME_TIPO_ELEMENTO


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
    SIMBOLO = auto()
    LACO_SELECAO = auto()
    MOVER_PRECISO = auto()


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
    FerramentaMockup.SIMBOLO,
}

# Ferramentas de CRIAÇÃO de geometria (não seleção/leitura/utilidade) —
# são as que Endpoint Offset Mode (Alt+clique, ver `_PainelOffsetEndpoint`)
# se aplica. Exclui de propósito CONTA_GOTAS/MEDIR (não criam elemento) e
# LACO_SELECAO/MOVER_PRECISO (são seleção/utilidade, não geometria).
_FERRAMENTAS_CRIACAO_GEOMETRIA = _FERRAMENTAS_RETANGULO_ARRASTO | {
    FerramentaMockup.LINHA,
    FerramentaMockup.TEXTO,
    FerramentaMockup.CALLOUT,
    FerramentaMockup.TABELA,
    FerramentaMockup.SIMBOLO,
}

# Cursor por ferramenta — módulo-level (não muda por instância) pra dar
# pra reusar tanto em `definir_ferramenta` quanto ao restaurar o cursor
# depois de um pan com o botão do meio (ver `mouseReleaseEvent`).
_CURSOR_POR_FERRAMENTA = {
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
    FerramentaMockup.SIMBOLO: Qt.CursorShape.CrossCursor,
    FerramentaMockup.LACO_SELECAO: Qt.CursorShape.CrossCursor,
    FerramentaMockup.MOVER_PRECISO: Qt.CursorShape.CrossCursor,
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

# Nome amigável de cada tipo de linha técnica — usado só pelo modo
# "Atributos" da ferramenta Medida (ver `_texto_atributos_sob_cursor`).
_NOME_TIPO_LINHA: dict[TipoLinha, str] = {
    TipoLinha.CORTE: "Corte",
    TipoLinha.VINCO: "Vinco",
    TipoLinha.CORTE_SERRA: "Corte de serra",
    TipoLinha.MEIO_CORTE: "Meio corte",
    TipoLinha.DOBRA: "Dobra (auxiliar)",
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

# Zona segura: margem de recuo a partir do vinco/corte de cada painel onde
# não é recomendado colocar conteúdo de mockup (risco de corte/dobra
# cortar texto/imagem). Puramente uma referência visual (não afeta
# exportação nem impede posicionar nada ali) — a mesma ideia de "linha de
# construção" do ArtiosCAD (ver REFERENCIA_FERRAMENTAS_ARTIOSCAD.md), mas
# como feature própria: não é apoio de desenho descartável, é aviso de
# produção que deve continuar visível enquanto o usuário monta o mockup.
_MARGEM_ZONA_SEGURA_MM = 3.0
_COR_ZONA_SEGURA = QColor(Cor.ERRO)

_r, _g, _b, _a = Cor.PAINEL_FLUTUANTE_RGBA
_ESTILO_PAINEL = (
    f"background: rgba({_r}, {_g}, {_b}, {_a});"
    f"border: 1px solid {Cor.BORDA};"
    "border-radius: 6px;"
    "padding: 4px 8px;"
    "font-size: 12px;"
)


class _PainelOffsetEndpoint(QWidget):
    """Endpoint Offset Mode (ArtiosCAD) — Alt+clique numa ferramenta de
    criação de geometria acha o PONTO DE REFERÊNCIA mais próximo (borda/
    centro de outro elemento, guia, ou o próprio ponto clicado se nada
    estiver perto) e mostra estes 2 campos (deslocamento X/Y em mm a
    partir dali) em vez de exigir o clique visual exato — Enter confirma
    (o ponto final = referência + deslocamento vira o 1º ponto da
    ferramenta ativa, normalmente), Esc cancela sem criar nada.

    Widget de verdade (não um item de cena) — mesmo motivo de
    `_rotulo_medida`: fica em coordenadas de TELA (pixel), não de cena,
    então não precisa reconverter nada com o zoom."""

    confirmado = Signal(float, float)
    cancelado = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_ESTILO_PAINEL + f"background: {Cor.CARTAO};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        self._spin_x = QDoubleSpinBox()
        self._spin_y = QDoubleSpinBox()
        for spin, sufixo in ((self._spin_x, " X mm"), (self._spin_y, " Y mm")):
            spin.setRange(-100000.0, 100000.0)
            spin.setDecimals(2)
            spin.setSuffix(sufixo)
            spin.setMinimumWidth(110)
            spin.installEventFilter(self)
            layout.addWidget(spin)
        self.setFocusProxy(self._spin_x)
        self.hide()

    def iniciar(self, pos_viewport) -> None:
        self._spin_x.blockSignals(True)
        self._spin_y.blockSignals(True)
        self._spin_x.setValue(0.0)
        self._spin_y.setValue(0.0)
        self._spin_x.blockSignals(False)
        self._spin_y.blockSignals(False)
        self.adjustSize()
        self.move(pos_viewport.x() + 14, pos_viewport.y() - self.height() - 10)
        self.show()
        self.raise_()
        self._spin_x.setFocus()
        self._spin_x.selectAll()

    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.hide()
                self.confirmado.emit(self._spin_x.value(), self._spin_y.value())
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                self.cancelado.emit()
                return True
            if event.key() == Qt.Key.Key_Tab and watched is self._spin_x:
                self._spin_y.setFocus()
                self._spin_y.selectAll()
                return True
        return super().eventFilter(watched, event)


class _RotuloMedidaFixado(QLabel):
    """Uma leitura da ferramenta Medida "fixada" na tela (ver
    `PreviewCanvas._fixar_leitura_medida`) — igual ArtiosCAD: passar o
    mouse mostra a leitura só enquanto o cursor fica em cima (rótulo
    único e reaproveitado, `PreviewCanvas._rotulo_medida`), soltar/clicar
    fixa ela como uma anotação permanente que fica na tela até o próprio
    usuário fechar — dá pra deixar várias abertas ao mesmo tempo,
    cada uma fechável só por ela mesma, sem afetar as outras.
    Clicar em cima de um rótulo fixado o remove (mesmo princípio de
    "clicar fecha" que fecha diálogo/popup no resto do app)."""

    def __init__(self, texto: str, ao_fechar, linha_associada=None, parent=None) -> None:
        super().__init__(texto, parent)
        self._ao_fechar = ao_fechar
        # Linha desenhada na cena junto com a leitura (só no sub-modo
        # Medida — Atributos fixa só o texto, sem linha, ver
        # `PreviewCanvas._fixar_leitura_medida`) — guardada aqui pra
        # `_remover_rotulo_fixado` saber o que mais tirar da cena junto
        # quando o usuário fecha o rótulo.
        self.linha_associada = linha_associada
        self.setObjectName("rotuloTecnico")
        self.setStyleSheet(_ESTILO_PAINEL + f"color: {Cor.TEXTO}; font-weight: 700; font-size: 12px;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Clique pra fechar")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._ao_fechar(self)
        event.accept()


def _cor_texto_legivel(r: int, g: int, b: int) -> QColor:
    """Usa a própria cor no texto (pedido do usuário: "vermelho" escrito em
    vermelho), mas escurece cores muito claras (ex.: amarelo) o mínimo
    necessário pra continuar legível sobre o fundo claro do canvas."""
    luminancia = 0.299 * r + 0.587 * g + 0.114 * b
    if luminancia > 200:
        fator = 0.65
        return QColor(int(r * fator), int(g * fator), int(b * fator))
    return QColor(r, g, b)


# ── Comandos de desfazer/refazer (QUndoStack, ver PreviewCanvas.__init__) ──
# Cobrem as ações mais destrutivas/comuns: adicionar (ferramenta, duplicar,
# colar), remover, e mover/redimensionar/girar (empurrados só ao FINAL do
# gesto, ver `ElementoMockup._registrar_undo_se_mudou`). Deliberadamente
# de fora por ora (escopo conservador, mesmo espírito de `paineis.py`):
# agrupar/desagrupar, alinhar, e edições feitas pelo painel de propriedades
# (cor, texto, fonte...) — ficam pra uma rodada futura.


class _ComandoAdicionarElemento(QUndoCommand):
    def __init__(self, canvas: "PreviewCanvas", elemento: ElementoMockup, texto: str = "Adicionar elemento") -> None:
        super().__init__(texto)
        self._canvas = canvas
        self._elemento = elemento

    def redo(self) -> None:  # noqa: N802 (nome exigido pelo Qt)
        self._canvas._reinserir_elemento(self._elemento)

    def undo(self) -> None:  # noqa: N802
        self._canvas._retirar_elemento(self._elemento)


class _ComandoRemoverElementos(QUndoCommand):
    def __init__(self, canvas: "PreviewCanvas", elementos: list[ElementoMockup], texto: str = "Remover elementos") -> None:
        super().__init__(texto)
        self._canvas = canvas
        self._elementos = list(elementos)

    def redo(self) -> None:  # noqa: N802
        for elemento in self._elementos:
            self._canvas._retirar_elemento(elemento)

    def undo(self) -> None:  # noqa: N802
        for elemento in self._elementos:
            self._canvas._reinserir_elemento(elemento)


class _ComandoAlterarGeometria(QUndoCommand):
    """Mover, redimensionar ou girar 1+ elementos — um comando só cobre os
    três porque todos vêm da mesma fonte (`ElementoMockup.
    _registrar_undo_se_mudou`, chamado ao soltar o mouse) com o mesmo
    formato de estado (pos/largura/altura/rotação por elemento)."""

    def __init__(self, antes: dict, depois: dict, texto: str = "Alterar geometria") -> None:
        super().__init__(texto)
        self._antes = antes
        self._depois = depois

    def redo(self) -> None:  # noqa: N802
        self._aplicar(self._depois)

    def undo(self) -> None:  # noqa: N802
        self._aplicar(self._antes)

    @staticmethod
    def _aplicar(estados: dict) -> None:
        for item, (pos, largura, altura, rotacao) in estados.items():
            item.definir_tamanho(largura, altura)
            item.setPos(pos)
            item.setRotation(rotacao)


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
    simbolo_solicitado = Signal(QPointF)
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
        # Precisa pra `mouseMoveEvent` disparar sem nenhum botão pressionado
        # (hover puro) — usado pelo sub-modo Atributos da ferramenta Medida.
        self.setMouseTracking(True)
        self._grade_visivel = True
        # Desligada por padrão — é um aviso de revisão pontual (checar
        # proximidade do vinco), não um apoio de desenho de uso contínuo
        # como grade/snap/réguas, que já vêm ligados.
        self._zona_segura_visivel = False
        # Desfazer/refazer (ver classes `_Comando*` acima do módulo) — um
        # QUndoStack só, do documento inteiro (não por elemento), igual
        # qualquer editor de verdade.
        self._pilha_desfazer = QUndoStack(self)

        self._zoom_atual = 1.0
        self._layout: LayoutCaixa | None = None
        # `ajustar_a_tela()` calcula o zoom em cima do tamanho ATUAL do
        # viewport — chamado logo que a janela abre (`definir_layout`),
        # antes do Qt terminar de dar o tamanho final pra janela, o
        # viewport ainda está pequeno/provisório, e o zoom calculado sai
        # errado (fica "pequeno" dentro da janela real, maior, que só
        # aparece um instante depois). Fica pendente até o primeiro
        # `resizeEvent` de verdade acontecer, que reajusta automaticamente
        # — depois disso, resize normal da janela não reajusta mais
        # sozinho (senão zoom/pan manual do usuário seria perdido a cada
        # redimensionamento da janela).
        self._ajuste_pendente = False

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

        # Laço poligonal de seleção (`FerramentaMockup.LACO_SELECAO`) —
        # gesto de VÁRIOS cliques (não clique-arrasto-solta como o resto
        # de `_iniciar_criacao`), então tem estado próprio em vez de
        # reusar `_criando`/`_ponto_inicial_criacao`. Cada clique some um
        # vértice; clicar perto do primeiro fecha o laço e seleciona.
        self._pontos_laco: list[QPointF] = []
        self._item_preview_laco: QGraphicsPathItem | None = None

        # Move tool de precisão (`FerramentaMockup.MOVER_PRECISO`) —
        # também 2 cliques em sequência (ponto de "pega" + ponto de
        # "solta"), não um arrasto contínuo — ver docstring de
        # `_continuar_mover_preciso`.
        self._ponto_pega_mover_preciso: QPointF | None = None
        self._elementos_mover_preciso: list[ElementoMockup] = []

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
        # Linhas-guia TEMPORÁRIAS de encaixe (ver
        # `_atualizar_guia_snap_preview`) — só aparecem durante um
        # arrasto, mostrando pra qual grade/elemento/guia o encaixe vai
        # grudar se soltar agora (o encaixe em si só é aplicado ao
        # soltar, ver `_calcular_snap`, mas sem isso não tinha como saber
        # ANTES de soltar que ia encaixar em algo).
        self._linhas_guia_snap: list[QGraphicsLineItem] = []

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
        # Sub-modo da ferramenta Medida — "medida" (clique-arrasta entre 2
        # pontos, como uma trena) ou "atributos" (passa o mouse por cima
        # de uma linha/elemento e mostra o que é). Trocado por Tab (ver
        # `keyPressEvent`), igual ArtiosCAD.
        self._modo_medida = "medida"
        # Leituras "fixadas" na tela (ver `_RotuloMedidaFixado`) — cada
        # clique/soltar com a ferramenta Medida ativa deixa uma dessas
        # pra trás, independente das outras, até o usuário clicar nela
        # pra fechar. Sobrevivem à troca de ferramenta de propósito (são
        # anotações que o usuário pediu pra guardar, diferente da leitura
        # ao vivo em `_rotulo_medida`, que é descartável).
        self._rotulos_fixados: list[_RotuloMedidaFixado] = []

        # Endpoint Offset Mode (ver `_PainelOffsetEndpoint`) — Alt+clique
        # numa ferramenta de criação de geometria pausa o gesto e pede um
        # deslocamento numérico a partir do ponto de referência mais
        # próximo, em vez de já criar no ponto clicado.
        self._painel_offset = _PainelOffsetEndpoint(self)
        self._painel_offset.confirmado.connect(self._ao_confirmar_offset_endpoint)
        self._painel_offset.cancelado.connect(self._painel_offset.hide)
        self._offset_referencia_cena = QPointF()

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
        self._ajuste_pendente = True
        self.ajustar_a_tela()

    def ajustar_a_tela(self) -> None:
        if not self._scene.items():
            return
        self.resetTransform()
        self._zoom_atual = 1.0
        margem = 20
        rect = self._scene.itemsBoundingRect().adjusted(-margem, -margem, margem, margem)
        # `fitInView` escala via `scale()` por baixo, que respeita
        # `transformationAnchor` — com `AnchorUnderMouse` (usado pro zoom
        # da roda do mouse), o resultado ancora onde o mouse estava da
        # ÚLTIMA vez (podendo estar fora do canvas, ou num canto), não no
        # centro do que acabou de ser calculado — era por isso que
        # "Ajustar à tela" saía descentralizado. Troca temporária pro
        # centro evita isso, e o `centerOn` depois garante mesmo se algum
        # resto de scroll sobrar.
        ancora_original = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.setTransformationAnchor(ancora_original)
        self.centerOn(rect.center())
        self._zoom_atual = self.transform().m11()
        self.zoom_alterado.emit(self._zoom_atual)

    # ── Fundo ───────────────────────────────────────────────────────
    def definir_grade_visivel(self, visivel: bool) -> None:
        self._grade_visivel = visivel
        self.viewport().update()

    def definir_zona_segura_visivel(self, visivel: bool) -> None:
        self._zona_segura_visivel = visivel
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

        if self._zona_segura_visivel and self._paineis:
            self._desenhar_zonas_seguras(painter, rect)

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

    def _desenhar_zonas_seguras(self, painter, rect) -> None:
        """Faixa de aviso (recuo de `_MARGEM_ZONA_SEGURA_MM` a partir do
        vinco/corte de cada painel) + contorno tracejado marcando o limite
        seguro — não afeta o que é exportado, é só referência visual pra
        evitar colocar texto/imagem colado demais numa dobra ou corte.
        Abas (`Painel.eh_aba`, ex.: aba de cola) ficam de fora — não são
        área de impressão na prática (ver docstring de `paineis.py`)."""
        m = _MARGEM_ZONA_SEGURA_MM
        cor_faixa = QColor(_COR_ZONA_SEGURA)
        cor_faixa.setAlpha(28)
        pen_contorno = QPen(_COR_ZONA_SEGURA)
        pen_contorno.setCosmetic(True)
        pen_contorno.setStyle(Qt.PenStyle.DashLine)

        for painel in self._paineis:
            if painel.eh_aba:
                continue
            area = QRectF(painel.x1, painel.y1, painel.largura, painel.altura)
            if not area.intersects(rect):
                continue
            interna = area.adjusted(m, m, -m, -m)
            if interna.width() <= 0 or interna.height() <= 0:
                continue  # painel menor que 2x a margem — nada de seguro a marcar

            caminho = QPainterPath()
            caminho.addRect(area)
            caminho.addRect(interna)
            painter.save()
            painter.setClipRect(area)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(cor_faixa))
            painter.drawPath(caminho)  # OddEven (padrão) = preenche só a faixa, não o miolo
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(pen_contorno)
            painter.drawRect(interna)
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
        if self._modo_mockup and (item is not None or self._pontos_laco or self._ponto_pega_mover_preciso is not None):
            # Também não deveria "ajustar à tela" no meio de um laço de
            # seleção ou de um Move tool de precisão em andamento — o
            # segundo clique de um clique-duplo acidental não passa por
            # `mousePressEvent` (vira `mouseDoubleClickEvent` direto), e
            # sem essa guarda o zoom resetava sozinho no meio do gesto.
            return
        self.ajustar_a_tela()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reposicionar_paineis()
        if self._ajuste_pendente:
            # Primeiro resize de verdade depois de `definir_layout()` —
            # ver comentário em `__init__` sobre por que o ajuste inicial
            # (calculado num viewport ainda provisório) precisa ser
            # refeito aqui. Só essa vez: depois disso, redimensionar a
            # janela não mexe mais no zoom/posição que o usuário escolheu.
            self._ajuste_pendente = False
            self.ajustar_a_tela()

    # ── Ferramenta ativa (ver `FerramentaMockup`) ──────────────────────
    @property
    def ferramenta_ativa(self) -> FerramentaMockup:
        return self._ferramenta

    def definir_ferramenta(self, ferramenta: FerramentaMockup) -> None:
        if self._criando:
            self._cancelar_criacao()
        if self._pontos_laco:
            self._cancelar_laco_selecao()
        if self._ponto_pega_mover_preciso is not None:
            self._cancelar_mover_preciso()
        self._painel_offset.hide()
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
        # `self.viewport().setCursor()`, não `self.setCursor()` — o
        # `QGraphicsView` é um `QAbstractScrollArea`, o cursor que aparece
        # sobre a área de desenho de verdade é o do widget `viewport()`
        # interno, não o do `QGraphicsView` em si (que só cobriria a
        # moldura, inexistente aqui — `NoFrame`). Setar no lugar errado é
        # por isso que o cursor nunca trocava visualmente ao mudar de
        # ferramenta, mesmo com o valor certo sendo calculado aqui.
        self.viewport().setCursor(_CURSOR_POR_FERRAMENTA[ferramenta])
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
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if (
            self._modo_mockup
            and event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
            and self._ferramenta in _FERRAMENTAS_CRIACAO_GEOMETRIA
            and not self._criando
            and not self._painel_offset.isVisible()
        ):
            # Endpoint Offset Mode — pausa o gesto de criação pra pedir
            # um deslocamento numérico a partir do ponto de referência
            # mais próximo, em vez de já iniciar com o clique visual (ver
            # `_PainelOffsetEndpoint`/`_ao_confirmar_offset_endpoint`).
            self._offset_referencia_cena = self._ponto_referencia_proximo(event.pos())
            self._painel_offset.iniciar(event.pos())
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
            self._atualizar_criacao(event.pos(), event.modifiers())
            event.accept()
            return
        if (
            self._modo_mockup
            and self._ferramenta == FerramentaMockup.MEDIR
            and self._modo_medida == "atributos"
        ):
            # Sub-modo Atributos: passar o mouse por cima já mostra a
            # leitura (não precisa clicar/arrastar) — clicar só FIXA ela
            # na tela (ver `_iniciar_criacao`).
            texto = self._texto_atributos_sob_cursor(event.pos())
            if texto is None:
                self._rotulo_medida.hide()
            else:
                self._rotulo_medida.setText(texto)
                self._rotulo_medida.adjustSize()
                pos = event.pos()
                self._rotulo_medida.move(pos.x() + 14, pos.y() - self._rotulo_medida.height() - 10)
                self._rotulo_medida.show()
        if self._pontos_laco:
            self._atualizar_preview_laco(self.mapToScene(event.pos()))
        if self._ponto_pega_mover_preciso is not None:
            self._atualizar_preview_mover_preciso(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self._panorama_ativo:
            self._panorama_ativo = False
            # Restaura o cursor da ferramenta ativa, não `unsetCursor()`
            # (que voltaria pro cursor padrão da seta, ignorando qual
            # ferramenta estava ativa antes do pan).
            self.viewport().setCursor(_CURSOR_POR_FERRAMENTA[self._ferramenta])
            event.accept()
            return
        if self._criando and event.button() == Qt.MouseButton.LeftButton:
            self._finalizar_criacao(event.pos(), event.modifiers())
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
                FerramentaMockup.SIMBOLO: self.simbolo_solicitado,
            }
            sinais_clique_unico[self._ferramenta].emit(self._ponto_inicial_criacao)
            return
        if self._ferramenta == FerramentaMockup.MEDIR and self._modo_medida == "atributos":
            # Sub-modo Atributos: também não precisa de arrasto — um
            # clique fixa na tela a leitura que já estava sendo mostrada
            # ao passar o mouse (ver `mouseMoveEvent`).
            texto = self._texto_atributos_sob_cursor(pos_viewport)
            if texto is not None:
                self._rotulo_medida.hide()
                self._fixar_leitura_medida(texto, pos_viewport)
            return
        if self._ferramenta == FerramentaMockup.LACO_SELECAO:
            self._continuar_laco_selecao(self._ponto_inicial_criacao, pos_viewport)
            return
        if self._ferramenta == FerramentaMockup.MOVER_PRECISO:
            self._continuar_mover_preciso(self._ponto_inicial_criacao)
            return

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

    def _retangulo_de_criacao(self, atual: QPointF, modificadores: Qt.KeyboardModifier) -> QRectF:
        """Canto-a-canto (padrão) ou "a partir do centro" se Alt estiver
        segurado durante o arrasto — o primeiro clique vira o CENTRO em
        vez de um canto, e a forma cresce simétrica dos dois lados
        (mesma convenção de "From Center" do ArtiosCAD/qualquer editor
        vetorial). Reavaliado a cada frame (dá pra soltar/segurar Alt no
        meio do arrasto e ver o efeito na hora, sem precisar recomeçar).
        Recebe os modificadores do evento (não `QApplication.keyboardModifiers()`
        global) — mais direto e mais fácil de testar."""
        if modificadores & Qt.KeyboardModifier.AltModifier:
            meia_diagonal = atual - self._ponto_inicial_criacao
            return QRectF(self._ponto_inicial_criacao - meia_diagonal, self._ponto_inicial_criacao + meia_diagonal).normalized()
        return QRectF(self._ponto_inicial_criacao, atual).normalized()

    def _atualizar_criacao(self, pos_viewport, modificadores: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        atual = self.mapToScene(pos_viewport)
        if self._ferramenta in _FERRAMENTAS_RETANGULO_ARRASTO and isinstance(self._item_preview_criacao, QGraphicsRectItem):
            self._item_preview_criacao.setRect(self._retangulo_de_criacao(atual, modificadores))
        elif isinstance(self._item_preview_criacao, QGraphicsLineItem):
            linha = QLineF(self._ponto_inicial_criacao, atual)
            self._item_preview_criacao.setLine(linha)
            if self._ferramenta == FerramentaMockup.MEDIR:
                self._rotulo_medida.setText(f"{linha.length():.1f} mm")
                self._rotulo_medida.adjustSize()
                self._rotulo_medida.move(pos_viewport.x() + 14, pos_viewport.y() - self._rotulo_medida.height() - 10)

    def _finalizar_criacao(self, pos_viewport, modificadores: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        self._criando = False
        if self._ferramenta == FerramentaMockup.MEDIR:
            # Só chega aqui no sub-modo Medida (Atributos nem passa por
            # `_criando`, ver `_iniciar_criacao`) — soltar o botão FIXA a
            # medida na tela como uma anotação permanente (igual a trena
            # do ArtiosCAD: clique num ponto, arraste até outro, solta pra
            # fixar), em vez de só mostrar enquanto arrasta.
            linha = self._item_preview_criacao
            self._item_preview_criacao = None
            self._rotulo_medida.hide()
            if linha is None:
                return
            comprimento = linha.line().length()
            if comprimento < 2.0:
                # Clique seco sem arrastar de verdade — descarta, não fixa
                # uma medida de comprimento ~0 sem querer.
                self._scene.removeItem(linha)
                return
            self._scene.removeItem(linha)
            self._fixar_leitura_medida(f"{comprimento:.1f} mm", pos_viewport, linha.line())
            return
        if self._item_preview_criacao is not None:
            self._scene.removeItem(self._item_preview_criacao)
            self._item_preview_criacao = None

        atual = self.mapToScene(pos_viewport)
        # Arrasto mínimo pra não criar uma forma de 0×0 num clique seco
        # sem querer arrastar de verdade (o gesto mais comum de quem
        # ainda tá aprendendo a ferramenta).
        if self._ferramenta in _FERRAMENTAS_RETANGULO_ARRASTO:
            rect = self._retangulo_de_criacao(atual, modificadores)
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

    # ── Laço poligonal de seleção ───────────────────────────────────────
    _LIMIAR_FECHAR_LACO_PX = 10.0

    def _continuar_laco_selecao(self, ponto_cena: QPointF, pos_viewport) -> None:
        """Cada clique soma um vértice ao laço; clicar perto do primeiro
        vértice de novo (com pelo menos 3 já colocados — um "polígono" de
        2 pontos não seleciona nada) fecha e seleciona. O limiar de
        "perto" é em PIXELS de tela, não mm de cena — senão fechar o laço
        ficaria cada vez mais difícil de acertar conforme o zoom
        diminuísse (mesmo espírito do raio de clique nas alças de
        redimensionar, ver `_MARGEM_CLIQUE_ALCA` em mockup_itens.py)."""
        if len(self._pontos_laco) >= 3:
            primeiro_viewport = self.mapFromScene(self._pontos_laco[0])
            distancia = math.hypot(pos_viewport.x() - primeiro_viewport.x(), pos_viewport.y() - primeiro_viewport.y())
            if distancia <= self._LIMIAR_FECHAR_LACO_PX:
                self._fechar_laco_selecao()
                return
        self._pontos_laco.append(ponto_cena)
        self._atualizar_preview_laco(ponto_cena)

    def _atualizar_preview_laco(self, ponto_atual_cena: QPointF | None = None) -> None:
        if not self._pontos_laco:
            if self._item_preview_laco is not None:
                self._scene.removeItem(self._item_preview_laco)
                self._item_preview_laco = None
            return
        caminho = QPainterPath()
        caminho.moveTo(self._pontos_laco[0])
        for ponto in self._pontos_laco[1:]:
            caminho.lineTo(ponto)
        if ponto_atual_cena is not None:
            caminho.lineTo(ponto_atual_cena)
        if self._item_preview_laco is None:
            self._item_preview_laco = QGraphicsPathItem()
            self._item_preview_laco.setPen(self._caneta_preview())
            self._scene.addItem(self._item_preview_laco)
        self._item_preview_laco.setPath(caminho)

    def _fechar_laco_selecao(self) -> None:
        """Seleciona todo `ElementoMockup` de nível superior cujo CENTRO
        (não a forma inteira — testar o polígono do laço contra a forma
        completa de cada elemento seria bem mais caro e a leitura visual
        de "cabe dentro do laço" já bate com o centro pra a maioria dos
        casos práticos) cai dentro do polígono desenhado."""
        poligono = QPolygonF(self._pontos_laco)
        self._scene.clearSelection()
        for elemento in self._elementos_mockup:
            centro = elemento.mapToScene(QPointF(elemento.largura / 2, elemento.altura / 2))
            if poligono.containsPoint(centro, Qt.FillRule.OddEvenFill):
                elemento.setSelected(True)
        self._cancelar_laco_selecao()

    def _cancelar_laco_selecao(self) -> None:
        self._pontos_laco = []
        if self._item_preview_laco is not None:
            self._scene.removeItem(self._item_preview_laco)
            self._item_preview_laco = None

    # ── Move tool de precisão (pega + solta) ────────────────────────────
    def _continuar_mover_preciso(self, ponto_cena: QPointF) -> None:
        """2 cliques em sequência, não um arrasto contínuo — o 1º define
        o ponto de "pega" (a referência; não precisa ser um ponto do
        próprio elemento, pode ser qualquer lugar da cena, igual o Move
        tool do ArtiosCAD), o 2º o ponto de "solta"; todos os elementos
        selecionados deslocam pelo delta entre os dois. Fica pronta pra
        um novo par de cliques em seguida (ferramenta de utilidade
        repetível, não "usa uma vez e volta pro ponteiro" como
        Texto/Callout)."""
        if self._ponto_pega_mover_preciso is None:
            self._elementos_mover_preciso = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
            if not self._elementos_mover_preciso:
                return
            self._ponto_pega_mover_preciso = ponto_cena
            return

        delta = ponto_cena - self._ponto_pega_mover_preciso
        elementos = self._elementos_mover_preciso
        self._ponto_pega_mover_preciso = None
        self._elementos_mover_preciso = []
        self._limpar_preview_mover_preciso()
        for elemento in elementos:
            elemento.setPos(elemento.pos() + delta)

    def _atualizar_preview_mover_preciso(self, pos_viewport) -> None:
        if self._ponto_pega_mover_preciso is None:
            return
        linha = QLineF(self._ponto_pega_mover_preciso, self.mapToScene(pos_viewport))
        if self._item_preview_criacao is None:
            self._item_preview_criacao = QGraphicsLineItem()
            self._item_preview_criacao.setPen(self._caneta_preview())
            self._scene.addItem(self._item_preview_criacao)
        self._item_preview_criacao.setLine(linha)
        self._rotulo_medida.setText(f"{linha.length():.1f} mm")
        self._rotulo_medida.adjustSize()
        self._rotulo_medida.move(pos_viewport.x() + 14, pos_viewport.y() - self._rotulo_medida.height() - 10)
        self._rotulo_medida.show()

    def _limpar_preview_mover_preciso(self) -> None:
        if self._item_preview_criacao is not None:
            self._scene.removeItem(self._item_preview_criacao)
            self._item_preview_criacao = None
        self._rotulo_medida.hide()

    def _cancelar_mover_preciso(self) -> None:
        self._ponto_pega_mover_preciso = None
        self._elementos_mover_preciso = []
        self._limpar_preview_mover_preciso()

    # ── Ferramenta Medida — sub-modo Atributos + leituras fixadas ──────
    def _texto_atributos_sob_cursor(self, pos_viewport) -> str | None:
        """O que tem embaixo do cursor, em texto curto — usado pelo
        sub-modo Atributos (linha técnica da faca: tipo + comprimento;
        elemento de mockup: tipo + tamanho). `None` quando não há nada
        reconhecível ali (área vazia do canvas)."""
        item = self.itemAt(pos_viewport)
        if isinstance(item, ElementoMockup):
            nome = NOME_TIPO_ELEMENTO.get(type(item), "Elemento")
            return f"{nome} — {item.largura:.1f} × {item.altura:.1f} mm"
        if isinstance(item, QGraphicsLineItem) and item in self._itens_dieline:
            nome = _NOME_TIPO_LINHA.get(item.data(0), "Linha")
            return f"{nome} — {item.line().length():.1f} mm"
        return None

    def _fixar_leitura_medida(self, texto: str, pos_viewport, linha_cena: QLineF | None = None) -> None:
        """Cria uma leitura permanente na tela (ver `_RotuloMedidaFixado`)
        — usada tanto pelo sub-modo Medida (com a linha da régua desenhada
        junto) quanto pelo Atributos (só o texto, sem linha)."""
        item_linha = None
        if linha_cena is not None:
            item_linha = QGraphicsLineItem(linha_cena)
            caneta = QPen(QColor(Cor.PRIMARIA), 0.4, Qt.PenStyle.DashLine)
            caneta.setCosmetic(True)
            item_linha.setPen(caneta)
            self._scene.addItem(item_linha)

        rotulo = _RotuloMedidaFixado(texto, self._remover_rotulo_fixado, item_linha, self)
        rotulo.adjustSize()
        rotulo.move(pos_viewport.x() + 14, pos_viewport.y() - rotulo.height() - 10)
        rotulo.show()
        self._rotulos_fixados.append(rotulo)

    def _remover_rotulo_fixado(self, rotulo: "_RotuloMedidaFixado") -> None:
        if rotulo.linha_associada is not None:
            self._scene.removeItem(rotulo.linha_associada)
        if rotulo in self._rotulos_fixados:
            self._rotulos_fixados.remove(rotulo)
        rotulo.deleteLater()

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

    @property
    def pilha_desfazer(self) -> QUndoStack:
        return self._pilha_desfazer

    def adicionar_elemento_mockup(self, elemento: ElementoMockup, pos: QPointF | None = None) -> None:
        self._scene.addItem(elemento)
        if pos is not None:
            elemento.setPos(pos)
        self._registrar_elemento_mockup(elemento)
        self._pilha_desfazer.push(_ComandoAdicionarElemento(self, elemento))

    def _registrar_elemento_mockup(self, elemento: ElementoMockup) -> None:
        """Cadastra o elemento em `_elementos_mockup` E liga o snap nele
        — ponto único pra isso, senão é fácil esquecer de ligar o snap
        num caminho de criação novo (duplicar, colar, desagrupar...) e o
        elemento ficar "mudo" pro encaixe sem ninguém notar na hora."""
        self._elementos_mockup.append(elemento)
        elemento.definir_calculador_snap(self._calcular_snap)
        elemento.definir_solicitador_duplicata(self._duplicar_no_lugar)
        elemento.definir_registrador_undo(self._registrar_comando_geometria)
        # Linha-guia de encaixe (ver `_atualizar_guia_snap_preview`) —
        # `geometria_alterada` já dispara em TODO arrasto (não só ao
        # soltar, ver `itemChange` em `mockup_itens.py`), então dá pra
        # reaproveitar sem precisar de outro sinal novo. O handler mesmo
        # filtra por `em_arrasto_corpo` pra só desenhar durante um arrasto
        # de corpo de verdade, não a cada mudança de posição/tamanho.
        elemento.geometria_alterada.connect(lambda el=elemento: self._atualizar_guia_snap_preview(el))

    def _reinserir_elemento(self, elemento: ElementoMockup) -> None:
        """Devolve um elemento já registrado (callbacks/sinal ligados uma
        vez na criação, ver `_registrar_elemento_mockup`) de volta à cena
        e à lista — usado por `_Comando*.redo/undo` acima. Guardado contra
        chamada redundante: `QUndoStack.push()` já chama `redo()` na hora,
        e a maioria dos chamadores também já adicionou o elemento antes de
        empurrar o comando (ver `adicionar_elemento_mockup` etc.)."""
        if elemento.scene() is None:
            self._scene.addItem(elemento)
        if elemento not in self._elementos_mockup:
            self._elementos_mockup.append(elemento)

    def _retirar_elemento(self, elemento: ElementoMockup) -> None:
        if elemento.scene() is not None:
            self._scene.removeItem(elemento)
        if elemento in self._elementos_mockup:
            self._elementos_mockup.remove(elemento)

    def _registrar_comando_geometria(self, antes: dict, depois: dict) -> None:
        self._pilha_desfazer.push(_ComandoAlterarGeometria(antes, depois))

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

    def _alvo_snap_proximo(self, bordas: tuple[float, float, float], alvos: list[float]) -> float | None:
        """Mesma busca de `_melhor_ajuste_snap`, mas devolve o ALVO em si
        (não o ajuste a somar) quando tem um dentro do limiar, ou `None` —
        usado só pra saber ONDE desenhar a linha-guia de preview, nunca
        pra mover nada (ver `_atualizar_guia_snap_preview`)."""
        candidatos = list(alvos)
        if self._grade_visivel:
            candidatos.extend(round(borda / _PASSO_GRADE_MM) * _PASSO_GRADE_MM for borda in bordas)

        melhor_alvo = None
        menor_distancia = self._LIMIAR_SNAP_MM
        for borda in bordas:
            for alvo in candidatos:
                distancia = abs(borda - alvo)
                if distancia < menor_distancia:
                    menor_distancia = distancia
                    melhor_alvo = alvo
        return melhor_alvo

    def _limpar_guias_snap_preview(self) -> None:
        for linha in self._linhas_guia_snap:
            self._scene.removeItem(linha)
        self._linhas_guia_snap = []

    def _atualizar_guia_snap_preview(self, elemento: ElementoMockup) -> None:
        self._limpar_guias_snap_preview()
        if not elemento.em_arrasto_corpo or not self._snap_ativo:
            return

        largura, altura = elemento.largura, elemento.altura
        pos = elemento.pos()
        bordas_x = (pos.x(), pos.x() + largura / 2, pos.x() + largura)
        bordas_y = (pos.y(), pos.y() + altura / 2, pos.y() + altura)
        alvo_x = self._alvo_snap_proximo(bordas_x, self._alvos_snap_x(elemento))
        alvo_y = self._alvo_snap_proximo(bordas_y, self._alvos_snap_y(elemento))
        if alvo_x is None and alvo_y is None:
            return

        # Span generoso (não só o retângulo dos itens) — a linha-guia
        # precisa atravessar visualmente a tela toda pra funcionar como
        # referência de alinhamento, igual guia de qualquer editor
        # vetorial (Figma/Illustrator), não só marcar um trechinho.
        rect = self._scene.itemsBoundingRect().adjusted(-200, -200, 200, 200)
        caneta = QPen(QColor(Cor.PRIMARIA), 0.25, Qt.PenStyle.DashLine)
        caneta.setCosmetic(True)
        if alvo_x is not None:
            linha = QGraphicsLineItem(QLineF(QPointF(alvo_x, rect.top()), QPointF(alvo_x, rect.bottom())))
            linha.setPen(caneta)
            linha.setZValue(2000)
            self._scene.addItem(linha)
            self._linhas_guia_snap.append(linha)
        if alvo_y is not None:
            linha = QGraphicsLineItem(QLineF(QPointF(rect.left(), alvo_y), QPointF(rect.right(), alvo_y)))
            linha.setPen(caneta)
            linha.setZValue(2000)
            self._scene.addItem(linha)
            self._linhas_guia_snap.append(linha)

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

    _LIMIAR_REFERENCIA_OFFSET_MM = 6.0

    def _ponto_referencia_proximo(self, pos_viewport) -> QPointF:
        """Pro Endpoint Offset Mode (ver `_PainelOffsetEndpoint`) — acha,
        em cada eixo independentemente (mesmo espírito do snap comum),
        a borda/centro de elemento ou guia mais próxima do clique; se
        nada estiver perto o bastante num eixo, usa a posição bruta do
        clique NAQUELE eixo (não trava esperando achar uma referência
        "perfeita" — sem nada por perto, o próprio clique já É a
        referência, exatamente como clicar normal sem Alt)."""
        ponto_cena = self.mapToScene(pos_viewport)
        candidatos_x = [g.posicao for g in self._guias if g.orientacao == "v"]
        candidatos_y = [g.posicao for g in self._guias if g.orientacao == "h"]
        for outro in self._elementos_mockup:
            candidatos_x.extend((outro.pos().x(), outro.pos().x() + outro.largura / 2, outro.pos().x() + outro.largura))
            candidatos_y.extend((outro.pos().y(), outro.pos().y() + outro.altura / 2, outro.pos().y() + outro.altura))

        def _mais_proximo(valor: float, candidatos: list[float]) -> float:
            if not candidatos:
                return valor
            melhor = min(candidatos, key=lambda c: abs(c - valor))
            return melhor if abs(melhor - valor) <= self._LIMIAR_REFERENCIA_OFFSET_MM else valor

        return QPointF(_mais_proximo(ponto_cena.x(), candidatos_x), _mais_proximo(ponto_cena.y(), candidatos_y))

    def _ao_confirmar_offset_endpoint(self, dx: float, dy: float) -> None:
        ponto_final_cena = self._offset_referencia_cena + QPointF(dx, dy)
        pos_viewport_final = self.mapFromScene(ponto_final_cena)
        self._iniciar_criacao(pos_viewport_final)

    def _painel_do_elemento(self, elemento: ElementoMockup) -> Painel | None:
        if elemento.painel_id is None:
            return None
        return next((p for p in self._paineis if p.id == elemento.painel_id), None)

    def alinhar_selecionados(self, alinhamento: str) -> None:
        """Alinha os elementos selecionados ENTRE SI (bordas/centro da
        própria seleção, não da face — isso já existe em
        `painel_propriedades_mockup.py::_alinhar_ao_painel`, pra um
        elemento só). Mesma simplificação de lá: usa `pos()`/`largura`/
        `altura` direto, ignorando rotação — alinhar caixa rotacionada
        por rotação de verdade exigiria decidir qual canto/eixo do
        retângulo girado conta como "borda", sem resposta óbvia."""
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if len(selecionados) < 2:
            return

        esquerdas = [el.pos().x() for el in selecionados]
        direitas = [el.pos().x() + el.largura for el in selecionados]
        topos = [el.pos().y() for el in selecionados]
        bases = [el.pos().y() + el.altura for el in selecionados]
        alvo_esquerda, alvo_direita = min(esquerdas), max(direitas)
        alvo_topo, alvo_base = min(topos), max(bases)
        centro_h = (alvo_esquerda + alvo_direita) / 2
        centro_v = (alvo_topo + alvo_base) / 2

        for el in selecionados:
            x, y = el.pos().x(), el.pos().y()
            if alinhamento == "esquerda":
                x = alvo_esquerda
            elif alinhamento == "direita":
                x = alvo_direita - el.largura
            elif alinhamento == "centro_h":
                x = centro_h - el.largura / 2
            elif alinhamento == "topo":
                y = alvo_topo
            elif alinhamento == "base":
                y = alvo_base - el.altura
            elif alinhamento == "centro_v":
                y = centro_v - el.altura / 2
            el.setPos(x, y)

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
        elementos = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        for item in list(self._scene.selectedItems()):
            if isinstance(item, GuiaCanvas):
                self.remover_guia(item)  # guias ficam fora do undo por ora — baixo risco, é só uma linha de referência
        if elementos:
            self._pilha_desfazer.push(_ComandoRemoverElementos(self, elementos))

    # ── Duplicar / copiar-colar (Ctrl+D, Ctrl+C, Ctrl+V) ────────────────
    _PASSO_DUPLICAR_MM = 6.0

    def _duplicar_no_lugar(self, elemento: ElementoMockup) -> None:
        """Chamado por `ElementoMockup.mousePressEvent` quando o usuário
        começa a arrastar o corpo segurando Alt — deixa um clone parado
        EXATAMENTE na posição atual de `elemento` (sem deslocamento, ao
        contrário de `duplicar_selecionados`/Ctrl+D), sem selecioná-lo.
        `elemento` continua sendo o item que se move dali pra frente."""
        clone = elemento.clonar()
        self._scene.addItem(clone)
        self._registrar_elemento_mockup(clone)
        self._pilha_desfazer.push(_ComandoAdicionarElemento(self, clone, "Duplicar elemento"))

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
            self._pilha_desfazer.push(_ComandoAdicionarElemento(self, clone, "Duplicar elemento"))
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
            self._pilha_desfazer.push(_ComandoAdicionarElemento(self, clone, "Colar elemento"))
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
                elif self._pontos_laco:
                    self._cancelar_laco_selecao()
                elif self._ponto_pega_mover_preciso is not None:
                    self._cancelar_mover_preciso()
                else:
                    self.definir_ferramenta(FerramentaMockup.SELECIONAR)
                return
            if event.key() == Qt.Key.Key_Delete:
                self.remover_selecionados()
                return
            if self._ferramenta == FerramentaMockup.MEDIR and event.key() == Qt.Key.Key_Tab:
                # Troca Medida <-> Atributos, igual ArtiosCAD. Some com
                # qualquer leitura ao vivo do modo anterior (a fixada, se
                # já tiver alguma, não é afetada — só a transitória).
                self._modo_medida = "atributos" if self._modo_medida == "medida" else "medida"
                self._rotulo_medida.hide()
                if self._criando:
                    self._cancelar_criacao()
                return
            eh_ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            eh_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if eh_ctrl and event.key() == Qt.Key.Key_Z:
                self._pilha_desfazer.redo() if eh_shift else self._pilha_desfazer.undo()
                return
            if eh_ctrl and event.key() == Qt.Key.Key_Y:
                self._pilha_desfazer.redo()
                return
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
                    antes = {}
                    for item in selecionados:
                        antes.update(_estado_recursivo(item))
                        item.setPos(item.pos() + delta)
                    depois = {}
                    for item in selecionados:
                        depois.update(_estado_recursivo(item))
                    self._pilha_desfazer.push(_ComandoAlterarGeometria(antes, depois, "Mover com seta"))
                    return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: N802
        # Sem isso, o Qt intercepta Tab pra navegação de foco entre
        # widgets ANTES de `keyPressEvent` — a troca de sub-modo da
        # ferramenta Medida (ver lá) nunca chegaria a rodar.
        if self._modo_mockup and self._ferramenta == FerramentaMockup.MEDIR:
            return False
        return super().focusNextPrevChild(next)


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
