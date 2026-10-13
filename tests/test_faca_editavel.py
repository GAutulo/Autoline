"""Faca editável na tela Dieline: mover linhas/pontas ligadas, linha nova,
tipo, remover, desfazer, trava das medidas e envio ao CorelDRAW."""

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

from gerador_layout.models import TipoLinha  # noqa: E402

ESQ = Qt.MouseButton.LeftButton
NENHUM = Qt.MouseButton.NoButton
SEM = Qt.KeyboardModifier.NoModifier


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(0)
    j.canvas.definir_snap_ativo(True)
    QApplication.processEvents()
    yield j
    j.close()


def _mouse(janela, tipo, ponto, botao, botoes, mods=SEM):
    vista = janela.canvas
    pos = QPointF(vista.mapFromScene(QPointF(*ponto)))
    evento = QMouseEvent(tipo, pos, vista.viewport().mapToGlobal(pos), botao, botoes, mods)
    QApplication.sendEvent(vista.viewport(), evento)


def _arrastar(janela, de, ate, mods=SEM):
    _mouse(janela, QEvent.Type.MouseButtonPress, de, ESQ, ESQ, mods)
    _mouse(janela, QEvent.Type.MouseMove, ((de[0] + ate[0]) / 2, (de[1] + ate[1]) / 2), NENHUM, ESQ, mods)
    _mouse(janela, QEvent.Type.MouseMove, ate, NENHUM, ESQ, mods)
    _mouse(janela, QEvent.Type.MouseButtonRelease, ate, ESQ, NENHUM, mods)


def _pixel(janela):
    return 1.0 / janela.canvas.transform().m11()


def _vinco_horizontal(janela):
    linhas = janela.canvas.linhas_faca()
    for i, l in enumerate(linhas):
        if l.tipo == TipoLinha.VINCO and abs(l.y1 - l.y2) < 1e-6 and abs(l.x2 - l.x1) > 50:
            return i, l
    raise AssertionError("sem vinco horizontal")


def test_arrastar_vinco_leva_as_pontas_ligadas_e_trava_medidas(janela):
    canvas = janela.canvas
    calculada = [(l.x1, l.y1, l.x2, l.y2) for l in canvas.linhas_faca()]
    i, vinco = _vinco_horizontal(janela)
    y0 = vinco.y1
    ligadas_antes = canvas._pontas_coincidentes(canvas.linhas_faca(), vinco.x1, vinco.y1)
    assert len(ligadas_antes) > 1  # o vinco encosta em outras linhas

    janela._acoes_faca["forma"].trigger()
    em_t = [k for k, l in enumerate(canvas.linhas_faca()) if k != i and l.tipo == TipoLinha.VINCO and abs(l.y1 - y0) < 1e-6 and abs(l.x1 - l.x2) < 1e-6]
    assert em_t  # vincos verticais chegando no meio do horizontal
    meio = (354.0, y0)  # entre duas junções, longe das pontas
    _arrastar(janela, meio, (meio[0], y0 + 12), Qt.KeyboardModifier.ShiftModifier)

    assert canvas.faca_editada
    movida = canvas.linhas_faca()[i]
    assert movida.y1 == pytest.approx(y0 + 12, abs=_pixel(janela) * 1.5)
    for k, qual in ligadas_antes:
        l = canvas.linhas_faca()[k]
        y = l.y1 if qual == 1 else l.y2
        assert y == pytest.approx(movida.y1)  # a faca não "abriu"
    for k in em_t:
        assert canvas.linhas_faca()[k].y1 == pytest.approx(movida.y1)  # a junção em "T" acompanhou
    assert not janela._grupo_medidas_cla.isEnabled() and not janela._grupo_tipo.isEnabled()
    assert not janela.aviso_faca_editada.isHidden()

    canvas.pilha_desfazer.undo()
    assert not canvas.faca_editada
    assert [(l.x1, l.y1, l.x2, l.y2) for l in canvas.linhas_faca()] == calculada
    assert janela._grupo_medidas_cla.isEnabled()


