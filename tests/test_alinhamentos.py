"""Alinhar: Shift+clique monta a seleção (como no CorelDRAW) e os objetos
alinham entre si; alinhar na face sem ter escolhido a face; alinhamento
das linhas do texto (esquerda/centro/direita), inclusive no CorelDRAW."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsScene, QToolButton  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402
from gerador_layout.ui.mockup_texto import ElementoTexto  # noqa: E402

PRETO = CorImpressao("PRETO", 0, 0, 0)
ESQ, NADA = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton


@pytest.fixture
def janela():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    yield j
    j.close()


def _clique(canvas, p, mods=Qt.KeyboardModifier.NoModifier):
    pos = QPointF(canvas.mapFromScene(p))
    for tipo, botao, botoes in ((QEvent.Type.MouseButtonPress, ESQ, ESQ), (QEvent.Type.MouseButtonRelease, ESQ, NADA)):
        QApplication.sendEvent(canvas.viewport(), QMouseEvent(tipo, pos, canvas.viewport().mapToGlobal(pos), botao, botoes, mods))
    QApplication.processEvents()


def _botao(janela, filtro):
    painel = janela.painel_propriedades_mockup
    return next(b for b in painel.findChildren(QToolButton) if b.isVisibleTo(painel) and filtro(b))


def test_shift_clique_monta_a_selecao_e_alinha_entre_si(janela):
    canvas = janela.canvas
    pagina = canvas.retangulo_pagina()
    a = ElementoRetangulo(largura=20, altura=10, cor_tinta=PRETO)
    b = ElementoTexto("CADEIRA LIA")
    b.definir_tamanho_pt(90)  # grande o bastante pro centro não cair numa alça
    canvas.adicionar_elemento_mockup(a, pagina.topLeft() + QPointF(100, 100))
    canvas.adicionar_elemento_mockup(b, pagina.topLeft() + QPointF(160, 140))
    canvas.ajustar_a_tela()
    _clique(canvas, a.mapToScene(a.largura / 2, a.altura / 2))
    _clique(canvas, b.mapToScene(b.largura / 2, b.altura / 2), Qt.KeyboardModifier.ShiftModifier)
    assert a.isSelected() and b.isSelected()
    assert janela.painel_propriedades_mockup._rotulo_tipo.text() == "2 selecionados"
    _botao(janela, lambda x: "Alinhar bordas esquerdas" in x.toolTip()).click()
    assert b.pos().x() == pytest.approx(a.pos().x())
    # Shift+clique de novo tira da seleção (e não desmarca o outro)
    _clique(canvas, b.mapToScene(b.largura / 2, b.altura / 2), Qt.KeyboardModifier.ShiftModifier)
    assert a.isSelected() and not b.isSelected()


def test_alinhar_na_face_sem_ter_escolhido_a_face(janela):
    canvas = janela.canvas
    painel_lateral = next(p for p in janela._paineis_disponiveis() if p.largura > 50)
    t = ElementoTexto("2 UNIDADES")
    canvas.adicionar_elemento_mockup(t, QPointF(painel_lateral.x1 + 3, painel_lateral.y1 + 5))
    canvas._scene.clearSelection()
    t.setSelected(True)
    QApplication.processEvents()
    assert t.painel_id is None
    botao = _botao(janela, lambda x: x.objectName() == "botaoAlinharFace" and x.property("alinhamento") == "centro_h")
    assert botao.isEnabled()  # antes ficava cinza até escolher a face
    botao.click()
    assert t.painel_id == painel_lateral.id  # achou a face onde ele está
    assert t.pos().x() + t.largura / 2 == pytest.approx((painel_lateral.x1 + painel_lateral.x2) / 2)


def test_alinhamento_das_linhas_do_texto(janela):
    t = ElementoTexto("CADEIRA LIA" + chr(10) + "2")
    janela.canvas.adicionar_elemento_mockup(t, QPointF(50, 50))
    largura, altura = t.largura, t.altura

    def inicio_linha_2():
        caminho = t.caminho_local()
        meio = altura * 0.75  # segunda linha
        xs = [caminho.elementAt(i).x for i in range(caminho.elementCount()) if caminho.elementAt(i).y > meio * 0.9]
        return min(xs)

    esquerda = inicio_linha_2()
    t.definir_alinhamento("centro")
    centro = inicio_linha_2()
    t.definir_alinhamento("direita")
    direita = inicio_linha_2()
    assert esquerda < centro < direita
    assert (t.largura, t.altura) == pytest.approx((largura, altura))  # a caixa não mexe
    # cursor: clicar no começo da linha 2 (já deslocada) cai na coluna 0 dela
    assert t._indice_no_ponto(QPointF(direita + 0.01, altura * 0.8)) == len("CADEIRA LIA") + 1
    # na barra: botões de alinhamento do texto
    janela.canvas._scene.clearSelection()
    t.setSelected(True)
    QApplication.processEvents()
    _botao(janela, lambda x: x.property("alinharTexto") == "centro").click()
    assert t.alinhamento == "centro"
    assert _botao(janela, lambda x: x.property("alinharTexto") == "centro").isChecked()
    assert not _botao(janela, lambda x: x.property("alinharTexto") == "direita").isChecked()
    assert t.clonar().alinhamento == "centro"


def test_alinhamento_do_texto_vai_pro_corel():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui import corel_bridge

    from test_cotas_corel import _Falso

    cena = QGraphicsScene()
    t = ElementoTexto("A" + chr(10) + "BB")
    t.definir_alinhamento("direita")
    cena.addItem(t)
    registro: list = []
    corel_bridge._desenhar_elemento_mockup(_Falso(registro), _Falso(registro, "layer"), t, 350.0)
    assert ("set", "Alignment") in registro
    assert corel_bridge._CDR_ALINHAMENTO_TEXTO == {"esquerda": 1, "direita": 2, "centro": 3}
