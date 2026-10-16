"""Tela 3D: a caixa montada a partir da mesma dieline, com animação de
planificar (abrir até virar a faca plana) e montar (dobrar de volta).

Renderização feita à mão com QPainter — projeção em perspectiva e
pintura por profundidade (painter's algorithm) — em vez de OpenGL/Qt3D/
WebEngine: são poucas dezenas de faces planas, cabe folgado em Python
puro, e não traz nenhuma dependência nova pro empacotamento (PyInstaller).

Pra a ordenação por profundidade acertar quando duas faces grandes se
cruzam na tela, cada painel é dividido numa grade de pedaços menores
(`_SUBDIVISOES`) e cada pedaço é ordenado sozinho. Só a borda real do
painel recebe contorno — as emendas entre pedaços não aparecem.

A arte do Layout (texto, formas, logotipo) entra como textura: uma imagem
POR FACE, renderizada da própria cena do canvas sem a faca
(`renderizar_arte_regioes`), na densidade que aquela face ocupa na tela
agora (com folga). Aproximar a câmera faz a face ser redesenhada mais
nítida — antes era uma imagem só da chapa inteira, limitada a ~2,4 px/mm,
e texto/logo saíam borrados e serrilhados. Cada pedaço da face externa
recebe o recorte dele via `QTransform.quadToQuad` — projetivo exato pra
uma face plana. A arte vai sem luz/sombra por cima, pra manter as cores
originais da marca.

A geometria (quais painéis existem, onde fica cada vinco, em que ordem
cada aba dobra) mora em `dobra3d.py`, sem nada de UI.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QEasingCurve, QLineF, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient, QTransform
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..dobra3d import (
    ModeloCaixa3D,
    Vetor,
    caixa_envolvente,
    normalizar,
    posicionar,
    produto_escalar,
    produto_vetorial,
)
from . import configuracoes
from .estilo import FONTE_MONO, Cor

_SUBDIVISOES = 5
_FOV_GRAUS = 34.0
_DURACAO_MONTAR_MS = 3400
_DURACAO_PLANIFICAR_MS = 2800
# Giro automático da caixa montada parada (soma ao arrasto do usuário).
_GIRO_AUTOMATICO_GRAUS_S = 8.0
_INTERVALO_QUADRO_MS = 33
_ZOOM_APROXIMA = 1.5  # zoom em que a câmera para de se aproximar e vira lupa
# Textura da arte, por face: densidade = a que a face ocupa na tela × folga,
# entre o mínimo e o máximo, e nunca mais que o lado máximo em pixels.
_ARTE_FOLGA_DENSIDADE = 1.6
_ARTE_PX_POR_MM_MIN = 1.0
_ARTE_PX_POR_MM_MAX = 24.0
_ARTE_LADO_MAX_PX = 6000
_ARTE_MARGEM_MM = 1.0

# Vista "3/4" da caixa montada (graus, relativos a `cima`/`frente` do modelo).
_YAW_MONTADA = -34.0
_PITCH_MONTADA = 24.0

# Papelão: lado impresso (kraft da marca) e miolo/lado de dentro, mais claro.
_COR_EXTERNA = QColor("#C79A5D")
_COR_INTERNA = QColor("#E6D0A8")
_COR_ARESTA = QColor(74, 54, 30, 210)
# Borda cortada do papelão (o miolo ondulado aparece mais escuro).
_COR_ESPESSURA = QColor("#9C7444")

# Papelões comuns (espessura em mm), como na escolha de papelão do ArtiosCAD.
PAPELOES = (
    ("Fino (sem espessura)", 0.0),
    # Escala reduzida (caixa desenhada em 1:10, como 605 mm → 60,5 mm).
    ("Onda B 1:10 (0,3 mm)", 0.3),
    ("Onda dupla BC 1:10 (0,7 mm)", 0.7),
    ("Cartão (0,5 mm)", 0.5),
    ("Micro-ondulado E (1,5 mm)", 1.5),
    ("Onda B (3 mm)", 3.0),
    ("Onda C (4 mm)", 4.0),
    ("Onda dupla BC (7 mm)", 7.0),
)

# Miolo do papelão visto na borda cortada: passo (mm) de cada ondulação, de
# fora pra dentro. Vazio = sem onda (folha ou cartão maciço).
_MIOLO_POR_ESPESSURA = {
    0.3: (0.65,),  # onda B em 1:10
    0.7: (0.65, 0.8),  # onda BC em 1:10
    0.5: (),
    1.5: (3.5,),  # E
    3.0: (6.5,),  # B
    4.0: (8.0,),  # C
    7.0: (6.5, 8.0),  # BC: onda B por fora, C por dentro
}
_CAPA_MM = 0.25  # espessura de cada capa (liner)


def miolo_do_papelao(espessura_mm: float) -> tuple[float, ...]:
    """Passos das ondulações do papelão com esta espessura: os da lista; um
    valor digitado vira onda simples até 5 mm e dupla acima disso, com o
    passo proporcional (vale pra desenho em escala reduzida também)."""
    for mm, ondas in _MIOLO_POR_ESPESSURA.items():
        if abs(mm - espessura_mm) < 1e-6:
            return ondas
    if espessura_mm <= 0:
        return ()
    if espessura_mm <= 5.0:
        return (2.2 * espessura_mm,)
    fator = espessura_mm / 7.0
    return (6.5 * fator, 8.0 * fator)
# Fundo claro neutro (mesmo no tema escuro: é um "estúdio" pra ver a caixa).
_COR_FUNDO = QColor("#ECEBE8")
_COR_TEXTO_FUNDO = QColor("#6B6862")

# Luz vinda de cima/esquerda/da frente, em coordenadas de câmera
# (x direita, y cima, z pra dentro da tela).
_LUZ = normalizar((-0.35, 0.6, -0.72))


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def _lerp_vetor(a: Vetor, b: Vetor, u: float) -> Vetor:
    return (_lerp(a[0], b[0], u), _lerp(a[1], b[1], u), _lerp(a[2], b[2], u))


def _suavizar(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def renderizar_arte_regioes(
    cena: QGraphicsScene, elementos: list, pedidos: list[tuple[QRectF, float]]
) -> list[QImage | None]:
    """Uma imagem transparente por pedido `(retângulo em mm, px por mm)`,
    só com os elementos de Layout — sem faca, guias nem seleção (mesma
    ideia de `_SelecaoOculta` em exportacao.py). A faca e as guias são
    escondidas UMA vez pra todos os pedidos. `None` quando o retângulo não
    encosta em nenhuma arte. Cada imagem guarda `px_por_mm`, `x_mm` e
    `y_mm` (canto do retângulo) em `QImage.text`."""
    visiveis = [el for el in elementos if el.isVisible()]
    if not visiveis or not pedidos:
        return [None] * len(pedidos)
    area_arte = QRectF()
    for el in visiveis:
        area_arte = area_arte.united(el.sceneBoundingRect())

    manter = set(elementos)
    ocultos = [it for it in cena.items() if it.parentItem() is None and it not in manter and it.isVisible()]
    selecionados = list(cena.selectedItems())
    for item in ocultos:
        item.setVisible(False)
    for item in selecionados:
        item.setSelected(False)
    resultado: list[QImage | None] = []
    from .mockup_itens import cache_desligado

    sem_cache = cache_desligado(cena)
    sem_cache.__enter__()  # textura na resolução pedida, não a do cache de tela
    try:
        for retangulo, px_por_mm in pedidos:
            if retangulo.isEmpty() or not retangulo.intersects(area_arte):
                resultado.append(None)
                continue
            px_por_mm = min(px_por_mm, _ARTE_LADO_MAX_PX / max(retangulo.width(), retangulo.height()))
            imagem = QImage(
                max(1, math.ceil(retangulo.width() * px_por_mm)),
                max(1, math.ceil(retangulo.height() * px_por_mm)),
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            imagem.fill(Qt.GlobalColor.transparent)
            p = QPainter(imagem)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            destino = QRectF(0.0, 0.0, retangulo.width() * px_por_mm, retangulo.height() * px_por_mm)
            cena.render(p, target=destino, source=retangulo, aspectRatioMode=Qt.AspectRatioMode.IgnoreAspectRatio)
            p.end()
            imagem.setText("px_por_mm", f"{px_por_mm}")
            imagem.setText("x_mm", f"{retangulo.left()}")
            imagem.setText("y_mm", f"{retangulo.top()}")
            resultado.append(imagem)
    finally:
        sem_cache.__exit__(None, None, None)
        for item in ocultos:
            item.setVisible(True)
        for item in selecionados:
            item.setSelected(True)
    return resultado


def renderizar_arte(cena: QGraphicsScene, elementos: list, largura_mm: float, altura_mm: float, px_por_mm: float = 4.0) -> QImage | None:
    """A chapa inteira numa imagem só (usado fora do 3D, ex.: testes)."""
    return renderizar_arte_regioes(cena, elementos, [(QRectF(0.0, 0.0, largura_mm, altura_mm), px_por_mm)])[0]


def _caminho_do_painel(painel) -> QPainterPath:
    caminho = QPainterPath()
    caminho.setFillRule(Qt.FillRule.OddEvenFill)  # furos ficam vazados
    caminho.addPolygon(QPolygonF([QPointF(x, y) for x, y in painel.poligono]))
    caminho.closeSubpath()
    for furo in painel.furos:
        caminho.addPolygon(QPolygonF([QPointF(x, y) for x, y in furo]))
        caminho.closeSubpath()
    return caminho


def _na_borda(q: QPointF, painel, tol: float = 1e-3) -> bool:
    """O ponto está sobre o contorno da face (ou de um furo)?"""
    for contorno in (painel.poligono, *painel.furos):
        n = len(contorno)
        for k in range(n):
            (x1, y1), (x2, y2) = contorno[k], contorno[(k + 1) % n]
            dx, dy = x2 - x1, y2 - y1
            c2 = dx * dx + dy * dy
            if c2 < 1e-12:
                continue
            t = max(0.0, min(1.0, ((q.x() - x1) * dx + (q.y() - y1) * dy) / c2))
            if math.hypot(q.x() - (x1 + dx * t), q.y() - (y1 + dy * t)) < tol:
                return True
    return False


class VistaCaixa3D(QWidget):
    """Viewport 3D. Arrastar gira, roda do mouse aproxima, duplo clique
    volta pra vista inicial."""

    progresso_alterado = Signal(float)
    # Modos "dobra" e "base" (dobra genérica, ver dobra_generica.py): clique
    # num vinco (índice da linha da faca) ou numa face (id do painel).
    dobra_clicada = Signal(int)
    face_clicada = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setMouseTracking(False)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._modelo = ModeloCaixa3D()
        self._medidas_texto = ""
        self._progresso = 1.0
        self._yaw_usuario = 0.0
        self._pitch_usuario = 0.0
        self._zoom = 1.0
        # Deslocamento da vista em pixels de tela (arrastar com o botão do
        # meio, o direito ou Shift): aproximar não fica preso no centro.
        self._pan = QPointF(0.0, 0.0)
        self._arrasto_pan: tuple[QPointF, QPointF] | None = None
        # Espessura do papelão (mm): o lado de dentro fica E mm pra dentro e
        # cada borda vira uma faixa de papelão. 0 = folha fina (como antes).
        self._espessura = 0.0
        self._arrasto: tuple[QPointF, float, float] | None = None
        self._modo = "girar"  # "girar" | "dobra" | "base"
        self._dobra_destacada: int | None = None
        self._dobradicas_tela: list[tuple[QPointF, QPointF, int, float]] = []
        self._faces_tela: list[tuple[float, QPolygonF, str]] = []
        # Enquadramento de cada estado — a câmera interpola entre os dois,
        # senão a caixa montada fica minúscula no quadro da chapa aberta.
        self._centro_plano: Vetor = (0.0, 0.0, 0.0)
        self._centro_montado: Vetor = (0.0, 0.0, 0.0)
        self._raio_plano = 1.0
        self._raio_montado = 1.0
        # Arte: `fonte(pedidos) -> imagens` (ver `renderizar_arte_regioes`)
        # e uma textura por painel: id → (imagem | None, px/mm, retângulo mm).
        self._fonte_arte = None
        self._texturas: dict[str, tuple[QImage | None, float, QRectF]] = {}
        self._texturas_pendentes: dict[str, tuple[QRectF, float]] = {}
        self._timer_texturas = QTimer(self)
        self._timer_texturas.setSingleShot(True)
        self._timer_texturas.setInterval(90)  # espera a câmera parar um instante
        self._timer_texturas.timeout.connect(self._gerar_texturas_pendentes)
        # Giro automático: só com a caixa montada, parada e sem arrasto.
        self._giro_auto = 0.0
        self._relogio = QElapsedTimer()
        self._timer_giro = QTimer(self)
        self._timer_giro.setInterval(_INTERVALO_QUADRO_MS)
        self._timer_giro.timeout.connect(self._passo_giro)
        self._girar_sozinho = configuracoes.giro_automatico_3d()
        # Quanto o último quadro levou pra desenhar (ms): o giro espera pelo
        # menos isso de novo antes do próximo, deixando metade do tempo livre
        # pro resto do app (antes pedia quadro a cada 33 ms e cada um levava
        # 25–70 ms — a janela inteira ficava sem responder direito).
        self._ultimo_quadro_ms = 0.0

    # ── API ──────────────────────────────────────────────────────────
    def definir_modelo(self, modelo: ModeloCaixa3D, medidas_texto: str = "") -> None:
        self._modelo = modelo
        self._medidas_texto = medidas_texto
        if not modelo.vazio:
            plano = caixa_envolvente(posicionar(modelo, 0.0))
            montado = caixa_envolvente(posicionar(modelo, 1.0))
            self._centro_plano = _lerp_vetor(plano[0], plano[1], 0.5)
            self._centro_montado = _lerp_vetor(montado[0], montado[1], 0.5)
            self._raio_plano = max(math.dist(plano[0], plano[1]) / 2.0, 1.0)
            self._raio_montado = max(math.dist(montado[0], montado[1]) / 2.0, 1.0)
        self._texturas.clear()  # painéis mudaram de lugar/tamanho
        self.update()

    def definir_fonte_arte(self, fonte) -> None:
        """`fonte(pedidos: list[(QRectF mm, px/mm)]) -> list[QImage | None]`,
        ou None sem arte. Joga fora as texturas: a arte pode ter mudado."""
        self._fonte_arte = fonte
        self._texturas.clear()
        self._texturas_pendentes.clear()
        self.update()

    def textura_do_painel(self, painel_id: str) -> tuple[QImage | None, float, QRectF] | None:
        return self._texturas.get(painel_id)

    def _gerar_texturas(self, pedidos: dict[str, tuple[QRectF, float]]) -> None:
        if self._fonte_arte is None or not pedidos:
            return
        chaves = list(pedidos)
        imagens = self._fonte_arte([pedidos[c] for c in chaves])
        for chave, imagem in zip(chaves, imagens):
            retangulo, densidade = pedidos[chave]
            if imagem is not None:
                densidade = float(imagem.text("px_por_mm") or densidade)
            self._texturas[chave] = (imagem, densidade, retangulo)

    def _gerar_texturas_pendentes(self) -> None:
        pendentes, self._texturas_pendentes = self._texturas_pendentes, {}
        self._gerar_texturas(pendentes)
        self.update()

    def progresso(self) -> float:
        return self._progresso

    @property
    def tem_dobras_editaveis(self) -> bool:
        """Só a dobra genérica tem ângulo por vinco e base escolhível."""
        return any(p.linha_origem is not None for p in self._modelo.paineis)

    def definir_modo(self, modo: str) -> None:
        self._modo = modo
        self.setCursor(Qt.CursorShape.OpenHandCursor if modo == "girar" else Qt.CursorShape.PointingHandCursor)
        self.update()

    def destacar_dobra(self, linha: int | None) -> None:
        self._dobra_destacada = linha
        self.update()

    def definir_progresso(self, valor: float) -> None:
        valor = max(0.0, min(1.0, valor))
        if valor != self._progresso:
            self._progresso = valor
            self.progresso_alterado.emit(valor)
            self._atualizar_timer_giro()
            self.update()

    @property
    def espessura(self) -> float:
        return self._espessura

    def definir_espessura(self, mm: float) -> None:
        self._espessura = max(0.0, float(mm))
        self.update()

    def vista_inicial(self) -> None:
        self._yaw_usuario = 0.0
        self._pitch_usuario = 0.0
        self._giro_auto = 0.0
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self.update()

    # ── Giro automático ──────────────────────────────────────────────
    @property
    def girar_sozinho(self) -> bool:
        return self._girar_sozinho

    def definir_girar_sozinho(self, ativo: bool) -> None:
        self._girar_sozinho = bool(ativo)
        configuracoes.definir_giro_automatico_3d(self._girar_sozinho)
        self._atualizar_timer_giro()

    def _atualizar_timer_giro(self) -> None:
        girar = (
            self._girar_sozinho
            and self.isVisible()
            and self._progresso >= 0.999
            and self._arrasto is None
            and not self._modelo.vazio
        )
        if girar and not self._timer_giro.isActive():
            self._relogio.start()
            self._timer_giro.start()
        elif not girar and self._timer_giro.isActive():
            self._timer_giro.stop()

    def _passo_giro(self) -> None:
        dt = self._relogio.restart() / 1000.0
        self._giro_auto = (self._giro_auto + _GIRO_AUTOMATICO_GRAUS_S * min(dt, 0.2)) % 360.0
        # Próximo quadro só depois de um intervalo do tamanho do quadro.
        self._timer_giro.setInterval(int(min(250.0, max(_INTERVALO_QUADRO_MS, 2.0 * self._ultimo_quadro_ms))))
        self.update()

    def showEvent(self, evento) -> None:  # noqa: N802
        super().showEvent(evento)
        self._atualizar_timer_giro()

    def hideEvent(self, evento) -> None:  # noqa: N802
        super().hideEvent(evento)
        self._atualizar_timer_giro()

    # ── Câmera ───────────────────────────────────────────────────────
    def _camera(self) -> tuple[Vetor, Vetor, Vetor, Vetor]:
        """(olho, direita, cima, frente) da câmera pro progresso atual.

        Sem o usuário mexer, a câmera acompanha a montagem: com a chapa
        plana ela olha o lado impresso de frente (igual à tela de
        Dieline); montada, vai pra uma vista 3/4 de cima. O giro do
        usuário soma por cima disso."""
        m = self._modelo
        u = _suavizar(self._progresso)
        yaw = math.radians(_lerp(0.0, _YAW_MONTADA, u) + self._yaw_usuario + self._giro_auto)
        pitch_graus = _lerp(m.pitch_planificada, _PITCH_MONTADA, u) + self._pitch_usuario
        pitch = math.radians(max(-90.0, min(90.0, pitch_graus)))

        cima = normalizar(m.cima)
        frente = normalizar(m.frente)
        lateral = produto_vetorial(cima, frente)
        frente_girada = tuple(frente[i] * math.cos(yaw) + lateral[i] * math.sin(yaw) for i in range(3))
        direcao = tuple(math.cos(pitch) * frente_girada[i] + math.sin(pitch) * cima[i] for i in range(3))
        cima_cam = normalizar(tuple(-math.sin(pitch) * frente_girada[i] + math.cos(pitch) * cima[i] for i in range(3)))
        olhar = tuple(-d for d in direcao)
        direita = normalizar(produto_vetorial(olhar, cima_cam))

        centro = _lerp_vetor(self._centro_plano, self._centro_montado, u)
        raio = _lerp(self._raio_plano, self._raio_montado, u)
        # Até _ZOOM_APROXIMA a câmera chega mais perto; daí em diante o zoom
        # vira ampliação da imagem (ver `escala` no desenho) — senão a câmera
        # entrava na caixa antes de chegar perto de uma borda.
        distancia = raio / math.sin(math.radians(_FOV_GRAUS) / 2.0) * 1.05 / min(self._zoom, _ZOOM_APROXIMA)
        olho = tuple(centro[i] + direcao[i] * distancia for i in range(3))
        return olho, direita, cima_cam, olhar  # type: ignore[return-value]

    # ── Pintura ──────────────────────────────────────────────────────
    def paintEvent(self, evento) -> None:  # noqa: N802 (API do Qt)
        relogio = QElapsedTimer()
        relogio.start()
        self._pintar(evento)
        self._ultimo_quadro_ms = float(relogio.elapsed())

    # ── Foto da vista (pra mandar pro cliente) ───────────────────────
    def renderizar_imagem(self, escala: float = 2.0, fundo: QColor | None = None, recortar: bool = True) -> QImage:
        """A vista atual como imagem, `escala` vezes o tamanho da tela, sem
        os textos de ajuda nem as marcas de dobra. `fundo` None = transparente
        (PNG); a arte das faces é gerada na resolução da foto."""
        escala = max(1.0, float(escala))
        self._foto = {"escala": escala, "fundo": fundo}
        try:
            imagem = self._pintar_em_imagem(escala, fundo)
            if self._texturas_pendentes:
                # A arte pediu resolução maior: gera agora e pinta de novo.
                pendentes, self._texturas_pendentes = self._texturas_pendentes, {}
                self._gerar_texturas(pendentes)
                imagem = self._pintar_em_imagem(escala, fundo)
            caixa = self._foto.get("caixa")
        finally:
            self._foto = None
            self._timer_texturas.start()  # a tela volta pra resolução dela
        if recortar and caixa is not None and not caixa.isEmpty():
            # Recorta em volta da caixa: margem de 12% (cabe a sombra embaixo).
            margem = max(caixa.width(), caixa.height()) * 0.12
            area = caixa.adjusted(-margem, -margem, margem, margem * 1.6).intersected(QRectF(self.rect()))
            px = area.toAlignedRect()
            imagem = imagem.copy(
                int(px.x() * escala), int(px.y() * escala), int(px.width() * escala), int(px.height() * escala)
            )
            imagem.setDevicePixelRatio(1.0)
        return imagem

    def _pintar_em_imagem(self, escala: float, fundo: QColor | None) -> QImage:
        imagem = QImage(int(self.width() * escala), int(self.height() * escala), QImage.Format.Format_ARGB32_Premultiplied)
        imagem.setDevicePixelRatio(escala)
        imagem.fill(Qt.GlobalColor.transparent if fundo is None else fundo)
        self._pintar(None, alvo=imagem)
        return imagem

    def _pintar(self, _evento, alvo=None) -> None:
        foto = getattr(self, "_foto", None)
        p = QPainter(self if alvo is None else alvo)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if foto is None:
            p.fillRect(self.rect(), _COR_FUNDO)

        if self._modelo.vazio:
            p.setPen(_COR_TEXTO_FUNDO)
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Nada pra dobrar ainda: desenhe na tela Dieline cortes e vincos que fechem as faces."
                if self._modelo.descricao
                else "Informe comprimento, largura e altura para ver a caixa em 3D.",
            )
            return

        olho, direita, cima, olhar = self._camera()
        escala = (min(self.width(), self.height()) / 2.0) / math.tan(math.radians(_FOV_GRAUS) / 2.0)
        escala *= max(1.0, self._zoom / _ZOOM_APROXIMA)  # lupa: além da aproximação
        cx, cy = self.width() / 2.0 + self._pan.x(), self.height() / 2.0 + self._pan.y()

        def para_camera(ponto: Vetor) -> Vetor:
            v = (ponto[0] - olho[0], ponto[1] - olho[1], ponto[2] - olho[2])
            return (produto_escalar(v, direita), produto_escalar(v, cima), produto_escalar(v, olhar))

        def para_tela(pc: Vetor) -> QPointF:
            return QPointF(cx + escala * pc[0] / pc[2], cy - escala * pc[1] / pc[2])

        self._desenhar_sombra(p, para_camera, para_tela, escala)

        # (profundidade, poligono, cor, arestas da borda, (recorte, quad) da arte em px | None)
        pedacos = []
        caixa_fechada = self._progresso >= 0.999 and self._modelo.solido_fechado
        vies_interno = 0.04 * self._raio_montado
        vies_camada = 0.08 * self._raio_montado
        n = _SUBDIVISOES
        self._dobradicas_tela = []
        self._faces_tela = []
        com_arte = self._fonte_arte is not None
        densidade_necessaria: dict[str, float] = {}
        retangulo_painel: dict[str, QRectF] = {}
        razao_pixels = foto["escala"] if foto else self.devicePixelRatioF()
        for pp in posicionar(self._modelo, self._progresso):
            painel = pp.painel
            if caixa_fechada and painel.camada > 0:
                continue  # fechada é um sólido: as abas por baixo nunca aparecem
            if painel.dobradica is not None and painel.linha_origem is not None:
                (ax, ay), (bx, by) = painel.dobradica
                ca, cb = para_camera(pp.ponto(ax, ay)), para_camera(pp.ponto(bx, by))
                if ca[2] > 1.0 and cb[2] > 1.0:
                    self._dobradicas_tela.append((para_tela(ca), para_tela(cb), painel.linha_origem, painel.angulo_fechado))
            normal = pp.normal_externa
            normal_cam = (
                produto_escalar(normal, direita),
                produto_escalar(normal, cima),
                produto_escalar(normal, olhar),
            )
            # Face que não é retângulo (dobra genérica): cada célula da grade é
            # recortada pelo contorno real da face (menos os furos).
            caminho_face = _caminho_do_painel(painel) if painel.poligono is not None else None
            # Grade (n+1)×(n+1) de pontos do painel já em coordenadas de câmera.
            grade = [
                [
                    para_camera(pp.ponto(_lerp(painel.x1, painel.x2, i / n), _lerp(painel.y1, painel.y2, j / n)))
                    for i in range(n + 1)
                ]
                for j in range(n + 1)
            ]
            espessura = self._espessura
            grade_dentro = (
                [
                    [
                        para_camera(
                            pp.transformacao.aplicar(
                                (_lerp(painel.x1, painel.x2, i / n), _lerp(painel.y1, painel.y2, j / n), espessura)
                            )
                        )
                        for i in range(n + 1)
                    ]
                    for j in range(n + 1)
                ]
                if espessura > 0
                else grade
            )
            for j in range(n):
                for i in range(n):
                    cantos = [grade[j][i], grade[j][i + 1], grade[j + 1][i + 1], grade[j + 1][i]]
                    if min(c[2] for c in cantos) <= 1.0:
                        continue  # atrás/encostado na câmera
                    centro = tuple(sum(c[k] for c in cantos) / 4.0 for k in range(3))
                    ve_lado_externo = produto_escalar(normal_cam, centro) < 0
                    if not ve_lado_externo and caixa_fechada:
                        continue  # caixa fechada é um sólido: o lado de dentro nunca aparece
                    z_lado = 0.0
                    if not ve_lado_externo and espessura > 0:
                        # Lado de dentro: a outra face do papelão, E mm pra dentro.
                        cantos = [grade_dentro[j][i], grade_dentro[j][i + 1], grade_dentro[j + 1][i + 1], grade_dentro[j + 1][i]]
                        if min(c[2] for c in cantos) <= 1.0:
                            continue
                        centro = tuple(sum(c[k] for c in cantos) / 4.0 for k in range(3))
                        z_lado = espessura
                    face_normal = normal_cam if ve_lado_externo else tuple(-c for c in normal_cam)
                    luz = 0.55 + 0.45 * max(0.0, produto_escalar(face_normal, _LUZ))
                    base = _COR_EXTERNA if ve_lado_externo else _COR_INTERNA
                    cor = QColor.fromRgbF(
                        min(1.0, base.redF() * luz), min(1.0, base.greenF() * luz), min(1.0, base.blueF() * luz)
                    )
                    tela = [para_tela(c) for c in cantos]
                    xa, xb = _lerp(painel.x1, painel.x2, i / n), _lerp(painel.x1, painel.x2, (i + 1) / n)
                    ya, yb = _lerp(painel.y1, painel.y2, j / n), _lerp(painel.y1, painel.y2, (j + 1) / n)
                    if caminho_face is None:
                        desenhos = [QPolygonF(tela)]
                        bordas = []
                        if j == 0:
                            bordas.append((tela[0], tela[1]))
                        if i == n - 1:
                            bordas.append((tela[1], tela[2]))
                        if j == n - 1:
                            bordas.append((tela[2], tela[3]))
                        if i == 0:
                            bordas.append((tela[3], tela[0]))
                    else:
                        celula = QPainterPath()
                        celula.addRect(QRectF(QPointF(xa, ya), QPointF(xb, yb)).normalized())
                        recortes = celula.intersected(caminho_face).toFillPolygons()
                        if not recortes:
                            continue

                        def projetar(q: QPointF, z: float = z_lado) -> QPointF:
                            return para_tela(para_camera(pp.transformacao.aplicar((q.x(), q.y(), z))))

                        desenhos, bordas = [], []
                        for recorte in recortes:
                            pontos = [recorte.at(k) for k in range(recorte.count())]
                            desenhos.append(QPolygonF([projetar(q) for q in pontos]))
                            for a, b in zip(pontos, pontos[1:] + pontos[:1]):
                                if _na_borda(QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2), painel):
                                    bordas.append((projetar(a), projetar(b)))
                    profundidade = math.sqrt(produto_escalar(centro, centro))
                    profundidade += painel.camada * vies_camada
                    if not ve_lado_externo:
                        # Lado de dentro só aparece olhando pra dentro da caixa
                        # aberta — puxar ele pra trás evita que vaze por cima de
                        # uma face externa quase no mesmo lugar (abas sobrepostas).
                        profundidade += vies_interno
                    arte_pedaco = None
                    if com_arte and ve_lado_externo:
                        # Densidade (px de tela por mm) que este pedaço ocupa agora.
                        densidade = razao_pixels * max(
                            math.dist((tela[1].x(), tela[1].y()), (tela[0].x(), tela[0].y())) / max(abs(xb - xa), 1e-6),
                            math.dist((tela[3].x(), tela[3].y()), (tela[0].x(), tela[0].y())) / max(abs(yb - ya), 1e-6),
                        )
                        densidade_necessaria[painel.id] = max(densidade_necessaria.get(painel.id, 0.0), densidade)
                        retangulo_painel[painel.id] = QRectF(
                            QPointF(min(painel.x1, painel.x2), min(painel.y1, painel.y2)),
                            QPointF(max(painel.x1, painel.x2), max(painel.y1, painel.y2)),
                        ).adjusted(-_ARTE_MARGEM_MM, -_ARTE_MARGEM_MM, _ARTE_MARGEM_MM, _ARTE_MARGEM_MM)
                        arte_pedaco = (painel.id, xa, xb, ya, yb, painel)
                    quad_tela = QPolygonF(tela)
                    for desenho in desenhos:
                        self._faces_tela.append((profundidade, desenho, painel.id))
                    for k, desenho in enumerate(desenhos):
                        # As bordas vão só no 1º pedaço da célula (não duplicar traço).
                        pedacos.append((profundidade, desenho, cor, bordas if k == 0 else [], arte_pedaco, quad_tela, None))
            if self._espessura > 0 and not caixa_fechada:
                # Fechada, a borda do papelão fica escondida nas emendas (e o
                # pintor por profundidade deixava pedaços vazarem nas quinas).
                self._faixas_de_espessura(pp, para_camera, para_tela, direita, cima, olhar, caixa_fechada, vies_camada, pedacos)

        self._atualizar_texturas(densidade_necessaria, retangulo_painel)
        pedacos.sort(key=lambda item: item[0], reverse=True)
        caneta_aresta = QPen(_COR_ARESTA, 1.2)
        caneta_aresta.setCosmetic(True)
        transformacao = QTransform()
        if foto is not None:
            # Onde a caixa caiu na imagem (pro recorte da foto).
            caixa_tela = QRectF()
            for item in pedacos:
                caixa_tela = caixa_tela.united(item[1].boundingRect())
            foto["caixa"] = caixa_tela
        for _prof, poligono, cor, bordas, arte_pedaco, quad_tela, miolo in pedacos:
            # Contorno da mesma cor fecha as frestas de antialiasing entre pedaços.
            caneta_fill = QPen(cor, 1.2)
            caneta_fill.setCosmetic(True)
            p.setPen(caneta_fill)
            p.setBrush(cor)
            p.drawPolygon(poligono)
            desenho = self._recorte_da_arte(arte_pedaco, quad_tela) if arte_pedaco is not None else None
            if desenho is not None and QTransform.quadToQuad(desenho[2], quad_tela, transformacao):
                # Sem luz nem mistura por cima: a arte mantém a cor original.
                imagem, recorte, _quad = desenho
                p.save()
                if poligono != quad_tela:
                    # Célula recortada pelo contorno da face: a arte também.
                    contorno = QPainterPath()
                    contorno.addPolygon(poligono)
                    p.setClipPath(contorno)
                p.setTransform(transformacao)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                p.drawImage(recorte, imagem, recorte)
                p.restore()
            if miolo is not None:
                self._desenhar_miolo(p, quad_tela, miolo, cor)
            if bordas:
                p.setPen(caneta_aresta)
                for a, b in bordas:
                    p.drawLine(a, b)

        if foto:
            return  # foto: só a caixa (e a sombra)
        if self._modo == "dobra":
            self._desenhar_dobradicas(p)
        self._desenhar_legenda(p)

    def _atualizar_texturas(self, necessaria: dict[str, float], retangulos: dict[str, QRectF]) -> None:
        """Gera na hora a textura das faces que ainda não têm (senão a arte
        piscaria) e agenda refazer as que ficaram sem resolução (câmera
        aproximou) ou com resolução demais (afastou: menos memória e menos
        serrilhado ao reduzir)."""
        if self._fonte_arte is None:
            return
        agora: dict[str, tuple[QRectF, float]] = {}
        for chave, densidade in necessaria.items():
            alvo = min(_ARTE_PX_POR_MM_MAX, max(_ARTE_PX_POR_MM_MIN, densidade * _ARTE_FOLGA_DENSIDADE))
            atual = self._texturas.get(chave)
            if atual is None:
                agora[chave] = (retangulos[chave], alvo)
            elif atual[0] is not None and (atual[1] < alvo / 1.3 or atual[1] > alvo * 3.0):
                self._texturas_pendentes[chave] = (retangulos[chave], alvo)
        self._gerar_texturas(agora)
        if self._texturas_pendentes:
            self._timer_texturas.start()

    def _recorte_da_arte(self, arte_pedaco, poligono: QPolygonF):
        """(imagem, recorte na imagem, quad de origem) do pedaço, ou None."""
        chave, xa, xb, ya, yb, painel = arte_pedaco
        textura = self._texturas.get(chave)
        if textura is None or textura[0] is None:
            return None
        imagem, k, retangulo = textura
        ox, oy = retangulo.left(), retangulo.top()

        def px(x: float, y: float) -> QPointF:
            return QPointF((x - ox) * k, (y - oy) * k)

        recorte = QRectF(px(xa, ya), px(xb, yb)).normalized()
        # Avança ~1,5 px DA TELA sobre os pedaços vizinhos da MESMA face
        # (nunca além da borda dela): o contorno de 1,2 px do preenchimento
        # do pedaço seguinte, pintado depois, invadia a beirada desta arte.
        px_tela_por_px_arte = max(
            math.dist((poligono[1].x(), poligono[1].y()), (poligono[0].x(), poligono[0].y())) / max(recorte.width(), 1e-6),
            math.dist((poligono[3].x(), poligono[3].y()), (poligono[0].x(), poligono[0].y())) / max(recorte.height(), 1e-6),
            1e-6,
        )
        margem = min(1.5 / px_tela_por_px_arte, recorte.width() / 2, recorte.height() / 2)
        face = QRectF(px(painel.x1, painel.y1), px(painel.x2, painel.y2)).normalized()
        recorte = recorte.adjusted(-margem, -margem, margem, margem).intersected(face)
        # Quad de origem na MESMA ordem dos cantos da tela.
        quad = QPolygonF([px(xa, ya), px(xb, ya), px(xb, yb), px(xa, yb)])
        return imagem, recorte, quad

    def _desenhar_sombra(self, p: QPainter, para_camera, para_tela, escala: float) -> None:
        """Sombra suave no chão, embaixo da caixa — some junto com a montagem."""
        u = _suavizar(self._progresso)
        if u <= 0.01:
            return
        cima = normalizar(self._modelo.cima)
        meia_altura = self._raio_montado * 0.6
        chao = tuple(self._centro_montado[i] - cima[i] * meia_altura for i in range(3))
        pc = para_camera(chao)
        if pc[2] <= 1.0:
            return
        centro = para_tela(pc)
        rx = escala * self._raio_montado * 1.1 / pc[2]
        gradiente = QRadialGradient(QPointF(0.0, 0.0), 1.0)
        gradiente.setColorAt(0.0, QColor(0, 0, 0, int(70 * u)))
        gradiente.setColorAt(0.6, QColor(0, 0, 0, int(28 * u)))
        gradiente.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.save()
        p.translate(centro)
        p.scale(rx, rx * 0.32)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gradiente)
        p.drawEllipse(QPointF(0.0, 0.0), 1.0, 1.0)
        p.restore()

    def _desenhar_dobradicas(self, p: QPainter) -> None:
        """Modo "Ângulo da dobra": cada vinco destacado com o ângulo atual."""
        fonte = QFont(FONTE_MONO)
        fonte.setPointSizeF(8.5)
        p.setFont(fonte)
        for a, b, linha, angulo in self._dobradicas_tela:
            destacada = linha == self._dobra_destacada
            caneta = QPen(QColor(0, 150, 220) if not destacada else QColor(230, 90, 20), 3.0 if destacada else 2.0)
            caneta.setCosmetic(True)
            p.setPen(caneta)
            p.drawLine(a, b)
            meio = (a + b) / 2
            texto = f"{angulo:g}°"
            caixa = QRectF(meio.x() - 20, meio.y() - 9, 40, 18)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawRoundedRect(caixa, 4, 4)
            p.setPen(QColor(40, 40, 40))
            p.drawText(caixa, Qt.AlignmentFlag.AlignCenter, texto)

    def _clique(self, ponto: QPointF) -> None:
        if self._modo == "dobra":
            melhor, menor = None, 10.0
            for a, b, linha, _angulo in self._dobradicas_tela:
                d = _distancia_tela(ponto, a, b)
                if d < menor:
                    melhor, menor = linha, d
            if melhor is not None:
                self.dobra_clicada.emit(melhor)
        elif self._modo == "base":
            # A face da frente (menor profundidade) sob o cursor.
            for _prof, poligono, painel_id in sorted(self._faces_tela, key=lambda item: item[0]):
                if poligono.containsPoint(ponto, Qt.FillRule.OddEvenFill):
                    self.face_clicada.emit(painel_id)
                    return

    def _desenhar_legenda(self, p: QPainter) -> None:
        fonte = QFont(FONTE_MONO)
        fonte.setPointSizeF(9.0)
        p.setFont(fonte)
        p.setPen(_COR_TEXTO_FUNDO)
        margem = 12
        texto = self._modelo.descricao
        if self._medidas_texto:
            texto += f"  ·  {self._medidas_texto}"
        p.drawText(margem, margem + 10, texto)
        p.drawText(
            margem,
            self.height() - margem,
            "Arraste para girar  ·  botão do meio, direito ou Shift + arrastar move  ·  roda aproxima onde está o mouse  ·  duplo clique volta à vista inicial",
        )

    def _faixas_de_espessura(self, pp, para_camera, para_tela, direita, cima, olhar, caixa_fechada, vies_camada, pedacos) -> None:
        vies_faixa = 0.06 * self._raio_montado
        """A borda cortada do papelão: uma faixa de E mm em cada aresta do
        contorno (e dos furos), dividida em trechos pra ordenar direito."""
        painel = pp.painel
        e = self._espessura
        ondas = miolo_do_papelao(e)
        if painel.poligono:
            aneis = [list(painel.poligono)] + [list(f) for f in painel.furos]
        else:
            aneis = [[(painel.x1, painel.y1), (painel.x2, painel.y1), (painel.x2, painel.y2), (painel.x1, painel.y2)]]
        maior = max(abs(painel.x2 - painel.x1), abs(painel.y2 - painel.y1), 1e-6)
        for anel in aneis:
            for (ax, ay), (bx, by) in zip(anel, anel[1:] + anel[:1]):
                comprimento = math.hypot(bx - ax, by - ay)
                if comprimento < 1e-6:
                    continue
                trechos = max(1, round(_SUBDIVISOES * comprimento / maior))
                # As ondas correm na direção Y da faca (na vertical das
                # paredes, como numa caixa de verdade): corte atravessado a
                # elas (borda mais em X) mostra a ondulação; corte paralelo,
                # só as capas.
                atravessado = abs(bx - ax) >= abs(by - ay)
                for k in range(trechos):
                    u0, u1 = k / trechos, (k + 1) / trechos
                    p0 = (ax + (bx - ax) * u0, ay + (by - ay) * u0)
                    p1 = (ax + (bx - ax) * u1, ay + (by - ay) * u1)
                    mundo = [
                        pp.transformacao.aplicar((p0[0], p0[1], 0.0)),
                        pp.transformacao.aplicar((p1[0], p1[1], 0.0)),
                        pp.transformacao.aplicar((p1[0], p1[1], e)),
                        pp.transformacao.aplicar((p0[0], p0[1], e)),
                    ]
                    cam = [para_camera(m) for m in mundo]
                    if min(c[2] for c in cam) <= 1.0:
                        continue
                    centro = tuple(sum(c[i] for c in cam) / 4.0 for i in range(3))
                    lado_a = tuple(cam[1][i] - cam[0][i] for i in range(3))
                    lado_b = tuple(cam[3][i] - cam[0][i] for i in range(3))
                    normal = normalizar(produto_vetorial(lado_a, lado_b))
                    if produto_escalar(normal, centro) > 0:
                        normal = tuple(-c for c in normal)  # a faixa vista é a que olha pra câmera
                    luz = 0.5 + 0.5 * max(0.0, produto_escalar(normal, _LUZ))
                    cor = QColor.fromRgbF(
                        min(1.0, _COR_ESPESSURA.redF() * luz),
                        min(1.0, _COR_ESPESSURA.greenF() * luz),
                        min(1.0, _COR_ESPESSURA.blueF() * luz),
                    )
                    tela = [para_tela(c) for c in cam]
                    # Um pouco atrás na ordem: a faixa é estreita e o centro dela
                    # "ganhava" da célula de face que a cobre (bordas de trás
                    # vazando na lateral da caixa fechada). Na borda aberta
                    # (tampa de bandeja, aba) nada a cobre e ela continua visível.
                    profundidade = (
                        math.sqrt(produto_escalar(centro, centro)) + painel.camada * vies_camada + vies_faixa
                    )
                    poligono = QPolygonF(tela)
                    # Miolo: posição ao longo da borda (mm, pra onda seguir
                    # sem emenda de um trecho pro outro) e o tipo do corte.
                    miolo = (comprimento * u0, comprimento * u1, e, ondas, atravessado)
                    pedacos.append((profundidade, poligono, cor, [(tela[0], tela[1]), (tela[3], tela[2])], None, poligono, miolo))

    def _desenhar_miolo(self, p: QPainter, quad_tela: QPolygonF, miolo, cor_faixa: QColor | None = None) -> None:
        """As camadas do papelão dentro da faixa da borda: capas e, no corte
        atravessado às ondas, a ondulação (uma na onda simples, duas com a
        capa do meio na onda dupla). Desenhado num quadrado unitário (u ao
        longo da borda, w de fora pra dentro) projetado na faixa."""
        s0, s1, espessura, ondas, atravessado = miolo
        lado_borda = QLineF(quad_tela.at(0), quad_tela.at(1)).length()
        lado_espessura = QLineF(quad_tela.at(0), quad_tela.at(3)).length()
        if lado_espessura < 4.0 or espessura <= 0:
            return  # longe demais pra enxergar camada
        quadrado = QPolygonF([QPointF(0, 0), QPointF(1, 0), QPointF(1, 1), QPointF(0, 1)])
        transformacao = QTransform()
        if not QTransform.quadToQuad(quadrado, quad_tela, transformacao):
            return
        capa = min(0.2, _CAPA_MM / espessura)
        # Cores tiradas da própria faixa (já com a luz daquela face): o vão
        # entre as ondas escuro, capas e onda (papel) claras — senão, numa
        # face mais escura, a onda sumia na cor da faixa.
        base = cor_faixa or _COR_ESPESSURA
        cor_vao, cor_papel = base.darker(150), base.lighter(140)
        p.save()
        p.setTransform(transformacao)
        p.setPen(Qt.PenStyle.NoPen)
        if ondas:
            p.setBrush(cor_vao)
            p.drawRect(QRectF(0, capa, 1, 1 - 2 * capa))
        # Capas: por fora, por dentro e (onda dupla) a do meio.
        p.setBrush(cor_papel)
        p.drawRect(QRectF(0, 0, 1, capa))
        p.drawRect(QRectF(0, 1 - capa, 1, capa))
        if len(ondas) == 2:
            p.drawRect(QRectF(0, 0.5 - capa / 2, 1, capa))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if ondas and atravessado:
            faixas = [(capa, 1.0 - capa)] if len(ondas) == 1 else [(capa, 0.5 - capa / 2), (0.5 + capa / 2, 1.0 - capa)]
            comprimento = max(s1 - s0, 1e-6)
            caneta_onda = QPen(cor_papel, 1.8)
            caneta_onda.setCosmetic(True)
            p.setPen(caneta_onda)
            for (w0, w1), passo in zip(faixas, ondas):
                n_ondas = comprimento / passo
                if lado_borda / max(n_ondas, 1e-6) < 5.0:
                    continue  # onda mais fina que ~5 px: vira borrão
                meio, amplitude = (w0 + w1) / 2, (w1 - w0) / 2 * 0.92
                amostras = max(8, min(240, int(n_ondas * 10)))
                caminho = QPainterPath()
                for i in range(amostras + 1):
                    u = i / amostras
                    w = meio + amplitude * math.sin(2 * math.pi * (s0 + u * comprimento) / passo)
                    if i == 0:
                        caminho.moveTo(u, w)
                    else:
                        caminho.lineTo(u, w)
                p.drawPath(caminho)
        p.restore()

    # ── Mouse ────────────────────────────────────────────────────────
    def _quer_mover(self, evento) -> bool:
        return evento.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton) or (
            evento.button() == Qt.MouseButton.LeftButton and bool(evento.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        )

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if self._quer_mover(evento):
            self._arrasto_pan = (evento.position(), QPointF(self._pan))
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            return
        if evento.button() == Qt.MouseButton.LeftButton:
            self._ponto_clique = evento.position()
            self._arrasto = (evento.position(), self._yaw_usuario, self._pitch_usuario)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._atualizar_timer_giro()

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if self._arrasto_pan is not None:
            inicio, pan0 = self._arrasto_pan
            self._pan = pan0 + (evento.position() - inicio)
            self.update()
            return
        if self._arrasto is None:
            return
        inicio, yaw0, pitch0 = self._arrasto
        delta = evento.position() - inicio
        self._yaw_usuario = yaw0 - delta.x() * 0.4
        self._pitch_usuario = max(-180.0, min(180.0, pitch0 + delta.y() * 0.4))
        self.update()

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        if self._arrasto_pan is not None:
            self._arrasto_pan = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        inicio = getattr(self, "_ponto_clique", None)
        if self._modo != "girar" and inicio is not None and (evento.position() - inicio).manhattanLength() < 4:
            # Clique sem arrastar: escolhe vinco/face; arrastar continua girando.
            self._yaw_usuario, self._pitch_usuario = self._arrasto[1], self._arrasto[2]
            self._clique(evento.position())
        self._ponto_clique = None
        self._arrasto = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._atualizar_timer_giro()

    def mouseDoubleClickEvent(self, evento) -> None:  # noqa: N802
        if self._modo != "girar":
            # O 2º clique do duplo clique não passa pelo press/release: conta
            # como mais um clique (alternar o ângulo de novo, como no ArtiosCAD).
            self._clique(evento.position())
            return
        self.vista_inicial()

    def wheelEvent(self, evento) -> None:  # noqa: N802
        passos = evento.angleDelta().y() / 120.0
        novo = max(0.4, min(40.0, self._zoom * (1.12**passos)))
        fator = novo / self._zoom
        # Aproxima onde está o mouse (como no CorelDRAW/Figma): o ponto sob
        # o cursor fica sob o cursor.
        cursor = evento.position() - QPointF(self.width() / 2.0, self.height() / 2.0)
        self._pan = cursor - (cursor - self._pan) * fator
        self._zoom = novo
        self.update()


def _distancia_tela(p: QPointF, a: QPointF, b: QPointF) -> float:
    ab = b - a
    c2 = ab.x() ** 2 + ab.y() ** 2
    if c2 < 1e-9:
        return math.hypot(p.x() - a.x(), p.y() - a.y())
    t = max(0.0, min(1.0, ((p.x() - a.x()) * ab.x() + (p.y() - a.y()) * ab.y()) / c2))
    q = a + ab * t
    return math.hypot(p.x() - q.x(), p.y() - q.y())


class Visualizacao3D(QWidget):
    """Viewport + barra de controles (Planificar/Montar e a régua de dobra)."""

    # Ângulo de um vinco mudou (índice da linha da faca, graus) — main_window
    # guarda e remonta o modelo. Face base escolhida: id do painel.
    angulo_alterado = Signal(int, float)
    face_base_escolhida = Signal(str)

    def salvar_imagem(self, caminho: str | None = None) -> str | None:
        """Pergunta onde salvar (se não vier o caminho) e grava a vista atual
        em alta resolução: JPG com fundo branco, PNG com fundo transparente."""
        if caminho is None:
            caminho, _filtro = QFileDialog.getSaveFileName(
                self, "Salvar imagem do 3D", "caixa-3d.jpg", "JPG (*.jpg *.jpeg);;PNG com fundo transparente (*.png)"
            )
            if not caminho:
                return None
        png = caminho.lower().endswith(".png")
        if not png and not caminho.lower().endswith((".jpg", ".jpeg")):
            caminho += ".jpg"
        # ~4000 px de largura na tela inteira (no mínimo o triplo): depois do
        # recorte em volta da caixa a foto ainda fica grande e nítida.
        escala = max(3.0, 4000.0 / max(1, self.vista.width()))
        imagem = self.vista.renderizar_imagem(escala, None if png else QColor(255, 255, 255))
        if not png:
            imagem = imagem.convertToFormat(QImage.Format.Format_RGB32)
        if not imagem.save(caminho, "PNG" if png else "JPG", -1 if png else 95):
            QMessageBox.critical(self, "Salvar imagem", f"Não consegui salvar em:\n{caminho}")
            return None
        return caminho

    def definir_espessura(self, mm: float) -> None:
        """Espessura do papelão do 3D: a lista mostra o papelão com essa
        espessura (E = 3 mm vira "Onda B"), ou "Personalizado"."""
        self.campo_espessura.setValue(float(mm))  # dispara _ao_digitar_espessura
        self._ao_digitar_espessura(self.campo_espessura.value())

    def _ao_escolher_papelao(self, indice: int) -> None:
        mm = self.combo_papelao.itemData(indice)
        if mm is None:  # "Personalizado": o valor é o do campo
            self.campo_espessura.setFocus()
            self.campo_espessura.selectAll()
            return
        self.definir_espessura(mm)

    def _ao_digitar_espessura(self, mm: float) -> None:
        self.vista.definir_espessura(mm)
        configuracoes.definir_espessura_papelao_mm(mm)
        indice = next(
            (i for i in range(self.combo_papelao.count()) if self.combo_papelao.itemData(i) is not None
             and abs(self.combo_papelao.itemData(i) - mm) < 1e-6),
            self.combo_papelao.count() - 1,
        )
        self.combo_papelao.blockSignals(True)
        self.combo_papelao.setCurrentIndex(indice)
        self.combo_papelao.blockSignals(False)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vista = VistaCaixa3D()
        self.vista.dobra_clicada.connect(self._ao_clicar_dobra)
        self.vista.face_clicada.connect(self.face_base_escolhida.emit)
        self._angulos_atuais: dict[int, float] = {}

        # Ferramentas do 3D no estilo ArtiosCAD (só na faca editada/livre).
        self._modos = QButtonGroup(self)
        self._botoes_modo: dict[str, QPushButton] = {}
        for chave, rotulo, dica in (
            ("girar", "Girar", "Arrastar gira a vista"),
            ("dobra", "Ângulo da dobra", "Clique num vinco: 90° → −90° → 0° (o campo ao lado define o valor exato)"),
            ("base", "Face base", "Clique numa face pra ela ficar parada e as outras dobrarem em volta"),
        ):
            botao = QPushButton(rotulo)
            botao.setCheckable(True)
            botao.setToolTip(dica)
            botao.clicked.connect(lambda _c=False, m=chave: self.vista.definir_modo(m))
            self._modos.addButton(botao)
            self._botoes_modo[chave] = botao
        self._botoes_modo["girar"].setChecked(True)
        self.campo_angulo = QDoubleSpinBox()
        self.campo_angulo.setRange(-180.0, 180.0)
        self.campo_angulo.setDecimals(1)
        self.campo_angulo.setSuffix(" °")
        self.campo_angulo.setKeyboardTracking(False)
        self.campo_angulo.setToolTip("Ângulo do vinco escolhido")
        self.campo_angulo.setEnabled(False)
        self.campo_angulo.valueChanged.connect(self._ao_digitar_angulo)
        self._dobra_escolhida: int | None = None

        self.botao_alternar = QPushButton("Planificar")
        self.botao_alternar.setProperty("primario", True)
        self.botao_alternar.setToolTip("Abre a caixa até virar a faca plana, ou dobra de volta")
        self.botao_alternar.clicked.connect(self._alternar)

        self.regua_dobra = QSlider(Qt.Orientation.Horizontal)
        self.regua_dobra.setRange(0, 1000)
        self.regua_dobra.setValue(1000)
        self.regua_dobra.setToolTip("Quanto a caixa está dobrada: 0% = plana (dieline), 100% = montada")
        self.regua_dobra.valueChanged.connect(self._ao_mover_regua)

        self.rotulo_dobra = QLabel("100%")
        self.rotulo_dobra.setObjectName("rotuloTecnico")
        self.rotulo_dobra.setMinimumWidth(44)

        botao_vista = QPushButton("Vista inicial")
        botao_vista.clicked.connect(self.vista.vista_inicial)
        self.botao_foto = QPushButton("Salvar imagem…")
        self.botao_foto.setToolTip("Salva a vista 3D como está agora (JPG, ou PNG com fundo transparente) pra mandar pro cliente")
        self.botao_foto.clicked.connect(lambda _marcado=False: self.salvar_imagem())
        self.botao_girar = QPushButton("Girar sozinho")
        self.botao_girar.setCheckable(True)
        self.botao_girar.setChecked(self.vista.girar_sozinho)
        self.botao_girar.setToolTip("A caixa montada fica girando devagar (gasta processador enquanto a aba 3D está aberta)")
        self.botao_girar.toggled.connect(self.vista.definir_girar_sozinho)

        rotulo_plana = QLabel("Plana")
        rotulo_montada = QLabel("Montada")
        for rotulo in (rotulo_plana, rotulo_montada):
            rotulo.setStyleSheet(f"color: {Cor.TEXTO_SECUNDARIO};")

        barra = QHBoxLayout()
        barra.setContentsMargins(12, 8, 0, 0)
        barra.setSpacing(10)
        barra.addWidget(self.botao_alternar)
        barra.addSpacing(8)
        barra.addWidget(rotulo_plana)
        barra.addWidget(self.regua_dobra, 1)
        barra.addWidget(rotulo_montada)
        barra.addWidget(self.rotulo_dobra)
        barra.addSpacing(8)
        barra.addWidget(self.botao_foto)
        barra.addWidget(self.botao_girar)
        barra.addWidget(botao_vista)

        ferramentas = QHBoxLayout()
        ferramentas.setContentsMargins(12, 6, 0, 0)
        ferramentas.setSpacing(6)
        for chave in ("girar", "dobra", "base"):
            ferramentas.addWidget(self._botoes_modo[chave])
        ferramentas.addWidget(self.campo_angulo)
        ferramentas.addSpacing(12)
        ferramentas.addWidget(QLabel("Papelão:"))
        self.combo_papelao = QComboBox()
        self.combo_papelao.setToolTip("Papelões comuns — ou digite a espessura exata no campo ao lado")
        for nome, mm in PAPELOES:
            self.combo_papelao.addItem(nome, mm)
        self.combo_papelao.addItem("Personalizado", None)
        self.combo_papelao.activated.connect(self._ao_escolher_papelao)
        ferramentas.addWidget(self.combo_papelao)
        # Espessura exata: digitada aqui (qualquer valor), ou vem da lista.
        self.campo_espessura = QDoubleSpinBox()
        self.campo_espessura.setRange(0.0, 30.0)
        self.campo_espessura.setDecimals(2)
        self.campo_espessura.setSingleStep(0.05)
        self.campo_espessura.setSuffix(" mm")
        self.campo_espessura.setKeyboardTracking(False)
        self.campo_espessura.setToolTip("Espessura do papelão no 3D (0 = folha fina). Fica guardada pra próxima vez.")
        self.campo_espessura.valueChanged.connect(self._ao_digitar_espessura)
        ferramentas.addWidget(self.campo_espessura)
        self.aviso_dobras = QLabel("Ângulo por vinco e face base: na faca editada à mão ou em branco.")
        self.aviso_dobras.setStyleSheet(f"color: {Cor.TEXTO_SECUNDARIO};")
        # O aviso é longo: pode encolher (e cortar) em vez de forçar a janela
        # inteira a ficar larga numa tela pequena.
        self.aviso_dobras.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.aviso_dobras.setToolTip(self.aviso_dobras.text())
        ferramentas.addWidget(self.aviso_dobras)
        ferramentas.addStretch(1)

        # A última espessura usada volta ao abrir o app.
        self.definir_espessura(configuracoes.espessura_papelao_mm())

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 6, 0, 0)
        vbox.setSpacing(0)
        vbox.addLayout(ferramentas)
        vbox.addWidget(self.vista, 1)
        vbox.addLayout(barra)

        self._animacao = QVariantAnimation(self)
        self._animacao.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animacao.valueChanged.connect(lambda v: self._aplicar_progresso(float(v)))
        self._animacao.finished.connect(self._atualizar_textos)
        self._alvo = 1.0

    def definir_modelo(self, modelo: ModeloCaixa3D, medidas_texto: str = "") -> None:
        self.vista.definir_modelo(modelo, medidas_texto)
        editavel = self.vista.tem_dobras_editaveis
        for chave in ("dobra", "base"):
            self._botoes_modo[chave].setEnabled(editavel)
        self.aviso_dobras.setVisible(not editavel)
        if not editavel:
            self._botoes_modo["girar"].setChecked(True)
            self.vista.definir_modo("girar")
        self._angulos_atuais = {p.linha_origem: p.angulo_fechado for p in modelo.paineis if p.linha_origem is not None}
        if self._dobra_escolhida not in self._angulos_atuais:
            self._dobra_escolhida = None
            self.campo_angulo.setEnabled(False)
        else:
            self._mostrar_angulo(self._dobra_escolhida)

    def _mostrar_angulo(self, linha: int) -> None:
        self.campo_angulo.blockSignals(True)
        self.campo_angulo.setValue(self._angulos_atuais.get(linha, 90.0))
        self.campo_angulo.blockSignals(False)
        self.campo_angulo.setEnabled(True)
        self.vista.destacar_dobra(linha)

    def _ao_clicar_dobra(self, linha: int) -> None:
        atual = self._angulos_atuais.get(linha, 90.0)
        proximo = {90.0: -90.0, -90.0: 0.0}.get(round(atual, 1), 90.0)
        self._dobra_escolhida = linha
        self.angulo_alterado.emit(linha, proximo)

    def _ao_digitar_angulo(self, valor: float) -> None:
        if self._dobra_escolhida is not None:
            self.angulo_alterado.emit(self._dobra_escolhida, valor)
        habilitado = not modelo.vazio
        self.botao_alternar.setEnabled(habilitado)
        self.regua_dobra.setEnabled(habilitado)

    def definir_fonte_arte(self, fonte) -> None:
        self.vista.definir_fonte_arte(fonte)

    def enquadrar(self) -> None:
        self.vista.vista_inicial()

    def _alternar(self) -> None:
        atual = self.vista.progresso()
        # Durante a animação, o clique inverte o sentido a partir de onde está.
        indo_para_montada = self._alvo < 0.5 if self._animacao.state() == QVariantAnimation.State.Running else atual < 0.5
        self._alvo = 1.0 if indo_para_montada else 0.0
        self._animacao.stop()
        self._animacao.setStartValue(atual)
        self._animacao.setEndValue(self._alvo)
        duracao = _DURACAO_MONTAR_MS if self._alvo == 1.0 else _DURACAO_PLANIFICAR_MS
        self._animacao.setDuration(max(200, int(duracao * abs(self._alvo - atual))))
        self.botao_alternar.setText("Planificar" if self._alvo == 1.0 else "Montar")
        self._animacao.start()

    def _ao_mover_regua(self, valor: int) -> None:
        # Só o usuário dispara isto — a animação move a régua com os
        # sinais bloqueados (ver `_aplicar_progresso`).
        self._animacao.stop()
        self.vista.definir_progresso(valor / 1000.0)
        self._alvo = self.vista.progresso()
        self._atualizar_textos()

    def _aplicar_progresso(self, valor: float) -> None:
        self.vista.definir_progresso(valor)
        self.regua_dobra.blockSignals(True)
        self.regua_dobra.setValue(round(valor * 1000))
        self.regua_dobra.blockSignals(False)
        self._atualizar_rotulo(valor)

    def _atualizar_textos(self) -> None:
        valor = self.vista.progresso()
        self._atualizar_rotulo(valor)
        self.botao_alternar.setText("Montar" if valor < 0.5 else "Planificar")

    def _atualizar_rotulo(self, valor: float) -> None:
        # As pontas da régua já dizem "Plana"/"Montada" — aqui só o número.
        self.rotulo_dobra.setText(f"{valor * 100:.0f}%")
