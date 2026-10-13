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

A arte do Layout (texto, formas, logotipo) entra como textura: a cena do
canvas é renderizada sem a faca numa imagem da chapa inteira
(`renderizar_arte`) e cada pedaço da face externa recebe o recorte dele
via `QTransform.quadToQuad` — projetivo exato pra uma face plana. A arte
vai sem luz/sombra por cima, pra manter as cores originais da marca.

A geometria (quais painéis existem, onde fica cada vinco, em que ordem
cada aba dobra) mora em `dobra3d.py`, sem nada de UI.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF, QRadialGradient, QTransform
from PySide6.QtWidgets import QGraphicsScene, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from ..dobra3d import (
    ModeloCaixa3D,
    Vetor,
    caixa_envolvente,
    normalizar,
    posicionar,
    produto_escalar,
    produto_vetorial,
)
from .estilo import FONTE_MONO, Cor

_SUBDIVISOES = 5
_FOV_GRAUS = 34.0
_DURACAO_MONTAR_MS = 3400
_DURACAO_PLANIFICAR_MS = 2800
# Giro automático da caixa montada parada (soma ao arrasto do usuário).
_GIRO_AUTOMATICO_GRAUS_S = 8.0
_INTERVALO_QUADRO_MS = 33
# Resolução da textura da arte: até 4 px/mm, limitada no lado maior.
_ARTE_PX_POR_MM = 4.0
_ARTE_LADO_MAX_PX = 2400

# Vista "3/4" da caixa montada (graus, relativos a `cima`/`frente` do modelo).
_YAW_MONTADA = -34.0
_PITCH_MONTADA = 24.0

# Papelão: lado impresso (kraft da marca) e miolo/lado de dentro, mais claro.
_COR_EXTERNA = QColor("#C79A5D")
_COR_INTERNA = QColor("#E6D0A8")
_COR_ARESTA = QColor(74, 54, 30, 210)
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


