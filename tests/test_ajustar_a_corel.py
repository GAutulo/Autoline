"""Menu "Ajustar a" do CorelDRAW: cada fonte de encaixe liga/desliga."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(1)
    j.canvas.definir_snap_ativo(True)
    j.canvas.definir_grade_visivel(False)  # isola as outras fontes
    yield j
    j.close()


def _ret(janela, x, y):
    el = ElementoRetangulo(largura=40, altura=20, cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    janela.canvas.adicionar_elemento_mockup(el, QPointF(x, y))
    return el


def test_pagina_gruda_na_borda_da_chapa(janela):
    el = _ret(janela, 500, 150)
    canvas = janela.canvas
    for chave in ("objetos", "guias"):
        canvas.definir_ajustar_a(chave, False)
    ajustada = canvas._calcular_snap(el, QPointF(1.0, 150))
    assert ajustada.x() == pytest.approx(0.0)
    canvas.definir_ajustar_a("pagina", False)
    assert canvas._calcular_snap(el, QPointF(1.0, 150)).x() == pytest.approx(1.0)


def test_objetos_desligado_ignora_outro_elemento(janela):
    canvas = janela.canvas
    canvas.definir_ajustar_a("pagina", False)
    canvas.definir_ajustar_a("guias", False)
    _ret(janela, 300, 100)
    movido = _ret(janela, 500, 300)
    assert canvas._calcular_snap(movido, QPointF(301.0, 300)).x() == pytest.approx(300.0)
    canvas.definir_ajustar_a("objetos", False)
    assert canvas._calcular_snap(movido, QPointF(301.0, 300)).x() == pytest.approx(301.0)


def test_atalhos_alt_z_ctrl_y_e_menu_acompanha(janela):
    canvas = janela.canvas
    assert canvas.ajustar_a("objetos") and canvas.ajustar_a("grade")
    QTest.keyClick(canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.AltModifier)
    assert not canvas.ajustar_a("objetos")
    assert not janela._acoes_ajustar_a["objetos"].isChecked()
    QTest.keyClick(canvas, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert not canvas.ajustar_a("grade")
    janela._acoes_ajustar_a["grade"].setChecked(True)
    assert canvas.ajustar_a("grade")
