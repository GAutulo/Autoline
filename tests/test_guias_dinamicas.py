"""Guias dinâmicas (CorelDRAW): o cursor alinha com nós ao desenhar."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.ui.mockup_curva import ElementoCurva  # noqa: E402
from gerador_layout.ui.preview_canvas import FerramentaMockup  # noqa: E402

ESQ = Qt.MouseButton.LeftButton
NENHUM = Qt.MouseButton.NoButton


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    j.canvas.definir_snap_ativo(False)  # isola as guias do encaixe em nó
    QApplication.processEvents()
    yield j
    j.close()


def _mouse(janela, tipo, ponto, botao, botoes):
    vista = janela.canvas
    pos = QPointF(vista.mapFromScene(QPointF(*ponto)))
    evento = QMouseEvent(tipo, pos, vista.viewport().mapToGlobal(pos), botao, botoes, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(vista.viewport(), evento)


def _arrastar(janela, de, ate):
    _mouse(janela, QEvent.Type.MouseButtonPress, de, ESQ, ESQ)
    _mouse(janela, QEvent.Type.MouseMove, ate, NENHUM, ESQ)
    _mouse(janela, QEvent.Type.MouseButtonRelease, ate, ESQ, NENHUM)


def test_retangulo_alinha_com_no_da_faca(janela):
    canvas = janela.canvas
    canto = canvas.linhas_faca()[1]  # corte de cima: começa em (204.5, 0)
    alvo_x = canto.x1
    canvas.definir_ferramenta(FerramentaMockup.RETANGULO)
    um_pixel = 1.0 / canvas.transform().m11()
    _arrastar(janela, (alvo_x - 60, 130), (alvo_x + 2 * um_pixel, 190))  # perto, mas não em cima
    ret = canvas.elementos_mockup[-1]
    assert ret.pos().x() + ret.largura == pytest.approx(alvo_x, abs=1e-6)  # borda direita na guia
    assert not canvas._linhas_dinamicas  # some ao soltar


def test_pairar_mostra_guia_e_atalho_desliga(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.RETANGULO)
    no = canvas.linhas_faca()[0]
    _mouse(janela, QEvent.Type.MouseMove, (no.x1 + 120, no.y1 + 0.3), NENHUM, NENHUM)
    assert canvas._linhas_dinamicas
    origem, ponto = canvas._linhas_dinamicas[-1]
    assert ponto.y() == pytest.approx(no.y1)

    QTest.keyClick(canvas, Qt.Key.Key_D, Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier)
    assert not canvas.guias_dinamicas and not janela._acao_guias_dinamicas.isChecked()
    _mouse(janela, QEvent.Type.MouseMove, (no.x1 + 120, no.y1 + 0.3), NENHUM, NENHUM)
    assert not canvas._linhas_dinamicas
    janela._acao_guias_dinamicas.setChecked(True)
    assert canvas.guias_dinamicas


def test_bezier_alinha_com_o_no_anterior(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.BEZIER)
    um_pixel = 1.0 / canvas.transform().m11()
    _arrastar(janela, (300, 160), (300, 160))
    _arrastar(janela, (300 + 2 * um_pixel, 215), (300 + 2 * um_pixel, 215))  # quase na vertical do 1º
    QTest.keyClick(canvas, Qt.Key.Key_Return)
    curva = canvas.elementos_mockup[-1]
    assert isinstance(curva, ElementoCurva)
    a, b = (curva.mapToScene(n.p) for n in curva.subcaminhos_locais()[0].nos)
    assert a.x() == pytest.approx(b.x(), abs=1e-6)


def test_linha_nova_da_faca_alinha(janela):
    canvas = janela.canvas
    janela.abas_tela.setCurrentIndex(0)
    janela._acoes_faca["corte"].trigger()
    um_pixel = 1.0 / canvas.transform().m11()
    no = canvas.linhas_faca()[0]  # (4, 0)
    _arrastar(janela, (no.x1 - 40, -30), (no.x1 + 2 * um_pixel, -60))
    nova = canvas.linhas_faca()[-1]
    assert nova.x2 == pytest.approx(no.x1, abs=1e-6)
