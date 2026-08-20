"""Símbolos de manuseio/transporte (pictogramas ISO 780) — achado numa
análise comparativa com a biblioteca padrão do ArtiosCAD (`Gm_SymbolPos*`
em `InstLib`), que traz um catálogo pronto de "Frágil", "Este lado para
cima", "Manter seco" etc. pra colar na embalagem. Reaproveita o mesmo
motor de `ElementoMockup` que qualquer outra forma — o pictograma em si é
só um `QPainterPath` fixo por tipo, escalado pra caber na caixa do
elemento (mesmo truque de `ElementoPoligono`/`ElementoAcabamento`), não
tenta reproduzir a arte oficial ISO traço a traço (fora de escopo aqui),
só ficar reconhecível o bastante pra servir de referência/rascunho no
mockup.
"""

from __future__ import annotations

import math
from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

_TAMANHO_PADRAO_MM = 30.0
_ESPACO_REFERENCIA = 100.0  # espaço normalizado em que cada pictograma é desenhado


class TipoSimbolo(Enum):
    FRAGIL = "Frágil"
    ESTE_LADO_CIMA = "Este lado para cima"
    MANTER_SECO = "Manter seco"
    NAO_EMPILHAR = "Não empilhar"
    RECICLAVEL = "Reciclável"
    CENTRO_GRAVIDADE = "Centro de gravidade"
    NAO_USAR_GANCHO = "Não usar gancho"


def _caminho_fragil() -> QPainterPath:
    """Taça quebrada — trinca em zigue-zague atravessando a taça."""
    caminho = QPainterPath()
    caminho.moveTo(30, 15)
    caminho.lineTo(70, 15)
    caminho.lineTo(58, 48)
    caminho.lineTo(50, 48)
    caminho.lineTo(50, 78)
    caminho.moveTo(35, 88)
    caminho.lineTo(65, 88)
    caminho.moveTo(50, 78)
    caminho.lineTo(50, 88)
    caminho.moveTo(50, 48)
    caminho.lineTo(42, 48)
    caminho.lineTo(30, 15)
    # trinca
    caminho.moveTo(38, 24)
    caminho.lineTo(48, 34)
    caminho.lineTo(41, 40)
    caminho.lineTo(56, 55)
    return caminho


def _caminho_este_lado_cima() -> QPainterPath:
    """2 setas apontando pra cima, empilhadas (pictograma ISO padrão)."""
    caminho = QPainterPath()
    for base_y, ponta_y, topo_y in ((88, 62, 42), (55, 30, 10)):
        caminho.moveTo(50, base_y)
        caminho.lineTo(50, ponta_y)
        caminho.moveTo(36, ponta_y)
        caminho.lineTo(50, topo_y)
        caminho.lineTo(64, ponta_y)
    return caminho


def _caminho_manter_seco() -> QPainterPath:
    """Guarda-chuva aberto sobre uma caixa — leitura universal de
    "proteger da chuva/umidade"."""
    caminho = QPainterPath()
    # cúpula do guarda-chuva
    caminho.moveTo(12, 45)
    caminho.cubicTo(12, 18, 88, 18, 88, 45)
    for x in (12, 31, 50, 69, 88):
        caminho.moveTo(x, 45)
        caminho.lineTo(x, 45 + (4 if 12 < x < 88 else 0))
    # cabo
    caminho.moveTo(50, 45)
    caminho.lineTo(50, 78)
    caminho.cubicTo(50, 90, 34, 90, 34, 80)
    # caixa embaixo
    caminho.addRect(QRectF(30, 84, 24, 12))
    return caminho


def _caminho_nao_empilhar() -> QPainterPath:
    """Caixa embaixo (sustenta) + caixa em cima riscada com X (não
    coloque peso nela)."""
    caminho = QPainterPath()
    caminho.addRect(QRectF(22, 55, 56, 33))
    caminho.addRect(QRectF(30, 22, 40, 33))
    caminho.moveTo(30, 22)
    caminho.lineTo(70, 55)
    caminho.moveTo(70, 22)
    caminho.lineTo(30, 55)
    return caminho


def _caminho_reciclavel() -> QPainterPath:
    """Triângulo de setas se perseguindo (símbolo de reciclagem) — 3
    setas retas, cada uma cobrindo o trecho do MEIO de um lado do
    triângulo (não a aresta inteira, senão as pontas dos 3 lados se
    encostariam nos cantos e a leitura de "3 setas separadas" se perde),
    apontando sempre no sentido horário pra próxima seta."""
    centro = QPointF(50, 54)
    raio = 32
    cantos = [
        QPointF(
            centro.x() + raio * math.cos(math.radians(angulo)),
            centro.y() + raio * math.sin(math.radians(angulo)),
        )
        for angulo in (-90, 30, 150)
    ]
    caminho = QPainterPath()
    for i in range(3):
        inicio, fim = cantos[i], cantos[(i + 1) % 3]
        vetor = fim - inicio
        p_inicio = inicio + vetor * 0.22
        p_fim = inicio + vetor * 0.78
        caminho.moveTo(p_inicio)
        caminho.lineTo(p_fim)

        norma = math.hypot(vetor.x(), vetor.y()) or 1.0
        ux, uy = vetor.x() / norma, vetor.y() / norma
        perp_x, perp_y = -uy, ux
        cabeca = 9.0
        base = p_fim - QPointF(ux * cabeca, uy * cabeca)
        caminho.moveTo(p_fim)
        caminho.lineTo(base + QPointF(perp_x * cabeca * 0.6, perp_y * cabeca * 0.6))
        caminho.moveTo(p_fim)
        caminho.lineTo(base - QPointF(perp_x * cabeca * 0.6, perp_y * cabeca * 0.6))
    return caminho


