"""Curvas Bézier editáveis por nós — o "objeto curva" do CorelDRAW (ver
REFERENCIA_CORELDRAW.md, etapa 7). Nascem das ferramentas Bézier e Mão
livre, de "Converter em curvas" (Ctrl+Q) e de Combinar/Separar
(Ctrl+L / Ctrl+K), e são editadas pela ferramenta Forma (F10).

Modelo: uma lista de subcaminhos; cada subcaminho é uma lista de nós
(`No`) com a posição e as duas alças (entrada e saída) da Bézier cúbica.
Um nó com as alças em cima dele mesmo é um nó de canto com segmentos
retos.

Os nós ficam em coordenadas "base" e a pintura escala da base pro
tamanho atual do elemento — assim redimensionar pelas alças comuns do
`ElementoMockup` estica a curva sem tocar nos nós. Toda edição de nó
"assenta" a escala de volta pra 1 (`_renormalizar`) mantendo a curva
exatamente onde estava na cena.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QTransform

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

_EPS = 1e-6
_BASE_MINIMA = 0.5  # abaixo disso (ex.: linha reta vertical) o eixo não escala


@dataclass
class No:
    p: QPointF
    entrada: QPointF
    saida: QPointF
    suave: bool = False

    @staticmethod
    def canto(p: QPointF) -> "No":
        return No(QPointF(p), QPointF(p), QPointF(p))

    def mapeado(self, f) -> "No":
        return No(f(self.p), f(self.entrada), f(self.saida), self.suave)


@dataclass
class SubCaminho:
    nos: list[No] = field(default_factory=list)
    fechado: bool = False


def _iguais(a: QPointF, b: QPointF) -> bool:
    return abs(a.x() - b.x()) < 1e-4 and abs(a.y() - b.y()) < 1e-4


def caminho_de_subcaminhos(subcaminhos: list[SubCaminho]) -> QPainterPath:
    caminho = QPainterPath()
    caminho.setFillRule(Qt.FillRule.OddEvenFill)  # combinar faz furos, como no CorelDRAW
    for sub in subcaminhos:
        if not sub.nos:
            continue
        caminho.moveTo(sub.nos[0].p)
        pares = list(zip(sub.nos, sub.nos[1:]))
        if sub.fechado and len(sub.nos) > 1:
            pares.append((sub.nos[-1], sub.nos[0]))
        for a, b in pares:
            if _iguais(a.saida, a.p) and _iguais(b.entrada, b.p):
                caminho.lineTo(b.p)
            else:
                caminho.cubicTo(a.saida, b.entrada, b.p)
        if sub.fechado:
            caminho.closeSubpath()
    return caminho


def subcaminhos_de_caminho(caminho: QPainterPath) -> list[SubCaminho]:
    """QPainterPath (MoveTo/LineTo/CurveTo) → subcaminhos de nós. Um
    subcaminho que volta ao ponto inicial vira fechado, com o último nó
    fundido no primeiro."""
    subs: list[SubCaminho] = []
    atual: SubCaminho | None = None
    i, n = 0, caminho.elementCount()
    while i < n:
        el = caminho.elementAt(i)
        ponto = QPointF(el.x, el.y)
        if el.type == QPainterPath.ElementType.MoveToElement:
            atual = SubCaminho([No.canto(ponto)])
            subs.append(atual)
            i += 1
        elif el.type == QPainterPath.ElementType.LineToElement:
            atual.nos.append(No.canto(ponto))
            i += 1
        elif el.type == QPainterPath.ElementType.CurveToElement:
            c2, fim = caminho.elementAt(i + 1), caminho.elementAt(i + 2)
            atual.nos[-1].saida = ponto
            atual.nos.append(No(QPointF(fim.x, fim.y), QPointF(c2.x, c2.y), QPointF(fim.x, fim.y)))
            i += 3
        else:
            i += 1
    for sub in subs:
        if len(sub.nos) > 2 and _iguais(sub.nos[0].p, sub.nos[-1].p):
            ultimo = sub.nos.pop()
            sub.nos[0].entrada = ultimo.entrada
            sub.fechado = True
        for no in sub.nos:
            no.suave = _alcas_alinhadas(no)
    return [s for s in subs if s.nos]


def _alcas_alinhadas(no: No) -> bool:
    """Nó suave = as duas alças existem e apontam pra lados opostos na
    mesma reta (o QPainterPath não guarda essa marca, então é deduzida)."""
    a, b = no.entrada - no.p, no.saida - no.p
    na, nb = math.hypot(a.x(), a.y()), math.hypot(b.x(), b.y())
    if na < 1e-6 or nb < 1e-6:
        return False
    cruzado = (a.x() * b.y() - a.y() * b.x()) / (na * nb)
    escalar = (a.x() * b.x() + a.y() * b.y()) / (na * nb)
    return abs(cruzado) < 1e-3 and escalar < 0


def _mapear(subcaminhos: list[SubCaminho], f) -> list[SubCaminho]:
    return [SubCaminho([no.mapeado(f) for no in s.nos], s.fechado) for s in subcaminhos]


class ElementoCurva(ElementoMockup):
    _largura_minima_mm = 0.5
    _altura_minima_mm = 0.5

    def __init__(
        self,
        subcaminhos: list[SubCaminho],
        cor_tinta: CorImpressao | None = None,
        preenchido: bool = False,
        largura_traco: float = 0.5,
        parent=None,
    ) -> None:
        caixa = caminho_de_subcaminhos(subcaminhos).boundingRect()
        tl = caixa.topLeft()
        self._subcaminhos = _mapear(subcaminhos, lambda q: q - tl)
        self._base_l = max(caixa.width(), 0.0)
        self._base_a = max(caixa.height(), 0.0)
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._preenchido = preenchido
        self._largura_traco = max(0.0, largura_traco)
        super().__init__(largura=max(self._base_l, 0.5), altura=max(self._base_a, 0.5), parent=parent)

    # ── Aparência ───────────────────────────────────────────────────
    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    @property
    def preenchido(self) -> bool:
        return self._preenchido

    def definir_preenchido(self, preenchido: bool) -> None:
        self._preenchido = preenchido
        self.update()

    @property
    def largura_traco(self) -> float:
        return self._largura_traco

    def definir_largura_traco(self, mm: float) -> None:
        self._largura_traco = max(0.0, mm)
        self.update()

    # ── Base ↔ local ────────────────────────────────────────────────
    def _escala_eixo(self, base: float, atual: float) -> tuple[float, float]:
        if base > _BASE_MINIMA:
            return atual / base, 0.0
        return 1.0, (atual - base) / 2  # eixo "achatado": só centraliza

    def _base_para_local(self) -> QTransform:
        sx, dx = self._escala_eixo(self._base_l, self._largura)
        sy, dy = self._escala_eixo(self._base_a, self._altura)
        return QTransform(sx, 0, 0, sy, dx, dy)

    @property
    def subcaminhos(self) -> list[SubCaminho]:
        return copy.deepcopy(self._subcaminhos)

    def subcaminhos_locais(self) -> list[SubCaminho]:
        t = self._base_para_local()
        return _mapear(self._subcaminhos, t.map)

    def caminho_local(self) -> QPainterPath:
        return caminho_de_subcaminhos(self.subcaminhos_locais())

    def caminho_cena(self) -> QPainterPath:
        """Caminho já na cena (posição, rotação e espelho aplicados)."""
        local = self.caminho_local()
        if self.espelho_h or self.espelho_v:
            t = QTransform()
            t.translate(self._largura / 2, self._altura / 2)
            t.scale(-1.0 if self.espelho_h else 1.0, -1.0 if self.espelho_v else 1.0)
            t.translate(-self._largura / 2, -self._altura / 2)
            local = t.map(local)
        return self.sceneTransform().map(local)

    # ── Pintura ─────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        if self._largura_traco > 0:
            caneta = QPen(cor, self._largura_traco)
            caneta.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(caneta)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor) if self._preenchido else QBrush(Qt.BrushStyle.NoBrush))
        painter.drawPath(self.caminho_local())

    def clonar(self) -> "ElementoCurva":
        novo = ElementoCurva(self.subcaminhos, self._cor_tinta, self._preenchido, self._largura_traco)
        novo._base_l, novo._base_a = self._base_l, self._base_a
        self._copiar_geometria_para(novo)
        return novo

    # ── Estado pra desfazer (ferramenta Forma) ──────────────────────
    def estado_nos(self) -> tuple:
        return (
            copy.deepcopy(self._subcaminhos),
            self._base_l,
            self._base_a,
            QPointF(self.pos()),
            self._largura,
            self._altura,
            self.espelho_h,
            self.espelho_v,
        )

    def definir_estado_nos(self, estado: tuple) -> None:
        subs, base_l, base_a, pos, largura, altura, esp_h, esp_v = estado
        self._subcaminhos = copy.deepcopy(subs)
        self._base_l, self._base_a = base_l, base_a
        self.definir_tamanho(largura, altura)
        self.setPos(pos)
        self.definir_espelho(esp_h, esp_v)

    # ── Edição de nós (coordenadas LOCAIS) ──────────────────────────
    def _assentar(self) -> list[SubCaminho]:
        """Nós em coordenadas locais com o espelho "assado" — ponto de
        partida de toda edição."""
        subs = self.subcaminhos_locais()
        if self.espelho_h or self.espelho_v:
            l, a = self._largura, self._altura

            def espelhar(q: QPointF) -> QPointF:
                return QPointF(l - q.x() if self.espelho_h else q.x(), a - q.y() if self.espelho_v else q.y())

            subs = _mapear(subs, espelhar)
            self.definir_espelho(False, False)
        return subs

    def _renormalizar(self, subs_locais: list[SubCaminho]) -> None:
        """Assenta nós editados (locais) como nova base em escala 1, sem
        mexer na curva na cena: só recalcula a caixa e a posição."""
        caixa = caminho_de_subcaminhos(subs_locais).boundingRect()
        tl = caixa.topLeft()
        pos_antiga = QPointF(self.pos())
        origem_antiga = QPointF(self._largura / 2, self._altura / 2)
        self._subcaminhos = _mapear(subs_locais, lambda q: q - tl)
        self._base_l, self._base_a = caixa.width(), caixa.height()
        self.prepareGeometryChange()
        self.definir_tamanho(max(caixa.width(), 0.5), max(caixa.height(), 0.5))
        # Ponto local antigo q = base + tl vira local novo base + d; a cena
        # dos dois tem de coincidir (rotação em torno do centro).
        d = self._base_para_local().map(QPointF(0, 0))
        origem_nova = QPointF(self._largura / 2, self._altura / 2)
        r = QTransform().rotate(self.rotation())
        self.setPos(pos_antiga + origem_antiga - origem_nova + r.map(tl - d + origem_nova - origem_antiga))

    def mover_no(self, i: int, j: int, local: QPointF) -> None:
        subs = self._assentar()
        no = subs[i].nos[j]
        delta = local - no.p
        no.p, no.entrada, no.saida = local, no.entrada + delta, no.saida + delta
        self._renormalizar(subs)

    def mover_alca(self, i: int, j: int, qual: str, local: QPointF) -> None:
        """Arrasta a alça `qual` ("entrada"/"saida"); num nó suave a alça
        oposta acompanha espelhada (mesma direção, comprimento próprio)."""
        subs = self._assentar()
        no = subs[i].nos[j]
        setattr(no, qual, local)
        if no.suave:
            outra = "saida" if qual == "entrada" else "entrada"
            v = local - no.p
            comprimento = math.hypot(v.x(), v.y())
            atual = getattr(no, outra) - no.p
            comp_outra = math.hypot(atual.x(), atual.y()) or comprimento
            if comprimento > _EPS:
                setattr(no, outra, no.p - v * (comp_outra / comprimento))
        self._renormalizar(subs)

    def alternar_suave(self, i: int, j: int) -> None:
        """Nó de canto ↔ suave. Suave sem alças ganha alças na direção dos
        vizinhos (a 1/3 da distância), como "Suave" no CorelDRAW."""
        subs = self._assentar()
        sub = subs[i]
        no = sub.nos[j]
        no.suave = not no.suave
        if no.suave and _iguais(no.entrada, no.p) and _iguais(no.saida, no.p) and len(sub.nos) > 1:
            anterior = sub.nos[j - 1] if (j > 0 or sub.fechado) else None
            seguinte = sub.nos[(j + 1) % len(sub.nos)] if (j < len(sub.nos) - 1 or sub.fechado) else None
            a = anterior.p if anterior else no.p
            b = seguinte.p if seguinte else no.p
            direcao = b - a
            comprimento = math.hypot(direcao.x(), direcao.y()) or 1.0
            u = direcao / comprimento
            d_ant = math.hypot((no.p - a).x(), (no.p - a).y()) / 3
            d_seg = math.hypot((b - no.p).x(), (b - no.p).y()) / 3
            no.entrada, no.saida = no.p - u * d_ant, no.p + u * d_seg
        elif not no.suave:
            no.entrada, no.saida = QPointF(no.p), QPointF(no.p)
        self._renormalizar(subs)

    def inserir_no(self, i: int, segmento: int, t: float) -> None:
        """Divide o segmento `segmento` (do nó k pro k+1) em `t` (de
        Casteljau), sem mudar o desenho."""
        subs = self._assentar()
        sub = subs[i]
        a = sub.nos[segmento]
        b = sub.nos[(segmento + 1) % len(sub.nos)]

        def lerp(p, q):
            return p + (q - p) * t

        p01, p12, p23 = lerp(a.p, a.saida), lerp(a.saida, b.entrada), lerp(b.entrada, b.p)
        p012, p123 = lerp(p01, p12), lerp(p12, p23)
        meio = lerp(p012, p123)
        reto = _iguais(a.saida, a.p) and _iguais(b.entrada, b.p)
        a.saida = QPointF(a.saida) if reto else p01
        b.entrada = QPointF(b.entrada) if reto else p23
        novo = No.canto(meio) if reto else No(meio, p012, p123, suave=True)
        sub.nos.insert(segmento + 1, novo)
        self._renormalizar(subs)

    def remover_no(self, i: int, j: int) -> bool:
        subs = self._assentar()
        minimo = 3 if subs[i].fechado else 2
        if len(subs[i].nos) <= minimo:
            return False
        del subs[i].nos[j]
        self._renormalizar(subs)
        return True

    def segmento_mais_proximo(self, local: QPointF, tolerancia: float) -> tuple[int, int, float] | None:
        """(subcaminho, segmento, t) do ponto da curva mais perto de
        `local`, se estiver dentro da tolerância (amostragem)."""
        melhor, menor = None, tolerancia
        for i, sub in enumerate(self.subcaminhos_locais()):
            n = len(sub.nos)
            total = n if sub.fechado else n - 1
            for k in range(total):
                a, b = sub.nos[k], sub.nos[(k + 1) % n]
                for passo in range(1, 40):
                    t = passo / 40
                    q = _ponto_bezier(a.p, a.saida, b.entrada, b.p, t)
                    d = math.hypot(q.x() - local.x(), q.y() - local.y())
                    if d < menor:
                        melhor, menor = (i, k, t), d
        return melhor


def _ponto_bezier(p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF, t: float) -> QPointF:
    u = 1 - t
    return p0 * (u * u * u) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t * t * t)


def curva_de_caminho_cena(caminho: QPainterPath, **aparencia) -> ElementoCurva | None:
    """Curva sem rotação posicionada exatamente sobre `caminho` (cena)."""
    subs = subcaminhos_de_caminho(caminho)
    if not subs:
        return None
    caixa = caminho_de_subcaminhos(subs).boundingRect()
    curva = ElementoCurva(subs, **aparencia)
    curva.setPos(caixa.topLeft() - curva._base_para_local().map(QPointF(0, 0)))
    return curva


def caminho_local_de(elemento: ElementoMockup) -> tuple[QPainterPath, bool, float] | None:
    """(caminho local, preenchido, espessura) que desenha `elemento` igual
    à pintura dele — base de "Converter em curvas". None se o tipo não
    tem conversão."""
    from .mockup_formas import ElementoElipse, ElementoLinha, ElementoPoligono, ElementoRetangulo
    from .mockup_texto import ElementoTexto

    l, a = elemento.largura, elemento.altura
    caminho = QPainterPath()
    if isinstance(elemento, ElementoCurva):
        return elemento.caminho_local(), elemento.preenchido, elemento.largura_traco
    if isinstance(elemento, (ElementoRetangulo, ElementoElipse)):
        m = elemento.largura_traco / 2
        retangulo = QRectF(m, m, max(0.01, l - 2 * m), max(0.01, a - 2 * m))
        if isinstance(elemento, ElementoRetangulo):
            caminho.addRect(retangulo)
        else:
            caminho.addEllipse(retangulo)
        return caminho, elemento.preenchido, elemento.largura_traco
    if isinstance(elemento, ElementoPoligono):
        m = elemento.largura_traco / 2
        t = QTransform()
        t.translate(l / 2, a / 2)
        t.scale(max(0.01, l / 2 - m), max(0.01, a / 2 - m))
        return t.map(elemento._caminho_normalizado()), elemento.preenchido, elemento.largura_traco
    if isinstance(elemento, ElementoLinha):
        caminho.moveTo(0, a / 2)
        caminho.lineTo(l, a / 2)
        return caminho, False, elemento.largura_traco
    if isinstance(elemento, ElementoTexto):
        return elemento.caminho_local(), True, 0.0
    return None


def converter_em_curva(elemento: ElementoMockup) -> ElementoCurva | None:
    """Ctrl+Q: curva com o mesmo desenho, no mesmo lugar e com a mesma
    rotação (o espelho é "assado" nos nós)."""
    resultado = caminho_local_de(elemento)
    if resultado is None:
        return None
    caminho, preenchido, traco = resultado
    l, a = elemento.largura, elemento.altura
    if elemento.espelho_h or elemento.espelho_v:
        t = QTransform()
        t.translate(l / 2, a / 2)
        t.scale(-1.0 if elemento.espelho_h else 1.0, -1.0 if elemento.espelho_v else 1.0)
        t.translate(-l / 2, -a / 2)
        caminho = t.map(caminho)
    subs = subcaminhos_de_caminho(caminho)
    if not subs:
        return None
    curva = ElementoCurva(
        subs, cor_tinta=getattr(elemento, "cor_tinta", None), preenchido=preenchido, largura_traco=traco
    )
    tl = caminho_de_subcaminhos(subs).boundingRect().topLeft()
    origem_antiga = QPointF(l / 2, a / 2)
    origem_nova = QPointF(curva.largura / 2, curva.altura / 2)
    deslocamento = curva._base_para_local().map(QPointF(0, 0))
    r = QTransform().rotate(elemento.rotation())
    curva.setRotation(elemento.rotation())
    curva.setPos(elemento.pos() + origem_antiga - origem_nova + r.map(tl - deslocamento + origem_nova - origem_antiga))
    curva.definir_painel(elemento.painel_id)
    return curva