def test_alt_solta_a_ponta(janela):
    canvas = janela.canvas
    i, vinco = _vinco_horizontal(janela)
    janela._acoes_faca["forma"].trigger()
    ponta = (vinco.x2, vinco.y2)
    outras = [k for k, _q in canvas._pontas_coincidentes(canvas.linhas_faca(), *ponta) if k != i]
    _arrastar(janela, ponta, (ponta[0], ponta[1] + 15), Qt.KeyboardModifier.AltModifier)
    linhas = canvas.linhas_faca()
    assert linhas[i].y2 == pytest.approx(ponta[1] + 15, abs=_pixel(janela) * 1.5)
    for k in outras:
        assert (linhas[k].x1, linhas[k].y1) == ponta or (linhas[k].x2, linhas[k].y2) == ponta


def test_nova_linha_de_vinco_gruda_nas_pontas_tipo_e_remover(janela):
    canvas = janela.canvas
    linhas = canvas.linhas_faca()
    a = (linhas[0].x1, linhas[0].y1)
    b = (linhas[0].x2, linhas[0].y2)
    antes = len(linhas)
    janela._acoes_faca["vinco"].trigger()
    _arrastar(janela, (a[0] + 0.4, a[1] + 0.3), (b[0] - 0.3, b[1] + 0.2))
    nova = canvas.linhas_faca()[-1]
    assert len(canvas.linhas_faca()) == antes + 1 and nova.tipo == TipoLinha.VINCO
    assert (nova.x1, nova.y1, nova.x2, nova.y2) == pytest.approx((*a, *b))  # grudou nas pontas
    assert canvas.linha_faca_selecionada_indice == antes

    canvas.definir_tipo_linha_selecionada(TipoLinha.MEIO_CORTE)
    assert canvas.linhas_faca()[-1].tipo == TipoLinha.MEIO_CORTE
    QTest.keyClick(canvas, Qt.Key.Key_Delete)
    assert len(canvas.linhas_faca()) == antes


def test_recalculo_sem_mudar_geometria_mantem_edicao_e_descartar(janela):
    canvas = janela.canvas
    janela._acoes_faca["forma"].trigger()
    i, vinco = _vinco_horizontal(janela)
    _arrastar(janela, ((vinco.x1 + vinco.x2) / 2, vinco.y1), ((vinco.x1 + vinco.x2) / 2, vinco.y1 + 8))
    editadas = [(l.x1, l.y1, l.x2, l.y2) for l in canvas.linhas_faca()]
    janela._chips_cor["Vermelho"][0].setChecked(True)  # recalcula (legenda) sem mudar a faca
    assert canvas.faca_editada
    assert [(l.x1, l.y1, l.x2, l.y2) for l in canvas.linhas_faca()] == editadas
    canvas.descartar_edicoes_faca()
    assert not canvas.faca_editada and janela._grupo_medidas_cla.isEnabled()


def test_envio_ao_corel_usa_a_faca_editada(janela, monkeypatch):
    from gerador_layout.ui import corel_bridge

    canvas = janela.canvas
    janela._acoes_faca["corte"].trigger()
    _arrastar(janela, (10, -20), (60, -20))
    enviado = {}
    monkeypatch.setattr(corel_bridge, "conectar", lambda: object())
    monkeypatch.setattr(corel_bridge, "desenhar_layout", lambda app, layout, els: enviado.setdefault("linhas", layout.linhas))
    janela._corel_app = None
    janela._exportar_corel()
    assert len(enviado["linhas"]) == len(canvas.linhas_faca())
    assert enviado["linhas"][-1].tipo == TipoLinha.CORTE


def test_faca_nao_edita_no_layout(janela):
    canvas = janela.canvas
    janela._acoes_faca["forma"].trigger()
    assert canvas.editando_faca
    janela.abas_tela.setCurrentIndex(1)
    assert not canvas.editando_faca and janela.barra_faca.isHidden()
    janela.abas_tela.setCurrentIndex(0)
    assert janela._acoes_faca["navegar"].isChecked()