def renderizar_arte(cena: QGraphicsScene, elementos: list, largura_mm: float, altura_mm: float) -> QImage | None:
    """Imagem transparente da chapa inteira (origem = canto da dieline)
    só com os elementos de Layout — sem faca, guias nem seleção (mesma
    ideia de `_SelecaoOculta` em exportacao.py). `None` quando não há arte."""
    if not elementos or largura_mm <= 0 or altura_mm <= 0:
        return None
    px_por_mm = min(_ARTE_PX_POR_MM, _ARTE_LADO_MAX_PX / max(largura_mm, altura_mm))
    imagem = QImage(
        max(1, round(largura_mm * px_por_mm)),
        max(1, round(altura_mm * px_por_mm)),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    imagem.fill(Qt.GlobalColor.transparent)

    manter = set(elementos)
    ocultos = [it for it in cena.items() if it.parentItem() is None and it not in manter and it.isVisible()]
    selecionados = list(cena.selectedItems())
    for item in ocultos:
        item.setVisible(False)
    for item in selecionados:
        item.setSelected(False)
    try:
        p = QPainter(imagem)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        cena.render(
            p,
            target=QRectF(imagem.rect()),
            source=QRectF(0.0, 0.0, largura_mm, altura_mm),
            aspectRatioMode=Qt.AspectRatioMode.IgnoreAspectRatio,
        )
        p.end()
    finally:
        for item in ocultos:
            item.setVisible(True)
        for item in selecionados:
            item.setSelected(True)
    imagem.setText("px_por_mm", f"{px_por_mm}")
    return imagem


class VistaCaixa3D(QWidget):
    """Viewport 3D. Arrastar gira, roda do mouse aproxima, duplo clique
    volta pra vista inicial."""

    progresso_alterado = Signal(float)

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
        self._arrasto: tuple[QPointF, float, float] | None = None
        # Enquadramento de cada estado — a câmera interpola entre os dois,
        # senão a caixa montada fica minúscula no quadro da chapa aberta.
        self._centro_plano: Vetor = (0.0, 0.0, 0.0)
        self._centro_montado: Vetor = (0.0, 0.0, 0.0)
        self._raio_plano = 1.0
        self._raio_montado = 1.0
        self._arte: QImage | None = None
        self._arte_px_por_mm = 1.0
        # Giro automático: só com a caixa montada, parada e sem arrasto.
        self._giro_auto = 0.0
        self._relogio = QElapsedTimer()
        self._timer_giro = QTimer(self)
        self._timer_giro.setInterval(_INTERVALO_QUADRO_MS)
        self._timer_giro.timeout.connect(self._passo_giro)

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
        self.update()

    def definir_arte(self, imagem: QImage | None) -> None:
        self._arte = imagem if imagem is not None and not imagem.isNull() else None
        if self._arte is not None:
            self._arte_px_por_mm = float(self._arte.text("px_por_mm") or 1.0)
        self.update()

    def progresso(self) -> float:
        return self._progresso

    def definir_progresso(self, valor: float) -> None:
        valor = max(0.0, min(1.0, valor))
        if valor != self._progresso:
            self._progresso = valor
            self.progresso_alterado.emit(valor)
            self._atualizar_timer_giro()
            self.update()

    def vista_inicial(self) -> None:
        self._yaw_usuario = 0.0
        self._pitch_usuario = 0.0
        self._giro_auto = 0.0
        self._zoom = 1.0
        self.update()

    # ── Giro automático ──────────────────────────────────────────────
    def _atualizar_timer_giro(self) -> None:
        girar = self.isVisible() and self._progresso >= 0.999 and self._arrasto is None and not self._modelo.vazio
        if girar and not self._timer_giro.isActive():
            self._relogio.start()
            self._timer_giro.start()
        elif not girar and self._timer_giro.isActive():
            self._timer_giro.stop()

    def _passo_giro(self) -> None:
        dt = self._relogio.restart() / 1000.0
        self._giro_auto = (self._giro_auto + _GIRO_AUTOMATICO_GRAUS_S * min(dt, 0.2)) % 360.0
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
        distancia = raio / math.sin(math.radians(_FOV_GRAUS) / 2.0) * 1.05 / self._zoom
        olho = tuple(centro[i] + direcao[i] * distancia for i in range(3))
        return olho, direita, cima_cam, olhar  # type: ignore[return-value]

    # ── Pintura ──────────────────────────────────────────────────────
    def paintEvent(self, _evento) -> None:  # noqa: N802 (API do Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), _COR_FUNDO)

        if self._modelo.vazio:
            p.setPen(_COR_TEXTO_FUNDO)
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Informe comprimento, largura e altura para ver a caixa em 3D.",
            )
            return

        olho, direita, cima, olhar = self._camera()
        escala = (min(self.width(), self.height()) / 2.0) / math.tan(math.radians(_FOV_GRAUS) / 2.0)
        cx, cy = self.width() / 2.0, self.height() / 2.0

        def para_camera(ponto: Vetor) -> Vetor:
            v = (ponto[0] - olho[0], ponto[1] - olho[1], ponto[2] - olho[2])
            return (produto_escalar(v, direita), produto_escalar(v, cima), produto_escalar(v, olhar))

        def para_tela(pc: Vetor) -> QPointF:
            return QPointF(cx + escala * pc[0] / pc[2], cy - escala * pc[1] / pc[2])

        self._desenhar_sombra(p, para_camera, para_tela, escala)

        # (profundidade, poligono, cor, arestas da borda, (recorte, quad) da arte em px | None)
        pedacos = []
        caixa_fechada = self._progresso >= 0.999
        vies_interno = 0.04 * self._raio_montado
        vies_camada = 0.08 * self._raio_montado
        n = _SUBDIVISOES
        arte = self._arte
        k = self._arte_px_por_mm
        for pp in posicionar(self._modelo, self._progresso):
            painel = pp.painel
            if caixa_fechada and painel.camada > 0:
                continue  # fechada é um sólido: as abas por baixo nunca aparecem
            normal = pp.normal_externa
            normal_cam = (
                produto_escalar(normal, direita),
                produto_escalar(normal, cima),
                produto_escalar(normal, olhar),
            )
            # Grade (n+1)×(n+1) de pontos do painel já em coordenadas de câmera.
            grade = [
                [
                    para_camera(pp.ponto(_lerp(painel.x1, painel.x2, i / n), _lerp(painel.y1, painel.y2, j / n)))
                    for i in range(n + 1)
                ]
                for j in range(n + 1)
            ]
            for j in range(n):
                for i in range(n):
                    cantos = [grade[j][i], grade[j][i + 1], grade[j + 1][i + 1], grade[j + 1][i]]
                    if min(c[2] for c in cantos) <= 1.0:
                        continue  # atrás/encostado na câmera
                    centro = tuple(sum(c[k] for c in cantos) / 4.0 for k in range(3))
                    ve_lado_externo = produto_escalar(normal_cam, centro) < 0
                    if not ve_lado_externo and caixa_fechada:
                        continue  # caixa fechada é um sólido: o lado de dentro nunca aparece
                    face_normal = normal_cam if ve_lado_externo else tuple(-c for c in normal_cam)
                    luz = 0.55 + 0.45 * max(0.0, produto_escalar(face_normal, _LUZ))
                    base = _COR_EXTERNA if ve_lado_externo else _COR_INTERNA
                    cor = QColor.fromRgbF(
                        min(1.0, base.redF() * luz), min(1.0, base.greenF() * luz), min(1.0, base.blueF() * luz)
                    )
                    tela = [para_tela(c) for c in cantos]
                    bordas = []
                    if j == 0:
                        bordas.append((tela[0], tela[1]))
                    if i == n - 1:
                        bordas.append((tela[1], tela[2]))
                    if j == n - 1:
                        bordas.append((tela[2], tela[3]))
                    if i == 0:
                        bordas.append((tela[3], tela[0]))
                    profundidade = math.sqrt(produto_escalar(centro, centro))
                    profundidade += painel.camada * vies_camada
                    if not ve_lado_externo:
                        # Lado de dentro só aparece olhando pra dentro da caixa
                        # aberta — puxar ele pra trás evita que vaze por cima de
                        # uma face externa quase no mesmo lugar (abas sobrepostas).
                        profundidade += vies_interno
                    arte_pedaco = None
                    if arte is not None and ve_lado_externo:
                        xa, xb = _lerp(painel.x1, painel.x2, i / n), _lerp(painel.x1, painel.x2, (i + 1) / n)
                        ya, yb = _lerp(painel.y1, painel.y2, j / n), _lerp(painel.y1, painel.y2, (j + 1) / n)
                        recorte = QRectF(QPointF(xa * k, ya * k), QPointF(xb * k, yb * k)).normalized()
                        # Avança ~1,5 px DA TELA sobre os pedaços vizinhos da
                        # MESMA face (nunca além da borda dela): o contorno de
                        # 1,2 px do preenchimento do pedaço seguinte, pintado
                        # depois, invadia a beirada desta arte e deixava emenda.
                        px_tela_por_px_arte = max(
                            math.dist((tela[1].x(), tela[1].y()), (tela[0].x(), tela[0].y())) / max(recorte.width(), 1e-6),
                            math.dist((tela[3].x(), tela[3].y()), (tela[0].x(), tela[0].y())) / max(recorte.height(), 1e-6),
                            1e-6,
                        )
                        margem = min(1.5 / px_tela_por_px_arte, recorte.width() / 2, recorte.height() / 2)
                        face = QRectF(QPointF(painel.x1 * k, painel.y1 * k), QPointF(painel.x2 * k, painel.y2 * k)).normalized()
                        recorte = recorte.adjusted(-margem, -margem, margem, margem).intersected(face)
                        # Quad de origem na MESMA ordem dos cantos da tela.
                        quad = QPolygonF(
                            [QPointF(xa * k, ya * k), QPointF(xb * k, ya * k), QPointF(xb * k, yb * k), QPointF(xa * k, yb * k)]
                        )
                        arte_pedaco = (recorte, quad)
                    pedacos.append((profundidade, QPolygonF(tela), cor, bordas, arte_pedaco))

        pedacos.sort(key=lambda item: item[0], reverse=True)
        caneta_aresta = QPen(_COR_ARESTA, 1.2)
        caneta_aresta.setCosmetic(True)
        transformacao = QTransform()
        for _prof, poligono, cor, bordas, arte_pedaco in pedacos:
            # Contorno da mesma cor fecha as frestas de antialiasing entre pedaços.
            caneta_fill = QPen(cor, 1.2)
            caneta_fill.setCosmetic(True)
            p.setPen(caneta_fill)
            p.setBrush(cor)
            p.drawPolygon(poligono)
            if arte_pedaco is not None and QTransform.quadToQuad(arte_pedaco[1], poligono, transformacao):
                # Sem luz nem mistura por cima: a arte mantém a cor original.
                p.save()
                p.setTransform(transformacao)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                p.drawImage(arte_pedaco[0], arte, arte_pedaco[0])
                p.restore()
            if bordas:
                p.setPen(caneta_aresta)
                for a, b in bordas:
                    p.drawLine(a, b)

        self._desenhar_legenda(p)

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
            "Arraste para girar  ·  roda do mouse para aproximar  ·  duplo clique volta à vista inicial",
        )

    # ── Mouse ────────────────────────────────────────────────────────
    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self._arrasto = (evento.position(), self._yaw_usuario, self._pitch_usuario)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._atualizar_timer_giro()

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if self._arrasto is None:
            return
        inicio, yaw0, pitch0 = self._arrasto
        delta = evento.position() - inicio
        self._yaw_usuario = yaw0 - delta.x() * 0.4
        self._pitch_usuario = max(-180.0, min(180.0, pitch0 + delta.y() * 0.4))
        self.update()

    def mouseReleaseEvent(self, _evento) -> None:  # noqa: N802
        self._arrasto = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._atualizar_timer_giro()

    def mouseDoubleClickEvent(self, _evento) -> None:  # noqa: N802
        self.vista_inicial()

    def wheelEvent(self, evento) -> None:  # noqa: N802
        passos = evento.angleDelta().y() / 120.0
        self._zoom = max(0.4, min(4.0, self._zoom * (1.12**passos)))
        self.update()


class Visualizacao3D(QWidget):
    """Viewport + barra de controles (Planificar/Montar e a régua de dobra)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vista = VistaCaixa3D()

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
        barra.addWidget(botao_vista)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 6, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self.vista, 1)
        vbox.addLayout(barra)

        self._animacao = QVariantAnimation(self)
        self._animacao.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animacao.valueChanged.connect(lambda v: self._aplicar_progresso(float(v)))
        self._animacao.finished.connect(self._atualizar_textos)
        self._alvo = 1.0

    def definir_modelo(self, modelo: ModeloCaixa3D, medidas_texto: str = "") -> None:
        self.vista.definir_modelo(modelo, medidas_texto)
        habilitado = not modelo.vazio
        self.botao_alternar.setEnabled(habilitado)
        self.regua_dobra.setEnabled(habilitado)

    def definir_arte(self, imagem: QImage | None) -> None:
        self.vista.definir_arte(imagem)

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
