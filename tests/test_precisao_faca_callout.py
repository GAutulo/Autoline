"""Precisão na faca (guia de alinhamento e medida ao arrastar linhas e
pontas) e callout digitado direto no balão, sem caixa de texto."""

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

from gerador_layout.models import LinhaDesenho, TipoLinha  # noqa: E402

C = TipoLinha.CORTE
ESQ = Qt.MouseButton.LeftButton
NENHUM = Qt.MouseButton.NoButton
SEM = Qt.KeyboardModifier.NoModifier


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


def _mouse(janela, tipo, ponto, botao, botoes, mods=SEM):
    vista = janela.canvas
    pos = QPointF(vista.mapFromScene(QPointF(*ponto)))
    evento = QMouseEvent(tipo, pos, vista.viewport().mapToGlobal(pos), botao, botoes, mods)
    QApplication.sendEvent(vista.viewport(), evento)


def _faca_duas_abas(janela):
    """Duas abas lado a lado, a da direita 1 mm mais baixa (o caso da tela)."""
    janela.abas_tela.setCurrentIndex(0)
    QApplication.processEvents()
    janela._nova_faca_em_branco()
    canvas = janela.canvas
    linhas = [
        LinhaDesenho(0, 50, 40, 50, C),  # topo da aba esquerda
        LinhaDesenho(0, 50, 0, 100, C),
        LinhaDesenho(40, 50, 40, 100, C),
        LinhaDesenho(160, 51, 200, 51, C),  # topo da aba direita, 1 mm abaixo
        LinhaDesenho(160, 51, 160, 100, C),
        LinhaDesenho(200, 51, 200, 100, C),
    ]
    canvas._aplicar_faca("teste", linhas)
    canvas.ajustar_a_tela()
    canvas.definir_snap_ativo(False)
    QApplication.processEvents()
    return canvas


def test_arrastar_linha_alinha_com_a_outra_aba_e_mostra_guia(janela):
    canvas = _faca_duas_abas(janela)
    janela._acoes_faca["forma"].trigger()
    px = 1.0 / canvas.transform().m11()
    _mouse(janela, QEvent.Type.MouseButtonPress, (180, 51), ESQ, ESQ)
    # solta 1 pixel fora do alinhamento: deve grudar em y = 50
    _mouse(janela, QEvent.Type.MouseMove, (180, 50 + px), NENHUM, ESQ)
    assert canvas._linhas_dinamicas  # guia de alinhamento aparece
    assert canvas._rotulo_faca is not None and "Δy" in canvas._rotulo_faca[1]
    _mouse(janela, QEvent.Type.MouseButtonRelease, (180, 50 + px), ESQ, NENHUM)
    topo = canvas.linhas_faca()[3]
    assert topo.y1 == pytest.approx(50) and topo.y2 == pytest.approx(50)
    assert canvas._rotulo_faca is None and not canvas._linhas_dinamicas


def test_arrastar_ponta_mostra_comprimento(janela):
    canvas = _faca_duas_abas(janela)
    janela._acoes_faca["forma"].trigger()
    _mouse(janela, QEvent.Type.MouseButtonPress, (200, 51), ESQ, ESQ)
    _mouse(janela, QEvent.Type.MouseMove, (210, 51), NENHUM, ESQ)
    assert canvas._rotulo_faca is not None and "mm" in canvas._rotulo_faca[1]
    _mouse(janela, QEvent.Type.MouseButtonRelease, (210, 51), ESQ, NENHUM)


def test_alinhar_pontos_gruda_em_no_parado(janela):
    canvas = _faca_duas_abas(janela)
    canvas.definir_snap_ativo(True)
    fixos = canvas._nos_fixos_faca(canvas.linhas_faca(), {(3, 1), (3, 2), (4, 1), (5, 1)})
    perto = QPointF(40 + canvas.limiar_snap() * 0.3, 50)
    correcao = canvas._alinhar_pontos_faca([perto], fixos)
    assert (perto + correcao) == QPointF(40, 50)
    assert canvas._indicador_encaixe[1] == "nó"


# ── Callout ───────────────────────────────────────────────────────────
def test_callout_digita_no_balao_sem_caixa(janela):
    from gerador_layout.ui.mockup_callout import ElementoCallout

    janela.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    canvas = janela.canvas
    janela._criar_callout_por_clique(canvas.retangulo_pagina().center())
    callout = next(el for el in canvas._elementos_mockup if isinstance(el, ElementoCallout))
    assert callout.editando
    assert not [c for c in callout.childItems() if c.__class__.__name__ == "QGraphicsProxyWidget"]
    largura_antes = callout.largura
    QTest.keyClicks(canvas.viewport(), "Sangria de 3 mm aqui por favor")
    assert callout.texto == "Sangria de 3 mm aqui por favor"  # substituiu o "Observação"
    assert callout.largura > largura_antes  # o balão cresce com o texto
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Return)
    assert not callout.editando
    canvas._pilha_desfazer.undo()
    assert callout.texto == "Observação"
    canvas._pilha_desfazer.redo()
    assert callout.texto == "Sangria de 3 mm aqui por favor"


def test_callout_editar_existente_e_apagar_tudo(janela):
    from gerador_layout.ui.mockup_callout import ElementoCallout

    janela.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    canvas = janela.canvas
    callout = ElementoCallout(texto="Cor")
    canvas.adicionar_elemento_mockup(callout, canvas.retangulo_pagina().center())
    callout.iniciar_edicao()
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Home)
    QTest.keyClicks(canvas.viewport(), "Pantone ")
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Escape)
    assert callout.texto == "Pantone Cor"
    callout.iniciar_edicao()
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Backspace)
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Return)
    assert callout not in canvas._elementos_mockup or not callout.scene()
    canvas._pilha_desfazer.undo()
    assert callout.scene() is not None and callout.texto == "Pantone Cor"
