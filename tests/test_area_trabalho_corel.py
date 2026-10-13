"""Área de trabalho estilo CorelDRAW: caixa de ferramentas com flyouts,
paleta de cores e barra de status (ver REFERENCIA_CORELDRAW.md)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402
from gerador_layout.ui.preview_canvas import FerramentaMockup  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(1)
    yield j
    j.close()


def _retangulo_selecionado(janela):
    el = ElementoRetangulo(largura=40, altura=20, cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    janela.canvas.adicionar_elemento_mockup(el, QPointF(50, 50))
    janela.canvas.cena.clearSelection()
    el.setSelected(True)
    return el


def test_disposicao_igual_ao_coreldraw(janela):
    assert janela.toolBarArea(janela.barra_mockup) == Qt.ToolBarArea.LeftToolBarArea
    assert janela.barra_mockup.orientation() == Qt.Orientation.Vertical
    assert janela.toolBarArea(janela.barra_paleta) == Qt.ToolBarArea.RightToolBarArea
    assert not janela.barra_paleta.isHidden() and not janela.barra_organizar.isHidden()
    janela.abas_tela.setCurrentIndex(0)
    assert janela.barra_paleta.isHidden() and janela.barra_mockup.isHidden()


def test_flyout_mostra_a_ferramenta_ativa(janela):
    botao = next(b for b in janela._botoes_flyout if janela._acoes_ferramenta[FerramentaMockup.TABELA] in b.acoes)
    assert botao.defaultAction() is janela._acoes_ferramenta[FerramentaMockup.POLIGONO]
    janela.canvas.definir_ferramenta(FerramentaMockup.TABELA)
    assert botao.defaultAction() is janela._acoes_ferramenta[FerramentaMockup.TABELA]
    assert janela._acoes_ferramenta[FerramentaMockup.TABELA].isChecked()


def test_paleta_esquerdo_preenche_direito_contorno(janela):
    el = _retangulo_selecionado(janela)
    janela._aplicar_cor_paleta(("Vermelho", (255, 0, 0)), contorno=False)
    assert el.preenchido and (el.cor_tinta.r, el.cor_tinta.g, el.cor_tinta.b) == (255, 0, 0)
    assert janela._chips_cor["Vermelho"][0].isChecked()  # tinta entra na legenda
    janela._aplicar_cor_paleta(("Azul", (0, 0, 255)), contorno=True)
    assert not el.preenchido and el.cor_tinta.b == 255
    janela._aplicar_cor_paleta(("Verde", (0, 160, 0)), contorno=False)
    janela._aplicar_cor_paleta(None, contorno=False)
    assert not el.preenchido


def test_status_mostra_objeto_e_amostras(janela):
    el = _retangulo_selecionado(janela)
    el.definir_preenchido(True)
    janela._ao_selecao_mockup_mudar()
    status = janela.painel_status
    assert "Retângulo" in status.rotulo_objeto.text()
    assert "40,0 × 20,0 mm" in status.rotulo_objeto.text()
    assert status.amostra_preenchimento._cor is not None
    status.definir_posicao(QPointF(12.34, 5.0))
    assert "12,3" in status.rotulo_posicao.text()


def test_canvas_tem_pagina_da_chapa(janela):
    pagina = janela.canvas.retangulo_pagina()
    layout = janela.canvas.layout_atual
    assert pagina.width() == pytest.approx(layout.largura_total)
    assert pagina.height() == pytest.approx(layout.altura_total)
