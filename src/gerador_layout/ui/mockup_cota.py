"""Cota (dimensão) persistente, como as ferramentas de cota do CorelDRAW
(paralela, horizontal e vertical) — ver REFERENCIA_CORELDRAW.md, etapa 6.

Ao contrário da ferramenta Medida (leitura temporária), a cota fica no
desenho e sai na exportação. Ela é um `ElementoMockup` comum: a
**largura** do elemento É a distância medida, então redimensionar pela
alça atualiza o valor sozinho, e mover/girar/desfazer vêm de graça do
motor em `mockup_itens.py`.

Coordenadas locais (y cresce pra baixo):

    y = 0 ............ topo (espaço do texto)
    y = linha ........ linha de cota com as setas; texto logo acima
    y = altura - ya .. ponto medido A (x = 0)
    y = altura - yb .. ponto medido B (x = largura)

`ya`/`yb` só diferem de zero na cota horizontal/vertical, quando os dois
pontos medidos não estão na mesma altura: cada linha de chamada desce até
o seu ponto, como no CorelDRAW.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen, QPolygonF, QTransform

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

TIPOS_COTA = ("paralela", "horizontal", "vertical")

_ALTURA_TEXTO_PADRAO_MM = 3.5
_AFASTAMENTO_PADRAO_MM = 10.0
_FOLGA_PONTO_MM = 1.0  # linha de chamada não encosta no objeto medido
_SOBRA_CHAMADA_MM = 1.5  # linha de chamada passa um pouco da linha de cota
_SETA_MM = 2.5
_TRACO_MM = 0.25
_TAMANHO_FONTE_REFERENCIA = 100.0


class ElementoCota(ElementoMockup):
    _altura_minima_mm = 4.0

    def __init__(
        self,
        largura: float = 50.0,
        afastamento: float = _AFASTAMENTO_PADRAO_MM,
        ya: float = 0.0,
        yb: float = 0.0,
        tipo: str = "paralela",
        cor_tinta: CorImpressao | None = None,
        altura_texto: float = _ALTURA_TEXTO_PADRAO_MM,
        parent=None,
    ) -> None:
        self._ya = max(0.0, ya)
        self._yb = max(0.0, yb)
        self._altura_texto = max(0.5, altura_texto)
        self._tipo = tipo if tipo in TIPOS_COTA else "paralela"
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        super().__init__(largura=largura, altura=self._altura_para(afastamento), parent=parent)

    # ── Geometria da cota ───────────────────────────────────────────
    def _margem_texto(self) -> float:
        return self._altura_texto * 1.4 + _SOBRA_CHAMADA_MM

    def _altura_para(self, afastamento: float) -> float:
        return self._margem_texto() + max(2.0, afastamento) + max(self._ya, self._yb)

    @property
    def tipo(self) -> str:
        return self._tipo

    @property
    def valor_mm(self) -> float:
        return self._largura

    @property
    def afastamento(self) -> float:
        return max(0.0, self._altura - self._margem_texto() - max(self._ya, self._yb))

    def definir_afastamento(self, mm: float) -> None:
        """Muda a distância entre os pontos medidos e a linha de cota,
        sem tirar os pontos medidos do lugar (cresce pra cima)."""
        altura_antes = self._altura
        nova = self._altura_para(mm)
        # Base (pontos medidos) fica parada: compensa a mudança de altura
        # e a troca do centro de rotação.
        base_antes = self.mapToScene(QPointF(0.0, altura_antes))
        self.definir_tamanho(self._largura, nova)
        base_depois = self.mapToScene(QPointF(0.0, nova))
        self.setPos(self.pos() + (base_antes - base_depois))

    @property
    def altura_texto(self) -> float:
        return self._altura_texto

    def definir_altura_texto(self, mm: float) -> None:
        afastamento = self.afastamento
        self._altura_texto = max(0.5, mm)
        self.definir_afastamento(afastamento)

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    def texto_valor(self) -> str:
        return f"{self._largura:.1f} mm".replace(".", ",")

    def segmentos_locais(self) -> list[tuple[QPointF, QPointF]]:
        """Linhas de chamada + linha de cota, em coordenadas locais —
        mesma geometria da pintura, usada também pela ponte do CorelDRAW."""
        h, l = self._altura, self._largura
        linha = self._margem_texto()
        topo_chamada = linha - _SOBRA_CHAMADA_MM
        return [
            (QPointF(0.0, h - self._ya - _FOLGA_PONTO_MM), QPointF(0.0, topo_chamada)),
            (QPointF(l, h - self._yb - _FOLGA_PONTO_MM), QPointF(l, topo_chamada)),
            (QPointF(0.0, linha), QPointF(l, linha)),
        ]

    def setas_locais(self) -> list[QPolygonF]:
        linha = self._margem_texto()
        s = min(_SETA_MM, self._largura / 3)
        meia = s * 0.35
        return [
            QPolygonF([QPointF(0.0, linha), QPointF(s, linha - meia), QPointF(s, linha + meia)]),
            QPolygonF([QPointF(self._largura, linha), QPointF(self._largura - s, linha - meia), QPointF(self._largura - s, linha + meia)]),
        ]

    def retangulo_texto_local(self) -> QRectF:
        linha = self._margem_texto()
        return QRectF(0.0, linha - self._altura_texto * 1.4, self._largura, self._altura_texto * 1.3)

    def texto_de_cabeca_pra_baixo(self) -> bool:
        """Texto sempre legível: entre 90° e 270° ele é virado."""
        angulo = self.rotation() % 360.0
        return 90.0 < angulo < 270.0

    # ── Pintura ─────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        pen = QPen(cor, _TRACO_MM)
        painter.setPen(pen)
        for a, b in self.segmentos_locais():
            painter.drawLine(a, b)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        for seta in self.setas_locais():
            painter.drawPolygon(seta)

        fonte = QFont("Arial")
        fonte.setPixelSize(int(_TAMANHO_FONTE_REFERENCIA))
        metricas = QFontMetricsF(fonte)
        escala = self._altura_texto / metricas.capHeight()
        texto = self.texto_valor()
        rect = self.retangulo_texto_local()
        painter.save()
        painter.translate(rect.center())
        if self.texto_de_cabeca_pra_baixo():
            painter.rotate(180.0)
        painter.scale(escala, escala)
        painter.setFont(fonte)
        painter.setPen(cor)
        largura_texto = metricas.horizontalAdvance(texto)
        painter.drawText(QPointF(-largura_texto / 2, metricas.capHeight() / 2), texto)
        painter.restore()

    def clonar(self) -> "ElementoCota":
        novo = ElementoCota(
            largura=self._largura,
            ya=self._ya,
            yb=self._yb,
            tipo=self._tipo,
            cor_tinta=self._cor_tinta,
            altura_texto=self._altura_texto,
        )
        self._copiar_geometria_para(novo)
        return novo


def criar_cota(
    p1: QPointF,
    p2: QPointF,
    tipo: str,
    afastamento: float = _AFASTAMENTO_PADRAO_MM,
    cor=None,
    centro_referencia: QPointF | None = None,
) -> ElementoCota | None:
    """Cota entre dois pontos da cena. Paralela mede a distância direta;
    horizontal só o Δx; vertical só o Δy. Com `centro_referencia` (o
    centro da chapa), horizontal/vertical vão pro lado de FORA — acima ou
    abaixo, à esquerda ou à direita —, que é onde se cota uma faca.
    Devolve None se a medida for praticamente zero."""
    meio = (p1 + p2) / 2
    if tipo == "horizontal":
        abaixo = centro_referencia is not None and meio.y() > centro_referencia.y()
        angulo = 180.0 if abaixo else 0.0
    elif tipo == "vertical":
        a_direita = centro_referencia is not None and meio.x() > centro_referencia.x()
        angulo = 90.0 if a_direita else -90.0
    else:
        angulo = math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))
        if 90.0 < angulo % 360.0 < 270.0:
            angulo -= 180.0  # mantém o texto de pé e a cota "por cima"
        angulo = (angulo + 180.0) % 360.0 - 180.0

    rad = math.radians(angulo)
    ao_longo = QPointF(math.cos(rad), math.sin(rad))
    pra_cima = QPointF(math.sin(rad), -math.cos(rad))  # -y local na cena

    def projecao(v: QPointF, eixo: QPointF) -> float:
        return v.x() * eixo.x() + v.y() * eixo.y()

    a, b = (p1, p2) if projecao(p2 - p1, ao_longo) >= 0 else (p2, p1)
    comprimento = projecao(b - a, ao_longo)
    if comprimento < 0.5:
        return None
    altura_b = projecao(b - a, pra_cima)
    base = min(0.0, altura_b)
    ya, yb = 0.0 - base, altura_b - base
    if tipo == "paralela":
        ya = yb = 0.0

    cota = ElementoCota(largura=comprimento, afastamento=afastamento, ya=ya, yb=yb, tipo=tipo, cor_tinta=cor)
    cota.setRotation(angulo)
    # pos tal que o ponto local (0, altura - ya) caia em `a`:
    # cena = pos + origem + R·(local − origem).
    origem = QPointF(cota.largura / 2, cota.altura / 2)
    local_a = QPointF(0.0, cota.altura - ya)
    cota.setPos(a - origem - QTransform().rotate(angulo).map(local_a - origem))
    return cota
