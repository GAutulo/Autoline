"""Coisas de tela (alças, grade, encaixe) acompanham o zoom e a escala do
desenho; ir pro 3D e voltar não perde o enquadramento."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402
from gerador_layout.ui.mockup_itens import ElementoMockup  # noqa: E402


@pytest.fixture
def janela():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    QApplication.processEvents()
    yield j
    j.close()


def _processar():
    for _ in range(5):
        QApplication.processEvents()


def test_ir_pro_3d_e_voltar_mantem_o_desenho_na_tela(janela):
    canvas = janela.canvas
    for medidas in ((300, 200, 150), (80.5, 55, 6)):  # tamanho normal e escala reduzida
        janela.spin_comprimento.setValue(medidas[0])
        janela.spin_largura.setValue(medidas[1])
        janela.spin_altura.setValue(medidas[2])
        for aba in (2, 0, 1, 2, 1, 0):
            janela.abas_tela.setCurrentIndex(aba)
            _processar()
        pagina = canvas.retangulo_pagina()
        centro = canvas.mapFromScene(pagina.center())
        assert canvas.viewport().rect().contains(centro)
        largura_na_tela = pagina.width() * canvas.transform().m11()
        assert largura_na_tela > canvas.viewport().width() * 0.5  # ocupa a tela, não virou um ponto


def test_alcas_em_pixels_acompanham_o_zoom(janela):
    canvas = janela.canvas
    janela.spin_comprimento.setValue(30)
    janela.spin_largura.setValue(20)
    janela.spin_altura.setValue(15)
    janela.abas_tela.setCurrentIndex(1)
    _processar()
    el = ElementoRetangulo(largura=3, altura=2, cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    canvas.adicionar_elemento_mockup(el, QPointF(10, 10))
    canvas.ajustar_a_tela()
    zoom = canvas.transform().m11()
    assert ElementoMockup.mm_por_px == pytest.approx(1.0 / zoom)
    margem_px = (el.boundingRect().width() - el.largura) / 2 * zoom
    assert 20 < margem_px < 60  # a alça de rotação fica a ~24 px, em qualquer escala
    canvas.scale(2, 2)
    canvas._zoom_atual *= 2
    canvas.zoom_alterado.emit(canvas._zoom_atual)
    margem_px_2 = (el.boundingRect().width() - el.largura) / 2 * canvas.transform().m11()
    assert margem_px_2 == pytest.approx(margem_px, rel=0.01)


def test_grade_e_encaixe_acompanham_a_escala(janela):
    canvas = janela.canvas
    janela.spin_comprimento.setValue(30)
    janela.spin_largura.setValue(20)
    janela.spin_altura.setValue(15)
    _processar()
    canvas.ajustar_a_tela()
    px_por_mm = canvas.transform().m11()
    passo = canvas.passo_grade()
    assert 12 <= passo * px_por_mm <= 120  # a grade aparece com espaçamento legível
    assert canvas.limiar_snap() <= 10.0 / px_por_mm + 1e-9


def test_guia_nao_estraga_o_ajustar_a_tela(janela):
    canvas = janela.canvas
    canvas.ajustar_a_tela()
    zoom = canvas.transform().m11()
    canvas.adicionar_guia("v", 500)
    canvas.adicionar_guia("h", 100)
    for aba in (2, 0):  # o caso relatado: ir pro 3D e voltar
        janela.abas_tela.setCurrentIndex(aba)
        _processar()
    canvas.ajustar_a_tela()
    assert canvas.transform().m11() == pytest.approx(zoom, rel=0.05)
