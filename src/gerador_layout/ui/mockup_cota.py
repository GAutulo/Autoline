"""Cota (dimensão) persistente, como as ferramentas de cota do CorelDRAW
(paralela, horizontal e vertical) — ver REFERENCIA_CORELDRAW.md, etapa 6.

Ao contrário da ferramenta Medida (leitura temporária), a cota fica no
desenho e sai na exportação. Ela é um `ElementoMockup` comum: a
**largura** do elemento É a distância medida, então redimensionar pela
alça atualiza o valor sozinho, e mover/girar/desfazer vêm de graça do
motor em `mockup_itens.py`.

Coordenadas locais (y cresce pra baixo):

    y = 0 ............ topo (espaço do texto)
    y = linha ........ linha de cota; o texto fica no meio dela, ou logo
                       acima quando não cabe entre as duas linhas de chamada
    y = altura - ya .. ponto medido A (x = 0)
    y = altura - yb .. ponto medido B (x = largura)

`ya`/`yb` só diferem de zero na cota horizontal/vertical, quando os dois
pontos medidos não estão na mesma altura: cada linha de chamada desce até
o seu ponto, como no CorelDRAW.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPolygonF, QTransform

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

TIPOS_COTA = ("paralela", "horizontal", "vertical")
UNIDADES_COTA = ("cm", "mm")  # só o nome: o número é sempre o do desenho

_ALTURA_TEXTO_PADRAO_MM = 3.5
_AFASTAMENTO_PADRAO_MM = 10.0
# Os três abaixo valem para a letra padrão e acompanham a letra: numa faca
# desenhada em escala reduzida, medida fixa em mm engrossaria tudo.
_FOLGA_PONTO_MM = 1.0  # linha de chamada não encosta no objeto medido
_SOBRA_CHAMADA_MM = 1.5  # linha de chamada passa um pouco da linha de cota
_MENOR_AFASTAMENTO_MM = 2.0
_TRACO_POR_ALTURA = 0.06  # fio fino: 6% da altura da letra
_TAMANHO_FONTE_REFERENCIA = 100.0


class ElementoCota(ElementoMockup):
    _altura_minima_mm = 0.5

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
        self._cor_tinta = cor_tinta or CorImpressao(nome="Vermelho", r=237, g=28, b=36)
        self._unidade = "cm"
        self._texto_proprio = ""  # vazio: a medida, calculada
        super().__init__(largura=largura, altura=self._altura_para(afastamento), parent=parent)

    # ── Geometria da cota ───────────────────────────────────────────
    def _na_escala_da_letra(self, mm: float) -> float:
        return mm * self._altura_texto / _ALTURA_TEXTO_PADRAO_MM

    def _margem_texto(self) -> float:
        return self._altura_texto * 1.4 + self._na_escala_da_letra(_SOBRA_CHAMADA_MM)

    def _altura_para(self, afastamento: float) -> float:
        menor = self._na_escala_da_letra(_MENOR_AFASTAMENTO_MM)
        return self._margem_texto() + max(menor, afastamento) + max(self._ya, self._yb)

    @property
    def traco_mm(self) -> float:
        return self._altura_texto * _TRACO_POR_ALTURA

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
        """O texto próprio, se houver; senão a medida do desenho com o nome
        da unidade escolhida. A unidade não converte nada: no desenho em
        1:10, 110 mm desenhados são lidos como 110 cm."""
        if self._texto_proprio.strip():
            return self._texto_proprio.strip()
        return f"{self._largura:.1f} {self._unidade}".replace(".", ",")

    @property
    def unidade(self) -> str:
        return self._unidade

    def definir_unidade(self, unidade: str) -> None:
        if unidade in UNIDADES_COTA:
            self.prepareGeometryChange()  # o texto muda de largura
            self._unidade = unidade
            self.update()

    @property
    def texto_proprio(self) -> str:
        return self._texto_proprio

    def definir_texto_proprio(self, texto: str) -> None:
        self.prepareGeometryChange()  # o texto muda de largura
        self._texto_proprio = texto.strip()
        self.update()

    def _area_local(self) -> QRectF:
        """A cota mais o texto que passa das pontas (texto próprio longo,
        acima da linha): é isso que a folha enquadra e a tela repinta."""
        area = QRectF(0.0, 0.0, self._largura, self._altura)
        if self.texto_na_linha():
            return area
        _fonte, metricas, escala = self._fonte_e_escala()
        sobra = (metricas.horizontalAdvance(self.texto_valor()) * escala - self._largura) / 2
        return area.adjusted(-sobra, 0.0, sobra, 0.0) if sobra > 0 else area

    def retangulo_conteudo_cena(self) -> QRectF:
        return self.mapRectToScene(self._area_local())

    def boundingRect(self) -> QRectF:  # noqa: N802
        return super().boundingRect().united(self._area_local())

    def _fonte_e_escala(self) -> tuple[QFont, QFontMetricsF, float]:
        fonte = QFont("Arial")
        fonte.setPixelSize(int(_TAMANHO_FONTE_REFERENCIA))
        metricas = QFontMetricsF(fonte)
        return fonte, metricas, self._altura_texto / metricas.capHeight()

    def _largura_vao_texto(self) -> float:
        """Vão do texto na linha de cota, com uma folga de cada lado."""
        _fonte, metricas, escala = self._fonte_e_escala()
        return metricas.horizontalAdvance(self.texto_valor()) * escala + self._altura_texto

    def texto_na_linha(self) -> bool:
        return self._largura_vao_texto() < self._largura - self._altura_texto

    def segmentos_locais(self) -> list[tuple[QPointF, QPointF]]:
        """Linhas de chamada + linha de cota, em coordenadas locais —
        mesma geometria da pintura, usada também pela ponte do CorelDRAW.
        O texto que cabe interrompe a linha de cota no meio."""
        h, l = self._altura, self._largura
        linha = self._margem_texto()
        topo_chamada = linha - self._na_escala_da_letra(_SOBRA_CHAMADA_MM)
        folga = self._na_escala_da_letra(_FOLGA_PONTO_MM)
        chamadas = [
            (QPointF(0.0, h - self._ya - folga), QPointF(0.0, topo_chamada)),
            (QPointF(l, h - self._yb - folga), QPointF(l, topo_chamada)),
        ]
        if not self.texto_na_linha():
            return chamadas + [(QPointF(0.0, linha), QPointF(l, linha))]
        vao = self._largura_vao_texto() / 2
        return chamadas + [
            (QPointF(0.0, linha), QPointF(l / 2 - vao, linha)),
            (QPointF(l / 2 + vao, linha), QPointF(l, linha)),
        ]

    def setas_locais(self) -> list[QPolygonF]:
        """Sem setas: a cota termina nas linhas de chamada. O método fica
        porque a ponte do CorelDRAW percorre o que ele devolve."""
        return []

    def retangulo_texto_local(self) -> QRectF:
        linha = self._margem_texto()
        topo = linha - self._altura_texto * (0.65 if self.texto_na_linha() else 1.4)
        return QRectF(0.0, topo, self._largura, self._altura_texto * 1.3)

    def texto_de_cabeca_pra_baixo(self) -> bool:
        """Texto sempre legível: entre 90° e 270° ele é virado."""
        angulo = self.rotation() % 360.0
        return 90.0 < angulo < 270.0

    # ── Pintura ─────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        pen = QPen(cor, self.traco_mm)
        painter.setPen(pen)
        for a, b in self.segmentos_locais():
            painter.drawLine(a, b)

        fonte, metricas, escala = self._fonte_e_escala()
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
        novo._unidade, novo._texto_proprio = self._unidade, self._texto_proprio
        self._copiar_geometria_para(novo)
        return novo


def criar_cota(
    p1: QPointF,
    p2: QPointF,
    tipo: str,
    afastamento: float = _AFASTAMENTO_PADRAO_MM,
    cor=None,
    centro_referencia: QPointF | None = None,
    altura_texto: float = _ALTURA_TEXTO_PADRAO_MM,
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

    cota = ElementoCota(
        largura=comprimento, afastamento=afastamento, ya=ya, yb=yb, tipo=tipo, cor_tinta=cor, altura_texto=altura_texto
    )
    cota.setRotation(angulo)
    # pos tal que o ponto local (0, altura - ya) caia em `a`:
    # cena = pos + origem + R·(local − origem).
    origem = QPointF(cota.largura / 2, cota.altura / 2)
    local_a = QPointF(0.0, cota.altura - ya)
    cota.setPos(a - origem - QTransform().rotate(angulo).map(local_a - origem))
    return cota
