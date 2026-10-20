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


def _cantos(el):
    from PySide6.QtCore import QRectF

    r = QRectF(0, 0, el.largura, el.altura)
    return [(round(p.x(), 3), round(p.y(), 3)) for p in (el.mapToScene(r.topLeft()), el.mapToScene(r.bottomRight()))]


def test_esticar_grupo_estica_o_girado_no_eixo_certo_e_campo_da_barra_escala_os_de_dentro():
    j, a, b = _janela()
    texto = ElementoTexto("CAMA JUVENIL")
    j.canvas.adicionar_elemento_mockup(texto, QPointF(150, 200))
    texto.setRotation(-90)
    j.canvas.cena.clearSelection()
    for el in (a, b, texto):
        el.setSelected(True)
    grupo = j.canvas.agrupar_selecionados()
    tela = texto.retangulo_conteudo_cena()
    antes = {el: _cantos(el) for el in (a, b, texto)}
    # pela barra (campo largura): os de dentro escalam junto; o texto a -90°
    # fica mais LARGO na tela, a altura dele na tela não muda
    j.canvas._com_undo_geometria("largura", lambda: grupo.definir_largura(grupo.largura * 1.5))
    novo = texto.retangulo_conteudo_cena()
    assert novo.width() == pytest.approx(tela.width() * 1.5, rel=1e-3)
    assert novo.height() == pytest.approx(tela.height(), rel=1e-3)
    assert a.retangulo_conteudo_cena().width() == pytest.approx(60, rel=1e-3)
    j.canvas.pilha_desfazer.undo()
    assert {el: _cantos(el) for el in (a, b, texto)} == antes
    j.close()


def test_abrir_projeto_com_grupo_girado_de_caixa_antiga(tmp_path):
    """Projeto salvo com a caixa do grupo maior que o desenho (versões
    anteriores): abre com tudo no lugar."""
    j, a, b = _janela()
    a.setRotation(30)
    j.canvas.cena.clearSelection()
    a.setSelected(True)
    b.setSelected(True)
    grupo = j.canvas.agrupar_selecionados()
    grupo.recalcular_limites()
    # caixa "antiga": 10 mm de folga em volta
    for el in grupo.elementos:
        el.setPos(el.pos() + QPointF(10, 10))
    grupo.setPos(grupo.pos() - QPointF(10, 10))
    grupo.prepareGeometryChange()
    grupo._largura += 20
    grupo._altura += 20
    grupo.setTransformOriginPoint(grupo._largura / 2, grupo._altura / 2)
    grupo.setRotation(25)
    antes = sorted(_cantos(el) for el in (a, b))
    arquivo = tmp_path / "x.autoline"
    projeto_arquivo.salvar(j, str(arquivo))
    k = JanelaPrincipal()
    projeto_arquivo.aplicar_na_janela(k, projeto_arquivo.ler(str(arquivo)))
    g2 = next(e for e in k.canvas._elementos_mockup if isinstance(e, GrupoMockup))
    assert sorted(_cantos(el) for el in g2.elementos) == antes
    k.close()
    j.close()


def _grupo_de(j, *els):
    j.canvas.cena.clearSelection()
    for el in els:
        el.setSelected(True)
    grupo = j.canvas.agrupar_selecionados()
    j.canvas.cena.clearSelection()
    return grupo


def _ctrl_selecionar(el):
    el.setFlag(el.GraphicsItemFlag.ItemIsSelectable, True)
    el.setSelected(True)


def test_apagar_objeto_de_dentro_do_grupo_sai_do_grupo_e_desfazer_devolve():
    j, a, b = _janela()
    c = ElementoRetangulo(largura=20, altura=20)
    j.canvas.adicionar_elemento_mockup(c, QPointF(300, 100))
    grupo = _grupo_de(j, a, b, c)
    grupo.setRotation(20)
    tela = a.retangulo_conteudo_cena()
    _ctrl_selecionar(a)
    j.canvas.remover_selecionados()
    assert a not in grupo.elementos and a.scene() is None
    dados = projeto_arquivo.estado_da_janela(j, com_arquivos=False)
    salvo = next(e for e in dados["elementos"] if e["tipo"] == "GrupoMockup")
    assert len(salvo["elementos"]) == 2  # não reaparece ao abrir o projeto
    j.canvas.pilha_desfazer.undo()
    assert a.parentItem() is grupo and a in grupo.elementos
    assert a.retangulo_conteudo_cena() == tela
    j.close()


def test_apagar_o_ultimo_de_dentro_some_com_o_grupo():
    j, a, b = _janela()
    grupo = _grupo_de(j, a, b)
    _ctrl_selecionar(a)
    j.canvas.remover_selecionados()
    _ctrl_selecionar(b)
    j.canvas.remover_selecionados()
    assert grupo.scene() is None and grupo not in j.canvas._elementos_mockup
    j.canvas.pilha_desfazer.undo()
    assert grupo.scene() is not None and b.parentItem() is grupo
    j.close()


def test_ctrl_d_num_objeto_de_dentro_do_grupo_nasce_ao_lado_dele():
    j, a, b = _janela()
    grupo = _grupo_de(j, a, b)
    grupo.setRotation(10)
    _ctrl_selecionar(a)
    clone = j.canvas.duplicar_selecionados()[0]
    centro = a.mapToScene(a.transformOriginPoint())
    centro_clone = clone.mapToScene(clone.transformOriginPoint())
    passo = centro_clone - centro
    assert passo.x() == pytest.approx(passo.y()) and 0 < passo.x() < 50
    assert clone.rotation() == pytest.approx(10)
    j.close()
