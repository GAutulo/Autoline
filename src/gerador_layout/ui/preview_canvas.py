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

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF, QTransform, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from .. import geometria_faca as geo
from ..models import CorImpressao, LayoutCaixa, LinhaDesenho, TipoLinha
from ..paineis import Painel
from . import configuracoes
from .estilo import FONTE_MONO, Cor
from .mockup_curva import (
    ElementoCurva,
    No,
    SubCaminho,
    caminho_de_subcaminhos,
    caminho_local_de,
    converter_em_curva,
    curva_de_caminho_cena,
)
from .mockup_itens import ElementoMockup, GrupoMockup, _estado_recursivo
from .mockup_texto import ElementoTexto
from .modelagem import OPERACOES, modelar, objetos_afetados
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
    COTA_PARALELA = auto()
    COTA_HORIZONTAL = auto()
    COTA_VERTICAL = auto()
    BEZIER = auto()
    MAO_LIVRE = auto()
    FORMA = auto()  # editar nós de curva (F10), ver mockup_curva.py
    COTA_ANGULAR = auto()  # 3 cliques: vértice, 1º braço, 2º braço (mockup_cota_angular.py)


# Cotas persistentes (CorelDRAW): mesmo gesto da Linha — clicar no 1º
# ponto e arrastar até o 2º. Ver `mockup_cota.py`.
FERRAMENTAS_COTA: dict[FerramentaMockup, str] = {
    FerramentaMockup.COTA_PARALELA: "paralela",
    FerramentaMockup.COTA_HORIZONTAL: "horizontal",
    FerramentaMockup.COTA_VERTICAL: "vertical",
}


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
    FerramentaMockup.COTA_PARALELA: Qt.CursorShape.CrossCursor,
    FerramentaMockup.COTA_HORIZONTAL: Qt.CursorShape.CrossCursor,
    FerramentaMockup.COTA_VERTICAL: Qt.CursorShape.CrossCursor,
    FerramentaMockup.BEZIER: Qt.CursorShape.CrossCursor,
    FerramentaMockup.MAO_LIVRE: Qt.CursorShape.CrossCursor,
    FerramentaMockup.FORMA: Qt.CursorShape.ArrowCursor,
    FerramentaMockup.COTA_ANGULAR: Qt.CursorShape.CrossCursor,
}

# Ferramentas de desenho em que as guias dinâmicas já aparecem ao pairar.
_FERRAMENTAS_DESENHO_COM_GUIAS = {
    FerramentaMockup.RETANGULO,
    FerramentaMockup.ELIPSE,
    FerramentaMockup.POLIGONO,
    FerramentaMockup.LINHA,
    FerramentaMockup.ACABAMENTO,
    FerramentaMockup.TEXTO,
    FerramentaMockup.BEZIER,
    FerramentaMockup.COTA_PARALELA,
    FerramentaMockup.COTA_HORIZONTAL,
    FerramentaMockup.COTA_VERTICAL,
    FerramentaMockup.COTA_ANGULAR,
}

# Ferramentas de curva com gesto próprio (não o clique/arrasto genérico de
# `_iniciar_criacao`) — ver `_curva_mouse_press` e seguintes.
_FERRAMENTAS_CURVA = {
    FerramentaMockup.BEZIER,
    FerramentaMockup.MAO_LIVRE,
    FerramentaMockup.FORMA,
    FerramentaMockup.COTA_ANGULAR,  # gesto de vários cliques, igual à Bézier
}
_TOLERANCIA_NO_PX = 6.0

# Cor das linhas técnicas na pré-visualização: a cor de texto do tema
# (`Cor.TEXTO`), não preto fixo — em tema escuro, "preto" literal
# desapareceria contra o fundo escuro do canvas. `Cor.TEXTO` já é claro
# no tema escuro e escuro no tema claro, então acompanha automaticamente.
# Desde a área de trabalho estilo CorelDRAW (página branca sobre a mesa,
# ver `drawBackground`), a faca é preta em qualquer tema — igual sai na
# gráfica e igual o CorelDRAW mostra.
_COR_LINHA = QColor(0, 0, 0)
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

# Fontes de encaixe do menu "Ajustar a" (CorelDRAW), na ordem do menu.
AJUSTAR_A: dict[str, str] = {
    "grade": "Grade do documento",
    "guias": "Guias",
    "objetos": "Objetos (e faces da caixa)",
    "pagina": "Página (chapa)",
}

# Atalhos de alinhar do CorelDRAW. C = centros numa linha vertical (mesmo
# X), E = centros numa linha horizontal (mesmo Y).
_TECLA_ALINHAR_CORELDRAW: dict[Qt.Key, str] = {
    Qt.Key.Key_L: "esquerda",
    Qt.Key.Key_R: "direita",
    Qt.Key.Key_T: "topo",
    Qt.Key.Key_B: "base",
    Qt.Key.Key_C: "centro_h",
    Qt.Key.Key_E: "centro_v",
}

# Teclas de ferramenta do CorelDRAW (F5 é a família de curvas; aqui, Linha).
_TECLA_FERRAMENTA_CORELDRAW: dict[Qt.Key, FerramentaMockup] = {
    Qt.Key.Key_F5: FerramentaMockup.MAO_LIVRE,
    Qt.Key.Key_F10: FerramentaMockup.FORMA,
    Qt.Key.Key_F6: FerramentaMockup.RETANGULO,
    Qt.Key.Key_F7: FerramentaMockup.ELIPSE,
    Qt.Key.Key_F8: FerramentaMockup.TEXTO,
    Qt.Key.Key_Y: FerramentaMockup.POLIGONO,
}

# Fundo do canvas: um branco liso incomoda a vista numa área grande (era
# a reclamação) e não lê como área de desenho técnico. Uma grade bem sutil
# de 10mm resolve as duas coisas — quebra a monotonia e ainda funciona
# como referência visual de escala. Traço fino/cosmetic (não escala
# espessura com o zoom) e cor quase invisível de propósito: é textura de
# fundo, não pode competir com as linhas do próprio layout. Vem de
# `Cor` (ver estilo.py) pra também inverter certo no tema escuro.
_COR_GRADE = QColor(30, 26, 22, 18)
# Área de trabalho do CorelDRAW: "mesa" cinza-clara com a página branca
# (aqui, a chapa da dieline) e uma sombra curta embaixo/à direita. Fixo,
# não segue o tema do app — é a superfície de desenho, não a moldura.
_COR_MESA = QColor("#E3E3E1")
_COR_PAGINA = QColor(255, 255, 255)
_COR_SOMBRA_PAGINA = QColor(0, 0, 0, 46)
_DESLOCAMENTO_SOMBRA_PX = 4
# Espaçamento da grade agora é preferência do usuário — ver
# `self.passo_grade()` (lido ao vivo em cada ponto de uso
# abaixo, mesmo motivo do traço do vinco: mudar na tela de Configurações
# já vale na hora, sem reiniciar), não uma constante fixa mais.

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

    def __init__(self, parent=None, sufixos: tuple[str, str] = (" X mm", " Y mm")) -> None:
        super().__init__(parent)
        self.setStyleSheet(_ESTILO_PAINEL + f"background: {Cor.CARTAO};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        self._spin_x = QDoubleSpinBox()
        self._spin_y = QDoubleSpinBox()
        for spin, sufixo in ((self._spin_x, sufixos[0]), (self._spin_y, sufixos[1])):
            spin.setRange(-100000.0, 100000.0)
            spin.setDecimals(2)
            spin.setSuffix(sufixo)
            spin.setMinimumWidth(110)
            spin.installEventFilter(self)
            layout.addWidget(spin)
        self.setFocusProxy(self._spin_x)
        self.hide()

    def iniciar(self, pos_viewport, valores: tuple[float, float] = (0.0, 0.0)) -> None:
        self._spin_x.blockSignals(True)
        self._spin_y.blockSignals(True)
        self._spin_x.setValue(valores[0])
        self._spin_y.setValue(valores[1])
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
        for item, (pos, largura, altura, rotacao, espelho_h, espelho_v) in estados.items():
            item.definir_tamanho(largura, altura)
            item.setPos(pos)
            item.setRotation(rotacao)
            item.definir_espelho(espelho_h, espelho_v)


class _ComandoEditarTexto(QUndoCommand):
    def __init__(self, texto, antes: tuple, depois: tuple) -> None:
        super().__init__("Editar texto")
        self._texto, self._antes, self._depois = texto, antes, depois

    def redo(self) -> None:  # noqa: N802
        self._texto.definir_estado_texto(self._depois)

    def undo(self) -> None:  # noqa: N802
        self._texto.definir_estado_texto(self._antes)


class _ComandoEditarCurva(QUndoCommand):
    """Edição de nós pela ferramenta Forma (mover, inserir, remover...)."""

    def __init__(self, curva: ElementoCurva, antes: tuple, depois: tuple, texto: str = "Editar nós") -> None:
        super().__init__(texto)
        self._curva, self._antes, self._depois = curva, antes, depois

    def redo(self) -> None:  # noqa: N802
        self._curva.definir_estado_nos(self._depois)

    def undo(self) -> None:  # noqa: N802
        self._curva.definir_estado_nos(self._antes)


def _simplificar(pontos: list[QPointF], tolerancia: float) -> list[QPointF]:
    """Ramer–Douglas–Peucker: tira pontos quase em linha do traço à mão livre."""
    if len(pontos) < 3:
        return list(pontos)
    a, b = pontos[0], pontos[-1]
    linha = QLineF(a, b)
    comprimento = linha.length()
    maior, indice = -1.0, 0
    for i in range(1, len(pontos) - 1):
        q = pontos[i]
        if comprimento < 1e-9:
            d = QLineF(a, q).length()
        else:
            d = abs((b.x() - a.x()) * (a.y() - q.y()) - (a.x() - q.x()) * (b.y() - a.y())) / comprimento
        if d > maior:
            maior, indice = d, i
    if maior <= tolerancia:
        return [a, b]
    return _simplificar(pontos[: indice + 1], tolerancia)[:-1] + _simplificar(pontos[indice:], tolerancia)


class _ComandoEditarFaca(QUndoCommand):
    """Edição manual da faca na tela Dieline (ver `PreviewCanvas.definir_edicao_faca`).
    `None` = faca calculada pelas medidas, sem edição."""

    def __init__(self, canvas: "PreviewCanvas", antes, depois, texto: str = "Editar faca") -> None:
        super().__init__(texto)
        self._canvas, self._antes, self._depois = canvas, antes, depois

    def redo(self) -> None:  # noqa: N802
        self._canvas._definir_linhas_editadas(self._depois)

    def undo(self) -> None:  # noqa: N802
        self._canvas._definir_linhas_editadas(self._antes)


def _copiar_linhas(linhas) -> list[LinhaDesenho] | None:
    if linhas is None:
        return None
    return [LinhaDesenho(l.x1, l.y1, l.x2, l.y2, l.tipo, l.bojo) for l in linhas]


def caminho_da_linha(l: LinhaDesenho) -> QPainterPath:
    """Reta, ou arco como Béziers cúbicas (curva de verdade no SVG/PDF)."""
    caminho = QPainterPath(QPointF(l.x1, l.y1))
    if not geo.e_arco(l):
        caminho.lineTo(QPointF(l.x2, l.y2))
        return caminho
    for _p0, c1, c2, p3 in geo.em_cubicas(l):
        caminho.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*p3))
    return caminho


def _mesmo_ponto(ax: float, ay: float, bx: float, by: float) -> bool:
    return abs(ax - bx) < 0.01 and abs(ay - by) < 0.01


