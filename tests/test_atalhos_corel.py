"""Atalhos e gestos do CorelDRAW na tela de Layout (ver REFERENCIA_CORELDRAW.md)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402
from gerador_layout.ui.mockup_itens import Alca, GrupoMockup  # noqa: E402
from gerador_layout.ui.preview_canvas import FerramentaMockup  # noqa: E402

TOL = 1e-6


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(1)  # Layout
    yield j
    j.close()


def _retangulo(janela, x, y, largura=40.0, altura=20.0):
    el = ElementoRetangulo(largura=largura, altura=altura, cor_tinta=CorImpressao("Preto", 0, 0, 0))
    janela.canvas.adicionar_elemento_mockup(el, QPointF(x, y))
    return el


def _selecionar(janela, *elementos):
    janela.canvas.cena.clearSelection()
    for el in elementos:
        el.setSelected(True)


def _tecla(janela, tecla, mods=Qt.KeyboardModifier.NoModifier):
    QTest.keyClick(janela.canvas, tecla, mods)


def test_alinhar_um_elemento_com_a_chapa(janela):
    el = _retangulo(janela, 100, 80)
    pagina = janela.canvas.retangulo_pagina()
    _selecionar(janela, el)
    _tecla(janela, Qt.Key.Key_L)
    assert el.pos().x() == pytest.approx(pagina.left())
    _tecla(janela, Qt.Key.Key_R)
    assert el.pos().x() + el.largura == pytest.approx(pagina.right())
    _tecla(janela, Qt.Key.Key_T)
    assert el.pos().y() == pytest.approx(pagina.top())
    _tecla(janela, Qt.Key.Key_B)
    assert el.pos().y() + el.altura == pytest.approx(pagina.bottom())


def test_alinhar_entre_si_e_desfazer(janela):
    a = _retangulo(janela, 10, 10)
    b = _retangulo(janela, 200, 50)
    _selecionar(janela, a, b)
    _tecla(janela, Qt.Key.Key_T)
    assert a.pos().y() == pytest.approx(10) and b.pos().y() == pytest.approx(10)
    janela.canvas.pilha_desfazer.undo()
    assert b.pos().y() == pytest.approx(50)


def test_p_centraliza_na_chapa(janela):
    el = _retangulo(janela, 5, 5)
    _selecionar(janela, el)
    _tecla(janela, Qt.Key.Key_P)
    centro = el.retangulo_conteudo_cena().center()
    pagina = janela.canvas.retangulo_pagina()
    assert (centro.x(), centro.y()) == pytest.approx((pagina.center().x(), pagina.center().y()))


def test_ctrl_a_e_ctrl_u(janela):
    a = _retangulo(janela, 10, 10)
    b = _retangulo(janela, 80, 10)
    janela.canvas.cena.clearSelection()
    _tecla(janela, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    assert a.isSelected() and b.isSelected()
    _tecla(janela, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    assert any(isinstance(e, GrupoMockup) for e in janela.canvas.elementos_mockup)
    _tecla(janela, Qt.Key.Key_U, Qt.KeyboardModifier.ControlModifier)
    assert not any(isinstance(e, GrupoMockup) for e in janela.canvas.elementos_mockup)


def test_mais_numerico_duplica_no_lugar(janela):
    el = _retangulo(janela, 30, 40)
    _selecionar(janela, el)
    antes = len(janela.canvas.elementos_mockup)
    _tecla(janela, Qt.Key.Key_Plus, Qt.KeyboardModifier.KeypadModifier)
    assert len(janela.canvas.elementos_mockup) == antes + 1
    copia = janela.canvas.elementos_mockup[-1]
    assert copia.isSelected() and not el.isSelected()
    assert copia.pos() == el.pos()


def test_ordem_um_nivel(janela):
    a = _retangulo(janela, 10, 10)
    b = _retangulo(janela, 20, 20)
    a.setZValue(1)
    b.setZValue(2)
    _selecionar(janela, a)
    _tecla(janela, Qt.Key.Key_PageUp, Qt.KeyboardModifier.ControlModifier)
    assert a.zValue() > b.zValue()
    _tecla(janela, Qt.Key.Key_PageDown, Qt.KeyboardModifier.ControlModifier)
    assert a.zValue() < b.zValue()


def test_teclas_de_ferramenta_e_espaco(janela):
    canvas = janela.canvas
    _tecla(janela, Qt.Key.Key_F6)
    assert canvas.ferramenta_ativa == FerramentaMockup.RETANGULO
    _tecla(janela, Qt.Key.Key_Space)
    assert canvas.ferramenta_ativa == FerramentaMockup.SELECIONAR
    _tecla(janela, Qt.Key.Key_Space)
    assert canvas.ferramenta_ativa == FerramentaMockup.RETANGULO
    _tecla(janela, Qt.Key.Key_F7)
    assert canvas.ferramenta_ativa == FerramentaMockup.ELIPSE
    _tecla(janela, Qt.Key.Key_F8)
    assert canvas.ferramenta_ativa == FerramentaMockup.TEXTO
    _tecla(janela, Qt.Key.Key_Y)
    assert canvas.ferramenta_ativa == FerramentaMockup.POLIGONO


def test_ctrl_seta_micro_deslocamento(janela):
    el = _retangulo(janela, 50, 50)
    _selecionar(janela, el)
    _tecla(janela, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
    from gerador_layout.ui import configuracoes

    assert el.pos().x() == pytest.approx(50 + configuracoes.passo_nudge_mm()[0] / 10.0)


def test_desenho_ctrl_quadrado_shift_centro(janela):
    canvas = janela.canvas
    canvas._ponto_inicial_criacao = QPointF(100, 100)
    ctrl, shift = Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier
    assert canvas._retangulo_de_criacao(QPointF(130, 110), ctrl) == QRectF(100, 100, 30, 30)
    assert canvas._retangulo_de_criacao(QPointF(130, 110), shift) == QRectF(70, 90, 60, 20)
    assert canvas._retangulo_de_criacao(QPointF(130, 110), ctrl | shift) == QRectF(70, 70, 60, 60)
    fim = canvas._fim_linha_de_criacao(QPointF(200, 103), ctrl)
    assert fim.y() == pytest.approx(100, abs=TOL)


def _arrastar_alca(el, alca, destino, mods=Qt.KeyboardModifier.NoModifier):
    from gerador_layout.ui.mockup_itens import _PONTO_RELATIVO_ALCA

    rel_x, rel_y = _PONTO_RELATIVO_ALCA[alca]
    el._alca_ativa = alca
    el._arrasto_largura_inicial = el.largura
    el._arrasto_altura_inicial = el.altura
    el._arrasto_angulo_inicial = el.rotation()
    el._arrasto_centro_cena = el.mapToScene(QPointF(el.largura / 2, el.altura / 2))
    el._arrasto_oposto_cena = el.mapToScene(QPointF((1 - rel_x) * el.largura, (1 - rel_y) * el.altura))
    el._redimensionar_para(destino, mods)


def test_alca_de_canto_e_proporcional(janela):
    el = _retangulo(janela, 0, 0, 40, 20)
    _arrastar_alca(el, Alca.INFERIOR_DIREITA, QPointF(80, 25))
    assert (el.largura, el.altura) == pytest.approx((80, 40))
    assert el.pos() == QPointF(0, 0)


def test_alca_de_canto_com_alt_e_livre(janela):
    el = _retangulo(janela, 0, 0, 40, 20)
    _arrastar_alca(el, Alca.INFERIOR_DIREITA, QPointF(80, 25), Qt.KeyboardModifier.AltModifier)
    assert (el.largura, el.altura) == pytest.approx((80, 25))


def test_shift_redimensiona_do_centro(janela):
    el = _retangulo(janela, 0, 0, 40, 20)
    _arrastar_alca(el, Alca.DIREITA, QPointF(50, 10), Qt.KeyboardModifier.ShiftModifier)
    assert el.largura == pytest.approx(60)
    centro = el.retangulo_conteudo_cena().center()
    assert (centro.x(), centro.y()) == pytest.approx((20, 10))


def test_ctrl_gira_em_passos_de_15(janela):
    el = _retangulo(janela, 0, 0, 40, 20)
    el._arrasto_centro_cena = QPointF(20, 10)
    el._arrasto_angulo_inicial = 0.0
    el._arrasto_angulo_mouse_inicial = 0.0
    el._girar_para(QPointF(20 + 100, 10 + 37), Qt.KeyboardModifier.ControlModifier)  # ~20,3°
    assert el.rotation() == pytest.approx(15.0)


def _mouse(janela, tipo, ponto_cena, botao, botoes):
    from PySide6.QtGui import QMouseEvent

    vista = janela.canvas
    pos = QPointF(vista.mapFromScene(ponto_cena))
    evento = QMouseEvent(tipo, pos, vista.viewport().mapToGlobal(pos), botao, botoes, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(vista.viewport(), evento)


def test_clique_direito_no_arrasto_deixa_copia(janela):
    from PySide6.QtCore import QEvent

    janela.resize(1400, 900)
    janela.show()
    QApplication.processEvents()
    el = _retangulo(janela, 100, 100, 40, 20)
    _selecionar(janela, el)
    antes = len(janela.canvas.elementos_mockup)
    esq, dir_ = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton
    _mouse(janela, QEvent.Type.MouseButtonPress, QPointF(120, 110), esq, esq)
    _mouse(janela, QEvent.Type.MouseMove, QPointF(170, 110), Qt.MouseButton.NoButton, esq)
    _mouse(janela, QEvent.Type.MouseButtonPress, QPointF(170, 110), dir_, esq | dir_)
    _mouse(janela, QEvent.Type.MouseButtonRelease, QPointF(170, 110), dir_, esq)
    _mouse(janela, QEvent.Type.MouseMove, QPointF(220, 110), Qt.MouseButton.NoButton, esq)
    _mouse(janela, QEvent.Type.MouseButtonRelease, QPointF(220, 110), esq, Qt.MouseButton.NoButton)
    assert len(janela.canvas.elementos_mockup) == antes + 1
    copia = janela.canvas.elementos_mockup[-1]
    assert el.pos().x() == pytest.approx(100, abs=0.5)
    assert copia.pos().x() == pytest.approx(200, abs=1.0)
    assert copia.isSelected() and not el.isSelected()


def test_digitar_texto_nao_dispara_atalhos(janela):
    from gerador_layout.ui.mockup_texto import ElementoTexto

    janela.show()
    QApplication.processEvents()
    texto = ElementoTexto("")
    janela.canvas.adicionar_elemento_mockup(texto, QPointF(300, 150))
    _selecionar(janela, texto)
    texto.iniciar_edicao_inline()
    QApplication.processEvents()
    pos_antes = QPointF(texto.pos())
    QTest.keyClicks(janela.canvas, "LRPTB")
    assert texto.pos() == pos_antes
    assert "LRPTB" in texto.texto  # as letras foram pro texto, não viraram atalhos