def _caminho_centro_gravidade() -> QPainterPath:
    """Símbolo ISO 7000-1317 — círculo cruzado, 2 quadrantes opostos
    preenchidos (efeito "xadrez")."""
    raio = 35
    centro = QPointF(50, 50)
    rect = QRectF(centro.x() - raio, centro.y() - raio, raio * 2, raio * 2)
    caminho = QPainterPath()
    caminho.addEllipse(rect)
    caminho.moveTo(centro.x() - raio, centro.y())
    caminho.lineTo(centro.x() + raio, centro.y())
    caminho.moveTo(centro.x(), centro.y() - raio)
    caminho.lineTo(centro.x(), centro.y() + raio)
    # 2 quadrantes preenchidos (topo-esquerda e base-direita)
    for angulo_inicial in (90, 270):
        fatia = QPainterPath()
        fatia.moveTo(centro)
        fatia.arcTo(rect, angulo_inicial, 90)
        fatia.closeSubpath()
        caminho.addPath(fatia)
    return caminho


def _caminho_nao_usar_gancho() -> QPainterPath:
    """Gancho (forma de "J") dentro do símbolo universal de proibição
    (círculo + barra diagonal)."""
    caminho = QPainterPath()
    caminho.moveTo(38, 15)
    caminho.lineTo(38, 55)
    caminho.cubicTo(38, 68, 58, 68, 58, 55)
    caminho.cubicTo(58, 46, 48, 46, 48, 53)
    # círculo de proibição + barra
    caminho.addEllipse(QRectF(6, 6, 88, 88))
    angulo = math.radians(45)
    r = 44
    caminho.moveTo(50 - r * math.cos(angulo), 50 - r * math.sin(angulo))
    caminho.lineTo(50 + r * math.cos(angulo), 50 + r * math.sin(angulo))
    return caminho


_CAMINHO_POR_TIPO = {
    TipoSimbolo.FRAGIL: _caminho_fragil,
    TipoSimbolo.ESTE_LADO_CIMA: _caminho_este_lado_cima,
    TipoSimbolo.MANTER_SECO: _caminho_manter_seco,
    TipoSimbolo.NAO_EMPILHAR: _caminho_nao_empilhar,
    TipoSimbolo.RECICLAVEL: _caminho_reciclavel,
    TipoSimbolo.CENTRO_GRAVIDADE: _caminho_centro_gravidade,
    TipoSimbolo.NAO_USAR_GANCHO: _caminho_nao_usar_gancho,
}

# Tipos cujo caminho tem áreas preenchidas de propósito (não é só contorno)
# — os outros são só traço, senão iam sair "borrados" de preto sólido.
_TIPOS_COM_PREENCHIMENTO = {TipoSimbolo.CENTRO_GRAVIDADE}


class ElementoSimbolo(ElementoMockup):
    def __init__(
        self,
        tipo: TipoSimbolo = TipoSimbolo.FRAGIL,
        cor_tinta: CorImpressao | None = None,
        parent=None,
    ) -> None:
        super().__init__(largura=_TAMANHO_PADRAO_MM, altura=_TAMANHO_PADRAO_MM, parent=parent)
        self._tipo = tipo
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)

    @property
    def tipo(self) -> TipoSimbolo:
        return self._tipo

    def definir_tipo(self, tipo: TipoSimbolo) -> None:
        self._tipo = tipo
        self.update()

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    def caminho_normalizado(self) -> QPainterPath:
        """O pictograma em si, no espaço de referência 0..100 — exposto
        (não só usado internamente) porque `corel_bridge.py` precisa dos
        MESMOS pontos pra recriar o desenho lá (ver `_desenhar_simbolo_cdr`,
        que achata esse caminho em segmentos de reta com
        `toSubpathPolygons()` em vez de tentar reproduzir curva por
        curva via COM)."""
        return _CAMINHO_POR_TIPO[self._tipo]()

    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        espessura = _ESPACO_REFERENCIA * 0.018
        caneta = QPen(cor, espessura)
        caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
        caneta.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(caneta)
        painter.setBrush(QBrush(cor) if self._tipo in _TIPOS_COM_PREENCHIMENTO else Qt.BrushStyle.NoBrush)
        painter.save()
        painter.scale(self._largura / _ESPACO_REFERENCIA, self._altura / _ESPACO_REFERENCIA)
        painter.drawPath(self.caminho_normalizado())
        painter.restore()

    def clonar(self) -> "ElementoSimbolo":
        novo = ElementoSimbolo(tipo=self._tipo, cor_tinta=self._cor_tinta)
        self._copiar_geometria_para(novo)
        return novo
