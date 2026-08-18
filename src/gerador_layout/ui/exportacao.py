"""Exportação do layout desenhado no canvas para arquivos.

SVG e PDF saem vetoriais (qualidade perfeita em qualquer escala — e como
as coordenadas da cena já são em milímetros, o PDF sai na escala real
1:1). JPG sai em raster, com supersampling pra ficar nítido.

Pro CorelDRAW em si não existe exportação de arquivo (.cdr é formato
proprietário, sem biblioteca aberta capaz de gravá-lo) — em vez disso, o
layout é desenhado direto num documento do CorelDRAW por automação COM,
ver `corel_bridge.py`.
"""

from __future__ import annotations

from PySide6.QtCore import QMarginsF, QRectF, QSize, QSizeF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPen,
)
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
)

from ..models import CorImpressao

_FONTE_LEGENDA = QFont("Segoe UI", 8)
_MARGEM_LEGENDA = 4.0  # mm entre o desenho e a legenda, e ao redor do texto


class _LegendaExportacao:
    """Desenha a legenda de cores como itens reais da cena, só durante a
    exportação (adicionados antes de renderizar, removidos logo em
    seguida) — assim o SVG/PDF/JPG sai com a legenda de verdade, sem
    afetar a pré-visualização em tela (que usa um widget à parte, ver
    `PainelLegendaCores` em `preview_canvas.py`).

    Fica ACIMA do desenho (acima de `rect_desenho.top()`) e usa
    QFontMetricsF pra medir o texto de verdade, em vez de estimar a
    largura — as duas causas do bug de viewBox que existia quando a
    legenda ainda fazia parte da cena permanente."""

    def __init__(self, scene: QGraphicsScene, cores: list[CorImpressao], rect_desenho: QRectF) -> None:
        self._scene = scene
        self._itens: list = []
        if not cores:
            return

        metrics = QFontMetricsF(_FONTE_LEGENDA)
        x = 0.0
        y = rect_desenho.top() - _MARGEM_LEGENDA - metrics.height()
        self._adicionar_texto("CORES:", x, y, QColor(30, 30, 35))
        x += metrics.horizontalAdvance("CORES:") + 6

        for cor in cores:
            bolinha = QGraphicsEllipseItem(QRectF(x, y + 1.5, 5, 5))
            bolinha.setBrush(QBrush(QColor(cor.r, cor.g, cor.b)))
            bolinha.setPen(QPen(QColor(90, 90, 90), 0.25))
            scene.addItem(bolinha)
            self._itens.append(bolinha)
            x += 8

            self._adicionar_texto(cor.nome, x, y, QColor(30, 30, 35))
            x += metrics.horizontalAdvance(cor.nome) + 10

    def _adicionar_texto(self, texto: str, x: float, y: float, cor: QColor) -> None:
        item = QGraphicsSimpleTextItem(texto)
        item.setFont(_FONTE_LEGENDA)
        item.setBrush(QBrush(cor))
        item.setPos(x, y)
        self._scene.addItem(item)
        self._itens.append(item)

    def remover(self) -> None:
        for item in self._itens:
            self._scene.removeItem(item)


def _rect_com_legenda(scene: QGraphicsScene, cores: list[CorImpressao]) -> tuple[QRectF, _LegendaExportacao]:
    rect_desenho = scene.itemsBoundingRect()
    legenda = _LegendaExportacao(scene, cores, rect_desenho)
    rect_final = scene.itemsBoundingRect() if legenda._itens else rect_desenho
    return rect_final, legenda


class _PenasExportacao:
    """Troca temporariamente o QPen cosmetic das linhas técnicas (usado na
    pré-visualização em tela pra manter espessura constante em qualquer
    zoom, ver `_desenhar_linhas_tecnicas` em `preview_canvas.py`) por um
    pen não-cosmetic equivalente, só durante a exportação — os motores de
    pintura vetorial/raster usados no `scene.render()` de exportação não
    preservam corretamente o dash pattern de um pen cosmetic (ele sai
    sólido mesmo em linhas tracejadas como o vinco). Restaura os pens
    originais depois do render."""

    def __init__(self, scene: QGraphicsScene) -> None:
        self._originais: list[tuple[QGraphicsLineItem, QPen]] = []
        for item in scene.items():
            if not isinstance(item, QGraphicsLineItem):
                continue
            pen_original = item.pen()
            if not pen_original.isCosmetic():
                continue
            self._originais.append((item, pen_original))
            pen_exportacao = QPen(pen_original)
            pen_exportacao.setCosmetic(False)
            item.setPen(pen_exportacao)

    def restaurar(self) -> None:
        for item, pen_original in self._originais:
            item.setPen(pen_original)


def exportar_svg(scene: QGraphicsScene, cores_legenda: list[CorImpressao], caminho: str) -> None:
    rect, legenda = _rect_com_legenda(scene, cores_legenda)
    penas = _PenasExportacao(scene)
    try:
        # QSvgGenerator só aceita resolução em DPI inteiro. Pra converter
        # "unidades da cena = mm" em tamanho físico SEM erro de arredondamento,
        # usa um fator de escala 100 com resolução 2540 DPI — 2540/100 = 25.4
        # (mm por polegada) exatos, então 1 unidade da cena = 1 mm no arquivo.
        fator = 100
        gerador = QSvgGenerator()
        gerador.setFileName(caminho)
        gerador.setSize(QSize(round(rect.width() * fator), round(rect.height() * fator)))
        gerador.setViewBox(rect)
        gerador.setResolution(2540)
        gerador.setTitle("Layout de caixa")
        gerador.setDescription("Gerado pelo LayoutCorel")

        painter = QPainter(gerador)
        try:
            scene.render(painter, source=rect)
        finally:
            painter.end()
    finally:
        penas.restaurar()
        legenda.remover()


def exportar_pdf(scene: QGraphicsScene, cores_legenda: list[CorImpressao], caminho: str) -> None:
    rect, legenda = _rect_com_legenda(scene, cores_legenda)
    penas = _PenasExportacao(scene)
    try:
        # As coordenadas da cena já são em mm — a página do PDF sai com o
        # tamanho exato do layout, então o desenho fica na escala real 1:1,
        # sem margens.
        tamanho_pagina = QPageSize(
            QSizeF(max(rect.width(), 1.0), max(rect.height(), 1.0)),
            QPageSize.Unit.Millimeter,
        )
        layout_pagina = QPageLayout(
            tamanho_pagina, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)
        )

        impressora = QPrinter(QPrinter.PrinterMode.HighResolution)
        impressora.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        impressora.setOutputFileName(caminho)
        impressora.setPageLayout(layout_pagina)

        painter = QPainter(impressora)
        try:
            scene.render(painter, source=rect)
        finally:
            painter.end()
    finally:
        penas.restaurar()
        legenda.remover()


def exportar_jpg(
    scene: QGraphicsScene, cores_legenda: list[CorImpressao], caminho: str, *, supersample: int = 4
) -> None:
    rect, legenda = _rect_com_legenda(scene, cores_legenda)
    penas = _PenasExportacao(scene)
    try:
        largura = max(1, int(rect.width() * supersample))
        altura = max(1, int(rect.height() * supersample))

        imagem = QImage(largura, altura, QImage.Format.Format_RGB32)
        imagem.fill(0xFFFFFFFF)  # fundo branco

        painter = QPainter(imagem)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            scene.render(painter, source=rect)
        finally:
            painter.end()
    finally:
        penas.restaurar()
        legenda.remover()

    imagem.save(caminho, "JPG", quality=92)
