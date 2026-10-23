"""JPG sai quadrado, com o layout centralizado: chapa comprida não fica
"esticada" onde a imagem é mostrada num quadrado (Explorer, WhatsApp)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.models import CorImpressao, TipoCaixa  # noqa: E402
from gerador_layout.ui import exportacao  # noqa: E402
from gerador_layout.ui.main_window import JanelaPrincipal  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402


def test_jpg_quadrado_com_o_layout_no_centro(tmp_path):
    j = JanelaPrincipal()
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE))
    j.spin_comprimento.setValue(136)
    j.spin_largura.setValue(16)
    j.spin_altura.setValue(9)
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    centro = j.canvas.retangulo_pagina().center()
    vermelho = ElementoRetangulo(largura=10, altura=6, cor_tinta=CorImpressao("VERMELHO", 255, 0, 0), preenchido=True)
    j.canvas.adicionar_elemento_mockup(vermelho, centro - QPointF(5, 3))
    caminho = tmp_path / "layout.jpg"
    exportacao.exportar_jpg(j.canvas.cena, j.canvas.layout_efetivo, str(caminho), dpi=150)
    imagem = QImage(str(caminho))
    assert imagem.width() == imagem.height()  # quadrado, a chapa é bem mais larga que alta
    assert imagem.dotsPerMeterX() == pytest.approx(150 / 0.0254, rel=0.01)  # tamanho real gravado
    meio = imagem.width() // 2
    cor = imagem.pixelColor(meio, meio)
    assert cor.red() > 200 and cor.green() < 60  # o centro do layout no centro da imagem
    for y in (3, imagem.height() - 4):  # sobra branca em cima e embaixo
        topo = imagem.pixelColor(meio, y)
        assert min(topo.red(), topo.green(), topo.blue()) > 245
    j.close()
