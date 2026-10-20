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

from contextlib import contextmanager

import math
from enum import Enum, auto

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget


@contextmanager
def cache_desligado(cena):
    """Durante exportação (SVG/PDF/JPG) e textura do 3D: desliga o cache de
    desenho dos elementos — com ele ligado, `scene.render` copia a imagem em
    cache (resolução de tela) em vez de desenhar vetorial."""
    itens = [it for it in cena.items() if it.cacheMode() != QGraphicsItem.CacheMode.NoCache]
    modos = [(it, it.cacheMode()) for it in itens]
    for it in itens:
        it.setCacheMode(QGraphicsItem.CacheMode.NoCache)
    try:
        yield
    finally:
        for it, modo in modos:
            it.setCacheMode(modo)


def desenhar_texto_escalado(painter: QPainter, pos: QPointF, fonte: QFont, texto: str) -> None:
    """Usar no lugar de `painter.drawText(pos, texto)` sempre que o texto
    estiver sendo pintado dentro de um `painter.scale(...)` pequeno com
    uma fonte grande (o truque de "fonte de referência grande + escala"
    usado em todo elemento de mockup com texto, pra evitar rasterização
    ruim em fonte pequena — ver `mockup_texto.py`/`mockup_checklist.py`).

    `drawText()` nessa combinação (fonte grande + scale + item com
    `setPos()` próprio) sai com posição/tamanho ERRADOS especificamente
    na exportação SVG — bug confirmado do próprio
    `QSvgGenerator`/`QGraphicsScene.render()` do Qt, reproduzido numa
    cena mínima sem nenhuma lógica deste app (não é algo que dá pra
    corrigir ajustando parâmetro de exportação). Convertendo o texto num
    `QPainterPath` (`addText`) e desenhando via `drawPath()` em vez de
    `drawText()` evita o bug inteiro — confirmado testando a mesma
    reprodução mínima com as duas abordagens lado a lado.

    ATENÇÃO: `drawPath()` preenche com o BRUSH do painter, não o PEN
    (diferente de `drawText()`, que usa o pen) — quem chama precisa
    garantir `painter.setBrush(QBrush(cor_do_texto))` antes de chamar
    isso, ou o texto sai com o brush que sobrou de outra coisa desenhada
    antes (ex.: invisível, se o brush anterior era branco/NoBrush)."""
    caminho = QPainterPath()
    caminho.addText(pos, fonte, texto)
    pincel_anterior = painter.pen()
    painter.setPen(Qt.PenStyle.NoPen)  # só preenchimento, igual drawText() normal (sem contorno)
    painter.drawPath(caminho)
    painter.setPen(pincel_anterior)