class PreviewCanvas(QGraphicsView):
    """Área de desenho do layout com zoom (roda do mouse) e pan (arrastar)."""

    zoom_alterado = Signal(float)
    # Lista/ordem/visibilidade dos elementos mudou (docker Objetos).
    elementos_alterados = Signal()
    ajustar_a_alterado = Signal(str, bool)
    guias_dinamicas_alteradas = Signal(bool)  # chave de AJUSTAR_A, ligado
    cursor_movido = Signal(object)  # QPointF em mm, ou None quando o mouse sai do canvas (barra de status)
    # Emitidos quando uma ferramenta de criação termina um gesto de
    # clique/arrasto no canvas vazio (ver `_finalizar_criacao` abaixo) —
    # o canvas só sabe a GEOMETRIA (onde/tamanho); quem monta o elemento
    # de verdade (cor de tinta padrão etc.) é `main_window.py`.
    retangulo_desenhado = Signal(QRectF)
    linha_desenhada = Signal(QPointF, QPointF)
    cota_desenhada = Signal(QPointF, QPointF, str)
    curva_desenhada = Signal(QPainterPath)
    cota_angular_desenhada = Signal(QPointF, QPointF, QPointF)  # vértice, ponto do 1º braço, do 2º  # Bézier / Mão livre terminada (coordenadas da cena)
    mensagem_status = Signal(str)
    # Faca editada à mão (True) ou voltou a ser a calculada (False).
    faca_editada_alterada = Signal(bool)
    # Tipo da linha selecionada na edição da faca (TipoLinha) ou None.
    linha_faca_selecionada = Signal(object)  # p1, p2, tipo (ver mockup_cota.TIPOS_COTA)
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
        self.setBackgroundBrush(QBrush(_COR_MESA))
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
        self._usuario_interagiu = False

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
        # Guias dinâmicas (CorelDRAW, Alt+Shift+D): ao desenhar, o cursor
        # alinha na horizontal/vertical com os nós da faca, dos objetos, da
        # chapa e com o 1º ponto do gesto — ver `_ajustar_guias_dinamicas`.
        self._guias_dinamicas = True
        # Ponto de encaixe atual (ponto, nome) e medidas de distância
        # (ponto, ponto, mm) desenhados por cima de tudo.
        self._indicador_encaixe: tuple[QPointF, str] | None = None
        self._medidas_distancia: list[tuple[QPointF, QPointF, float]] = []
        # Medida ao vivo ao desenhar/arrastar a faca: (ponto do cursor, texto).
        self._rotulo_faca: tuple[QPointF, str] | None = None
        self._alt_distancias = False
        self._timer_alt: QTimer | None = None
        self._linhas_dinamicas: list[tuple[QPointF, QPointF]] = []
        # Edição manual da faca na tela Dieline (ver `definir_edicao_faca`).
        self._linhas_editadas: list[LinhaDesenho] | None = None
        self._editando_faca = False
        # "forma" | "corte" | "vinco" | "retangulo" | "medida" | "arco" |
        # "aparar" | "estender" | "arredondar" (ver `definir_edicao_faca`)
        self._faca_ferramenta = "forma"
        self._faca_tipo_novo = TipoLinha.CORTE  # retângulo, medida e arco nascem deste tipo
        self._raio_arredondar = 5.0
        self._ultima_medida = (50.0, 0.0)  # comprimento, ângulo
        self._medida_origem: QPointF | None = None
        self._faca_sel: int | None = None
        self._faca_arrasto: tuple | None = None
        self._faca_antes = None
        # Ferramentas de curva (ver `_curva_mouse_press`).
        self._bezier_nos: list[No] = []
        self._angular_pontos: list[QPointF] = []
        self._bezier_arrastando = False
        self._mao_livre_pontos: list[QPointF] | None = None
        self._item_preview_curva: QGraphicsPathItem | None = None
        self._forma_alvo: ElementoCurva | None = None
        self._forma_no: tuple[int, int] | None = None
        self._forma_arrasto: tuple[str, int, int] | None = None
        self._forma_estado_antes: tuple | None = None
        # Barra de espaço alterna entre Selecionar e a última ferramenta usada (CorelDRAW).
        self._ferramenta_anterior = FerramentaMockup.SELECIONAR
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
        # face e das guias (ver `_calcular_snap`). Só o estado INICIAL
        # vem de `configuracoes.py` (preferência salva) — o usuário ainda
        # liga/desliga isso pelo menu Exibir durante a sessão, sem mexer
        # na preferência salva (mesmo espírito da grade, ver lá).
        self._snap_ativo = configuracoes.snap_ativo_padrao()
        # "Ajustar a" do CorelDRAW: liga/desliga cada fonte de encaixe.
        # `objetos` inclui as bordas da face do elemento.
        self._ajustar_a: dict[str, bool] = {chave: True for chave in AJUSTAR_A}
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
        self.zoom_alterado.connect(self._atualizar_escala_tela)
        # Fundo (mesa, página, grade) em cache: arrastar um elemento não
        # redesenha milhares de linhas de grade a cada quadro.
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        # Linha por medida da faca: comprimento e ângulo (0° → direita, 90° → cima).
        self._painel_medida = _PainelOffsetEndpoint(self, sufixos=(" mm", " °"))
        self._painel_medida.confirmado.connect(self._ao_confirmar_medida)
        self._painel_medida.cancelado.connect(lambda: setattr(self, "_medida_origem", None))
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
        # Edição manual da faca sobrevive a recálculos que não mudam a
        # geometria (ex.: marcar uma cor na legenda); se a faca calculada
        # mudar, a edição perde o sentido e é descartada.
        if self._linhas_editadas is not None:
            antigas = [] if self._layout is None else self._layout.linhas
            novas = [] if layout is None else layout.linhas
            if antigas != novas:
                self._linhas_editadas = None
                self._faca_sel = None
                self.faca_editada_alterada.emit(False)
        self._layout = layout
        self.resetCachedContent()  # página mudou de tamanho
        self._redesenhar()
        self._ajuste_pendente = True
        self.ajustar_a_tela()

    def _atualizar_escala_tela(self, zoom: float) -> None:
        """Alças e outras coisas "de tela" acompanham o zoom (ver
        `ElementoMockup.definir_escala_tela`)."""
        if zoom > 0:
            itens = [it for it in self._scene.items() if isinstance(it, (ElementoMockup, GuiaCanvas))]
            ElementoMockup.definir_escala_tela(1.0 / zoom, itens)

    def mm_por_px(self) -> float:
        return 1.0 / (self.transform().m11() or 1.0)

    def passo_grade(self) -> float:
        """Passo da grade que de fato aparece: o de Configurações quando dá
        entre 12 e 120 px na tela; fora disso, o número "redondo" (1/2/5 ×
        10^n mm) mais perto que caiba — assim a grade acompanha a escala do
        desenho (caixa desenhada em 1:10, por exemplo) e o zoom."""
        px_por_mm = self.transform().m11() or 1.0
        preferido = configuracoes.passo_grade_mm()
        if 12.0 <= preferido * px_por_mm <= 120.0:
            return preferido
        for expoente in range(-3, 5):
            for base in (1.0, 2.0, 5.0):
                passo = base * 10.0**expoente
                if passo * px_por_mm >= 12.0:
                    return passo
        return preferido

    def limiar_snap(self) -> float:
        """Distância de encaixe: a de Configurações, mas nunca mais que ~10 px
        de tela — num desenho em escala reduzida, 2 mm pode ser meia caixa."""
        return min(configuracoes.limiar_snap_mm(), 10.0 * self.mm_por_px())

    def retangulo_do_desenho(self) -> QRectF:
        """O que "ajustar à tela" enquadra: faca, chapa e elementos do Layout.
        Nunca as guias — elas atravessam a cena inteira (2 km de propósito) e,
        somadas, levavam o zoom a ~0% e o desenho "sumia"."""
        rect = QRectF()
        for item in self._itens_dieline:
            rect = rect.united(item.sceneBoundingRect())
        pagina = self.retangulo_pagina()
        if pagina is not None:
            rect = rect.united(pagina)
        for el in self._elementos_mockup:
            if el.isVisible():
                rect = rect.united(el.retangulo_conteudo_cena())
        return rect if not rect.isEmpty() else self._scene.itemsBoundingRect()

    def ajustar_a_tela(self) -> None:
        if not self._scene.items():
            return
        if self.viewport().width() < 50 or self.viewport().height() < 50 or not self.isVisible():
            # Canvas escondido ou ainda sem tamanho (ex.: aba 3D aberta):
            # encaixar agora daria zoom ~0. Fica pendente e o próximo
            # resizeEvent/exibição faz o encaixe de verdade.
            self._ajuste_pendente = True
            return
        self.resetTransform()
        self._zoom_atual = 1.0
        desenho = self.retangulo_do_desenho()
        # Folga proporcional ao desenho (não 20 mm fixos: numa caixa
        # desenhada em escala reduzida isso era quase a caixa inteira).
        margem = max(desenho.width(), desenho.height()) * 0.04 or 1.0
        rect = desenho.adjusted(-margem, -margem, margem, margem)
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
        self._vista_do_ajuste = (self._zoom_atual, self.mapToScene(self.viewport().rect().center()))
        self._usuario_interagiu = False
        self.zoom_alterado.emit(self._zoom_atual)

    # ── Fundo ───────────────────────────────────────────────────────
    def definir_grade_visivel(self, visivel: bool) -> None:
        self._grade_visivel = visivel
        self._fundo_mudou()

    def definir_zona_segura_visivel(self, visivel: bool) -> None:
        self._zona_segura_visivel = visivel
        self._fundo_mudou()

    def definir_paineis(self, paineis: list[Painel]) -> None:
        """Faces da caixa atual (ver `paineis.py`) — usadas só pra
        encaixar a grade de fundo em cada face (grade própria, alinhada
        ao canto de cada painel, em vez de uma grade só cobrindo o
        canvas inteiro sem relação com onde as faces realmente estão)."""
        self._paineis = list(paineis)
        self._fundo_mudou()

    def _fundo_mudou(self) -> None:
        """O fundo (mesa, página, grade, zonas seguras) fica em cache; quem
        muda qualquer coisa dele chama isto."""
        self.resetCachedContent()
        self.viewport().update()

    def drawBackground(self, painter, rect) -> None:  # noqa: N802
        painter.fillRect(rect, _COR_MESA)
        pagina = self.retangulo_pagina()
        if pagina is not None:
            # Sombra com deslocamento constante em PIXELS (não mm), como no
            # CorelDRAW: não cresce nem some com o zoom.
            escala = self.transform().m11() or 1.0
            d = _DESLOCAMENTO_SOMBRA_PX / escala
            painter.fillRect(pagina.translated(d, d), _COR_SOMBRA_PAGINA)
            painter.fillRect(pagina, _COR_PAGINA)
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
        passo = self.passo_grade()
        linhas = []
        x = math.floor(rect.left() / passo) * passo
        while x < rect.right():
            linhas.append(QLineF(x, rect.top(), x, rect.bottom()))
            x += passo
        y = math.floor(rect.top() / passo) * passo
        while y < rect.bottom():
            linhas.append(QLineF(rect.left(), y, rect.right(), y))
            y += passo
        painter.drawLines(linhas)  # uma chamada só (era uma por linha)

    def _desenhar_grade_por_painel(self, painter, rect, pen) -> None:
        """Uma grade por face, começando do canto de CADA painel (não de
        um (0,0) global) — assim a grade sempre marca "quão longe da
        borda desta face" em vez de uma origem arbitrária do desenho
        inteiro, que é o que realmente ajuda a posicionar arte numa face
        específica."""
        passo = self.passo_grade()
        for painel in self._paineis:
            area = QRectF(painel.x1, painel.y1, painel.largura, painel.altura)
            visivel = area.intersected(rect)
            if visivel.isEmpty():
                continue
            # Só as linhas que caem na parte visível, numa chamada só.
            linhas = []
            x = painel.x1 + math.ceil((visivel.left() - painel.x1) / passo) * passo
            while x <= visivel.right():
                linhas.append(QLineF(x, visivel.top(), x, visivel.bottom()))
                x += passo
            y = painel.y1 + math.ceil((visivel.top() - painel.y1) / passo) * passo
            while y <= visivel.bottom():
                linhas.append(QLineF(visivel.left(), y, visivel.right(), y))
                y += passo
            painter.setPen(pen)
            painter.drawLines(linhas)

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
        if self._editando_faca and not self._modo_mockup:
            event.accept()  # sem "ajustar à tela" no meio da edição da faca
            return
        if self._modo_mockup and self._ferramenta in _FERRAMENTAS_CURVA:
            self._curva_duplo_clique(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        # Duplo-clique num elemento (ex.: texto, ver `mockup_texto.py`)
        # tem tratamento próprio no item (editar inline) — só cai pro
        # "ajustar à tela" de conveniência quando o clique foi em área
        # vazia do canvas, senão os dois efeitos brigavam (editar texto
        # E mudar o zoom no mesmo clique).
        item = self.itemAt(event.position().toPoint())
        super().mouseDoubleClickEvent(event)
        if self._modo_mockup and (item is not None or self._pontos_laco or self._ponto_pega_mover_preciso is not None):
            # Também não deveria "ajustar à tela" no meio de um laço de
            # seleção ou de um Move tool de precisão em andamento — o
            # segundo clique de um clique-duplo acidental não passa por
            # `mousePressEvent` (vira `mouseDoubleClickEvent` direto), e
            # sem essa guarda o zoom resetava sozinho no meio do gesto.
            return
        self.ajustar_a_tela()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._ajuste_pendente:
            QTimer.singleShot(0, self._ajuste_pendente_agora)

    def _ajuste_pendente_agora(self) -> None:
        if self._ajuste_pendente and self.viewport().width() >= 50:
            self._ajuste_pendente = False
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
        elif self._vista_ainda_ajustada(event.oldSize()) and not self._usuario_interagiu:
            # Ninguém mexeu no zoom nem rolou desde o último "Ajustar à
            # tela": a janela mudou de tamanho (abrir maximizada, barra
            # quebrando linha), então reajusta. Depois que o usuário
            # mexe, o zoom dele fica.
            self.ajustar_a_tela()

    def _vista_ainda_ajustada(self, tamanho_antigo) -> bool:
        ajuste = getattr(self, "_vista_do_ajuste", None)
        if ajuste is None or not self.isVisible() or self.viewport().width() < 50:
            return False
        # Só mudança de tamanho de verdade (maximizar, barra quebrando
        # linha) e nunca no meio de um clique: selecionar um objeto mexe
        # alguns pixels na barra de status, e reajustar ali mudava o zoom
        # durante o arrasto, jogando o objeto longe.
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            return False
        if abs(self.width() - tamanho_antigo.width()) + abs(self.height() - tamanho_antigo.height()) < 40:
            return False
        zoom, centro = ajuste
        if abs(self.transform().m11() - zoom) > 1e-9:
            return False
        # O centro da vista anda junto com o redimensionamento: compara com
        # folga do quanto a janela mudou, em pixels de tela.
        atual = self.mapToScene(self.viewport().rect().center())
        folga = (abs(self.width() - tamanho_antigo.width()) + abs(self.height() - tamanho_antigo.height()) + 4) / zoom
        return abs(atual.x() - centro.x()) <= folga and abs(atual.y() - centro.y()) <= folga

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
        self._cancelar_curva_em_andamento()
        self._limpar_guias_dinamicas()
        if ferramenta == FerramentaMockup.FORMA:
            selecionadas = [it for it in self._scene.selectedItems() if isinstance(it, ElementoCurva)]
            self._definir_alvo_forma(selecionadas[0] if len(selecionadas) == 1 else None)
        else:
            self._definir_alvo_forma(None)
        if self._ferramenta != ferramenta:
            self._ferramenta_anterior = self._ferramenta
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
        self._usuario_interagiu = True  # daqui pra frente o zoom/posição são do usuário
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
            self._offset_referencia_cena = self._ponto_referencia_proximo(event.position().toPoint())
            self._painel_offset.iniciar(event.position().toPoint())
            event.accept()
            return
        if self._editando_faca and not self._modo_mockup and event.button() == Qt.MouseButton.LeftButton:
            self._faca_mouse_press(self.mapToScene(event.position().toPoint()), event.modifiers())
            event.accept()
            return
        if self._modo_mockup and event.button() == Qt.MouseButton.LeftButton and self._ferramenta in _FERRAMENTAS_CURVA:
            self._curva_mouse_press(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if (
            self._modo_mockup
            and self._ferramenta != FerramentaMockup.SELECIONAR
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._iniciar_criacao(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.cursor_movido.emit(None)
        if not self._criando and self._faca_arrasto is None:
            self._mostrar_indicador(None)
        if self._faca_arrasto is None and not self._criando:
            self._limpar_guias_dinamicas()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.cursor_movido.emit(self.mapToScene(event.position().toPoint()))
        if self._panorama_ativo:
            ponto = event.position()
            delta = ponto - self._panorama_ultimo_ponto
            self._panorama_ultimo_ponto = ponto
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton) and self._mostra_guias_ao_pairar():
            sob_cursor = self.mapToScene(event.position().toPoint())
            achado = self.encaixe_mais_proximo(sob_cursor)
            self._mostrar_indicador(achado)
            if achado is None:
                self._ajustar_guias_dinamicas(sob_cursor)
            else:
                self._limpar_guias_dinamicas()
        if self._editando_faca and not self._modo_mockup and self._faca_arrasto is not None:
            self._faca_mouse_move(self.mapToScene(event.position().toPoint()), event.modifiers())
            event.accept()
            return
        if self._modo_mockup and self._ferramenta in _FERRAMENTAS_CURVA:
            self._curva_mouse_move(self.mapToScene(event.position().toPoint()), event.buttons())
        if self._criando:
            self._atualizar_criacao(event.position().toPoint(), event.modifiers())
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
            texto = self._texto_atributos_sob_cursor(event.position().toPoint())
            if texto is None:
                self._rotulo_medida.hide()
            else:
                self._rotulo_medida.setText(texto)
                self._rotulo_medida.adjustSize()
                pos = event.position().toPoint()
                self._rotulo_medida.move(pos.x() + 14, pos.y() - self._rotulo_medida.height() - 10)
                self._rotulo_medida.show()
        if self._pontos_laco:
            self._atualizar_preview_laco(self.mapToScene(event.position().toPoint()))
        if self._ponto_pega_mover_preciso is not None:
            self._atualizar_preview_mover_preciso(event.position().toPoint())
        super().mouseMoveEvent(event)

    def _limpar_indicadores(self) -> None:
        if self._indicador_encaixe is not None or self._medidas_distancia:
            self._indicador_encaixe = None
            self._medidas_distancia = []
            self.viewport().update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            QTimer.singleShot(0, self._limpar_indicadores)  # depois do soltar do item
        if event.button() == Qt.MouseButton.MiddleButton and self._panorama_ativo:
            self._panorama_ativo = False
            # Restaura o cursor da ferramenta ativa, não `unsetCursor()`
            # (que voltaria pro cursor padrão da seta, ignorando qual
            # ferramenta estava ativa antes do pan).
            self.viewport().setCursor(_CURSOR_POR_FERRAMENTA[self._ferramenta])
            event.accept()
            return
        if self._editando_faca and not self._modo_mockup and event.button() == Qt.MouseButton.LeftButton:
            self._faca_mouse_release()
            event.accept()
            return
        if self._modo_mockup and event.button() == Qt.MouseButton.LeftButton and self._ferramenta in _FERRAMENTAS_CURVA:
            self._curva_mouse_release(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._criando and event.button() == Qt.MouseButton.LeftButton:
            self._finalizar_criacao(event.position().toPoint(), event.modifiers())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ── Gesto de criação (clique/arrasto com uma ferramenta ativa) ─────
    def _caneta_preview(self) -> QPen:
        caneta = QPen(QColor(Cor.PRIMARIA), 0.6, Qt.PenStyle.DashLine)
        caneta.setCosmetic(True)
        return caneta

    def _iniciar_criacao(self, pos_viewport) -> None:
        self._ponto_inicial_criacao = self._ajustar_guias_dinamicas(self.mapToScene(pos_viewport))
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
            if self._ferramenta == FerramentaMockup.TEXTO:
                # Como no CorelDRAW: clicar num texto com a ferramenta Texto
                # edita ele (cursor onde clicou), em vez de criar outro.
                alvo = self._elemento_raiz_em(self._ponto_inicial_criacao)
                if isinstance(alvo, ElementoTexto):
                    self._scene.clearSelection()
                    alvo.setSelected(True)
                    alvo.iniciar_edicao(alvo.mapFromScene(self._ponto_inicial_criacao))
                    return
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
        if self._ferramenta in FERRAMENTAS_COTA:
            # Cota começa grudada no nó mais próximo (canto da faca, de um
            # objeto ou da chapa), como a cota do CorelDRAW.
            self._ponto_inicial_criacao = self.encaixar_ponto(self._ponto_inicial_criacao)
        if self._ferramenta in _FERRAMENTAS_RETANGULO_ARRASTO:
            self._item_preview_criacao = QGraphicsRectItem()
        elif self._ferramenta in (FerramentaMockup.LINHA, FerramentaMockup.MEDIR) or self._ferramenta in FERRAMENTAS_COTA:
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
        global) — mais direto e mais fácil de testar.

        Convenção do CorelDRAW por cima disso: **Shift** também desenha a
        partir do centro e **Ctrl** força lados iguais (quadrado/círculo)."""
        diagonal = atual - self._ponto_inicial_criacao
        if modificadores & Qt.KeyboardModifier.ControlModifier:
            lado = max(abs(diagonal.x()), abs(diagonal.y()))
            diagonal = QPointF(math.copysign(lado, diagonal.x()), math.copysign(lado, diagonal.y()))
        if modificadores & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier):
            return QRectF(self._ponto_inicial_criacao - diagonal, self._ponto_inicial_criacao + diagonal).normalized()
        return QRectF(self._ponto_inicial_criacao, self._ponto_inicial_criacao + diagonal).normalized()

    def _fim_linha_de_criacao(self, atual: QPointF, modificadores: Qt.KeyboardModifier) -> QPointF:
        """Ctrl prende o ângulo da linha em passos de 15° (CorelDRAW). Nas
        cotas, o ponto final também gruda no nó mais próximo."""
        if self._ferramenta in FERRAMENTAS_COTA and not modificadores & Qt.KeyboardModifier.ControlModifier:
            return self.encaixar_ponto(atual)
        if not modificadores & Qt.KeyboardModifier.ControlModifier:
            return atual
        linha = QLineF(self._ponto_inicial_criacao, atual)
        linha.setAngle(round(linha.angle() / 15.0) * 15.0)
        return linha.p2()

    def _atualizar_criacao(self, pos_viewport, modificadores: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        atual = self._ajustar_guias_dinamicas(self.mapToScene(pos_viewport), (self._ponto_inicial_criacao,))
        if self._ferramenta in _FERRAMENTAS_RETANGULO_ARRASTO and isinstance(self._item_preview_criacao, QGraphicsRectItem):
            self._item_preview_criacao.setRect(self._retangulo_de_criacao(atual, modificadores))
        elif isinstance(self._item_preview_criacao, QGraphicsLineItem):
            linha = QLineF(self._ponto_inicial_criacao, self._fim_linha_de_criacao(atual, modificadores))
            self._item_preview_criacao.setLine(linha)
            if self._ferramenta == FerramentaMockup.MEDIR:
                self._rotulo_medida.setText(f"{linha.length():.1f} mm")
                self._rotulo_medida.adjustSize()
                self._rotulo_medida.move(pos_viewport.x() + 14, pos_viewport.y() - self._rotulo_medida.height() - 10)

    def _finalizar_criacao(self, pos_viewport, modificadores: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        self._criando = False
        self._limpar_guias_dinamicas()
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

        atual = self._ajustar_guias_dinamicas(self.mapToScene(pos_viewport), (self._ponto_inicial_criacao,))
        self._limpar_guias_dinamicas()
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
            atual = self._fim_linha_de_criacao(atual, modificadores)
            if QLineF(self._ponto_inicial_criacao, atual).length() >= 2.0:
                self.linha_desenhada.emit(self._ponto_inicial_criacao, atual)
        elif self._ferramenta in FERRAMENTAS_COTA:
            atual = self._fim_linha_de_criacao(atual, modificadores)
            if QLineF(self._ponto_inicial_criacao, atual).length() >= 2.0:
                self.cota_desenhada.emit(self._ponto_inicial_criacao, atual, FERRAMENTAS_COTA[self._ferramenta])

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
    def _atualizar_area_rolagem(self) -> None:
        """Mesa grande em volta da chapa (3× o tamanho dela pra cada lado,
        no mínimo 500 mm), como a área de trabalho do CorelDRAW. Sem isso a
        área de rolagem era só o tamanho do desenho: dando zoom, a vista não
        passava da borda e o desenho ficava "preso" num canto da tela."""
        desenho = self.retangulo_do_desenho()
        if desenho.isEmpty():
            return
        folga = max(500.0, 3.0 * max(desenho.width(), desenho.height()))
        self.setSceneRect(desenho.adjusted(-folga, -folga, folga, folga))

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
        self._atualizar_area_rolagem()
        self._atualizar_painel_dimensao()
        self._reposicionar_paineis()

    def _desenhar_linhas_tecnicas(self) -> None:
        assert self._layout is not None
        for linha in self.linhas_faca():
            cor, estilo, largura = _ESTILO_POR_TIPO.get(
                linha.tipo, (QColor(0, 0, 0), Qt.PenStyle.SolidLine, 0.5)
            )
            pen = QPen(cor, largura, estilo)
            pen.setCosmetic(True)  # espessura constante independente do zoom
            if geo.e_arco(linha):
                item = QGraphicsPathItem(caminho_da_linha(linha))
            else:
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
        if ativo and self._editando_faca:
            self._editando_faca = False
            self._faca_sel = None
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

    def iniciar_texto_novo(self, texto: "ElementoTexto", pos: QPointF) -> None:
        """Texto da ferramenta Texto: entra na cena e já em edição, mas só
        vira passo de desfazer quando a digitação termina — e se terminar
        vazio some sem deixar rastro, como no CorelDRAW."""
        self._scene.addItem(texto)
        texto.setPos(pos)
        self._registrar_elemento_mockup(texto)
        self._scene.clearSelection()
        texto.setSelected(True)
        texto.iniciar_edicao(recem_criado=True)

    def _ao_terminar_edicao_texto(self, texto, antes: tuple, depois: tuple, era_novo: bool) -> None:
        vazio = not depois[0].strip()
        if era_novo:
            if vazio:
                self._retirar_elemento(texto)
            else:
                self._pilha_desfazer.push(_ComandoAdicionarElemento(self, texto, "Texto"))
            return
        if vazio:
            # Apagou tudo de um texto que existia: some, com desfazer que
            # devolve o texto como era.
            texto.definir_estado_texto(antes)
            self._pilha_desfazer.push(_ComandoRemoverElementos(self, [texto], "Apagar texto"))
        elif antes != depois:
            self._pilha_desfazer.push(_ComandoEditarTexto(texto, antes, depois))

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
        self.elementos_alterados.emit()
        if hasattr(elemento, "ao_terminar_edicao"):  # texto e callout
            elemento.ao_terminar_edicao = self._ao_terminar_edicao_texto
        elemento.definir_calculador_snap(self._calcular_snap)
        elemento.definir_ajustador_arrasto(self._ajustar_arrasto)
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
        self.elementos_alterados.emit()

    def _retirar_elemento(self, elemento: ElementoMockup) -> None:
        if elemento.scene() is not None:
            self._scene.removeItem(elemento)
        if elemento in self._elementos_mockup:
            self._elementos_mockup.remove(elemento)
        self.elementos_alterados.emit()

    def _registrar_comando_geometria(self, antes: dict, depois: dict) -> None:
        self._pilha_desfazer.push(_ComandoAlterarGeometria(antes, depois))

    def definir_snap_ativo(self, ativo: bool) -> None:
        self._snap_ativo = ativo

    def ajustar_a(self, chave: str) -> bool:
        return self._ajustar_a[chave]

    def definir_ajustar_a(self, chave: str, ativo: bool) -> None:
        if self._ajustar_a[chave] != ativo:
            self._ajustar_a[chave] = ativo
            self.ajustar_a_alterado.emit(chave, ativo)

    def adicionar_guia(self, orientacao: str, posicao_mm: float) -> GuiaCanvas:
        guia = GuiaCanvas(orientacao, posicao_mm)
        self._scene.addItem(guia)
        self._guias.append(guia)
        return guia

    def remover_guia(self, guia: GuiaCanvas) -> None:
        if guia in self._guias:
            self._guias.remove(guia)
        self._scene.removeItem(guia)

    # ── Encaixe (snap) — grade/bordas de outros elementos/face/guias ───
    # Limiar e passo de grade lidos ao vivo de `configuracoes.py` (mesmo
    # motivo do traço do vinco — mudar na tela de Configurações já vale
    # na próxima vez que soltar o arrasto, sem reiniciar), não mais
    # constante fixa.

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
        if self._grade_visivel and self._ajustar_a["grade"]:
            # Grade só participa do encaixe se estiver visível — senão a
            # peça "gruda" numa referência que a pessoa nem está vendo,
            # o que pareceria um bug ("por que não solta exatamente onde
            # eu larguei o mouse?").
            passo = self.passo_grade()
            candidatos.extend(round(borda / passo) * passo for borda in bordas)

        melhor_ajuste = 0.0
        menor_distancia = self.limiar_snap()
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
        if self._grade_visivel and self._ajustar_a["grade"]:
            passo = self.passo_grade()
            candidatos.extend(round(borda / passo) * passo for borda in bordas)

        melhor_alvo = None
        menor_distancia = self.limiar_snap()
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
        alvos = [g.posicao for g in self._guias if g.orientacao == "v"] if self._ajustar_a["guias"] else []
        if self._ajustar_a["objetos"]:
            for outro in self._elementos_mockup:
                if outro is elemento:
                    continue
                alvos.extend((outro.pos().x(), outro.pos().x() + outro.largura / 2, outro.pos().x() + outro.largura))
            painel = self._painel_do_elemento(elemento)
            if painel is not None:
                alvos.extend((painel.x1, (painel.x1 + painel.x2) / 2, painel.x2))
        pagina = self.retangulo_pagina()
        if self._ajustar_a["pagina"] and pagina is not None:
            alvos.extend((pagina.left(), pagina.center().x(), pagina.right()))
        return alvos

    def _alvos_snap_y(self, elemento: ElementoMockup) -> list[float]:
        alvos = [g.posicao for g in self._guias if g.orientacao == "h"] if self._ajustar_a["guias"] else []
        if self._ajustar_a["objetos"]:
            for outro in self._elementos_mockup:
                if outro is elemento:
                    continue
                alvos.extend((outro.pos().y(), outro.pos().y() + outro.altura / 2, outro.pos().y() + outro.altura))
            painel = self._painel_do_elemento(elemento)
            if painel is not None:
                alvos.extend((painel.y1, (painel.y1 + painel.y2) / 2, painel.y2))
        pagina = self.retangulo_pagina()
        if self._ajustar_a["pagina"] and pagina is not None:
            alvos.extend((pagina.top(), pagina.center().y(), pagina.bottom()))
        return alvos

    # ── Endpoint Offset Mode (Alt+clique numa ferramenta de criação) ───
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

    # ── Alinhar / agrupar / desagrupar / remover a seleção atual ───────
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
        self.elementos_alterados.emit()
        return grupo

    def desagrupar_selecionados(self) -> None:
        grupos = [it for it in self._scene.selectedItems() if isinstance(it, GrupoMockup)]
        for grupo in grupos:
            if grupo in self._elementos_mockup:
                self._elementos_mockup.remove(grupo)
            for filho in grupo.desagrupar():
                self._registrar_elemento_mockup(filho)
        self.elementos_alterados.emit()

    def remover_selecionados(self) -> None:
        elementos = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        for item in list(self._scene.selectedItems()):
            if isinstance(item, GuiaCanvas):
                self.remover_guia(item)  # guias ficam fora do undo por ora — baixo risco, é só uma linha de referência
        if elementos:
            self._pilha_desfazer.push(_ComandoRemoverElementos(self, elementos))

    # ── Duplicar / copiar-colar (Ctrl+D, Ctrl+C, Ctrl+V) ────────────────
    # `configuracoes.passo_duplicar_mm()` — deslocamento de cada cópia,
    # lido ao vivo (ver seção de snap acima pro mesmo motivo).

    def _duplicar_no_lugar(self, elemento: ElementoMockup) -> ElementoMockup:
        """Chamado por `ElementoMockup.mousePressEvent` quando o usuário
        começa a arrastar o corpo segurando Alt — deixa um clone parado
        EXATAMENTE na posição atual de `elemento` (sem deslocamento, ao
        contrário de `duplicar_selecionados`/Ctrl+D), sem selecioná-lo.
        `elemento` continua sendo o item que se move dali pra frente."""
        clone = elemento.clonar()
        self._scene.addItem(clone)
        self._registrar_elemento_mockup(clone)
        self._pilha_desfazer.push(_ComandoAdicionarElemento(self, clone, "Duplicar elemento"))
        return clone

    def duplicar_selecionados(self) -> list[ElementoMockup]:
        """Ctrl+D — clona e desloca na hora, já selecionando o clone (não
        o original), pra continuar arrastando/ajustando ele direto. Sem
        passar pela área de transferência: Ctrl+D é "mais um igual, aqui
        do lado", não "guardar pra colar depois em outro lugar/momento"
        (isso é o que Ctrl+C/V fazem, ver abaixo)."""
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if not selecionados:
            return []
        passo = configuracoes.passo_duplicar_mm()
        clones = []
        for it in selecionados:
            it.setSelected(False)
            clone = it.clonar()
            clone.setPos(clone.pos() + QPointF(passo, passo))
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
        passo = configuracoes.passo_duplicar_mm()
        clones = []
        for original in self._area_transferencia:
            clone = original.clonar()
            clone.setPos(clone.pos() + QPointF(passo, passo))
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
        self.elementos_alterados.emit()

    def enviar_para_tras(self) -> None:
        selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
        if not selecionados:
            return
        menor = min((it.zValue() for it in self._elementos_mockup), default=0.0)
        for item in selecionados:
            menor -= 1
            item.setZValue(menor)
        self.elementos_alterados.emit()

    # ── Atalhos do CorelDRAW (ver REFERENCIA_CORELDRAW.md, seção 4) ──────
    def _selecionados_mockup(self) -> list[ElementoMockup]:
        return [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]

    def _com_undo_geometria(self, texto: str, acao) -> None:
        """Roda `acao()` e empurra um único passo de desfazer com a
        geometria de antes/depois de toda a seleção."""
        selecionados = self._selecionados_mockup()
        antes: dict = {}
        for item in selecionados:
            antes.update(_estado_recursivo(item))
        acao()
        depois: dict = {}
        for item in selecionados:
            depois.update(_estado_recursivo(item))
        if antes and depois != antes:
            self._pilha_desfazer.push(_ComandoAlterarGeometria(antes, depois, texto))

    def retangulo_pagina(self) -> QRectF | None:
        """A "página" do CorelDRAW aqui é a chapa da dieline."""
        if self._layout is None:
            return None
        return QRectF(0.0, 0.0, self._layout.largura_total, self._layout.altura_total)

    def alinhar_corel(self, alinhamento: str) -> None:
        """L/R/T/B/C/E do CorelDRAW: 2+ objetos alinham entre si; um
        objeto sozinho alinha com a página (chapa da dieline)."""
        selecionados = self._selecionados_mockup()
        if not selecionados:
            return
        if len(selecionados) > 1:
            self._com_undo_geometria("Alinhar", lambda: self.alinhar_selecionados(alinhamento))
            return
        pagina = self.retangulo_pagina()
        if pagina is None:
            return
        el = selecionados[0]

        def aplicar() -> None:
            x, y = el.pos().x(), el.pos().y()
            if alinhamento == "esquerda":
                x = pagina.left()
            elif alinhamento == "direita":
                x = pagina.right() - el.largura
            elif alinhamento == "centro_h":
                x = pagina.center().x() - el.largura / 2
            elif alinhamento == "topo":
                y = pagina.top()
            elif alinhamento == "base":
                y = pagina.bottom() - el.altura
            elif alinhamento == "centro_v":
                y = pagina.center().y() - el.altura / 2
            el.setPos(x, y)

        self._com_undo_geometria("Alinhar à página", aplicar)

    def centralizar_na_pagina(self) -> None:
        """P do CorelDRAW: centro da seleção (como bloco) no centro da página."""
        selecionados = self._selecionados_mockup()
        pagina = self.retangulo_pagina()
        if not selecionados or pagina is None:
            return
        bloco = QRectF()
        for el in selecionados:
            bloco = bloco.united(el.retangulo_conteudo_cena())
        delta = pagina.center() - bloco.center()

        def aplicar() -> None:
            for el in selecionados:
                el.setPos(el.pos() + delta)

        self._com_undo_geometria("Centralizar na página", aplicar)

    # ── Faca editável (tela Dieline) ───────────────────────────────────
    def linhas_faca(self) -> list[LinhaDesenho]:
        """As linhas da faca que valem agora: as editadas à mão, se houver,
        senão as calculadas pelas medidas."""
        if self._linhas_editadas is not None:
            return self._linhas_editadas
        return [] if self._layout is None else self._layout.linhas

    @property
    def faca_editada(self) -> bool:
        return self._linhas_editadas is not None

    def _definir_linhas_editadas(self, linhas) -> None:
        estava = self._linhas_editadas is not None
        self._linhas_editadas = _copiar_linhas(linhas)
        if self._faca_sel is not None and self._faca_sel >= len(self.linhas_faca()):
            self._selecionar_linha_faca(None)
        self._redesenhar()
        if estava != (self._linhas_editadas is not None):
            self.faca_editada_alterada.emit(self._linhas_editadas is not None)
        self.viewport().update()

    def _aplicar_faca(self, texto: str, depois) -> None:
        antes = _copiar_linhas(self._linhas_editadas)
        if depois != antes:
            self._pilha_desfazer.push(_ComandoEditarFaca(self, antes, _copiar_linhas(depois), texto))

    def _linhas_para_editar(self) -> list[LinhaDesenho]:
        return _copiar_linhas(self.linhas_faca())

    @property
    def editando_faca(self) -> bool:
        return self._editando_faca

    def definir_edicao_faca(self, ativo: bool, ferramenta: str = "forma") -> None:
        """Liga a edição da faca (só fora do modo Layout): `forma` seleciona
        e arrasta linhas/pontas; `corte`/`vinco` desenham linha nova."""
        self._editando_faca = ativo and not self._modo_mockup
        self._faca_ferramenta = ferramenta
        self._faca_arrasto = None
        self._rotulo_faca = None
        if not self._editando_faca:
            self._selecionar_linha_faca(None)
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if not self._modo_mockup else self.dragMode())
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(
                Qt.CursorShape.ArrowCursor if ferramenta == "forma" else Qt.CursorShape.CrossCursor
            )
        if ferramenta in ("corte", "vinco"):
            self._faca_tipo_novo = TipoLinha.VINCO if ferramenta == "vinco" else TipoLinha.CORTE
        self._atualizar_preview_curva(None)
        self._painel_medida.hide()
        self._medida_origem = None
        self.viewport().update()

    def criar_paralela_selecionada(self, distancia_mm: float) -> bool:
        """Paralela da linha selecionada (positivo = um lado, negativo = o
        outro; no arco, pra fora/pra dentro). A nova fica selecionada."""
        if self._faca_sel is None:
            return False
        linhas = self._linhas_para_editar()
        linhas.append(geo.paralela(linhas[self._faca_sel], distancia_mm))
        self._aplicar_faca("Paralela", linhas)
        self._selecionar_linha_faca(len(linhas) - 1)
        return True

    def _ao_confirmar_medida(self, comprimento: float, angulo: float) -> None:
        """Linha por medida (ArtiosCAD: ângulo e comprimento digitados). A
        próxima começa onde esta terminou — dá pra desenhar a faca inteira
        só digitando; Esc para."""
        origem = self._medida_origem
        if origem is None or comprimento <= 0:
            return
        self._ultima_medida = (comprimento, angulo)
        nova = geo.linha_por_medida((origem.x(), origem.y()), comprimento, angulo, self._faca_tipo_novo)
        linhas = self._linhas_para_editar()
        linhas.append(nova)
        self._aplicar_faca("Linha por medida", linhas)
        self._selecionar_linha_faca(len(linhas) - 1)
        self._medida_origem = QPointF(nova.x2, nova.y2)
        self._painel_medida.iniciar(self.mapFromScene(self._medida_origem), self._ultima_medida)

    def _selecionar_linha_faca(self, indice: int | None) -> None:
        self._faca_sel = indice
        linhas = self.linhas_faca()
        self.linha_faca_selecionada.emit(None if indice is None or indice >= len(linhas) else linhas[indice].tipo)
        self.viewport().update()

    @property
    def linha_faca_selecionada_indice(self) -> int | None:
        return self._faca_sel

    def definir_tipo_linha_selecionada(self, tipo: TipoLinha) -> None:
        if self._faca_sel is None:
            return
        linhas = self._linhas_para_editar()
        if linhas[self._faca_sel].tipo == tipo:
            return
        linhas[self._faca_sel].tipo = tipo
        self._aplicar_faca("Mudar tipo da linha", linhas)

    def remover_linha_faca_selecionada(self) -> None:
        if self._faca_sel is None:
            return
        linhas = self._linhas_para_editar()
        del linhas[self._faca_sel]
        self._selecionar_linha_faca(None)
        self._aplicar_faca("Remover linha da faca", linhas)

    def descartar_edicoes_faca(self) -> None:
        if self._linhas_editadas is not None:
            self._selecionar_linha_faca(None)
            self._pilha_desfazer.push(_ComandoEditarFaca(self, _copiar_linhas(self._linhas_editadas), None, "Descartar edições da faca"))

    def _pontas_coincidentes(self, linhas, x: float, y: float) -> list[tuple[int, int]]:
        """(linha, 1|2) de toda ponta que está em (x, y) — as linhas da faca
        se tocam nas quinas e nos vincos, e mexer numa ponta leva as outras
        junto (como um nó compartilhado), senão a faca "abre"."""
        pontas = []
        for i, l in enumerate(linhas):
            if _mesmo_ponto(l.x1, l.y1, x, y):
                pontas.append((i, 1))
            if _mesmo_ponto(l.x2, l.y2, x, y):
                pontas.append((i, 2))
        return pontas

    def _encaixar_na_faca(self, ponto: QPointF, ignorar: set[tuple[int, int]] = frozenset()) -> QPointF:
        """Gruda numa ponta de linha da faca (exceto as que estão sendo
        arrastadas) — e, sem ponta por perto, no encaixe comum."""
        if not self._snap_ativo:
            return ponto
        limiar = self.limiar_snap()
        melhor, menor = None, limiar
        for i, l in enumerate(self.linhas_faca()):
            for qual, (x, y) in ((1, (l.x1, l.y1)), (2, (l.x2, l.y2))):
                if (i, qual) in ignorar:
                    continue
                d = math.hypot(x - ponto.x(), y - ponto.y())
                if d < menor:
                    melhor, menor = QPointF(x, y), d
        return melhor if melhor is not None else self.encaixar_ponto(ponto)

    def _faca_acertar(self, ponto: QPointF) -> tuple | None:
        """("ponta", linha, 1|2) ou ("linha", linha) sob o cursor."""
        tol = self._tolerancia_mm()
        linhas = self.linhas_faca()
        ordem = list(range(len(linhas)))
        if self._faca_sel is not None and self._faca_sel < len(linhas):
            ordem.remove(self._faca_sel)
            ordem.insert(0, self._faca_sel)  # a selecionada tem prioridade
        for i in ordem:
            l = linhas[i]
            for qual, (x, y) in ((1, (l.x1, l.y1)), (2, (l.x2, l.y2))):
                if math.hypot(x - ponto.x(), y - ponto.y()) <= tol:
                    return ("ponta", i, qual)
        melhor, menor = None, tol
        for i, l in enumerate(linhas):
            d = geo.distancia((ponto.x(), ponto.y()), l)
            if d <= menor:
                melhor, menor = ("linha", i), d
        return melhor

    def definir_tipo_linha_nova(self, tipo: TipoLinha) -> None:
        self._faca_tipo_novo = tipo

    def definir_raio_arredondar(self, raio: float) -> None:
        self._raio_arredondar = max(0.1, raio)

    def _ponto_de_desenho(self, ponto: QPointF, *extras: QPointF) -> QPointF:
        encaixado = self._encaixar_na_faca(ponto)
        return encaixado if encaixado != ponto else self._ajustar_guias_dinamicas(ponto, extras)

    def _faca_ferramenta_de_clique(self, ponto: QPointF) -> bool:
        """Aparar / estender / arredondar: um clique só, sobre a linha (ou o
        canto). Devolve True se tratou o clique."""
        ferramenta = self._faca_ferramenta
        if ferramenta not in ("aparar", "estender", "arredondar"):
            return False
        linhas = self._linhas_para_editar()
        clique = (ponto.x(), ponto.y())
        if ferramenta == "arredondar":
            canto = self._encaixar_na_faca(ponto)
            resultado = geo.arredondar(linhas, (canto.x(), canto.y()), self._raio_arredondar)
            if resultado is None:
                self.mensagem_status.emit(
                    "Arredondar: clique num canto onde duas retas se encontram (e o raio precisa caber nelas)."
                )
                return True
            self._aplicar_faca("Arredondar canto", resultado)
            self._selecionar_linha_faca(len(resultado) - 1)
            return True
        acerto = self._faca_acertar(ponto)
        if acerto is None:
            return True
        operacao = geo.aparar if ferramenta == "aparar" else geo.estender
        resultado = operacao(linhas, acerto[1], clique)
        if resultado is None:
            self.mensagem_status.emit(
                "Aparar: a linha precisa cruzar outra (e ser reta)."
                if ferramenta == "aparar"
                else "Estender: não há linha no caminho dessa ponta (ou a linha é arco)."
            )
            return True
        self._selecionar_linha_faca(None)
        self._aplicar_faca("Aparar linha" if ferramenta == "aparar" else "Estender linha", resultado)
        return True

    def _faca_mouse_press(self, ponto: QPointF, modificadores) -> None:
        if self._faca_ferramenta_de_clique(ponto):
            return
        if self._faca_arrasto is not None and self._faca_arrasto[0] == "arco_curvar":
            # 3º clique do arco: confirma a curvatura.
            _t, a, b, bojo = self._faca_arrasto
            self._faca_arrasto = None
            self._atualizar_preview_curva(None)
            self._limpar_guias_dinamicas()
            linhas = self._linhas_para_editar()
            linhas.append(LinhaDesenho(a.x(), a.y(), b.x(), b.y(), self._faca_tipo_novo, bojo))
            self._aplicar_faca("Arco na faca", linhas)
            self._selecionar_linha_faca(len(linhas) - 1)
            return
        if self._faca_ferramenta == "medida":
            self._medida_origem = self._ponto_de_desenho(ponto)
            self._limpar_guias_dinamicas()
            self._painel_medida.iniciar(self.mapFromScene(self._medida_origem), self._ultima_medida)
            return
        if self._faca_ferramenta in ("retangulo", "arco"):
            inicio = self._ponto_de_desenho(ponto)
            self._faca_arrasto = (self._faca_ferramenta, inicio, inicio)
            self._atualizar_preview_curva(QPainterPath(inicio))
            return
        if self._faca_ferramenta in ("corte", "vinco"):
            inicio = self._encaixar_na_faca(ponto)
            if inicio == ponto:
                inicio = self._ajustar_guias_dinamicas(ponto)
            self._faca_arrasto = ("nova", inicio, inicio)
            self._atualizar_preview_curva(QPainterPath(inicio))
            return
        acerto = self._faca_acertar(ponto)
        if acerto is None:
            self._selecionar_linha_faca(None)
            return
        linhas = self.linhas_faca()
        self._selecionar_linha_faca(acerto[1])
        self._faca_antes = _copiar_linhas(self._linhas_editadas)
        so_esta = bool(modificadores & Qt.KeyboardModifier.AltModifier)  # Alt solta a ponta das vizinhas
        if acerto[0] == "ponta":
            _t, i, qual = acerto
            l = linhas[i]
            x, y = (l.x1, l.y1) if qual == 1 else (l.x2, l.y2)
            pontas = [(i, qual)] if so_esta else self._pontas_coincidentes(linhas, x, y)
            self._faca_arrasto = ("ponta", pontas, QPointF(x, y), self._linhas_para_editar())
        else:
            i = acerto[1]
            l = linhas[i]
            pontas = {(i, 1), (i, 2)}
            if not so_esta:
                # Pontas ligadas: as que coincidem com as da linha E as que
                # encostam no meio dela (junção em "T", ex.: vinco vertical
                # chegando no vinco horizontal) — todas andam junto.
                for k, outra in enumerate(linhas):
                    if k == i:
                        continue
                    for qual, (x, y) in ((1, (outra.x1, outra.y1)), (2, (outra.x2, outra.y2))):
                        if geo.distancia((x, y), l) < 0.01:
                            pontas.add((k, qual))
            self._faca_arrasto = ("linha", sorted(pontas), QPointF(ponto), self._linhas_para_editar())

    def _faca_mouse_move(self, ponto: QPointF, modificadores) -> None:
        arrasto = self._faca_arrasto
        if arrasto is None:
            return
        if arrasto[0] in ("retangulo", "arco"):
            fim = self._ponto_de_desenho(ponto, arrasto[1])
            if arrasto[0] == "arco" and modificadores & Qt.KeyboardModifier.ControlModifier:
                linha = QLineF(arrasto[1], ponto)
                linha.setAngle(round(linha.angle() / 15.0) * 15.0)
                fim = linha.p2()
            self._faca_arrasto = (arrasto[0], arrasto[1], fim)
            if arrasto[0] == "retangulo":
                caminho = QPainterPath()
                caminho.addRect(QRectF(arrasto[1], fim).normalized())
                r = QRectF(arrasto[1], fim).normalized()
                self._rotulo_faca = (ponto, f"{r.width():.2f} × {r.height():.2f} mm".replace(".", ","))
            else:
                caminho = QPainterPath(arrasto[1])
                caminho.lineTo(fim)
            self._atualizar_preview_curva(caminho)
            return
        if arrasto[0] == "arco_curvar":
            # Depois de soltar a corda: mexer o mouse curva o arco, que passa
            # pelo cursor; o próximo clique confirma.
            _t, a, b, _bojo = arrasto
            bojo = geo.bojo_por_tres_pontos((a.x(), a.y()), (ponto.x(), ponto.y()), (b.x(), b.y()))
            self._faca_arrasto = ("arco_curvar", a, b, bojo)
            self._atualizar_preview_curva(caminho_da_linha(LinhaDesenho(a.x(), a.y(), b.x(), b.y(), self._faca_tipo_novo, bojo)))
            return
        if arrasto[0] == "nova":
            fim = self._encaixar_na_faca(ponto)
            if fim == ponto:
                fim = self._ajustar_guias_dinamicas(ponto, (arrasto[1],))
            if modificadores & Qt.KeyboardModifier.ControlModifier:
                linha = QLineF(arrasto[1], ponto)
                linha.setAngle(round(linha.angle() / 15.0) * 15.0)
                fim = linha.p2()
            self._faca_arrasto = ("nova", arrasto[1], fim)
            linha_nova = QLineF(arrasto[1], fim)
            self._rotulo_faca = (ponto, f"{linha_nova.length():.2f} mm  {linha_nova.angle():.1f}°".replace(".", ","))
            caminho = QPainterPath(arrasto[1])
            caminho.lineTo(fim)
            self._atualizar_preview_curva(caminho)
            return
        tipo, pontas, inicio, originais = arrasto
        delta = ponto - inicio
        trava = None
        if modificadores & Qt.KeyboardModifier.ShiftModifier:
            # Shift: só na horizontal ou na vertical, como no CorelDRAW.
            trava = "h" if abs(delta.x()) >= abs(delta.y()) else "v"
            delta = QPointF(delta.x(), 0.0) if trava == "h" else QPointF(0.0, delta.y())
        # Precisão (CorelDRAW): os pontos que se mexem grudam em nós e
        # alinham na horizontal/vertical com os nós que ficam parados,
        # com a guia tracejada mostrando com quem está alinhado.
        moventes = []
        for i, qual in pontas:
            o = originais[i]
            p = QPointF(o.x1, o.y1) if qual == 1 else QPointF(o.x2, o.y2)
            if all(abs(p.x() - m.x()) > 1e-6 or abs(p.y() - m.y()) > 1e-6 for m in moventes):
                moventes.append(p)
        correcao = self._alinhar_pontos_faca([m + delta for m in moventes], self._nos_fixos_faca(originais, set(pontas)), trava)
        delta += correcao
        self._rotulo_faca = self._texto_medida_arrasto(tipo, pontas, originais, delta, ponto)
        linhas = _copiar_linhas(originais)
        for i, qual in pontas:
            l, o = linhas[i], originais[i]
            if qual == 1:
                l.x1, l.y1 = o.x1 + delta.x(), o.y1 + delta.y()
            else:
                l.x2, l.y2 = o.x2 + delta.x(), o.y2 + delta.y()
        self._linhas_editadas = linhas
        self._redesenhar()
        self.viewport().update()

    def _nos_fixos_faca(self, linhas, moventes: set) -> list[tuple[QPointF, str]]:
        """Nós que NÃO se mexem no arrasto: pontas paradas da faca, meio das
        linhas que ficam inteiras paradas, objetos e chapa."""
        fixos: list[tuple[QPointF, str]] = []
        for i, l in enumerate(linhas):
            parada1, parada2 = (i, 1) not in moventes, (i, 2) not in moventes
            if parada1:
                fixos.append((QPointF(l.x1, l.y1), "nó"))
            if parada2:
                fixos.append((QPointF(l.x2, l.y2), "nó"))
            if parada1 and parada2:
                fixos.append((QPointF((l.x1 + l.x2) / 2, (l.y1 + l.y2) / 2), "ponto médio"))
        fixos += self.nos_de_encaixe_com_tipo(incluir_faca=False)
        return fixos

    def _alinhar_pontos_faca(self, propostos: list[QPointF], fixos, trava: str | None = None) -> QPointF:
        """Correção a somar no deslocamento: primeiro gruda num nó (2D, com
        o nome dele na tela); senão alinha cada eixo com o nó parado mais
        próximo e desenha a guia até ele."""
        self._linhas_dinamicas = []
        self._mostrar_indicador(None)
        if not propostos:
            return QPointF()
        if self._snap_ativo and trava is None:
            melhor, menor = None, self.limiar_snap()
            for p in propostos:
                for f, nome in fixos:
                    d = math.hypot(f.x() - p.x(), f.y() - p.y())
                    if d < menor:
                        melhor, menor = (f - p, f, nome), d
            if melhor is not None:
                self._mostrar_indicador((QPointF(melhor[1]), melhor[2]))
                return melhor[0]
        if not self._guias_dinamicas:
            return QPointF()
        tol = self._tolerancia_mm()
        bx = by = None  # (diferença, fixo, proposto)
        for p in propostos:
            for f, _nome in fixos:
                dx, dy = f.x() - p.x(), f.y() - p.y()
                if trava != "h" and abs(dx) < tol and (bx is None or abs(dx) < abs(bx[0])):
                    bx = (dx, f, p)
                if trava != "v" and abs(dy) < tol and (by is None or abs(dy) < abs(by[0])):
                    by = (dy, f, p)
        correcao = QPointF(bx[0] if bx else 0.0, by[0] if by else 0.0)
        for achado in (bx, by):
            if achado is not None:
                self._linhas_dinamicas.append((QPointF(achado[1]), achado[2] + correcao))
        self.viewport().update()
        return correcao

    def _texto_medida_arrasto(self, tipo, pontas, originais, delta: QPointF, cursor: QPointF):
        """Rótulo ao lado do cursor: ao mover a linha, o deslocamento; ao
        mover a ponta, o comprimento e o ângulo da linha."""
        def mm(v: float) -> str:
            return f"{v:.2f}".replace(".", ",")

        if tipo == "linha":
            return (cursor, f"Δx {mm(delta.x())}  Δy {mm(-delta.y())} mm")
        i, qual = next(((i, q) for i, q in pontas if i == self._faca_sel), pontas[0])
        o = originais[i]
        a = QPointF(o.x2, o.y2) if qual == 1 else QPointF(o.x1, o.y1)
        b = (QPointF(o.x1, o.y1) if qual == 1 else QPointF(o.x2, o.y2)) + delta
        linha = QLineF(a, b)
        return (cursor, f"{mm(linha.length())} mm  {linha.angle():.1f}°".replace(".", ","))

    def _faca_mouse_release(self) -> None:
        self._limpar_guias_dinamicas()
        self._rotulo_faca = None
        self._mostrar_indicador(None)
        arrasto, self._faca_arrasto = self._faca_arrasto, None
        if arrasto is None:
            return
        if arrasto[0] == "arco_curvar":
            self._faca_arrasto = arrasto  # continua esperando o clique que confirma
            return
        if arrasto[0] in ("retangulo", "arco"):
            _t, a, b = arrasto
            if QLineF(a, b).length() < 1.0:
                self._atualizar_preview_curva(None)
                return
            if arrasto[0] == "arco":
                self._faca_arrasto = ("arco_curvar", a, b, 0.0)
                self.mensagem_status.emit("Arco: mexa o mouse pra curvar e clique pra confirmar (Esc cancela).")
                return
            self._atualizar_preview_curva(None)
            if abs(a.x() - b.x()) < 1.0 or abs(a.y() - b.y()) < 1.0:
                return
            linhas = self._linhas_para_editar()
            linhas += geo.retangulo((a.x(), a.y()), (b.x(), b.y()), self._faca_tipo_novo)
            self._aplicar_faca("Retângulo na faca", linhas)
            return
        if arrasto[0] == "nova":
            self._atualizar_preview_curva(None)
            _t, inicio, fim = arrasto
            if QLineF(inicio, fim).length() < 1.0:
                return
            tipo = TipoLinha.VINCO if self._faca_ferramenta == "vinco" else TipoLinha.CORTE
            linhas = self._linhas_para_editar()
            linhas.append(LinhaDesenho(inicio.x(), inicio.y(), fim.x(), fim.y(), tipo))
            self._aplicar_faca("Nova linha na faca", linhas)
            self._selecionar_linha_faca(len(linhas) - 1)
            return
        depois = _copiar_linhas(self._linhas_editadas)
        # Volta pro estado de antes do gesto e empurra UM comando de desfazer.
        self._linhas_editadas = _copiar_linhas(self._faca_antes)
        if depois != (self._faca_antes if self._faca_antes is not None else self._layout.linhas):
            self._pilha_desfazer.push(_ComandoEditarFaca(self, self._faca_antes, depois, "Mover na faca"))
        else:
            self._redesenhar()
        self._faca_antes = None

    def _tecla_faca(self, event) -> bool:
        if event.key() == Qt.Key.Key_Delete and self._faca_sel is not None:
            self.remover_linha_faca_selecionada()
            return True
        if event.key() == Qt.Key.Key_Escape:
            if self._faca_arrasto is not None and self._faca_arrasto[0] in ("retangulo", "arco", "arco_curvar", "nova"):
                self._faca_arrasto = None
                self._atualizar_preview_curva(None)
                return True
            if self._faca_arrasto is not None:
                self._faca_arrasto = None
                self._atualizar_preview_curva(None)
                self._linhas_editadas = _copiar_linhas(self._faca_antes) if self._faca_antes is not None else self._linhas_editadas
                self._redesenhar()
            else:
                self._selecionar_linha_faca(None)
            return True
        return False

    def _desenhar_overlay_faca(self, painter) -> None:
        escala = self.transform().m11() or 1.0
        lado = 5.0 / escala
        caneta = QPen(QColor(Cor.PRIMARIA), 1.0)
        caneta.setCosmetic(True)
        painter.save()
        painter.setPen(caneta)
        linhas = self.linhas_faca()
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        vistos = set()
        for l in linhas:
            for x, y in ((l.x1, l.y1), (l.x2, l.y2)):
                chave = (round(x, 2), round(y, 2))
                if chave in vistos:
                    continue
                vistos.add(chave)
                painter.drawRect(QRectF(x - lado / 2, y - lado / 2, lado, lado))
        if self._faca_sel is not None and self._faca_sel < len(linhas):
            l = linhas[self._faca_sel]
            destaque = QPen(QColor(Cor.PRIMARIA), 3.0)
            destaque.setCosmetic(True)
            painter.setPen(destaque)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(caminho_da_linha(l))
            painter.setPen(caneta)
            painter.setBrush(QBrush(QColor(Cor.PRIMARIA)))
            for x, y in ((l.x1, l.y1), (l.x2, l.y2)):
                painter.drawRect(QRectF(x - lado / 2, y - lado / 2, lado, lado))
        painter.restore()

    # ── Curvas: Bézier, Mão livre e Forma (ver mockup_curva.py) ─────────
    def _tolerancia_mm(self) -> float:
        return _TOLERANCIA_NO_PX / (self.transform().m11() or 1.0)

    def _atualizar_preview_curva(self, caminho: QPainterPath | None) -> None:
        if caminho is None:
            if self._item_preview_curva is not None:
                self._scene.removeItem(self._item_preview_curva)
                self._item_preview_curva = None
            return
        if self._item_preview_curva is None:
            self._item_preview_curva = QGraphicsPathItem()
            self._item_preview_curva.setPen(self._caneta_preview())
            self._item_preview_curva.setZValue(3000)
            self._scene.addItem(self._item_preview_curva)
        self._item_preview_curva.setPath(caminho)

    def _cancelar_curva_em_andamento(self) -> None:
        self._limpar_guias_dinamicas()
        self._angular_pontos = []
        self._bezier_nos = []
        self._bezier_arrastando = False
        self._mao_livre_pontos = None
        self._atualizar_preview_curva(None)

    def _terminar_bezier(self, fechar: bool) -> None:
        if len(self._bezier_nos) >= 2:
            self.curva_desenhada.emit(caminho_de_subcaminhos([SubCaminho(self._bezier_nos, fechar)]))
        self._cancelar_curva_em_andamento()

    def _definir_alvo_forma(self, curva: ElementoCurva | None) -> None:
        if curva is not None and (curva.espelho_h or curva.espelho_v):
            curva._renormalizar(curva._assentar())  # assa o espelho antes de editar nós
        anterior = self._forma_alvo
        if anterior is not None and anterior is not curva:
            try:
                anterior.definir_alcas_visiveis(True)
            except RuntimeError:
                pass  # já destruído
        if curva is not None:
            curva.definir_alcas_visiveis(False)
        self._forma_alvo = curva
        self._forma_no = None
        self._forma_arrasto = None
        self.viewport().update()

    def _nos_cena(self, curva: ElementoCurva) -> list[list[No]]:
        f = curva.mapToScene
        return [[no.mapeado(f) for no in sub.nos] for sub in curva.subcaminhos_locais()]

    def _forma_acertar(self, ponto: QPointF) -> tuple[str, int, int] | None:
        curva = self._forma_alvo
        if curva is None or curva.scene() is None:
            return None
        tol = self._tolerancia_mm()
        nos = self._nos_cena(curva)

        def perto(q: QPointF) -> bool:
            return QLineF(q, ponto).length() <= tol

        if self._forma_no is not None:
            i, j = self._forma_no
            if i < len(nos) and j < len(nos[i]):
                no = nos[i][j]
                for qual in ("entrada", "saida"):
                    alca = getattr(no, qual)
                    if QLineF(alca, no.p).length() > 1e-6 and perto(alca):
                        return (qual, i, j)
        for i, sub in enumerate(nos):
            for j, no in enumerate(sub):
                if perto(no.p):
                    return ("no", i, j)
        return None

    def _elemento_raiz_em(self, ponto: QPointF) -> ElementoMockup | None:
        for item in self._scene.items(ponto):
            while item is not None and not isinstance(item, ElementoMockup):
                item = item.parentItem()
            if item is None:
                continue
            while isinstance(item.parentItem(), ElementoMockup):
                item = item.parentItem()
            return item
        return None

    def _preview_angular(self, cursor: QPointF | None) -> None:
        pontos = self._angular_pontos
        if not pontos:
            self._atualizar_preview_curva(None)
            return
        caminho = QPainterPath(pontos[0])
        for q in pontos[1:] + ([cursor] if cursor is not None else []):
            caminho.moveTo(pontos[0])
            caminho.lineTo(q)
        self._atualizar_preview_curva(caminho)

    def _curva_mouse_press(self, ponto: QPointF) -> None:
        if self._ferramenta == FerramentaMockup.COTA_ANGULAR:
            encaixado = self.encaixar_ponto(ponto)
            ponto = encaixado if encaixado != ponto else self._ajustar_guias_dinamicas(ponto, self._angular_pontos)
            self._angular_pontos.append(ponto)
            if len(self._angular_pontos) == 3:
                v, a, b = self._angular_pontos
                self._cancelar_curva_em_andamento()
                if QLineF(v, a).length() >= 1.0 and QLineF(v, b).length() >= 1.0:
                    self.cota_angular_desenhada.emit(v, a, b)
            else:
                self._preview_angular(None)
            return
        if self._ferramenta == FerramentaMockup.BEZIER:
            encaixado = self.encaixar_ponto(ponto)
            ponto = encaixado if encaixado != ponto else self._ajustar_guias_dinamicas(ponto, [n.p for n in self._bezier_nos])
            if len(self._bezier_nos) >= 2 and QLineF(ponto, self._bezier_nos[0].p).length() <= self._tolerancia_mm():
                self._terminar_bezier(fechar=True)
                return
            self._bezier_nos.append(No.canto(ponto))
            self._bezier_arrastando = True
            self._atualizar_preview_curva(caminho_de_subcaminhos([SubCaminho(self._bezier_nos)]))
            return
        if self._ferramenta == FerramentaMockup.MAO_LIVRE:
            self._mao_livre_pontos = [ponto]
            return
        # Forma
        acerto = self._forma_acertar(ponto)
        if acerto is not None:
            qual, i, j = acerto
            if qual == "no":
                self._forma_no = (i, j)
            self._forma_arrasto = acerto
            self._forma_estado_antes = self._forma_alvo.estado_nos()
            self.viewport().update()
            return
        elemento = self._elemento_raiz_em(ponto)
        self._scene.clearSelection()
        if isinstance(elemento, ElementoCurva):
            elemento.setSelected(True)
            self._definir_alvo_forma(elemento)
        else:
            self._definir_alvo_forma(None)
            if elemento is not None:
                elemento.setSelected(True)
                self.mensagem_status.emit("Converta em curvas (Ctrl+Q) pra editar os nós deste objeto.")

    def _curva_mouse_move(self, ponto: QPointF, botoes) -> None:
        segurando = bool(botoes & Qt.MouseButton.LeftButton)
        if self._ferramenta == FerramentaMockup.COTA_ANGULAR:
            if self._angular_pontos:
                encaixado = self.encaixar_ponto(ponto)
                if encaixado == ponto:
                    encaixado = self._ajustar_guias_dinamicas(ponto, self._angular_pontos)
                self._preview_angular(encaixado)
            return
        if self._ferramenta == FerramentaMockup.BEZIER and self._bezier_nos:
            if segurando and self._bezier_arrastando:
                no = self._bezier_nos[-1]
                no.saida = QPointF(ponto)
                no.entrada = no.p * 2 - ponto
                no.suave = True
                caminho = caminho_de_subcaminhos([SubCaminho(self._bezier_nos)])
            else:
                encaixado = self.encaixar_ponto(ponto)
                if encaixado == ponto:
                    encaixado = self._ajustar_guias_dinamicas(ponto, [n.p for n in self._bezier_nos])
                caminho = caminho_de_subcaminhos([SubCaminho(self._bezier_nos + [No.canto(encaixado)])])
            self._atualizar_preview_curva(caminho)
        elif self._ferramenta == FerramentaMockup.MAO_LIVRE and self._mao_livre_pontos is not None and segurando:
            if QLineF(self._mao_livre_pontos[-1], ponto).length() >= 0.3:
                self._mao_livre_pontos.append(QPointF(ponto))
                caminho = QPainterPath(self._mao_livre_pontos[0])
                for q in self._mao_livre_pontos[1:]:
                    caminho.lineTo(q)
                self._atualizar_preview_curva(caminho)
        elif self._ferramenta == FerramentaMockup.FORMA and self._forma_arrasto is not None and segurando:
            qual, i, j = self._forma_arrasto
            local = self._forma_alvo.mapFromScene(ponto)
            if qual == "no":
                self._forma_alvo.mover_no(i, j, local)
            else:
                self._forma_alvo.mover_alca(i, j, qual, local)
            self.viewport().update()

    def _curva_mouse_release(self, ponto: QPointF) -> None:
        if self._ferramenta == FerramentaMockup.BEZIER and self._bezier_nos:
            self._bezier_arrastando = False
            no = self._bezier_nos[-1]
            if QLineF(no.saida, no.p).length() < 0.3:
                self._bezier_nos[-1] = No.canto(no.p)  # clique seco = nó de canto
        elif self._ferramenta == FerramentaMockup.MAO_LIVRE and self._mao_livre_pontos is not None:
            pontos = _simplificar(self._mao_livre_pontos + [QPointF(ponto)], 0.35)
            self._mao_livre_pontos = None
            self._atualizar_preview_curva(None)
            if len(pontos) >= 2 and QLineF(pontos[0], pontos[-1]).length() + len(pontos) > 2.5:
                fechar = len(pontos) > 2 and QLineF(pontos[0], pontos[-1]).length() <= self._tolerancia_mm()
                if fechar:
                    pontos = pontos[:-1]
                self.curva_desenhada.emit(caminho_de_subcaminhos([SubCaminho([No.canto(q) for q in pontos], fechar)]))
        elif self._ferramenta == FerramentaMockup.FORMA and self._forma_arrasto is not None:
            self._forma_arrasto = None
            depois = self._forma_alvo.estado_nos()
            if self._forma_estado_antes is not None and depois != self._forma_estado_antes:
                self._pilha_desfazer.push(_ComandoEditarCurva(self._forma_alvo, self._forma_estado_antes, depois))
            self._forma_estado_antes = None

    def _editar_curva(self, texto: str, acao) -> None:
        curva = self._forma_alvo
        antes = curva.estado_nos()
        resultado = acao()
        depois = curva.estado_nos()
        if depois != antes:
            self._pilha_desfazer.push(_ComandoEditarCurva(curva, antes, depois, texto))
        self.viewport().update()
        return resultado

    def _curva_duplo_clique(self, ponto: QPointF) -> None:
        if self._ferramenta == FerramentaMockup.COTA_ANGULAR:
            # O 2º clique do duplo clique não passa por `mousePressEvent`:
            # conta como mais um ponto, senão a cota "engoliria" o clique.
            self._curva_mouse_press(ponto)
            return
        if self._ferramenta == FerramentaMockup.BEZIER:
            self._terminar_bezier(fechar=False)
            return
        if self._ferramenta != FerramentaMockup.FORMA or self._forma_alvo is None:
            return
        acerto = self._forma_acertar(ponto)
        if acerto is not None and acerto[0] == "no":
            # Duplo clique no nó remove (CorelDRAW); na curva, adiciona.
            _q, i, j = acerto
            if self._editar_curva("Remover nó", lambda: self._forma_alvo.remover_no(i, j)):
                self._forma_no = None
            return
        # Item sem escala própria: local e cena têm a mesma unidade (mm).
        local = self._forma_alvo.mapFromScene(ponto)
        segmento = self._forma_alvo.segmento_mais_proximo(local, self._tolerancia_mm())
        if segmento is not None:
            i, k, t = segmento
            self._editar_curva("Adicionar nó", lambda: self._forma_alvo.inserir_no(i, k, t))
            self._forma_no = (i, k + 1)

    def _tecla_curva(self, event) -> bool:
        tecla = event.key()
        if self._ferramenta == FerramentaMockup.COTA_ANGULAR and self._angular_pontos and tecla == Qt.Key.Key_Escape:
            self._cancelar_curva_em_andamento()
            return True
        if self._ferramenta == FerramentaMockup.BEZIER and self._bezier_nos:
            if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self._terminar_bezier(fechar=False)
                return True
            if tecla == Qt.Key.Key_Escape:
                self._cancelar_curva_em_andamento()
                return True
        if self._ferramenta == FerramentaMockup.FORMA and self._forma_alvo is not None and self._forma_no is not None:
            i, j = self._forma_no
            if tecla == Qt.Key.Key_Delete:
                if self._editar_curva("Remover nó", lambda: self._forma_alvo.remover_no(i, j)):
                    self._forma_no = None
                return True
            if tecla == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.NoModifier:
                self._editar_curva("Canto/suave", lambda: self._forma_alvo.alternar_suave(i, j))
                return True
        return False

    def drawForeground(self, painter, rect) -> None:  # noqa: N802
        super().drawForeground(painter, rect)
        if self._indicador_encaixe is not None or self._medidas_distancia or self._rotulo_faca is not None:
            self._desenhar_indicadores(painter)
        if self._linhas_dinamicas:
            self._desenhar_guias_dinamicas(painter)
        if self._editando_faca and not self._modo_mockup:
            self._desenhar_overlay_faca(painter)
        curva = self._forma_alvo
        if not (self._modo_mockup and self._ferramenta == FerramentaMockup.FORMA and curva is not None and curva.scene()):
            return
        escala = self.transform().m11() or 1.0
        lado = 6.0 / escala
        caneta = QPen(QColor(Cor.PRIMARIA), 1.0)
        caneta.setCosmetic(True)
        painter.save()
        painter.setPen(caneta)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(curva.caminho_cena())
        for i, sub in enumerate(self._nos_cena(curva)):
            for j, no in enumerate(sub):
                selecionado = self._forma_no == (i, j)
                if selecionado:
                    for alca in (no.entrada, no.saida):
                        if QLineF(alca, no.p).length() > 1e-6:
                            painter.drawLine(no.p, alca)
                            painter.setBrush(QBrush(QColor(Cor.PRIMARIA)))
                            painter.drawEllipse(alca, lado * 0.45, lado * 0.45)
                painter.setBrush(QBrush(QColor(Cor.PRIMARIA) if selecionado else QColor(255, 255, 255)))
                painter.drawRect(QRectF(no.p.x() - lado / 2, no.p.y() - lado / 2, lado, lado))
        painter.restore()

    # ── Converter / combinar / separar (Ctrl+Q / Ctrl+L / Ctrl+K) ──────
    def _caminho_cena_de(self, elemento: ElementoMockup) -> QPainterPath | None:
        if isinstance(elemento, ElementoCurva):
            return elemento.caminho_cena()
        resultado = caminho_local_de(elemento)
        if resultado is None:
            return None
        caminho = resultado[0]
        if elemento.espelho_h or elemento.espelho_v:
            t = QTransform()
            t.translate(elemento.largura / 2, elemento.altura / 2)
            t.scale(-1.0 if elemento.espelho_h else 1.0, -1.0 if elemento.espelho_v else 1.0)
            t.translate(-elemento.largura / 2, -elemento.altura / 2)
            caminho = t.map(caminho)
        return elemento.sceneTransform().map(caminho)

    def _trocar_elementos(self, texto: str, removidos: list[ElementoMockup], novos: list[ElementoMockup]) -> None:
        """Um passo de desfazer: tira `removidos` e põe `novos` (selecionados)."""
        self._pilha_desfazer.beginMacro(texto)
        try:
            self._pilha_desfazer.push(_ComandoRemoverElementos(self, removidos))
            for novo in novos:
                if novo.scene() is None:
                    self._scene.addItem(novo)
                self._registrar_elemento_mockup(novo)
                self._pilha_desfazer.push(_ComandoAdicionarElemento(self, novo, texto))
        finally:
            self._pilha_desfazer.endMacro()
        self._scene.clearSelection()
        for novo in novos:
            novo.setSelected(True)
        self.elementos_alterados.emit()

    def converter_selecionados_em_curvas(self) -> int:
        removidos, novos = [], []
        for el in self._selecionados_mockup():
            if isinstance(el, ElementoCurva):
                continue
            curva = converter_em_curva(el)
            if curva is None:
                continue
            curva.setZValue(el.zValue())
            removidos.append(el)
            novos.append(curva)
        if novos:
            self._trocar_elementos("Converter em curvas", removidos, novos)
        elif self._selecionados_mockup():
            self.mensagem_status.emit("Este tipo de objeto ainda não converte em curvas.")
        return len(novos)

    def combinar_selecionados(self) -> ElementoCurva | None:
        selecionados = [el for el in self._selecionados_mockup() if self._caminho_cena_de(el) is not None]
        if len(selecionados) < 2:
            return None
        base = min(selecionados, key=lambda el: el.zValue())  # aparência do de baixo
        caminho = QPainterPath()
        for el in sorted(selecionados, key=lambda el: el.zValue()):
            caminho.addPath(self._caminho_cena_de(el))
        resultado = caminho_local_de(base)
        curva = curva_de_caminho_cena(
            caminho,
            cor_tinta=getattr(base, "cor_tinta", None),
            preenchido=resultado[1] if resultado else False,
            largura_traco=resultado[2] if resultado else 0.5,
        )
        if curva is None:
            return None
        curva.setZValue(max(el.zValue() for el in selecionados))
        self._trocar_elementos("Combinar", selecionados, [curva])
        return curva

    def separar_selecionados(self) -> list[ElementoCurva]:
        removidos, novos = [], []
        for curva in [el for el in self._selecionados_mockup() if isinstance(el, ElementoCurva)]:
            pedacos = []
            for sub in curva.subcaminhos_locais():
                local = caminho_de_subcaminhos([sub])
                if curva.espelho_h or curva.espelho_v:
                    t = QTransform()
                    t.translate(curva.largura / 2, curva.altura / 2)
                    t.scale(-1.0 if curva.espelho_h else 1.0, -1.0 if curva.espelho_v else 1.0)
                    t.translate(-curva.largura / 2, -curva.altura / 2)
                    local = t.map(local)
                pedacos.append(curva.sceneTransform().map(local))
            if len(pedacos) < 2:
                continue
            removidos.append(curva)
            for pedaco in pedacos:
                nova = curva_de_caminho_cena(
                    pedaco, cor_tinta=curva.cor_tinta, preenchido=curva.preenchido, largura_traco=curva.largura_traco
                )
                if nova is not None:
                    nova.setZValue(curva.zValue())
                    novos.append(nova)
        if novos:
            self._trocar_elementos("Separar", removidos, novos)
        return novos

    # ── Guias dinâmicas ───────────────────────────────────────────────
    @property
    def guias_dinamicas(self) -> bool:
        return self._guias_dinamicas

    def definir_guias_dinamicas(self, ativas: bool) -> None:
        if self._guias_dinamicas != ativas:
            self._guias_dinamicas = ativas
            self._limpar_guias_dinamicas()
            self.guias_dinamicas_alteradas.emit(ativas)

    def _mostra_guias_ao_pairar(self) -> bool:
        if self._modo_mockup:
            return self._ferramenta in _FERRAMENTAS_DESENHO_COM_GUIAS and not (
                (self._ferramenta == FerramentaMockup.BEZIER and self._bezier_nos)
                or (self._ferramenta == FerramentaMockup.COTA_ANGULAR and self._angular_pontos)
            )
        return self._editando_faca and self._faca_ferramenta in ("corte", "vinco")

    def _limpar_guias_dinamicas(self) -> None:
        if self._linhas_dinamicas:
            self._linhas_dinamicas = []
            self.viewport().update()

    def _ajustar_guias_dinamicas(self, ponto: QPointF, extras: list[QPointF] | tuple = ()) -> QPointF:
        """Alinha `ponto` na vertical e/ou na horizontal com o nó mais
        próximo (dentro de alguns pixels) e guarda as guias pra desenhar.
        Cada eixo é independente — pode alinhar com um nó em X e outro em Y,
        e aí o ponto cai no cruzamento das duas guias, como no CorelDRAW."""
        self._linhas_dinamicas = []
        if not self._guias_dinamicas:
            return ponto
        tol = self._tolerancia_mm()
        melhor_x, menor_x = None, tol
        melhor_y, menor_y = None, tol
        for no in list(self.nos_de_encaixe()) + list(extras):
            dx, dy = abs(no.x() - ponto.x()), abs(no.y() - ponto.y())
            if dx < 1e-6 and dy < 1e-6:
                continue  # em cima do próprio nó: isso é encaixe em nó, não guia
            if dx < menor_x:
                melhor_x, menor_x = no, dx
            if dy < menor_y:
                melhor_y, menor_y = no, dy
        ajustado = QPointF(melhor_x.x() if melhor_x is not None else ponto.x(), melhor_y.y() if melhor_y is not None else ponto.y())
        if melhor_x is not None:
            self._linhas_dinamicas.append((QPointF(melhor_x), ajustado))
        if melhor_y is not None:
            self._linhas_dinamicas.append((QPointF(melhor_y), ajustado))
        self.viewport().update()
        return ajustado

    def _desenhar_guias_dinamicas(self, painter) -> None:
        escala = self.transform().m11() or 1.0
        sobra = 24.0 / escala
        marca = 4.0 / escala
        caneta = QPen(QColor(0, 150, 220), 1.0, Qt.PenStyle.DashLine)
        caneta.setCosmetic(True)
        painter.save()
        painter.setPen(caneta)
        for origem, ponto in self._linhas_dinamicas:
            linha = QLineF(origem, ponto)
            if linha.length() > 1e-6:
                linha.setLength(linha.length() + sobra)  # passa um pouco do cursor
            painter.drawLine(linha)
            painter.drawLine(QPointF(origem.x() - marca, origem.y() - marca), QPointF(origem.x() + marca, origem.y() + marca))
            painter.drawLine(QPointF(origem.x() - marca, origem.y() + marca), QPointF(origem.x() + marca, origem.y() - marca))
        painter.restore()

    def modelar_selecionados(self, operacao: str) -> ElementoCurva | None:
        """Objeto > Modelar (CorelDRAW): Soldar, Aparar, Interseção, Frente
        menos atrás, Atrás menos frente. O "alvo" é o objeto de baixo (ou o
        de cima, em Frente menos atrás) e empresta a aparência ao resultado,
        que vira uma curva. Um passo só de desfazer."""
        candidatos = [el for el in self._selecionados_mockup() if self._caminho_cena_de(el) is not None]
        if len(candidatos) < 2:
            self.mensagem_status.emit(f"{OPERACOES[operacao]}: selecione 2 ou mais formas (texto e curvas valem; imagem não).")
            return None
        ordem = sorted(candidatos, key=lambda el: el.zValue())
        resultado_cena = modelar(operacao, [self._caminho_cena_de(el) for el in ordem])
        if resultado_cena.isEmpty():
            self.mensagem_status.emit(f"{OPERACOES[operacao]}: as formas não se sobrepõem — nada a fazer.")
            return None
        indices_removidos, indice_aparencia = objetos_afetados(operacao, len(ordem))
        modelo = ordem[indice_aparencia]
        aparencia = caminho_local_de(modelo)
        resultado = curva_de_caminho_cena(
            resultado_cena,
            cor_tinta=getattr(modelo, "cor_tinta", None),
            preenchido=aparencia[1] if aparencia else True,
            largura_traco=aparencia[2] if aparencia else 0.5,
        )
        if resultado is None:
            return None
        if operacao == "intersecao":
            resultado.setZValue(max(el.zValue() for el in ordem) + 1)
        else:
            resultado.setZValue(modelo.zValue())
        self._trocar_elementos(OPERACOES[operacao], [ordem[i] for i in indices_removidos], [resultado])
        return resultado

    def nos_de_encaixe_com_tipo(self, ignorar: set | frozenset = frozenset(), incluir_faca: bool = True) -> list[tuple[QPointF, str]]:
        """Pontos de encaixe com o NOME de cada um (o que aparece ao lado do
        cursor, como no CorelDRAW): nós, pontos médios e interseções da
        faca; cantos, meios das bordas e centro dos objetos; cantos e centro
        da chapa. `ignorar`: elementos que não contam (os que estão sendo
        arrastados)."""
        pontos: list[tuple[QPointF, str]] = []
        if self._layout is not None and incluir_faca:
            linhas = self.linhas_faca()
            for linha in linhas:
                pontos.append((QPointF(linha.x1, linha.y1), "nó"))
                pontos.append((QPointF(linha.x2, linha.y2), "nó"))
                pontos.append((QPointF((linha.x1 + linha.x2) / 2, (linha.y1 + linha.y2) / 2), "ponto médio"))
            pontos.extend((p, "interseção") for p in self._intersecoes_da_faca(linhas))
        for el in self._elementos_mockup:
            if el in ignorar or not el.isVisible():
                continue
            r = QRectF(0.0, 0.0, el.largura, el.altura)
            for canto in (r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()):
                pontos.append((el.mapToScene(canto), "canto"))
            for meio in (QPointF(r.center().x(), 0), QPointF(r.right(), r.center().y()), QPointF(r.center().x(), r.bottom()), QPointF(0, r.center().y())):
                pontos.append((el.mapToScene(meio), "ponto médio"))
            pontos.append((el.mapToScene(r.center()), "centro"))
        pagina = self.retangulo_pagina()
        if pagina is not None:
            for canto in (pagina.topLeft(), pagina.topRight(), pagina.bottomRight(), pagina.bottomLeft()):
                pontos.append((canto, "canto da chapa"))
            pontos.append((pagina.center(), "centro da chapa"))
        return pontos

    def _intersecoes_da_faca(self, linhas) -> list[QPointF]:
        """Cruzamentos entre linhas da faca (fora das pontas) — guardados
        enquanto a faca não muda."""
        chave = tuple((l.x1, l.y1, l.x2, l.y2) for l in linhas)
        if getattr(self, "_cache_intersecoes", (None,))[0] == chave:
            return self._cache_intersecoes[1]
        saida = []
        for i, a in enumerate(linhas):
            for b in linhas[i + 1 :]:
                p = QPointF()
                tipo, p = QLineF(a.x1, a.y1, a.x2, a.y2).intersects(QLineF(b.x1, b.y1, b.x2, b.y2))
                if tipo != QLineF.IntersectionType.BoundedIntersection:
                    continue
                pontas = ((a.x1, a.y1), (a.x2, a.y2), (b.x1, b.y1), (b.x2, b.y2))
                if any(abs(p.x() - x) < 0.01 and abs(p.y() - y) < 0.01 for x, y in pontas):
                    continue
                saida.append(QPointF(p))
        self._cache_intersecoes = (chave, saida)
        return saida

    def nos_de_encaixe(self) -> list[QPointF]:
        return [p for p, _tipo in self.nos_de_encaixe_com_tipo()]

    def encaixe_mais_proximo(self, ponto: QPointF, ignorar: set | frozenset = frozenset()) -> tuple[QPointF, str] | None:
        if not self._snap_ativo:
            return None
        melhor, menor = None, self.limiar_snap()
        for no, tipo in self.nos_de_encaixe_com_tipo(ignorar):
            distancia = math.hypot(no.x() - ponto.x(), no.y() - ponto.y())
            if distancia < menor:
                melhor, menor = (QPointF(no), tipo), distancia
        return melhor

    def encaixar_ponto(self, ponto: QPointF) -> QPointF:
        """Nó mais próximo dentro do limiar de encaixe, ou o próprio ponto
        (com o encaixe desligado, nunca mexe). Mostra o nome do ponto."""
        achado = self.encaixe_mais_proximo(ponto)
        self._mostrar_indicador(achado)
        return ponto if achado is None else achado[0]

    def _mostrar_indicador(self, achado: tuple[QPointF, str] | None) -> None:
        if achado != self._indicador_encaixe:
            self._indicador_encaixe = achado
            self.viewport().update()

    # ── Encaixe ao vivo e distâncias ao arrastar ─────────────────────
    def _ajustar_arrasto(self, elemento: ElementoMockup, delta: QPointF) -> tuple[QPointF, bool]:
        """Encaixe AO VIVO (CorelDRAW): o canto, meio de borda ou centro do
        objeto arrastado que chegar perto de um ponto de encaixe gruda nele
        já durante o arrasto, com o nome do ponto na tela. Também atualiza
        as distâncias até as bordas e vizinhos."""
        movendo = set(elemento._arrasto_corpo_posicoes_iniciais) or {elemento}
        deslocamento = delta - (elemento.pos() - elemento._arrasto_corpo_posicoes_iniciais.get(elemento, elemento.pos()))
        r = QRectF(0.0, 0.0, elemento.largura, elemento.altura)
        locais = (
            (r.topLeft(), "canto"), (r.topRight(), "canto"), (r.bottomRight(), "canto"), (r.bottomLeft(), "canto"),
            (QPointF(r.center().x(), 0), "meio"), (QPointF(r.right(), r.center().y()), "meio"),
            (QPointF(r.center().x(), r.bottom()), "meio"), (QPointF(0, r.center().y()), "meio"),
            (r.center(), "centro"),
        )
        ajustado, achado = delta, None
        if self._snap_ativo:
            alvos = self.nos_de_encaixe_com_tipo(ignorar=movendo)
            menor = self.limiar_snap()
            for local, nome_proprio in locais:
                proposto = elemento.mapToScene(local) + deslocamento
                for alvo, tipo in alvos:
                    d = math.hypot(alvo.x() - proposto.x(), alvo.y() - proposto.y())
                    if d < menor:
                        menor = d
                        ajustado = delta + (alvo - proposto)
                        achado = (QPointF(alvo), f"{nome_proprio} → {tipo}")
        self._mostrar_indicador(achado)
        caixa = elemento.retangulo_conteudo_cena().translated(deslocamento + (ajustado - delta))
        self._medidas_distancia = self._distancias_da_caixa(caixa, ignorar=movendo)
        self.viewport().update()
        return ajustado, achado is not None

    def _distancias_da_caixa(self, caixa: QRectF, ignorar: set | frozenset = frozenset()) -> list[tuple[QPointF, QPointF, float]]:
        """Distância da caixa até o que está mais perto em cada direção
        (esquerda, direita, cima, baixo): borda de outro objeto que esteja
        na mesma faixa, borda da face onde a caixa está e borda da chapa —
        como as medidas do Illustrator/Figma."""
        paredes_x: list[tuple[float, float, float]] = []  # (x, y1, y2) bordas verticais
        paredes_y: list[tuple[float, float, float]] = []  # (y, x1, x2) bordas horizontais
        for el in self._elementos_mockup:
            if el in ignorar or not el.isVisible():
                continue
            r = el.retangulo_conteudo_cena()
            paredes_x += [(r.left(), r.top(), r.bottom()), (r.right(), r.top(), r.bottom())]
            paredes_y += [(r.top(), r.left(), r.right()), (r.bottom(), r.left(), r.right())]
        centro = caixa.center()
        contornos = []
        face = next(
            (QRectF(p.x1, p.y1, p.largura, p.altura) for p in self._paineis if QRectF(p.x1, p.y1, p.largura, p.altura).contains(centro)),
            None,
        )
        if face is not None:
            contornos.append(face)
        pagina = self.retangulo_pagina()
        if pagina is not None:
            contornos.append(pagina)
        for r in contornos:
            paredes_x += [(r.left(), r.top(), r.bottom()), (r.right(), r.top(), r.bottom())]
            paredes_y += [(r.top(), r.left(), r.right()), (r.bottom(), r.left(), r.right())]
        cy, cx = centro.y(), centro.x()
        medidas = []
        esquerda = [x for x, y1, y2 in paredes_x if x <= caixa.left() + 1e-6 and y1 - 1e-6 <= cy <= y2 + 1e-6]
        direita = [x for x, y1, y2 in paredes_x if x >= caixa.right() - 1e-6 and y1 - 1e-6 <= cy <= y2 + 1e-6]
        cima = [y for y, x1, x2 in paredes_y if y <= caixa.top() + 1e-6 and x1 - 1e-6 <= cx <= x2 + 1e-6]
        baixo = [y for y, x1, x2 in paredes_y if y >= caixa.bottom() - 1e-6 and x1 - 1e-6 <= cx <= x2 + 1e-6]
        if esquerda:
            x = max(esquerda)
            medidas.append((QPointF(x, cy), QPointF(caixa.left(), cy), caixa.left() - x))
        if direita:
            x = min(direita)
            medidas.append((QPointF(caixa.right(), cy), QPointF(x, cy), x - caixa.right()))
        if cima:
            y = max(cima)
            medidas.append((QPointF(cx, y), QPointF(cx, caixa.top()), caixa.top() - y))
        if baixo:
            y = min(baixo)
            medidas.append((QPointF(cx, caixa.bottom()), QPointF(cx, y), y - caixa.bottom()))
        return [m for m in medidas if m[2] > 0.005]

    def mostrar_distancias_da_selecao(self, mostrar: bool) -> None:
        """Alt segurado com objeto selecionado: mostra as distâncias até as
        bordas e vizinhos sem precisar arrastar, e as setas movem com as
        medidas acompanhando (como no Figma). Soltou o Alt, somem."""
        self._alt_distancias = mostrar
        selecionados = self._selecionados_mockup()
        if mostrar and len(selecionados) == 1:
            el = selecionados[0]
            self._medidas_distancia = self._distancias_da_caixa(el.retangulo_conteudo_cena(), ignorar={el})
        else:
            self._medidas_distancia = []
        if mostrar:
            # No Windows o "soltar Alt" vai pro menu e nunca chega aqui:
            # confere o teclado de verdade enquanto estiver mostrando.
            if self._timer_alt is None:
                self._timer_alt = QTimer(self)
                self._timer_alt.setInterval(80)
                self._timer_alt.timeout.connect(self._conferir_alt)
            self._timer_alt.start()
        elif self._timer_alt is not None:
            self._timer_alt.stop()
        self.viewport().update()

    def _conferir_alt(self) -> None:
        if not (QApplication.queryKeyboardModifiers() & Qt.KeyboardModifier.AltModifier):
            self.mostrar_distancias_da_selecao(False)

    def _desenhar_indicadores(self, painter) -> None:
        """Marca do ponto de encaixe com o nome, e as medidas de distância
        (em pixels de tela: legíveis em qualquer zoom)."""
        escala = self.transform().m11() or 1.0
        painter.save()
        fonte = QFont(FONTE_MONO)
        fonte.setPixelSize(11)
        if self._medidas_distancia:
            caneta = QPen(QColor(230, 40, 90), 1.0)
            caneta.setCosmetic(True)
            for a, b, valor in self._medidas_distancia:
                painter.setPen(caneta)
                painter.drawLine(a, b)
                ponta = 3.0 / escala
                vertical = abs(a.x() - b.x()) < 1e-9
                for p in (a, b):
                    if vertical:
                        painter.drawLine(QPointF(p.x() - ponta, p.y()), QPointF(p.x() + ponta, p.y()))
                    else:
                        painter.drawLine(QPointF(p.x(), p.y() - ponta), QPointF(p.x(), p.y() + ponta))
                self._rotulo_tela(painter, (a + b) / 2, f"{valor:.1f} mm".replace(".", ","), fonte, QColor(230, 40, 90))
        if self._rotulo_faca is not None:
            ponto, texto = self._rotulo_faca
            self._rotulo_tela(painter, ponto + QPointF(14.0 / escala, 18.0 / escala), texto, fonte, QColor(40, 40, 40), alinhar_esquerda=True)
        if self._indicador_encaixe is not None:
            ponto, nome = self._indicador_encaixe
            lado = 7.0 / escala
            caneta = QPen(QColor(0, 150, 220), 1.5)
            caneta.setCosmetic(True)
            painter.setPen(caneta)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(ponto.x() - lado / 2, ponto.y() - lado / 2, lado, lado))
            self._rotulo_tela(painter, ponto + QPointF(9.0 / escala, -9.0 / escala), nome, fonte, QColor(0, 120, 200), alinhar_esquerda=True)
        painter.restore()

    def _rotulo_tela(self, painter, ponto: QPointF, texto: str, fonte: QFont, cor: QColor, alinhar_esquerda: bool = False) -> None:
        """Texto com fundo, desenhado em pixels de tela no ponto da cena."""
        painter.save()
        tela = self.mapFromScene(ponto)
        painter.resetTransform()
        painter.setFont(fonte)
        largura = QFontMetricsF(fonte).horizontalAdvance(texto) + 8
        x = tela.x() if alinhar_esquerda else tela.x() - largura / 2
        caixa = QRectF(x, tela.y() - 9, largura, 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawRoundedRect(caixa, 3, 3)
        painter.setPen(cor)
        painter.drawText(caixa, Qt.AlignmentFlag.AlignCenter, texto)
        painter.restore()

    def selecionados_mockup(self) -> list[ElementoMockup]:
        return self._selecionados_mockup()

    def alinhar_a(self, referencia: str, alinhamento: str) -> None:
        """Docker Alinhar e distribuir: `referencia` é "selecao" (entre
        si), "pagina" (chapa) ou "face" (a face de cada elemento)."""
        selecionados = self._selecionados_mockup()
        if not selecionados:
            return
        if referencia == "selecao":
            if len(selecionados) > 1:
                self._com_undo_geometria("Alinhar", lambda: self.alinhar_selecionados(alinhamento))
            return

        def alvo_de(el: ElementoMockup) -> QRectF | None:
            if referencia == "pagina":
                return self.retangulo_pagina()
            painel = self._painel_do_elemento(el)
            return None if painel is None else QRectF(painel.x1, painel.y1, painel.largura, painel.altura)

        def aplicar() -> None:
            for el in selecionados:
                alvo = alvo_de(el)
                if alvo is None:
                    continue
                x, y = el.pos().x(), el.pos().y()
                if alinhamento == "esquerda":
                    x = alvo.left()
                elif alinhamento == "direita":
                    x = alvo.right() - el.largura
                elif alinhamento == "centro_h":
                    x = alvo.center().x() - el.largura / 2
                elif alinhamento == "topo":
                    y = alvo.top()
                elif alinhamento == "base":
                    y = alvo.bottom() - el.altura
                elif alinhamento == "centro_v":
                    y = alvo.center().y() - el.altura / 2
                el.setPos(x, y)

        self._com_undo_geometria("Alinhar", aplicar)

    def distribuir(self, eixo: str, modo: str) -> None:
        """Distribui 3+ objetos no eixo "h" ou "v": `modo` "centros"
        (centros equidistantes) ou "espacos" (vãos iguais entre eles),
        mantendo o primeiro e o último no lugar."""
        selecionados = self._selecionados_mockup()
        if len(selecionados) < 3:
            return
        horizontal = eixo == "h"

        def inicio(el):
            return el.pos().x() if horizontal else el.pos().y()

        def tamanho(el):
            return el.largura if horizontal else el.altura

        ordem = sorted(selecionados, key=lambda el: inicio(el) + tamanho(el) / 2)

        def mover_para(el, valor: float) -> None:
            if horizontal:
                el.setPos(valor, el.pos().y())
            else:
                el.setPos(el.pos().x(), valor)

        def aplicar() -> None:
            n = len(ordem)
            if modo == "centros":
                c0 = inicio(ordem[0]) + tamanho(ordem[0]) / 2
                c1 = inicio(ordem[-1]) + tamanho(ordem[-1]) / 2
                for i, el in enumerate(ordem[1:-1], start=1):
                    mover_para(el, c0 + (c1 - c0) * i / (n - 1) - tamanho(el) / 2)
            else:
                total = inicio(ordem[-1]) + tamanho(ordem[-1]) - inicio(ordem[0])
                vao = (total - sum(tamanho(el) for el in ordem)) / (n - 1)
                cursor = inicio(ordem[0]) + tamanho(ordem[0]) + vao
                for el in ordem[1:-1]:
                    mover_para(el, cursor)
                    cursor += tamanho(el) + vao

        self._com_undo_geometria("Distribuir", aplicar)

    def transformar(self, texto: str, funcao, copias: int = 0) -> None:
        """Docker Transformações: aplica `funcao(elemento)` na seleção.
        Com `copias` > 0, como no CorelDRAW, o original fica e cada cópia
        recebe a transformação a partir da anterior (efeito cumulativo);
        a última cópia termina selecionada. Um passo só de desfazer."""
        base = self._selecionados_mockup()
        if not base:
            return
        if copias <= 0:
            self._com_undo_geometria(texto, lambda: [funcao(el) for el in base])
            return
        self._pilha_desfazer.beginMacro(texto)
        try:
            for el in base:
                el.setSelected(False)
            atual = base
            for _ in range(copias):
                novos = []
                for el in atual:
                    clone = el.clonar()
                    funcao(clone)
                    self._scene.addItem(clone)
                    self._registrar_elemento_mockup(clone)
                    self._pilha_desfazer.push(_ComandoAdicionarElemento(self, clone, texto))
                    novos.append(clone)
                atual = novos
            for el in atual:
                el.setSelected(True)
        finally:
            self._pilha_desfazer.endMacro()

    def selecionar_tudo(self) -> None:
        for el in self._elementos_mockup:
            el.setSelected(True)

    def duplicar_no_lugar_selecionados(self) -> None:
        """+ do teclado numérico do CorelDRAW: cópia exatamente em cima,
        já selecionada (o original fica parado embaixo)."""
        selecionados = self._selecionados_mockup()
        for it in selecionados:
            it.setSelected(False)
            clone = it.clonar()
            self._scene.addItem(clone)
            self._registrar_elemento_mockup(clone)
            self._pilha_desfazer.push(_ComandoAdicionarElemento(self, clone, "Duplicar no lugar"))
            clone.setSelected(True)

    def mover_na_ordem(self, passo: int) -> None:
        """Ctrl+PgUp / Ctrl+PgDn: um nível à frente / atrás, trocando de
        lugar com o vizinho mais próximo na pilha."""
        for item in self._selecionados_mockup():
            if item not in self._elementos_mockup:
                continue
            outros = [o for o in self._elementos_mockup if o is not item and not o.isSelected()]
            if passo > 0:
                vizinhos = [o for o in outros if o.zValue() >= item.zValue()]
                vizinho = min(vizinhos, key=lambda o: o.zValue(), default=None)
            else:
                vizinhos = [o for o in outros if o.zValue() <= item.zValue()]
                vizinho = max(vizinhos, key=lambda o: o.zValue(), default=None)
            if vizinho is None:
                continue
            z_item, z_vizinho = item.zValue(), vizinho.zValue()
            if z_item == z_vizinho:
                z_item = z_vizinho + passo
                item.setZValue(z_item)
            else:
                item.setZValue(z_vizinho)
                vizinho.setZValue(z_item)
        self.elementos_alterados.emit()

    def enquadrar(self, rect: QRectF) -> None:
        """Mesmo enquadramento de `ajustar_a_tela`, pra um retângulo qualquer."""
        if rect.isEmpty():
            return
        margem = 10
        rect = rect.adjusted(-margem, -margem, margem, margem)
        ancora_original = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.resetTransform()
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.setTransformationAnchor(ancora_original)
        self.centerOn(rect.center())
        self._zoom_atual = self.transform().m11()
        self.zoom_alterado.emit(self._zoom_atual)

    def _atalho_corel(self, event) -> bool:
        """Atalhos de teclado do CorelDRAW. Devolve True se tratou a tecla."""
        tecla = event.key()
        mods = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        ctrl = Qt.KeyboardModifier.ControlModifier
        shift = Qt.KeyboardModifier.ShiftModifier
        nenhum = Qt.KeyboardModifier.NoModifier

        alt = Qt.KeyboardModifier.AltModifier
        if mods == alt and tecla == Qt.Key.Key_Z:
            self.definir_ajustar_a("objetos", not self._ajustar_a["objetos"])
        elif mods == ctrl and tecla == Qt.Key.Key_Y:
            self.definir_ajustar_a("grade", not self._ajustar_a["grade"])
        elif mods == ctrl and tecla == Qt.Key.Key_Q:
            self.converter_selecionados_em_curvas()
        elif mods == ctrl and tecla == Qt.Key.Key_L:
            self.combinar_selecionados()
        elif mods == ctrl and tecla == Qt.Key.Key_K:
            self.separar_selecionados()
        elif mods == ctrl and tecla == Qt.Key.Key_U:
            self.desagrupar_selecionados()
        elif mods == ctrl and tecla == Qt.Key.Key_A:
            self.selecionar_tudo()
        elif mods == shift and tecla == Qt.Key.Key_PageUp:
            self.trazer_para_frente()
        elif mods == shift and tecla == Qt.Key.Key_PageDown:
            self.enviar_para_tras()
        elif mods == ctrl and tecla == Qt.Key.Key_PageUp:
            self.mover_na_ordem(+1)
        elif mods == ctrl and tecla == Qt.Key.Key_PageDown:
            self.mover_na_ordem(-1)
        elif mods == nenhum and tecla == Qt.Key.Key_F4:
            self.ajustar_a_tela()
        elif mods == shift and tecla == Qt.Key.Key_F4:
            pagina = self.retangulo_pagina()
            if pagina is not None:
                self.enquadrar(pagina)
        elif mods == shift and tecla == Qt.Key.Key_F2:
            bloco = QRectF()
            for el in self._selecionados_mockup():
                bloco = bloco.united(el.retangulo_conteudo_cena())
            self.enquadrar(bloco)
        elif tecla == Qt.Key.Key_Plus and event.modifiers() & Qt.KeyboardModifier.KeypadModifier:
            self.duplicar_no_lugar_selecionados()
        elif mods == nenhum and tecla in _TECLA_ALINHAR_CORELDRAW:
            self.alinhar_corel(_TECLA_ALINHAR_CORELDRAW[tecla])
        elif mods == nenhum and tecla == Qt.Key.Key_P:
            self.centralizar_na_pagina()
        elif mods == nenhum and tecla in _TECLA_FERRAMENTA_CORELDRAW:
            self.definir_ferramenta(_TECLA_FERRAMENTA_CORELDRAW[tecla])
        elif mods == nenhum and tecla == Qt.Key.Key_Space and not event.isAutoRepeat():
            if self._criando:
                return True
            if self._ferramenta == FerramentaMockup.SELECIONAR:
                self.definir_ferramenta(self._ferramenta_anterior)
            else:
                self.definir_ferramenta(FerramentaMockup.SELECIONAR)
        else:
            return False
        return True

    def keyPressEvent(self, event) -> None:  # noqa: N802
        foco = self._scene.focusItem()
        if event.key() == Qt.Key.Key_Alt and self._modo_mockup and not getattr(foco, "editando", False):
            self.mostrar_distancias_da_selecao(True)
        if isinstance(foco, QGraphicsProxyWidget) or getattr(foco, "editando", False):
            # Digitando um texto no desenho (ver `mockup_texto.py`) ou num
            # campo embutido: toda tecla é do texto — senão L/R/T/B/E/C/P
            # (atalhos de alinhar do CorelDRAW) roubariam letras digitadas.
            super().keyPressEvent(event)
            return
        if self._editando_faca and not self._modo_mockup and self._tecla_faca(event):
            return
        if self._modo_mockup and self._ferramenta in _FERRAMENTAS_CURVA and self._tecla_curva(event):
            return
        if event.key() == Qt.Key.Key_D and event.modifiers() == (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier):
            self.definir_guias_dinamicas(not self._guias_dinamicas)
            return
        if self._modo_mockup and self._atalho_corel(event):
            return
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
            if event.key() in _DELTA_SETA_NUDGE:
                # Mover fino pelo teclado — passo configurável em
                # Configurações > Ferramentas (padrão 1mm por toque, 10mm
                # com Shift, mesmo padrão de qualquer CAD: mouse pro
                # grosso, seta pro ajuste fino de precisão). Só intercepta
                # a seta quando tem elemento selecionado — sem seleção, a
                # seta continua rolando a view (comportamento nativo de
                # QGraphicsView, não mexi nisso).
                selecionados = [it for it in self._scene.selectedItems() if isinstance(it, ElementoMockup)]
                if selecionados:
                    passo_normal, passo_shift = configuracoes.passo_nudge_mm()
                    passo = passo_shift if eh_shift else passo_normal
                    if bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                        passo = passo_normal / 10.0  # micro-deslocamento (Ctrl+seta), igual CorelDRAW
                    delta = _DELTA_SETA_NUDGE[event.key()] * passo
                    antes = {}
                    for item in selecionados:
                        antes.update(_estado_recursivo(item))
                        item.setPos(item.pos() + delta)
                    depois = {}
                    for item in selecionados:
                        depois.update(_estado_recursivo(item))
                    self._pilha_desfazer.push(_ComandoAlterarGeometria(antes, depois, "Mover com seta"))
                    if self._alt_distancias:
                        self.mostrar_distancias_da_selecao(True)  # medidas acompanham
                    return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Alt:
            self.mostrar_distancias_da_selecao(False)
        super().keyReleaseEvent(event)

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


def _distancia_ao_segmento(p: QPointF, a: QPointF, b: QPointF) -> float:
    ab = b - a
    comprimento2 = ab.x() ** 2 + ab.y() ** 2
    if comprimento2 < 1e-12:
        return math.hypot(p.x() - a.x(), p.y() - a.y())
    t = max(0.0, min(1.0, ((p.x() - a.x()) * ab.x() + (p.y() - a.y()) * ab.y()) / comprimento2))
    q = a + ab * t
    return math.hypot(p.x() - q.x(), p.y() - q.y())
