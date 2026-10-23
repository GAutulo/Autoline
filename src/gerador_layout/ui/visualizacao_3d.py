"""Tela 3D: a caixa montada a partir da mesma dieline, com animação de
planificar (abrir até virar a faca plana) e montar (dobrar de volta).

Renderização feita à mão com QPainter — projeção em perspectiva e
pintura por profundidade (painter's algorithm) — em vez de OpenGL/Qt3D/
WebEngine: são poucas dezenas de faces planas, cabe folgado em Python
puro, e não traz nenhuma dependência nova pro empacotamento (PyInstaller).

A ordem de pintura vem de uma árvore BSP (`bsp3d.py`) com todas as
superfícies — lado impresso, lado de dentro e borda cortada do papelão de
cada painel: exata mesmo com aba colada por dentro da parede, abas
sobrepostas e quinas (a pintura por distância do centro errava ali). Cada
superfície é UM polígono (cortado em pedaços só onde cruza outra), então a
arte de uma face é desenhada uma vez, com uma transformação projetiva só.

A arte do Layout (texto, formas, logotipo) entra como textura: uma imagem
POR FACE, renderizada da própria cena do canvas sem a faca
(`renderizar_arte_regioes`), na densidade que aquela face ocupa na tela
agora (com folga). Aproximar a câmera faz a face ser redesenhada mais
nítida — antes era uma imagem só da chapa inteira, limitada a ~2,4 px/mm,
e texto/logo saíam borrados e serrilhados. Cada pedaço da face externa
é desenhada inteira via `QTransform.quadToQuad` — projetivo exato pra
uma face plana — recortada no pedaço visível. A arte vai sem luz/sombra por cima, pra manter as cores
originais da marca.

A geometria (quais painéis existem, onde fica cada vinco, em que ordem
cada aba dobra) mora em `dobra3d.py`, sem nada de UI.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QEasingCurve, QLineF, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient, QRegion, QTransform
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
from .bsp3d import Poligono as Poligono3D
from .bsp3d import construir as construir_bsp
from .bsp3d import de_tras_pra_frente
from .estilo import FONTE_MONO, Cor

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
_ARTE_PX_POR_MM_MAX = 128.0  # só a textura de detalhe (pedaço visível) chega perto disso
_ARTE_LADO_MAX_PX = 6000
_ARTE_MARGEM_MM = 1.0
# De perto, a face inteira não cabe na resolução que a tela pede (lado máximo
# em pixels): ganha uma 2ª textura, de DETALHE, só do pedaço visível (com
# esta folga em volta, pra um pequeno arrasto não pedir outra).
_DETALHE_FOLGA = 0.25


def _escala_local(t: QTransform, ponto: QPointF) -> float:
    """Pixels de tela por mm da chapa neste ponto (a perspectiva amplia a
    parte da face mais perto da câmera: a média da face subestima)."""
    a = t.map(ponto)
    return max(
        QLineF(a, t.map(QPointF(ponto.x() + 1.0, ponto.y()))).length(),
        QLineF(a, t.map(QPointF(ponto.x(), ponto.y() + 1.0))).length(),
    )

# Vista "3/4" da caixa montada (graus, relativos a `cima`/`frente` do modelo).
_YAW_MONTADA = -42.0  # mostra bem a lateral, não só a frente
_PITCH_MONTADA = 24.0

# Papelão: a cor do lado impresso vem das Configurações (a do papelão da
# fábrica); o lado de dentro sai mais claro e a borda cortada (o miolo
# ondulado) mais escura, na mesma proporção de sempre.
_COR_ARESTA = QColor(74, 54, 30, 210)


def cores_papelao() -> tuple[QColor, QColor, QColor]:
    """(lado de fora, lado de dentro, borda cortada)."""
    externa = QColor(configuracoes.cor_papelao_3d())
    return externa, externa.lighter(116), externa.darker(128)

# Papelões comuns (espessura em mm), como na escolha de papelão do ArtiosCAD.
# Primeiro os da escala 1:10 (a caixa desenhada em 1:10, como 605 mm → 60,5
# mm — o normal aqui); depois, separados, os de tamanho real.
PAPELOES_1_10 = (
    ("Fino (sem espessura)", 0.0),
    ("Onda B — escala 1:10 (0,3 mm)", 0.3),
    ("Onda dupla BC — escala 1:10 (0,7 mm)", 0.7),
    ("Micro-ondulado E — escala 1:10 (0,15 mm)", 0.15),
)
PAPELOES_TAMANHO_REAL = (
    ("Onda B — tamanho real (3 mm)", 3.0),
    ("Onda C — tamanho real (4 mm)", 4.0),
    ("Onda dupla BC — tamanho real (7 mm)", 7.0),
    ("Micro-ondulado E — tamanho real (1,5 mm)", 1.5),
    ("Cartão — tamanho real (0,5 mm)", 0.5),
)
PAPELOES = PAPELOES_1_10 + PAPELOES_TAMANHO_REAL

# Miolo do papelão visto na borda cortada: passo (mm) de cada ondulação, de
# fora pra dentro. Vazio = sem onda (folha ou cartão maciço).
_MIOLO_POR_ESPESSURA = {
    0.3: (0.65,),  # onda B em 1:10
    0.7: (0.65, 0.8),  # onda BC em 1:10
    0.15: (0.35,),  # E em 1:10
    0.5: (),
    1.5: (3.5,),  # E
    3.0: (6.5,),  # B
    4.0: (8.0,),  # C
    7.0: (6.5, 8.0),  # BC: onda B por fora, C por dentro
}
_CAPA_FRACAO = 0.08  # cada capa (liner) ≈ 0,25 mm de 3 mm, em qualquer escala


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


_PERTO = 1.0  # mm na frente do olho: o que vem antes disso é cortado


class _Superficie:
    """Uma superfície desenhável: o lado de fora ou de dentro de um painel
    (``face``) ou um trecho da borda cortada do papelão (``borda``)."""

    __slots__ = ("tipo", "pp", "externo", "normal", "quad_mundo", "quad_local", "contorno_local", "miolo")
    # contorno_local: [(QLineF na chapa, é_vinco)] — corte e vinco desenhados diferente

    def __init__(self, tipo, pp, externo, normal, quad_mundo, quad_local=None, contorno_local=None, miolo=None):
        self.tipo, self.pp, self.externo, self.normal = tipo, pp, externo, normal
        self.quad_mundo, self.quad_local, self.contorno_local, self.miolo = quad_mundo, quad_local, contorno_local, miolo


def _contorno_do_painel(painel, dobradicas) -> list[tuple[QLineF, bool]]:
    """A borda do painel (contorno e furos) na chapa, em trechos marcados
    como vinco (sobre a dobradiça de algum painel) ou corte (o resto) — no
    3D, sobretudo planificado, o corte precisa aparecer diferente do vinco."""
    trechos: list[tuple[QLineF, bool]] = []
    for anel in (painel.cantos, *painel.furos):
        n = len(anel)
        for k in range(n):
            (ax, ay), (bx, by) = anel[k], anel[(k + 1) % n]
            dx, dy = bx - ax, by - ay
            comprimento2 = dx * dx + dy * dy
            if comprimento2 < 1e-12:
                continue
            comprimento = math.sqrt(comprimento2)
            cobertos = []
            for (px, py), (qx, qy) in dobradicas:
                # dobradiça na mesma reta da aresta?
                if abs((px - ax) * dy - (py - ay) * dx) / comprimento > 1e-3:
                    continue
                if abs((qx - ax) * dy - (qy - ay) * dx) / comprimento > 1e-3:
                    continue
                t0 = ((px - ax) * dx + (py - ay) * dy) / comprimento2
                t1 = ((qx - ax) * dx + (qy - ay) * dy) / comprimento2
                t0, t1 = max(0.0, min(t0, t1)), min(1.0, max(t0, t1))
                if t1 - t0 > 1e-6:
                    cobertos.append((t0, t1))
            cobertos.sort()
            t = 0.0
            for t0, t1 in cobertos:
                if t0 > t + 1e-9:
                    trechos.append((QLineF(ax + dx * t, ay + dy * t, ax + dx * t0, ay + dy * t0), False))
                if t1 > t:
                    trechos.append((QLineF(ax + dx * max(t, t0), ay + dy * max(t, t0), ax + dx * t1, ay + dy * t1), True))
                    t = t1
            if t < 1.0 - 1e-9:
                trechos.append((QLineF(ax + dx * t, ay + dy * t, bx, by), False))
    return trechos


def _superficies(posicionados, espessura: float, caixa_fechada: bool) -> list[Poligono3D]:
    """Os polígonos (no mundo) de tudo o que pode aparecer: o lado impresso
    de cada painel, o lado de dentro (E mm pra dentro) e a borda cortada do
    papelão. Caixa fechada é um sólido: só o lado de fora das faces de fora."""
    poligonos: list[Poligono3D] = []
    e = espessura
    ondas = miolo_do_papelao(e)
    dobradicas = [pp.painel.dobradica for pp in posicionados if pp.painel.dobradica is not None]
    for pp in posicionados:
        painel = pp.painel
        if caixa_fechada and painel.camada > 0:
            continue
        anel = list(painel.cantos)
        aplicar = pp.transformacao.aplicar
        n_ext = normalizar(pp.normal_externa)
        n_int = (-n_ext[0], -n_ext[1], -n_ext[2])
        x1, y1, x2, y2 = painel.x1, painel.y1, painel.x2, painel.y2
        quad_local = QPolygonF([QPointF(x1, y1), QPointF(x2, y1), QPointF(x2, y2), QPointF(x1, y2)])
        contorno = _contorno_do_painel(painel, dobradicas)
        for externo, z, normal in ((True, 0.0, n_ext), (False, e, n_int)):
            if caixa_fechada and not externo:
                continue
            quad_mundo = [aplicar((x1, y1, z)), aplicar((x2, y1, z)), aplicar((x2, y2, z)), aplicar((x1, y2, z))]
            sup = _Superficie("face", pp, externo, normal, quad_mundo, quad_local, contorno)
            # Mesmo plano (aba colada sem espessura): a de fora pinta por cima
            # vista de fora; vista de dentro, a de dentro.
            prioridade = -painel.camada if externo else painel.camada
            poligonos.append(Poligono3D([aplicar((x, y, z)) for x, y in anel], list(anel), sup, normal, prioridade))
        if e <= 0 or caixa_fechada:
            continue
        centro = aplicar((sum(x for x, _y in anel) / len(anel), sum(y for _x, y in anel) / len(anel), e / 2))
        aneis = [(anel, False)] + [(list(f), True) for f in painel.furos]
        for contorno_anel, furo in aneis:
            meio_furo = None
            if furo:
                meio_furo = aplicar((
                    sum(x for x, _y in contorno_anel) / len(contorno_anel),
                    sum(y for _x, y in contorno_anel) / len(contorno_anel),
                    e / 2,
                ))
            for (ax, ay), (bx, by) in zip(contorno_anel, contorno_anel[1:] + contorno_anel[:1]):
                comprimento = math.hypot(bx - ax, by - ay)
                if comprimento < 1e-6:
                    continue
                quad = [aplicar((ax, ay, 0.0)), aplicar((bx, by, 0.0)), aplicar((bx, by, e)), aplicar((ax, ay, e))]
                lado_a = tuple(quad[1][i] - quad[0][i] for i in range(3))
                lado_b = tuple(quad[3][i] - quad[0][i] for i in range(3))
                normal = normalizar(produto_vetorial(lado_a, lado_b))
                alvo = meio_furo if furo else centro  # borda olha pra fora do papelão
                para_dentro = tuple(alvo[i] - quad[0][i] for i in range(3))
                if (produto_escalar(normal, para_dentro) > 0) != furo:
                    normal = (-normal[0], -normal[1], -normal[2])
                # As ondas correm na direção Y da faca (vertical das paredes):
                # o corte atravessado a elas (borda mais em X) mostra a onda.
                atravessado = abs(bx - ax) >= abs(by - ay)
                sup = _Superficie("borda", pp, True, normal, quad, miolo=(0.0, comprimento, e, ondas, atravessado))
                locais = [(0.0, 0.0), (comprimento, 0.0), (comprimento, 1.0), (0.0, 1.0)]
                poligonos.append(Poligono3D(quad, locais, sup, normal, -painel.camada))
    return poligonos


def _recortar_perto(cam: list) -> list:
    """Recorta o polígono (coordenadas de câmera) no plano z = _PERTO."""
    if all(c[2] > _PERTO for c in cam):
        return cam
    saida = []
    n = len(cam)
    for i in range(n):
        a, b = cam[i], cam[(i + 1) % n]
        dentro_a, dentro_b = a[2] > _PERTO, b[2] > _PERTO
        if dentro_a:
            saida.append(a)
        if dentro_a != dentro_b:
            t = (_PERTO - a[2]) / (b[2] - a[2])
            saida.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
    return saida


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
        self._detalhes: dict[str, tuple[QImage | None, float, QRectF]] = {}
        self._detalhes_pendentes: dict[str, tuple[QRectF, float]] = {}
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
        self._cache_arvore = None  # (chave, posicionados, árvore BSP)
        self._versao_modelo = 0

    # ── API ──────────────────────────────────────────────────────────
    def definir_modelo(self, modelo: ModeloCaixa3D, medidas_texto: str = "") -> None:
        self._modelo = modelo
        self._versao_modelo += 1
        self._medidas_texto = medidas_texto
        if not modelo.vazio:
            plano = caixa_envolvente(posicionar(modelo, 0.0))
            montado = caixa_envolvente(posicionar(modelo, 1.0))
            self._centro_plano = _lerp_vetor(plano[0], plano[1], 0.5)
            self._centro_montado = _lerp_vetor(montado[0], montado[1], 0.5)
            self._raio_plano = max(math.dist(plano[0], plano[1]) / 2.0, 1.0)
            self._raio_montado = max(math.dist(montado[0], montado[1]) / 2.0, 1.0)
        self._texturas.clear()  # painéis mudaram de lugar/tamanho
        self._detalhes.clear()
        self.update()

    def definir_fonte_arte(self, fonte) -> None:
        """`fonte(pedidos: list[(QRectF mm, px/mm)]) -> list[QImage | None]`,
        ou None sem arte. Joga fora as texturas: a arte pode ter mudado."""
        self._fonte_arte = fonte
        self._texturas.clear()
        self._texturas_pendentes.clear()
        self._detalhes.clear()
        self._detalhes_pendentes.clear()
        self.update()

    def textura_do_painel(self, painel_id: str) -> tuple[QImage | None, float, QRectF] | None:
        return self._texturas.get(painel_id)

    def _gerar_texturas(self, pedidos: dict[str, tuple[QRectF, float]], destino: dict | None = None) -> None:
        if self._fonte_arte is None or not pedidos:
            return
        destino = self._texturas if destino is None else destino
        chaves = list(pedidos)
        imagens = self._fonte_arte([pedidos[c] for c in chaves])
        for chave, imagem in zip(chaves, imagens):
            retangulo, densidade = pedidos[chave]
            if imagem is not None:
                densidade = float(imagem.text("px_por_mm") or densidade)
            destino[chave] = (imagem, densidade, retangulo)

    def _gerar_texturas_pendentes(self) -> None:
        pendentes, self._texturas_pendentes = self._texturas_pendentes, {}
        self._gerar_texturas(pendentes)
        detalhes, self._detalhes_pendentes = self._detalhes_pendentes, {}
        self._gerar_texturas(detalhes, self._detalhes)
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
        pitch = math.radians(pitch_graus)  # sem trava: dá a volta e olha por baixo

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
            antes = {k for k, t in self._texturas.items() if t[0] is not None}
            imagem = self._pintar_em_imagem(escala, fundo)
            if {k for k, t in self._texturas.items() if t[0] is not None} != antes and not self._texturas_pendentes:
                # A pintura acabou de gerar a arte de alguma face (ela é feita
                # depois de pintar): a foto sai de novo, já com ela.
                imagem = self._pintar_em_imagem(escala, fundo)
            if self._texturas_pendentes or self._detalhes_pendentes:
                # A arte pediu resolução maior: gera agora e pinta de novo.
                pendentes, self._texturas_pendentes = self._texturas_pendentes, {}
                self._gerar_texturas(pendentes)
                detalhes, self._detalhes_pendentes = self._detalhes_pendentes, {}
                self._gerar_texturas(detalhes, self._detalhes)
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

        caixa_fechada = self._progresso >= 0.999 and self._modelo.solido_fechado
        posicionados, arvore = self._arvore(caixa_fechada)
        self._dobradicas_tela = []
        self._faces_tela = []
        for pp in posicionados:
            painel = pp.painel
            if painel.dobradica is not None and painel.linha_origem is not None:
                (ax, ay), (bx, by) = painel.dobradica
                ca, cb = para_camera(pp.ponto(ax, ay)), para_camera(pp.ponto(bx, by))
                if ca[2] > _PERTO and cb[2] > _PERTO:
                    self._dobradicas_tela.append((para_tela(ca), para_tela(cb), painel.linha_origem, painel.angulo_fechado))

        com_arte = self._fonte_arte is not None
        densidade_necessaria: dict[str, float] = {}
        retangulo_painel: dict[str, QRectF] = {}
        visivel_painel: dict[str, QRectF] = {}  # parte da face na tela, em mm da chapa
        razao_pixels = foto["escala"] if foto else self.devicePixelRatioF()
        caneta_aresta = QPen(_COR_ARESTA, 1.2)
        caneta_aresta.setCosmetic(True)
        # Corte: linha cheia e mais escura. Vinco: tracejado enquanto a caixa
        # está aberta (como na dieline); montada, só um traço leve na dobra.
        caneta_corte = QPen(QColor(40, 26, 10), 1.6)
        caneta_corte.setCosmetic(True)
        if self._progresso < 0.5:
            caneta_vinco = QPen(QColor(74, 54, 30, 200), 1.1, Qt.PenStyle.DashLine)
        else:
            caneta_vinco = QPen(QColor(74, 54, 30, 120), 1.0)
        caneta_vinco.setCosmetic(True)
        info: dict[int, dict] = {}  # por superfície, neste quadro
        cor_externa, cor_interna, cor_espessura = cores_papelao()
        caixa_tela = QRectF()
        ordem = de_tras_pra_frente(arvore, olho, [])
        area_visivel = QRectF(0.0, 0.0, self.width(), self.height()).adjusted(-4, -4, 4, 4)

        def projetar_quad(mundo) -> QPolygonF | None:
            cam = [para_camera(q) for q in mundo]
            if min(c[2] for c in cam) <= _PERTO:
                return None
            return QPolygonF([para_tela(c) for c in cam])

        # 1ª passada, da frente pra trás: projeta e descarta o que está fora da
        # tela ou inteiro atrás do que já cobre (com zoom, quase tudo atrás da
        # face da frente) — pintar é o que custa.
        cobertura = QRegion()
        a_pintar = []
        for indice in range(len(ordem) - 1, -1, -1):
            poligono = ordem[indice]
            cam = _recortar_perto([para_camera(q) for q in poligono.pontos])
            if len(cam) < 3:
                continue
            tela = QPolygonF([para_tela(c) for c in cam])
            limites = tela.boundingRect()
            caixa_tela = caixa_tela.united(limites)
            sup = poligono.superficie
            if sup.tipo == "face":
                self._faces_tela.append((-indice, tela, sup.pp.painel.id))
            if not limites.intersects(area_visivel):
                continue  # fora da tela
            regiao = QRegion(tela.toPolygon())
            if not cobertura.isEmpty() and regiao.subtracted(cobertura).isEmpty():
                continue  # escondido atrás do que já foi visto
            if not (sup.tipo == "face" and sup.pp.painel.furos):
                cobertura = cobertura.united(regiao)
            a_pintar.append((indice, poligono, cam, tela))

        for indice, poligono, cam, tela in reversed(a_pintar):
            sup = poligono.superficie
            pp, painel = sup.pp, sup.pp.painel
            dados = info.get(id(sup))
            if dados is None:
                normal_cam = (
                    produto_escalar(sup.normal, direita),
                    produto_escalar(sup.normal, cima),
                    produto_escalar(sup.normal, olhar),
                )
                if sup.tipo == "face":
                    luz = 0.55 + 0.45 * max(0.0, produto_escalar(normal_cam, _LUZ))
                    base = cor_externa if sup.externo else cor_interna
                else:
                    luz = 0.5 + 0.5 * max(0.0, produto_escalar(normal_cam, _LUZ))
                    base = cor_espessura
                cor = QColor.fromRgbF(min(1.0, base.redF() * luz), min(1.0, base.greenF() * luz), min(1.0, base.blueF() * luz))
                caneta_fill = QPen(cor, 1.0)
                caneta_fill.setCosmetic(True)  # fecha a fresta de antialiasing entre pedaços
                quad = projetar_quad(sup.quad_mundo)
                transformacao = None
                contorno_tela = None
                if sup.tipo == "face" and quad is not None:
                    transformacao = QTransform()
                    if QTransform.quadToQuad(sup.quad_local, quad, transformacao):
                        contorno_tela = [(transformacao.map(linha), vinco) for linha, vinco in sup.contorno_local]
                    else:
                        transformacao = None
                dados = {"cor": cor, "caneta": caneta_fill, "quad": quad, "t": transformacao, "contorno": contorno_tela}
                info[id(sup)] = dados
                if sup.tipo == "face" and sup.externo and com_arte and quad is not None:
                    larg = abs(painel.x2 - painel.x1) or 1e-6
                    alt = abs(painel.y2 - painel.y1) or 1e-6
                    densidade = razao_pixels * max(
                        QLineF(quad.at(0), quad.at(1)).length() / larg, QLineF(quad.at(0), quad.at(3)).length() / alt
                    )
                    if transformacao is not None:
                        # Em perspectiva, o canto mais perto pede mais que a média.
                        densidade = max(
                            densidade,
                            razao_pixels * max(_escala_local(transformacao, sup.quad_local.at(i)) for i in range(sup.quad_local.count())),
                        )
                    densidade_necessaria[painel.id] = max(densidade_necessaria.get(painel.id, 0.0), densidade)
                    retangulo_painel[painel.id] = QRectF(
                        QPointF(min(painel.x1, painel.x2), min(painel.y1, painel.y2)),
                        QPointF(max(painel.x1, painel.x2), max(painel.y1, painel.y2)),
                    ).adjusted(-_ARTE_MARGEM_MM, -_ARTE_MARGEM_MM, _ARTE_MARGEM_MM, _ARTE_MARGEM_MM)
            cor, quad, transformacao = dados["cor"], dados["quad"], dados["t"]
            recortado = not poligono.inteiro or len(cam) != len(poligono.pontos)
            if sup.tipo == "face" and sup.externo and com_arte and transformacao is not None:
                inversa, ok = transformacao.inverted()
                if ok:
                    na_tela = tela.intersected(QPolygonF(area_visivel))
                    if not na_tela.isEmpty():
                        area_mm = inversa.map(na_tela).boundingRect()
                        visivel_painel[painel.id] = visivel_painel.get(painel.id, QRectF()).united(area_mm)
            p.setPen(dados["caneta"])
            p.setBrush(cor)
            com_furos = sup.tipo == "face" and painel.furos and transformacao is not None
            if com_furos:
                contorno = QPainterPath()
                contorno.addPolygon(tela)
                contorno.closeSubpath()
                area = transformacao.map(_caminho_do_painel(painel)).intersected(contorno)
                p.drawPath(area)
            else:
                p.drawPolygon(tela)
            if sup.tipo == "face":
                textura = self._texturas.get(painel.id) if sup.externo and transformacao is not None else None
                tem_arte = textura is not None and textura[0] is not None
                if not tem_arte and dados["contorno"] is None:
                    continue
                p.save()
                if com_furos:
                    p.setClipPath(area)
                elif recortado:
                    p.setClipRegion(QRegion(tela.toPolygon()))
                if tem_arte:
                    detalhe = self._detalhes.get(painel.id)
                    for imagem, k, retangulo in (textura, detalhe):
                        if imagem is None:
                            continue
                        da_imagem = QTransform.fromScale(1.0 / k, 1.0 / k) * QTransform.fromTranslate(retangulo.left(), retangulo.top())
                        p.setTransform(da_imagem * transformacao)
                        p.drawImage(QPointF(0.0, 0.0), imagem)
                        p.resetTransform()
                        if detalhe is None:
                            break
                if dados["contorno"] is not None:
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    for linha, vinco in dados["contorno"]:
                        p.setPen(caneta_vinco if vinco else caneta_corte)
                        p.drawLine(linha)
                p.restore()
            elif quad is not None:
                p.save()
                if recortado:
                    p.setClipRegion(QRegion(tela.toPolygon()))
                self._desenhar_miolo(p, quad, sup.miolo, cor)
                p.setPen(caneta_aresta)
                p.drawLine(quad.at(0), quad.at(1))
                p.drawLine(quad.at(3), quad.at(2))
                p.restore()

        self._atualizar_texturas(densidade_necessaria, retangulo_painel, visivel_painel)
        if foto is not None:
            foto["caixa"] = caixa_tela  # onde a caixa caiu na imagem (pro recorte da foto)

        if foto:
            return  # foto: só a caixa (e a sombra)
        if self._modo == "dobra":
            self._desenhar_dobradicas(p)
        self._desenhar_legenda(p)

    def _atualizar_texturas(
        self, necessaria: dict[str, float], retangulos: dict[str, QRectF], visiveis: dict[str, QRectF] | None = None
    ) -> None:
        """Gera na hora a textura das faces que ainda não têm (senão a arte
        piscaria) e agenda refazer as que ficaram sem resolução (câmera
        aproximou) ou com resolução demais (afastou: menos memória e menos
        serrilhado ao reduzir). De perto, além da textura da face inteira
        (limitada pelo lado máximo em pixels), agenda uma de DETALHE só do
        pedaço visível, na resolução que a tela pede."""
        if self._fonte_arte is None:
            return
        visiveis = visiveis or {}
        agora: dict[str, tuple[QRectF, float]] = {}
        for chave, densidade in necessaria.items():
            alvo = min(_ARTE_PX_POR_MM_MAX, max(_ARTE_PX_POR_MM_MIN, densidade * _ARTE_FOLGA_DENSIDADE))
            retangulo = retangulos[chave]
            # O que a face inteira consegue (lado máximo em pixels).
            teto = _ARTE_LADO_MAX_PX / max(retangulo.width(), retangulo.height(), 1e-6)
            alvo_base = min(alvo, teto)
            atual = self._texturas.get(chave)
            if atual is None:
                agora[chave] = (retangulo, alvo_base)
            elif atual[0] is not None and (atual[1] < alvo_base / 1.3 or atual[1] > alvo_base * 3.0):
                self._texturas_pendentes[chave] = (retangulo, alvo_base)
            self._pedir_detalhe(chave, alvo, teto, retangulo, visiveis.get(chave))
        self._gerar_texturas(agora)
        if self._texturas_pendentes or self._detalhes_pendentes:
            self._timer_texturas.start()

    def _pedir_detalhe(self, chave: str, alvo: float, teto: float, retangulo: QRectF, visivel: QRectF | None) -> None:
        if alvo <= teto * 1.3 or visivel is None or visivel.isEmpty():
            self._detalhes.pop(chave, None)  # a face inteira já basta
            self._detalhes_pendentes.pop(chave, None)
            return
        visivel = visivel.intersected(retangulo)
        if visivel.isEmpty():
            return
        atual = self._detalhes.get(chave)
        if atual is not None and atual[2].contains(visivel) and alvo / 1.3 <= atual[1] <= alvo * 3.0:
            return  # o detalhe que já tem cobre e tem resolução
        folga_x, folga_y = visivel.width() * _DETALHE_FOLGA, visivel.height() * _DETALHE_FOLGA
        area = visivel.adjusted(-folga_x, -folga_y, folga_x, folga_y).intersected(retangulo)
        self._detalhes_pendentes[chave] = (area, alvo)

    def _desenhar_sombra(self, p: QPainter, para_camera, para_tela, escala: float) -> None:
        """Sombra suave no chão, embaixo da caixa — some junto com a montagem."""
        u = _suavizar(self._progresso)
        if u <= 0.01:
            return
        cima = normalizar(self._modelo.cima)
        meia_altura = self._raio_montado * 0.6
        chao = tuple(self._centro_montado[i] - cima[i] * meia_altura for i in range(3))
        olho = self._camera()[0]
        if produto_escalar(tuple(olho[i] - chao[i] for i in range(3)), cima) <= 0:
            return  # olhando por baixo do chão: não tem sombra pra ver
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

    def _arvore(self, caixa_fechada: bool):
        """Painéis posicionados e a árvore BSP de todas as superfícies — refeita
        só quando a montagem, o modelo ou o papelão mudam (girar não refaz)."""
        chave = (self._versao_modelo, self._progresso, self._espessura, caixa_fechada)
        if self._cache_arvore is not None and self._cache_arvore[0] == chave:
            return self._cache_arvore[1], self._cache_arvore[2]
        posicionados = posicionar(self._modelo, self._progresso)
        poligonos = _superficies(posicionados, self._espessura, caixa_fechada)
        arvore = construir_bsp(poligonos)
        self._cache_arvore = (chave, posicionados, arvore)
        return posicionados, arvore

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
        capa = _CAPA_FRACAO
        # Cores tiradas da própria faixa (já com a luz daquela face): o vão
        # entre as ondas escuro, capas e onda (papel) claras — senão, numa
        # face mais escura, a onda sumia na cor da faixa.
        base = cor_faixa or cores_papelao()[2]
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
            caneta_onda = QPen(cor_papel, 1.1)
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
        self._pitch_usuario = pitch0 + delta.y() * 0.4
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

    # Nome do projeto aberto (a janela preenche): vira o nome sugerido da foto.
    nome_sugerido = "caixa"

    def salvar_imagem(self, caminho: str | None = None) -> str | None:
        """Pergunta onde salvar (se não vier o caminho) e grava a vista atual
        em alta resolução: JPG com fundo branco, PNG com fundo transparente.
        Sugere a pasta das imagens do 3D (Configurações) ou a última usada."""
        if caminho is None:
            import os

            pasta = configuracoes.pasta_imagens_3d() or configuracoes.pasta_ultima("imagem_3d")
            sugestao = os.path.join(pasta, f"{self.nome_sugerido} 3D.jpg") if pasta else f"{self.nome_sugerido} 3D.jpg"
            caminho, _filtro = QFileDialog.getSaveFileName(
                self, "Salvar imagem do 3D", sugestao, "JPG (*.jpg *.jpeg);;PNG com fundo transparente (*.png)"
            )
            if not caminho:
                return None
            configuracoes.definir_pasta_ultima("imagem_3d", os.path.dirname(caminho))
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
        for nome, mm in PAPELOES_1_10:
            self.combo_papelao.addItem(nome, mm)
        self.combo_papelao.insertSeparator(self.combo_papelao.count())
        for nome, mm in PAPELOES_TAMANHO_REAL:
            self.combo_papelao.addItem(nome, mm)
        self.combo_papelao.insertSeparator(self.combo_papelao.count())
        self.combo_papelao.addItem("Personalizado", None)
        # Fechada, a caixinha fica curta (o nome inteiro está na dica e na
        # lista aberta) — senão a barra do 3D alargava a janela toda.
        self.combo_papelao.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_papelao.setMinimumContentsLength(22)
        self.combo_papelao.view().setMinimumWidth(self.combo_papelao.view().sizeHintForColumn(0) + 24)
        self.combo_papelao.currentTextChanged.connect(self.combo_papelao.setToolTip)
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