# Alças em PIXELS DE TELA, como no CorelDRAW: o mesmo tamanho na tela em
# qualquer zoom e em qualquer escala de desenho (quem desenha a caixa de
# 605 mm como 60,5 mm não pode ver alça de 3 mm do tamanho da caixa).
# Convertidas pra mm da cena com `ElementoMockup.mm_por_px`, que o canvas
# atualiza a cada mudança de zoom.
_TAMANHO_ALCA_PX = 8.0
_TAMANHO_ALCA_ROTACAO_PX = 10.0
_DISTANCIA_ALCA_ROTACAO_PX = 24.0
# Tamanho mínimo de um elemento — pequeno de propósito: as alças não dependem
# mais dele pra ficarem clicáveis.
_LARGURA_MINIMA_MM = 0.5
_ALTURA_MINIMA_MM = 0.5
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

    # Mínimo padrão pra qualquer elemento (mantém alças de redimensionar
    # sempre clicáveis — antes; hoje as alças são em px, ver `_TAMANHO_ALCA_PX`) — atributo de CLASSE, não
    # module-level direto, pra subclasses conseguirem sobrescrever o
    # próprio mínimo quando o valor não representa "tamanho da forma"
    # (ex.: `ElementoTexto`, onde altura = tamanho de fonte, e 4mm de
    # piso impedia texto miúdo tipo letra de rodapé/composição).
    _largura_minima_mm = _LARGURA_MINIMA_MM
    _altura_minima_mm = _ALTURA_MINIMA_MM

    # mm da cena por pixel de tela (ver `definir_escala_tela`).
    mm_por_px = 0.25

    @classmethod
    def definir_escala_tela(cls, mm_por_px: float, itens) -> None:
        """Chamado pelo canvas a cada zoom: as alças (em px) mudam de
        tamanho em mm, então a área de repintura de cada item também."""
        if mm_por_px <= 0 or abs(mm_por_px - cls.mm_por_px) < 1e-12:
            return
        for item in itens:
            item.prepareGeometryChange()
        cls.mm_por_px = mm_por_px

    def __init__(self, largura: float = 40.0, altura: float = 24.0, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._largura = max(self._largura_minima_mm, largura)
        self._altura = max(self._altura_minima_mm, altura)
        self.setTransformOriginPoint(self._largura / 2, self._altura / 2)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        # Sem isso, `itemChange` abaixo nunca é chamado pra posição — e é
        # o único jeito de saber que a posição mudou por causa de um
        # arrasto comum (mover o corpo), que usa o `setPos` nativo do Qt
        # direto, sem passar pelo nosso `_redimensionar_para`/`_girar_para`
        # (que já emitem `geometria_alterada` manualmente). Precisa disso
        # pro painel de propriedades atualizar os campos X/Y ao vivo
        # enquanto o usuário arrasta, não só depois de soltar o mouse.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        # Desempenho: o desenho do elemento (SVG, texto, símbolo...) vira
        # uma imagem em cache NA RESOLUÇÃO DA TELA; arrastar só move a
        # imagem pronta em vez de redesenhar o conteúdo a cada quadro. O
        # cache se refaz sozinho no zoom e a cada `update()` (mudança de
        # aparência). Exportação e textura do 3D (`scene.render`) não usam
        # esse cache — saem vetoriais/na resolução pedida.
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        # Painel "dono" do elemento (frente, lateral, tampa...) — pura
        # etiqueta informativa, sem nenhum recorte/trava associada: o
        # usuário confirmou que às vezes uma impressão atravessa pra um
        # painel vizinho, então travar nisso atrapalharia mais do que
        # ajudaria. Serve pra Fase 3 (3D) saber em qual face colar o quê.
        self._painel_id: str | None = None

        # Trava de proporção (item 4 da lista de melhorias inspiradas em
        # ArtiosCAD/CorelDRAW/etc.) — afeta tanto arrastar uma alça
        # (`_redimensionar_para` abaixo) quanto editar Largura/Altura
        # pelos campos do painel de propriedades (`definir_tamanho`).
        self._proporcao_travada = False

        # Espelhar horizontal/vertical (barra de propriedades, igual ao
        # CorelDRAW). Só o CONTEÚDO é desenhado espelhado em torno do
        # centro (ver `paint`) — posição, tamanho e alças não mudam.
        self._espelho_h = False
        self._espelho_v = False
        # A ferramenta Forma esconde as alças comuns enquanto mostra os nós.
        self._alcas_visiveis = True

        # Callback opcional (ver `definir_calculador_snap`) que o canvas
        # liga em todo elemento que cria/duplica/desagrupa — o elemento
        # não sabe nada de grade/outros elementos/guias sozinho, só pede
        # "essa posição que eu larguei, tem uma melhor bem pertinho?" ao
        # SOLTAR o botão depois de arrastar o CORPO (não durante
        # redimensionar/rotacionar, nem em `setPos()` programático tipo
        # nudge/alinhar/colar — ver `_arrastando_corpo` e
        # `mouseReleaseEvent` abaixo. Corrigir só no soltar, não durante o
        # arrasto: mudar a posição por baixo do arrasto NATIVO do Qt
        # confunde a conta interna dele — ver comentário lá).
        self._calculador_snap = None
        self._arrastando_corpo = False
        self._arrasto_corpo_iniciado = False
        self._arrasto_corpo_tela_inicial = QPointF()

        # Callback opcional (ver `definir_solicitador_duplicata`) que o
        # canvas liga em todo elemento — pedido quando o usuário começa a
        # arrastar o CORPO segurando Alt (ver `mousePressEvent`): deixa
        # uma cópia parada exatamente na posição atual (o item que
        # continua em movimento é sempre `self`, nunca a cópia — mais
        # simples que tentar "trocar" qual item o Qt está arrastando no
        # meio do gesto).
        self._solicitar_duplicata = None

        # Encaixe AO VIVO durante o arrasto (CorelDRAW): `ajustador(elemento,
        # delta) -> (delta ajustado, encaixou)`, ligado pelo canvas. Quando
        # encaixa ao vivo, o encaixe de "soltar" não mexe mais na posição.
        self._ajustar_arrasto = None
        self._encaixou_ao_vivo = False

        # Callback opcional (ver `definir_registrador_undo`) — chamado no
        # FIM de um gesto de mover/redimensionar/girar (nunca por frame,
        # mesmo espírito do snap) com o estado de geometria de antes e
        # depois, pra quem quiser empurrar num QUndoStack. Sem isso, o
        # elemento continua funcionando normalmente, só sem desfazer.
        self._registrar_geometria_undo = None
        self._arrasto_geometria_antes: dict[ElementoMockup, tuple] = {}
        self._grupo_antes_do_arrasto: dict[ElementoMockup, tuple] | None = None

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

        # Arrasto do CORPO (mover) — MANUAL, não nativo (`ItemIsMovable`
        # continua ligado só pra deixar o Qt tratar seleção por clique
        # certo; o movimento em si é todo calculado aqui). Motivo: mover
        # o grupo inteiro numa seleção múltipla E restringir a um eixo
        # com Shift exigem calcular a posição de cada item a partir de um
        # delta comum — não dá pra fazer isso em cima do arrasto nativo
        # do Qt sem cair no mesmo problema já documentado pro snap (mudar
        # a posição por baixo dele no meio do gesto desincroniza a conta
        # interna e o item "trava"). Ver `mousePressEvent`/`mouseMoveEvent`.
        self._arrasto_corpo_ponto_inicial_cena = QPointF()
        self._arrasto_corpo_posicoes_iniciais: dict[ElementoMockup, QPointF] = {}
        # Clique direito no meio do arrasto (CorelDRAW): ao soltar, deixa
        # uma cópia no destino e o original volta pro lugar de origem.
        self._deixar_copia_ao_soltar = False

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

    @property
    def em_arrasto_corpo(self) -> bool:
        """Se está no meio de um arrasto pelo CORPO (mover, não
        redimensionar/rotacionar) agora mesmo — usado pelo canvas pra
        saber quando desenhar linhas-guia de encaixe (ver
        `preview_canvas.py::_atualizar_guia_snap_preview`)."""
        return self._arrastando_corpo

    @property
    def proporcao_travada(self) -> bool:
        return self._proporcao_travada

    def definir_proporcao_travada(self, travada: bool) -> None:
        self._proporcao_travada = travada

    @property
    def espelho_h(self) -> bool:
        return self._espelho_h

    @property
    def espelho_v(self) -> bool:
        return self._espelho_v

    def definir_alcas_visiveis(self, visiveis: bool) -> None:
        self._alcas_visiveis = visiveis
        self.update()

    def definir_espelho(self, horizontal: bool, vertical: bool) -> None:
        self._espelho_h = horizontal
        self._espelho_v = vertical
        self.update()

    def definir_calculador_snap(self, calculador) -> None:
        """`calculador(elemento, ponto_proposto) -> ponto_ajustado` —
        chamado pelo canvas (ver `preview_canvas.py::_calcular_snap`)
        toda vez que o elemento tenta se mover arrastando o corpo."""
        self._calculador_snap = calculador

    def definir_solicitador_duplicata(self, solicitador) -> None:
        """`solicitador(elemento) -> None` — chamado pelo canvas (ver
        `preview_canvas.py::_duplicar_no_lugar`) assim que o usuário
        começa a arrastar o corpo segurando Alt: cria e registra um clone
        exatamente na posição atual, sem selecioná-lo. `self` continua
        sendo o item que se move dali pra frente."""
        self._solicitar_duplicata = solicitador

    def definir_ajustador_arrasto(self, ajustador) -> None:
        self._ajustar_arrasto = ajustador

    def definir_registrador_undo(self, registrador) -> None:
        """`registrador(antes: dict, depois: dict) -> None` — chamado ao
        FINAL de um gesto de mover/redimensionar/girar que realmente
        mudou alguma coisa (ver `_estado_recursivo`/`mouseReleaseEvent`)."""
        self._registrar_geometria_undo = registrador

    def _estado_geometria(self) -> tuple:
        return (self.pos(), self._largura, self._altura, self.rotation(), self._espelho_h, self._espelho_v)

    def definir_largura(self, largura: float) -> None:
        """Muda só a largura — se a proporção estiver travada, a altura
        acompanha na mesma razão atual. Ver docstring de `definir_tamanho`
        pra por que isso é um método à parte, não uma inferência dentro
        de `definir_tamanho`."""
        altura = self._altura
        if self._proporcao_travada and self._largura:
            altura = self._altura * (largura / self._largura)
        self._mudar_tamanho_parado(largura, altura)

    def definir_altura(self, altura: float) -> None:
        largura = self._largura
        if self._proporcao_travada and self._altura:
            largura = self._largura * (altura / self._altura)
        self._mudar_tamanho_parado(largura, altura)

    def _mudar_tamanho_parado(self, largura: float, altura: float) -> None:
        """Tamanho pelos campos da barra. Girado, o objeto cresce em volta
        do centro (que fica parado): sem isso, cada toque na setinha do campo
        fazia o objeto escorregar na tela (o centro de giro mudava)."""
        if not self.rotation() % 360:
            self.definir_tamanho(largura, altura)
            return
        centro = self.mapToScene(QPointF(self._largura / 2, self._altura / 2))
        self.definir_tamanho(largura, altura)
        self.setPos(self.pos() + centro - self.mapToScene(QPointF(self._largura / 2, self._altura / 2)))

    def definir_tamanho(self, largura: float, altura: float) -> None:
        """Define largura E altura de uma vez, sem nenhuma lógica de
        proporção — quem quer editar só um lado respeitando a trava usa
        `definir_largura`/`definir_altura` acima, não este método.

        (Antes esse método tentava ADIVINHAR qual dos dois lados o
        chamador queria mudar, comparando com o valor atual — parecia
        certo num teste manual com `setValue()`, mas quebrava na prática:
        `QDoubleSpinBox` dispara `valueChanged` a CADA TECLA digitada, não
        só no Enter, então "digitar 20" gerava uma sequência de chamadas
        com o valor "atual" já alterado pela tecla anterior — cada
        chamada via uma comparação diferente e a conta de escala
        divergia a cada dígito, resultado final errado. Método explícito
        e sem essa suposição resolve de vez.)"""
        self.prepareGeometryChange()
        self._largura = max(self._largura_minima_mm, largura)
        self._altura = max(self._altura_minima_mm, altura)
        self.setTransformOriginPoint(self._largura / 2, self._altura / 2)
        self.update()
        self.geometria_alterada.emit()

    def clonar(self) -> "ElementoMockup":
        """Duplica o elemento (Ctrl+D/Ctrl+C+V, ver `preview_canvas.py`)
        — cada subclasse implementa reconstruindo com o MESMO conteúdo
        (texto, cor, arquivo...) via seu próprio construtor, depois chama
        `_copiar_geometria_para` (abaixo) pra igualar tamanho/posição/
        rotação/painel/trava de proporção, que é sempre a mesma receita
        não importa o tipo."""
        raise NotImplementedError

    def _copiar_geometria_para(self, novo: "ElementoMockup") -> None:
        novo.definir_tamanho(self._largura, self._altura)
        novo.setPos(self.pos())
        novo.setRotation(self.rotation())
        novo.definir_painel(self.painel_id)
        novo.definir_proporcao_travada(self.proporcao_travada)
        novo.definir_espelho(self._espelho_h, self._espelho_v)

    def retangulo_conteudo_cena(self) -> QRectF:
        """Retângulo de conteúdo de verdade — sem a margem das alças de
        seleção que `boundingRect()` inclui (ver abaixo) — em coordenadas
        da CENA. É o que a exportação usa: `boundingRect()` existe pra o
        Qt saber até onde repintar durante a edição, nunca deveria
        definir o tamanho de um arquivo exportado."""
        return self.mapRectToScene(QRectF(0, 0, self._largura, self._altura))

    # ── QGraphicsItem ────────────────────────────────────────────────
    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.geometria_alterada.emit()
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged and not value:
            if self._grupo_pai() is not None:
                # Saiu da seleção feita com Ctrl+clique: volta a ser "parte do grupo".
                self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        return super().itemChange(change, value)

    def _grupo_pai(self) -> "GrupoMockup | None":
        pai = self.parentItem()
        return pai if isinstance(pai, GrupoMockup) else None

    def boundingRect(self) -> QRectF:
        margem = (_DISTANCIA_ALCA_ROTACAO_PX + _TAMANHO_ALCA_ROTACAO_PX + 2.0) * ElementoMockup.mm_por_px
        return QRectF(0, 0, self._largura, self._altura).adjusted(-margem, -margem, margem, margem)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        if self._espelho_h or self._espelho_v:
            painter.save()
            painter.translate(self._largura / 2, self._altura / 2)
            painter.scale(-1.0 if self._espelho_h else 1.0, -1.0 if self._espelho_v else 1.0)
            painter.translate(-self._largura / 2, -self._altura / 2)
            self._pintar_conteudo(painter)
            painter.restore()
        else:
            self._pintar_conteudo(painter)
        if self.isSelected() and self._alcas_visiveis:
            self._pintar_selecao(painter)

    def _pintar_conteudo(self, painter: QPainter) -> None:
        """Subclasses sobrescrevem pra desenhar o conteúdo real (texto,
        forma, imagem) dentro do retângulo `(0, 0, largura, altura)`."""
        raise NotImplementedError

    def _pintar_selecao(self, painter: QPainter) -> None:
        k = ElementoMockup.mm_por_px
        raio = (_TAMANHO_ALCA_PX / 2.0) * k
        distancia_rotacao = _DISTANCIA_ALCA_ROTACAO_PX * k

        pen_contorno = QPen(_COR_SELECAO, 1.0)
        pen_contorno.setCosmetic(True)  # traço de 1 px em qualquer zoom
        painter.setPen(pen_contorno)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, self._largura, self._altura))

        centro_x = self._largura / 2
        painter.drawLine(QPointF(centro_x, 0), QPointF(centro_x, -distancia_rotacao))

        painter.setBrush(QBrush(_COR_ALCA_PREENCHIMENTO))
        pen_alca = QPen(_COR_SELECAO, 1.5)
        pen_alca.setCosmetic(True)
        painter.setPen(pen_alca)
        for _alca, (rel_x, rel_y) in _PONTO_RELATIVO_ALCA.items():
            centro = QPointF(rel_x * self._largura, rel_y * self._altura)
            painter.drawRect(QRectF(centro.x() - raio, centro.y() - raio, raio * 2, raio * 2))

        raio_rotacao = _TAMANHO_ALCA_ROTACAO_PX / 2.0 * k
        centro_rotacao = QPointF(centro_x, -distancia_rotacao)
        painter.drawEllipse(centro_rotacao, raio_rotacao, raio_rotacao)

    # ── Detecção de alça sob o cursor ────────────────────────────────
    def _alca_em(self, ponto_local: QPointF) -> Alca:
        if not self.isSelected():
            return Alca.CORPO if self._contem_corpo(ponto_local) else Alca.NENHUMA

        k = ElementoMockup.mm_por_px
        centro_x = self._largura / 2
        centro_rotacao = QPointF(centro_x, -_DISTANCIA_ALCA_ROTACAO_PX * k)
        raio_rotacao = (_TAMANHO_ALCA_ROTACAO_PX / 2.0) * k * _MARGEM_CLIQUE_ALCA
        if _distancia(ponto_local, centro_rotacao) <= raio_rotacao:
            return Alca.ROTACAO

        raio = (_TAMANHO_ALCA_PX / 2.0) * k * _MARGEM_CLIQUE_ALCA
        for alca, (rel_x, rel_y) in _PONTO_RELATIVO_ALCA.items():
            centro = QPointF(rel_x * self._largura, rel_y * self._altura)
            if abs(ponto_local.x() - centro.x()) <= raio and abs(ponto_local.y() - centro.y()) <= raio:
                return alca

        return Alca.CORPO if self._contem_corpo(ponto_local) else Alca.NENHUMA

    def _contem_corpo(self, ponto_local: QPointF) -> bool:
        return QRectF(0, 0, self._largura, self._altura).contains(ponto_local)

    # ── Interação de mouse ───────────────────────────────────────────
    def hoverMoveEvent(self, event) -> None:  # noqa: N802
        vistas = self.scene().views() if self.scene() is not None else []
        if vistas and not getattr(vistas[0], "ferramenta_selecionar_ativa", True):
            # Outra ferramenta ativa (retângulo, conta-gotas...): o cursor é o
            # dela, não a seta/setas de redimensionar do objeto debaixo.
            self.unsetCursor()
        else:
            alca = self._alca_em(event.pos())
            self.setCursor(_CURSOR_POR_ALCA.get(alca, Qt.CursorShape.ArrowCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton and self._arrastando_corpo:
            self._deixar_copia_ao_soltar = not self._deixar_copia_ao_soltar
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        alca = self._alca_em(event.pos())

        if alca == Alca.NENHUMA:
            event.ignore()
            return

        grupo = self._grupo_pai()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if grupo is not None and not self.isSelected():
            if not ctrl:
                # Como no CorelDRAW: clicar num objeto agrupado pega o GRUPO
                # (o clique segue pro grupo, que fica por baixo).
                event.ignore()
                return
            # Ctrl+clique: entra no grupo e pega só este objeto.
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            if self.scene() is not None:
                self.scene().clearSelection()
            self.setSelected(True)

        if alca == Alca.CORPO:
            # Alt segurado = duplicar e arrastar a cópia (convenção comum
            # de editor vetorial) — ANTES de resolver a seleção nativa,
            # senão a cópia nasceria já contando como "o clique de agora"
            # e a lógica abaixo ficaria confusa sobre qual item é qual.
            # Usa Alt, não Ctrl (a referência de ArtiosCAD usa Ctrl, ver
            # `REFERENCIA_FERRAMENTAS_ARTIOSCAD.md`) porque o Qt já usa
            # Ctrl+clique nativamente pra alternar item dentro/fora de uma
            # seleção múltipla — os dois brigariam pelo mesmo clique.
            if event.modifiers() & Qt.KeyboardModifier.AltModifier and self._solicitar_duplicata is not None:
                self._solicitar_duplicata(self)
            # Shift+clique acrescenta/tira este da seleção, como no CorelDRAW
            # (o Qt só faz isso com Ctrl). Feito à mão: o press/release
            # nativo sem Ctrl desmarcaria os outros.
            self._clique_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if grupo is not None:
                self._clique_shift = True  # seleção já resolvida acima (não deixa o Ctrl nativo alternar)
            elif self._clique_shift:
                self.setSelected(not self.isSelected())
                event.accept()
            else:
                super().mousePressEvent(event)  # só resolve SELEÇÃO (clique simples/Ctrl) — mover é manual, ver abaixo
            self._arrastando_corpo = True
            self._deixar_copia_ao_soltar = False
            self._arrasto_corpo_ponto_inicial_cena = event.scenePos()
            # Só vira arrasto depois de o mouse andar alguns pixels (como no
            # CorelDRAW): a tremida de um clique pra selecionar não mexe o
            # objeto nem dispara o encaixe ao vivo.
            self._arrasto_corpo_tela_inicial = event.screenPos()
            self._arrasto_corpo_iniciado = False
            # Congela a posição de largada de TODOS os itens selecionados
            # agora (não só `self`) — arrastar um item de uma seleção
            # múltipla move o grupo inteiro junto, mesmo comportamento que
            # o arrasto nativo do Qt já dava de graça e que precisa ser
            # replicado à mão agora que o movimento é calculado aqui (ver
            # docstring do `__init__` pro motivo de não ser mais nativo).
            cena = self.scene()
            selecionados = cena.selectedItems() if cena is not None else [self]
            self._arrasto_corpo_posicoes_iniciais = {
                item: item.pos() for item in selecionados if isinstance(item, ElementoMockup)
            }
            if self not in self._arrasto_corpo_posicoes_iniciais:
                self._arrasto_corpo_posicoes_iniciais[self] = self.pos()
            self._arrasto_geometria_antes = {}
            self._encaixou_ao_vivo = False
            for item in self._arrasto_corpo_posicoes_iniciais:
                self._arrasto_geometria_antes.update(_estado_recursivo(item))
            self._guardar_grupo_antes_do_arrasto()
            return

        # Alça de redimensionar ou rotação — só aparece quando já
        # selecionado, então não precisa re-selecionar aqui.
        self._alca_ativa = alca
        self._arrastando = True
        self._arrasto_largura_inicial = self._largura
        self._arrasto_altura_inicial = self._altura
        self._arrasto_angulo_inicial = self.rotation()
        self._arrasto_geometria_antes = _estado_recursivo(self)
        self._guardar_grupo_antes_do_arrasto()
        self._arrasto_centro_cena = self.mapToScene(QPointF(self._largura / 2, self._altura / 2))

        if alca == Alca.ROTACAO:
            delta = event.scenePos() - self._arrasto_centro_cena
            self._arrasto_angulo_mouse_inicial = math.degrees(math.atan2(delta.y(), delta.x()))
        else:
            rel_x, rel_y = _PONTO_RELATIVO_ALCA[alca]
            oposto_local = QPointF((1 - rel_x) * self._largura, (1 - rel_y) * self._altura)
            self._arrasto_oposto_cena = self.mapToScene(oposto_local)

        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._arrastando and self._alca_ativa == Alca.ROTACAO:
            self._girar_para(event.scenePos(), event.modifiers())
            return
        if self._arrastando and self._alca_ativa not in (Alca.NENHUMA, Alca.CORPO):
            self._redimensionar_para(event.scenePos(), event.modifiers())
            return
        if self._arrastando_corpo:
            if not self._arrasto_corpo_iniciado:
                andou = (event.screenPos() - self._arrasto_corpo_tela_inicial).manhattanLength()
                if andou < QApplication.startDragDistance():
                    return
                self._arrasto_corpo_iniciado = True
            delta = event.scenePos() - self._arrasto_corpo_ponto_inicial_cena
            if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier):
                # Restringe a UM eixo — o que tiver o maior deslocamento
                # até agora "ganha", trava o outro em zero. Reavaliado a
                # cada frame (não fixado no primeiro pixel de movimento),
                # então dá pra "corrigir" qual eixo pretendia sem soltar o
                # botão, igual Illustrator/CorelDRAW.
                if abs(delta.x()) >= abs(delta.y()):
                    delta = QPointF(delta.x(), 0.0)
                else:
                    delta = QPointF(0.0, delta.y())
            if self._ajustar_arrasto is not None:
                delta, self._encaixou_ao_vivo = self._ajustar_arrasto(self, delta)
            for item, pos_inicial in self._arrasto_corpo_posicoes_iniciais.items():
                item.setPos(pos_inicial + delta)
            return
        # NÃO chama o mouseMoveEvent nativo: ele move o item sozinho
        # (ItemIsMovable) e o movimento aqui é todo calculado à mão. Um
        # movimento "repetido" pelo Qt quando a vista muda de tamanho no meio
        # do clique (selecionar mexe na barra de status) chegava antes do
        # arrasto começar e deslocava o objeto.
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton and (self._arrastando_corpo or self._arrastando):
            event.accept()  # soltar o direito (cópia) não termina o arrasto
            return
        if self._arrastando_corpo:
            self._arrastando_corpo = False
            if not getattr(self, "_clique_shift", False):
                super().mouseReleaseEvent(event)
            self._clique_shift = False
            if self._calculador_snap is not None and not self._encaixou_ao_vivo and self._arrasto_corpo_iniciado:
                # Encaixe só ao SOLTAR o botão, não durante o arrasto —
                # aplicado a partir de `self` (o item realmente clicado),
                # o ajuste resultante é então somado a TODO o grupo que se
                # moveu junto, senão o encaixe de um item sozinho
                # desalinharia ele em relação aos outros que vieram junto.
                pos_antes = self.pos()
                nova_pos = self._calculador_snap(self, pos_antes)
                delta_snap = nova_pos - pos_antes
                if delta_snap != QPointF(0.0, 0.0):
                    for item in self._arrasto_corpo_posicoes_iniciais:
                        item.setPos(item.pos() + delta_snap)
            if self._deixar_copia_ao_soltar and self._solicitar_duplicata is not None:
                self._deixar_copia_ao_soltar = False
                for item, pos_inicial in self._arrasto_corpo_posicoes_iniciais.items():
                    copia = self._solicitar_duplicata(item)  # nasce no destino
                    item.setPos(pos_inicial)
                    if copia is not None:
                        item.setSelected(False)
                        copia.setSelected(True)
            self._registrar_undo_se_mudou()
            self._arrasto_corpo_posicoes_iniciais = {}
            self._arrasto_geometria_antes = {}
            return
        if self._arrastando:
            self._arrastando = False
            self._alca_ativa = Alca.NENHUMA
            self._registrar_undo_se_mudou()
            self._arrasto_geometria_antes = {}
            self.geometria_alterada.emit()
            return
        super().mouseReleaseEvent(event)

    def _registrar_undo_se_mudou(self) -> None:
        """Chamado no fim de todo gesto (mover/redimensionar/girar) —
        compara com o estado congelado no início e só empurra um comando
        de undo se algo realmente mudou (ex.: um clique sem arrastar de
        verdade não deveria virar uma entrada de undo vazia)."""
        grupo = self._grupo_pai()
        if grupo is not None:
            # Mexeu num objeto DENTRO do grupo (Ctrl+clique): a caixa do grupo
            # se refaz em volta dele, e o desfazer guarda o grupo todo.
            grupo.recalcular_limites()
            if self._grupo_antes_do_arrasto:
                self._arrasto_geometria_antes = {**self._arrasto_geometria_antes, **self._grupo_antes_do_arrasto}
            self._grupo_antes_do_arrasto = None
        if self._registrar_geometria_undo is None or not self._arrasto_geometria_antes:
            return
        depois: dict[ElementoMockup, tuple] = {}
        for item in self._arrasto_geometria_antes:
            depois.update(_estado_recursivo(item))
        if depois != self._arrasto_geometria_antes:
            self._registrar_geometria_undo(dict(self._arrasto_geometria_antes), depois)

    def _guardar_grupo_antes_do_arrasto(self) -> None:
        grupo = self._grupo_pai()
        self._grupo_antes_do_arrasto = _estado_recursivo(grupo) if grupo is not None else None

    # ── Redimensionar ────────────────────────────────────────────────
    def _redimensionar_para(self, ponto_cena: QPointF, modificadores=Qt.KeyboardModifier.NoModifier) -> None:
        """Convenções do CorelDRAW: alça de **canto** escala proporcional
        (Alt solta a proporção), alça do **meio** estica um eixo só, e
        **Shift** redimensiona a partir do centro."""
        rel_x, rel_y = _PONTO_RELATIVO_ALCA[self._alca_ativa]
        do_centro = bool(modificadores & Qt.KeyboardModifier.ShiftModifier)
        canto = rel_x != 0.5 and rel_y != 0.5

        rotacao_inversa = QTransform().rotate(-self._arrasto_angulo_inicial)
        ancora = self._arrasto_centro_cena if do_centro else self._arrasto_oposto_cena
        diff_local = rotacao_inversa.map(ponto_cena - ancora)
        fator = 2.0 if do_centro else 1.0

        nova_largura = self._arrasto_largura_inicial
        nova_altura = self._arrasto_altura_inicial
        if rel_x != 0.5:
            nova_largura = max(self._largura_minima_mm, abs(diff_local.x()) * fator)
        if rel_y != 0.5:
            nova_altura = max(self._altura_minima_mm, abs(diff_local.y()) * fator)

        proporcional = self._proporcao_travada or (canto and not modificadores & Qt.KeyboardModifier.AltModifier)
        if proporcional and canto and self._arrasto_largura_inicial and self._arrasto_altura_inicial:
            escala = max(nova_largura / self._arrasto_largura_inicial, nova_altura / self._arrasto_altura_inicial)
            nova_largura = max(self._largura_minima_mm, self._arrasto_largura_inicial * escala)
            nova_altura = max(self._altura_minima_mm, self._arrasto_altura_inicial * escala)
        elif self._proporcao_travada and self._arrasto_largura_inicial and self._arrasto_altura_inicial:
            # Mesmo puxando só uma alça de borda (largura OU altura), com
            # a proporção travada o outro eixo acompanha na mesma escala
            # — não só as alças de canto. Usa o eixo que a alça realmente
            # controla como referência da escala (o outro, se também
            # mudou, é ignorado — só um eixo pode ser "o motivo" do
            # arrasto de cada vez).
            escala = (
                nova_largura / self._arrasto_largura_inicial
                if rel_x != 0.5
                else nova_altura / self._arrasto_altura_inicial
            )
            nova_largura = max(self._largura_minima_mm, self._arrasto_largura_inicial * escala)
            nova_altura = max(self._altura_minima_mm, self._arrasto_altura_inicial * escala)

        origem_nova = QPointF(nova_largura / 2, nova_altura / 2)
        if do_centro:
            # Origem de transformação = centro, então o centro fica parado.
            nova_pos = self._arrasto_centro_cena - origem_nova
        else:
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
    def _girar_para(self, ponto_cena: QPointF, modificadores=Qt.KeyboardModifier.NoModifier) -> None:
        delta = ponto_cena - self._arrasto_centro_cena
        angulo_atual = math.degrees(math.atan2(delta.y(), delta.x()))
        variacao = angulo_atual - self._arrasto_angulo_mouse_inicial
        angulo = self._arrasto_angulo_inicial + variacao
        if modificadores & Qt.KeyboardModifier.ControlModifier:
            angulo = round(angulo / 15.0) * 15.0  # Ctrl = passos de 15° (CorelDRAW)
        self.setRotation(angulo)
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
        # Só o desenho (sem a folga das alças de seleção): senão a caixa do
        # grupo nascia maior e "pulava" no primeiro Ctrl+clique.
        rect_cena = elementos[0].retangulo_conteudo_cena()
        for el in elementos[1:]:
            rect_cena = rect_cena.united(el.retangulo_conteudo_cena())

        self.setRotation(0)
        self.prepareGeometryChange()
        self._largura = max(_LARGURA_MINIMA_MM, rect_cena.width())
        self._altura = max(_ALTURA_MINIMA_MM, rect_cena.height())
        self.setTransformOriginPoint(self._largura / 2, self._altura / 2)
        if cena is not None:
            cena.addItem(self)
        self.setPos(rect_cena.topLeft())

        for el in elementos:
            # Pelo centro (o ponto em volta do qual o objeto gira), não pela
            # origem: num objeto girado a origem fica em outro lugar e ele pulava.
            centro = el.transformOriginPoint()
            centro_cena = el.mapToScene(centro)
            el.setSelected(False)
            el.setParentItem(self)
            el.setPos(self.mapFromScene(centro_cena) - centro)
            # Dentro do grupo, o objeto só se seleciona com Ctrl+clique (CorelDRAW).
            el.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self._elementos.append(el)

    def desagrupar(self) -> list[ElementoMockup]:
        """Devolve os filhos pro nível da cena, preservando posição/
        rotação absolutas, e remove este grupo (vazio) da cena."""
        cena = self.scene()
        elementos = list(self._elementos)
        for el in elementos:
            centro = el.transformOriginPoint()
            centro_cena = el.mapToScene(centro)  # pelo centro: ver _agrupar
            rotacao_absoluta = el.rotation() + self.rotation()
            el.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            el.setParentItem(None)
            if cena is not None:
                cena.addItem(el)
            el.setRotation(rotacao_absoluta)
            el.setPos(centro_cena - centro)
            el.setSelected(True)
        self._elementos.clear()
        if cena is not None:
            cena.removeItem(self)
        return elementos

    def recalcular_limites(self) -> None:
        """Caixa do grupo de novo em volta dos filhos (depois de um deles ser
        movido com Ctrl+clique). Grupo girado fica como está (mexer na caixa
        mudaria o centro de giro e a arte pularia)."""
        if not self._elementos or self.rotation() % 360:
            return
        area = QRectF()
        for el in self._elementos:
            area = area.united(el.mapRectToParent(QRectF(0, 0, el.largura, el.altura)))
        if area.isEmpty() or (abs(area.left()) < 1e-6 and abs(area.top()) < 1e-6
                              and abs(area.width() - self._largura) < 1e-6 and abs(area.height() - self._altura) < 1e-6):
            return
        self.prepareGeometryChange()
        for el in self._elementos:
            el.setPos(el.pos() - area.topLeft())
        self.setPos(self.pos() + area.topLeft())
        self._largura = max(_LARGURA_MINIMA_MM, area.width())
        self._altura = max(_ALTURA_MINIMA_MM, area.height())
        self.setTransformOriginPoint(self._largura / 2, self._altura / 2)
        self.update()
        self.geometria_alterada.emit()

    def _redimensionar_para(self, ponto_cena: QPointF, modificadores=Qt.KeyboardModifier.NoModifier) -> None:
        largura_antes = self._largura
        altura_antes = self._altura
        super()._redimensionar_para(ponto_cena, modificadores)
        fator_x = self._largura / largura_antes if largura_antes else 1.0
        fator_y = self._altura / altura_antes if altura_antes else 1.0
        self._escalar_filhos(fator_x, fator_y)

    def definir_tamanho(self, largura: float, altura: float) -> None:
        """Tamanho do grupo pela barra (campos, escala %) ou pelo desfazer:
        os de dentro escalam junto (antes só a caixa do grupo mudava)."""
        largura_antes, altura_antes = self._largura, self._altura
        super().definir_tamanho(largura, altura)
        self._escalar_filhos(
            self._largura / largura_antes if largura_antes else 1.0,
            self._altura / altura_antes if altura_antes else 1.0,
        )

    def _escalar_filhos(self, fator_x: float, fator_y: float) -> None:
        """Escala cada filho pelo CENTRO dele, no eixo certo mesmo girado: um
        texto a 90° esticado na horizontal fica mais comprido na tela, não
        mais alto (antes esticava o eixo errado e o texto sumia)."""
        if abs(fator_x - 1.0) < 1e-12 and abs(fator_y - 1.0) < 1e-12:
            return
        for el in self._elementos:
            angulo = math.radians(el.rotation())
            c, s = math.cos(angulo), math.sin(angulo)
            fator_largura = math.hypot(fator_x * c, fator_y * s)
            fator_altura = math.hypot(fator_x * s, fator_y * c)
            centro = el.pos() + QPointF(el.largura / 2, el.altura / 2)
            novo_centro = QPointF(centro.x() * fator_x, centro.y() * fator_y)
            el.definir_tamanho(el.largura * fator_largura, el.altura * fator_altura)
            el.setPos(novo_centro - QPointF(el.largura / 2, el.altura / 2))

    def _pintar_conteudo(self, painter: QPainter) -> None:
        pass  # o conteúdo visível são os próprios filhos — o Qt já desenha eles

    def clonar(self) -> "GrupoMockup":
        # Não passa pelo `_agrupar` normal (ele calcula a geometria a
        # partir de `sceneBoundingRect()` dos filhos, que exige que já
        # estejam na cena) — aqui já sabemos a geometria de sobra (a do
        # próprio grupo original), só falta clonar cada filho preservando
        # a posição/rotação LOCAL dele (que `clonar()` de cada um já
        # copia certo, ver `_copiar_geometria_para`) e reparentar.
        novo = GrupoMockup([])
        self._copiar_geometria_para(novo)
        for el in self._elementos:
            clone = el.clonar()
            clone.setParentItem(novo)
            clone.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            novo._elementos.append(clone)
        return novo


def _estado_recursivo(item: ElementoMockup) -> dict[ElementoMockup, tuple]:
    """Estado de geometria de `item` + de todo filho (recursivo) se for um
    `GrupoMockup` — redimensionar um grupo reescreve a geometria de cada
    filho (ver `GrupoMockup._redimensionar_para`), então desfazer isso
    precisa restaurar os filhos também, não só o grupo em si."""
    estados = {item: item._estado_geometria()}
    if isinstance(item, GrupoMockup):
        for filho in item.elementos:
            estados.update(_estado_recursivo(filho))
    return estados
