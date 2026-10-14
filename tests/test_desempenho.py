"""Cache de desenho (desempenho) não pode estragar exportação nem 3D."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsItem  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui import exportacao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoElipse  # noqa: E402
from gerador_layout.ui.mockup_texto import ElementoTexto  # noqa: E402


def test_elementos_em_cache_mas_exportacao_vetorial(tmp_path):
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1200, 800)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    canvas = j.canvas
    texto = ElementoTexto("MARCA", cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    canvas.adicionar_elemento_mockup(texto, QPointF(300, 200))
    canvas.adicionar_elemento_mockup(ElementoElipse(largura=40, altura=30, cor_tinta=CorImpressao("PRETO", 0, 0, 0)), QPointF(400, 150))
    assert texto.cacheMode() == QGraphicsItem.CacheMode.DeviceCoordinateCache
    canvas.viewport().repaint()  # popula o cache de tela
    QApplication.processEvents()
    destino = tmp_path / "saida.svg"
    exportacao.exportar_svg(canvas.cena, canvas.layout_atual, str(destino))
    svg = destino.read_text(encoding="utf-8")
    assert "<image" not in svg  # nada virou imagem de cache
    assert svg.count("<path") >= 2
    assert texto.cacheMode() == QGraphicsItem.CacheMode.DeviceCoordinateCache  # cache religado
    j.close()
