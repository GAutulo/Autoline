"""Texto artístico como no CorelDRAW: digitar direto no desenho, sem caixa."""

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
from PySide6.QtWidgets import QApplication, QGraphicsProxyWidget  # noqa: E402

from gerador_layout.ui.mockup_texto import ElementoTexto  # noqa: E402
from gerador_layout.ui.preview_canvas import FerramentaMockup  # noqa: E402

ESQ = Qt.MouseButton.LeftButton


@pytest.fixture
def janela():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    for _ in range(3):
        QApplication.processEvents()
    yield j
    j.close()


def _clique(janela, ponto, duplo=False):
    vista = janela.canvas
    pos = QPointF(vista.mapFromScene(QPointF(*ponto)))
    tipos = [(QEvent.Type.MouseButtonPress, ESQ), (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)]
    if duplo:
        tipos.append((QEvent.Type.MouseButtonDblClick, ESQ))
    for tipo, botoes in tipos:
        QApplication.sendEvent(
            vista.viewport(), QMouseEvent(tipo, pos, vista.viewport().mapToGlobal(pos), ESQ, botoes, Qt.KeyboardModifier.NoModifier)
        )


def _texto_em_edicao(canvas):
    return next(el for el in canvas.elementos_mockup if isinstance(el, ElementoTexto) and el.editando)


def test_clicar_e_digitar_sem_caixa_com_varias_linhas(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.TEXTO)
    antes_desfazer = canvas.pilha_desfazer.count()
    _clique(janela, (300, 150))
    texto = _texto_em_edicao(canvas)
    assert not any(isinstance(it, QGraphicsProxyWidget) for it in canvas.cena.items())  # nenhuma caixa
    QTest.keyClicks(canvas, "MINI CAMA")
    QTest.keyClick(canvas, Qt.Key.Key_Return)
    QTest.keyClicks(canvas, "JUVENIL")
    assert texto.texto == "MINI CAMA\nJUVENIL"
    altura_uma_linha = texto.altura
    assert texto.tamanho_pt > 0
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert not texto.editando
    assert canvas.pilha_desfazer.count() == antes_desfazer + 1  # um passo só: o texto inteiro
    canvas.pilha_desfazer.undo()
    assert texto not in canvas.elementos_mockup
    canvas.pilha_desfazer.redo()
    assert texto in canvas.elementos_mockup and texto.texto == "MINI CAMA\nJUVENIL"
    assert altura_uma_linha > 0


def test_texto_vazio_some_sem_deixar_rastro(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.TEXTO)
    antes = (len(canvas.elementos_mockup), canvas.pilha_desfazer.count())
    _clique(janela, (300, 150))
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert (len(canvas.elementos_mockup), canvas.pilha_desfazer.count()) == antes


def test_edicao_com_cursor_selecao_e_tamanho_mantido(janela):
    canvas = janela.canvas
    texto = ElementoTexto("COR: AZUL")
    canvas.adicionar_elemento_mockup(texto, QPointF(300, 200))
    texto.definir_tamanho_pt(30)
    altura = texto.altura
    texto.iniciar_edicao()
    QTest.keyClick(canvas, Qt.Key.Key_Backspace)
    QTest.keyClick(canvas, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClick(canvas, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClicks(canvas, "XX")  # substitui a seleção
    assert texto.texto == "COR: AXX"
    QTest.keyClick(canvas, Qt.Key.Key_Home)
    QTest.keyClicks(canvas, "> ")
    assert texto.texto == "> COR: AXX"
    assert texto.altura == pytest.approx(altura)  # editar não muda o tamanho da letra
    assert texto.tamanho_pt == pytest.approx(30, rel=1e-3)
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    canvas.pilha_desfazer.undo()
    assert texto.texto == "COR: AZUL"


def test_ferramenta_texto_em_texto_existente_edita_e_atalhos_nao_disparam(janela):
    canvas = janela.canvas
    texto = ElementoTexto("ABC")
    canvas.adicionar_elemento_mockup(texto, QPointF(300, 200))
    texto.definir_tamanho_pt(40)
    canvas.definir_ferramenta(FerramentaMockup.TEXTO)
    centro = texto.mapToScene(QPointF(texto.largura * 0.99, texto.altura / 2))
    quantos = len(canvas.elementos_mockup)
    _clique(janela, (centro.x(), centro.y()))
    assert texto.editando and len(canvas.elementos_mockup) == quantos  # editou, não criou outro
    pos = texto.pos()
    QTest.keyClicks(canvas, "LP")  # L e P são atalhos de alinhar fora da edição
    assert texto.texto == "ABCLP" and texto.pos() == pos


def test_tamanho_novo_acompanha_o_zoom(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.TEXTO)
    _clique(janela, (300, 150))
    QTest.keyClicks(canvas, "A")
    texto = _texto_em_edicao(canvas)
    altura_tela = texto.altura * canvas.transform().m11()
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    canvas.scale(5, 5)
    canvas._zoom_atual *= 5
    canvas.zoom_alterado.emit(canvas._zoom_atual)
    canvas.definir_ferramenta(FerramentaMockup.TEXTO)
    _clique(janela, (310, 160))
    QTest.keyClicks(canvas, "A")
    outro = _texto_em_edicao(canvas)
    assert outro.altura * canvas.transform().m11() == pytest.approx(altura_tela, rel=0.02)


def test_seletor_de_fonte_reaproveitado_entre_selecoes():
    """Criar um QFontComboBox custa ~150 ms: a barra usa um só e troca o
    texto a que ele está ligado."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QFontComboBox

    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_texto import ElementoTexto

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    canvas = j.canvas
    a, b = ElementoTexto("A"), ElementoTexto("B")
    canvas.adicionar_elemento_mockup(a, QPointF(10, 10))
    canvas.adicionar_elemento_mockup(b, QPointF(60, 10))
    painel = j.painel_propriedades_mockup
    combos = []
    for el in (a, b, a, b):
        canvas._scene.clearSelection()
        el.setSelected(True)
        QApplication.processEvents()
        combos.append(next(c for c in painel.findChildren(QFontComboBox) if c.isVisibleTo(painel)))
    assert all(c is combos[0] for c in combos)  # o mesmo seletor, nunca recriado
    fonte_a = a.fonte_familia
    combos[0].currentFontChanged.emit(QFont("Fonte Escolhida"))  # b está selecionado agora
    assert b.fonte_familia == "Fonte Escolhida" and a.fonte_familia == fonte_a  # só o texto atual muda
    j.close()
