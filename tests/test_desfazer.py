"""Desfazer/refazer (Ctrl+Z / Ctrl+Y): agrupar, remover, mexer dentro do
grupo, cor e qualquer campo da barra de propriedades voltam exatamente."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDoubleSpinBox  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.ui import projeto_arquivo  # noqa: E402
from gerador_layout.ui.main_window import JanelaPrincipal  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402
from gerador_layout.ui.mockup_itens import GrupoMockup  # noqa: E402
from gerador_layout.ui.mockup_texto import ElementoTexto  # noqa: E402


def _janela():
    j = JanelaPrincipal()
    j.resize(1200, 800)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    a, b = ElementoRetangulo(largura=40, altura=30), ElementoRetangulo(largura=40, altura=30)
    j.canvas.adicionar_elemento_mockup(a, QPointF(100, 100))
    j.canvas.adicionar_elemento_mockup(b, QPointF(200, 100))
    return j, a, b


def _foto(j):
    d = projeto_arquivo.estado_da_janela(j, com_arquivos=False)
    return [
        (e["tipo"], round(e["geometria"]["pos"][0], 2), round(e["geometria"]["pos"][1], 2), e.get("cor"))
        for e in d["elementos"]
    ]


def _ida_e_volta(j, passos):
    pilha = j.canvas.pilha_desfazer
    inicio, n0 = _foto(j), pilha.index()
    passos()
    fim = _foto(j)
    while pilha.index() > n0:
        pilha.undo()
    assert _foto(j) == inicio
    while pilha.canRedo():
        pilha.redo()
    assert _foto(j) == fim


def test_agrupar_e_desagrupar_voltam():
    j, a, b = _janela()

    def passos():
        j.canvas.cena.clearSelection()
        a.setSelected(True)
        b.setSelected(True)
        g = j.canvas.agrupar_selecionados()
        j.canvas._com_undo_geometria("mover", lambda: g.setPos(g.pos() + QPointF(0, 50)))

    _ida_e_volta(j, passos)
    j.canvas.pilha_desfazer.undo()
    j.canvas.pilha_desfazer.undo()
    assert a.parentItem() is None and not any(isinstance(e, GrupoMockup) for e in j.canvas._elementos_mockup)
    j.close()


def test_remover_volta_no_mesmo_lugar_da_ordem():
    j, a, b = _janela()

    def passos():
        j.canvas.cena.clearSelection()
        a.setSelected(True)
        j.canvas.remover_selecionados()

    _ida_e_volta(j, passos)
    j.canvas.pilha_desfazer.undo()
    assert j.canvas._elementos_mockup.index(a) < j.canvas._elementos_mockup.index(b)
    j.close()


def test_cor_da_paleta_desfaz():
    j, a, _b = _janela()

    def passos():
        j.canvas.cena.clearSelection()
        a.setSelected(True)
        j._aplicar_cor_paleta(("Vermelho", (255, 0, 0)), contorno=False)

    _ida_e_volta(j, passos)
    j.close()


def test_mexer_dentro_do_grupo_com_ctrl_desfaz_o_grupo_todo():
    from PySide6.QtTest import QTest

    j, a, b = _janela()
    j.canvas.cena.clearSelection()
    a.setSelected(True)
    b.setSelected(True)
    grupo = j.canvas.agrupar_selecionados()
    j.canvas.cena.clearSelection()
    QApplication.processEvents()
    a_antes, grupo_antes = a.scenePos(), (grupo.pos(), grupo.largura, grupo.altura)
    vp = j.canvas.viewport()
    ponto = j.canvas.mapFromScene(a.sceneBoundingRect().center())
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, ponto)
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, ponto)
    for k in range(1, 6):
        QTest.mouseMove(vp, ponto + QPoint(-10 * k, 0))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, ponto + QPoint(-50, 0))
    assert a.scenePos().x() < a_antes.x() - 5
    assert grupo.pos().x() < grupo_antes[0].x() - 5  # a caixa do grupo acompanhou
    j.canvas.pilha_desfazer.undo()
    assert a.scenePos().x() == pytest.approx(a_antes.x())
    assert (grupo.pos(), grupo.largura, grupo.altura) == grupo_antes  # o grupo voltou junto
    j.close()


def test_campo_da_barra_de_propriedades_desfaz_num_passo():
    j, _a, _b = _janela()
    texto = ElementoTexto("ABC")
    j.canvas.adicionar_elemento_mockup(texto, QPointF(300, 200))
    j.canvas.cena.clearSelection()
    texto.setSelected(True)
    QApplication.processEvents()
    espaco = j.painel_propriedades_mockup.findChild(QDoubleSpinBox, "espacoLetras")
    n0 = j.canvas.pilha_desfazer.index()
    for v in (5, 10, 15):  # setinha clicada três vezes: um passo só
        espaco.setValue(v)
    assert texto.espaco_letras == pytest.approx(0.15)
    assert j.canvas.pilha_desfazer.index() == n0 + 1
    j.canvas.pilha_desfazer.undo()
    assert texto.espaco_letras == pytest.approx(0)
    assert texto.texto == "ABC"
    j.canvas.pilha_desfazer.redo()
    assert texto.espaco_letras == pytest.approx(0.15)
    j.close()


def test_agrupar_objeto_girado_nao_sai_do_lugar():
    j, a, b = _janela()
    texto = ElementoTexto("CAMA JUVENIL")
    j.canvas.adicionar_elemento_mockup(texto, QPointF(150, 200))
    texto.setRotation(-90)
    a.setRotation(30)
    a.definir_espelho(True, False)

    def caixa(el):
        r = el.retangulo_conteudo_cena()
        return (round(r.x(), 4), round(r.y(), 4), round(r.width(), 4), round(r.height(), 4))

    antes = {el: caixa(el) for el in (a, b, texto)}
    j.canvas.cena.clearSelection()
    for el in (a, b, texto):
        el.setSelected(True)
    grupo = j.canvas.agrupar_selecionados()
    assert {el: caixa(el) for el in (a, b, texto)} == antes
    grupo.setRotation(20)  # girar o grupo e desagrupar: tudo fica onde está
    girados = {el: caixa(el) for el in (a, b, texto)}
    j.canvas.cena.clearSelection()
    grupo.setSelected(True)
    j.canvas.desagrupar_selecionados()
    assert {el: caixa(el) for el in (a, b, texto)} == girados
    j.close()
