"""Checklist de cores como caixa de texto que se organiza sozinha (fonte,
tamanho, negrito, empilhado/lado a lado, edição no desenho) e a área dos
objetos batendo com o desenho."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsScene  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_checklist import EMPILHADO, LADO_A_LADO, ElementoChecklistCores  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402

PRETO = CorImpressao("PRETO", 0, 0, 0)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    yield j
    j.close()


def _pixels_pintados(elemento, escala=6.0, margem=20):
    """Limites (x0, y0, x1, y1), em px, do que o elemento pinta."""
    largura = int(elemento.largura * escala) + 2 * margem
    altura = int(elemento.altura * escala) + 2 * margem
    img = QImage(largura, altura, QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.translate(margem, margem)
    p.scale(escala, escala)
    elemento._pintar_conteudo(p)
    p.end()
    pontos = [(x, y) for x in range(largura) for y in range(altura) if QColor(img.pixel(x, y)).black() > 100]
    xs, ys = [x for x, _ in pontos], [y for _, y in pontos]
    return min(xs) - margem, min(ys) - margem, max(xs) - margem, max(ys) - margem


def test_retangulo_de_traco_grosso_ocupa_a_area_exata(app):
    """Bug relatado: a área de seleção ficava maior que o retângulo. O
    drawRect com 4 números caía na versão de INTEIROS do Qt e truncava."""
    el = ElementoRetangulo(largura=19.26, altura=14.22, cor_tinta=PRETO)
    el.definir_largura_traco(1.5)
    x0, y0, x1, y1 = _pixels_pintados(el)
    assert abs(x0) <= 1 and abs(y0) <= 1
    assert x1 == pytest.approx(19.26 * 6, abs=1.5) and y1 == pytest.approx(14.22 * 6, abs=1.5)


def test_checklist_cabe_exato_na_caixa(app):
    el = ElementoChecklistCores(["Preto", "Branco", "Cinza claro"], tamanho_pt=14)
    itens, largura, altura = el.itens_layout()
    assert (el.largura, el.altura) == pytest.approx((largura, altura))
    assert len(itens) == 3 and all(i["caixa"].left() == 0 for i in itens)  # empilhado: uma coluna
    x0, y0, x1, y1 = _pixels_pintados(el)
    assert x0 >= -1 and y0 >= -1 and x1 <= el.largura * 6 + 1.5 and y1 <= el.altura * 6 + 1.5


def test_checklist_fonte_tamanho_negrito_e_arranjo(app):
    el = ElementoChecklistCores(["A", "Branco", "Cinza"], tamanho_pt=10)
    altura_10 = el.altura
    el.definir_tamanho_pt(20)
    assert el.altura == pytest.approx(altura_10 * 2, rel=0.02)  # letra maior, caixa acompanha
    largura_normal = el.largura
    el.definir_negrito(True)
    assert el.negrito and el.largura >= largura_normal
    el.definir_fonte("Courier New")
    assert el.fonte_familia == "Courier New"

    el.definir_disposicao(LADO_A_LADO)
    itens, _l, _a = el.itens_layout()
    assert len({round(i["caixa"].top(), 6) for i in itens}) == 1  # lado a lado: uma linha só
    assert el.largura > largura_normal
    # caixa mais estreita: quebra pra linha de baixo, a letra não muda
    el.definir_largura(el.largura * 0.5)
    itens, _l, altura = el.itens_layout()
    assert len({round(i["caixa"].top(), 6) for i in itens}) >= 2 and el.tamanho_pt == 20
    assert el.altura == pytest.approx(altura)
    # nunca mais estreita que o item mais largo
    el.definir_largura(0.1)
    assert el.largura >= max(i["largura"] for i in el.itens_layout()[0]) - 1e-6
    el.definir_disposicao(EMPILHADO)
    assert len({round(i["caixa"].left(), 6) for i in el.itens_layout()[0]}) == 1


def test_checklist_editado_no_desenho_com_desfazer(janela):
    canvas = janela.canvas
    janela._adicionar_checklist()
    el = [e for e in canvas.elementos_mockup if isinstance(e, ElementoChecklistCores)][-1]
    el.iniciar_edicao()
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_End)
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Return)
    QTest.keyClicks(canvas.viewport(), "Preto")
    assert el.variantes[-1] == "Preto" and len(el.itens_layout()[0]) == 3
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Return)  # linha vazia no fim...
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Escape)
    assert el.variantes == ["Cor 1", "Cor 2", "Preto"]  # ...não vira cor
    canvas._pilha_desfazer.undo()
    assert el.variantes == ["Cor 1", "Cor 2"]
    canvas._pilha_desfazer.redo()
    assert el.variantes == ["Cor 1", "Cor 2", "Preto"]
    # apagar tudo apaga o checklist (desfazer devolve)
    el.iniciar_edicao()
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Backspace)
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Escape)
    assert el.scene() is None
    canvas._pilha_desfazer.undo()
    assert el.scene() is not None and el.variantes == ["Cor 1", "Cor 2", "Preto"]


def test_checklist_canto_muda_a_letra_e_desfazer_volta(janela):
    canvas = janela.canvas
    el = ElementoChecklistCores(["Preto", "Branco"], tamanho_pt=12)
    canvas.adicionar_elemento_mockup(el, canvas.retangulo_pagina().center())
    antes = canvas._pilha_desfazer.count()
    from gerador_layout.ui.mockup_itens import Alca, _estado_recursivo

    estado_antes = _estado_recursivo(el)
    el._pt_no_inicio_arrasto = el.tamanho_pt
    el._alca_ativa = Alca.INFERIOR_DIREITA
    el._arrasto_largura_inicial, el._arrasto_altura_inicial = el.largura, el.altura
    el._arrasto_angulo_inicial = 0.0
    el._arrasto_centro_cena = el.mapToScene(el.largura / 2, el.altura / 2)
    el._arrasto_oposto_cena = el.mapToScene(0, 0)
    el._redimensionar_para(el.mapToScene(el.largura * 2, el.altura * 2))
    assert el.tamanho_pt == pytest.approx(24, rel=0.02)  # canto dobrou: letra dobrou
    canvas._registrar_comando_geometria(estado_antes, _estado_recursivo(el))  # o que o soltar do mouse faz
    assert canvas._pilha_desfazer.count() == antes + 1
    canvas._pilha_desfazer.undo()
    assert el.tamanho_pt == pytest.approx(12)


def test_checklist_vai_pro_corel_nas_mesmas_posicoes(app):
    from gerador_layout.ui import corel_bridge

    from test_cotas_corel import _Falso

    cena = QGraphicsScene()
    el = ElementoChecklistCores(["Preto", "Branco", "Cinza"], tamanho_pt=12, disposicao=LADO_A_LADO)
    cena.addItem(el)
    registro: list = []
    corel_bridge._desenhar_elemento_mockup(_Falso(registro), _Falso(registro, "layer"), el, 350.0)
    chamadas = [nome for nome, *_ in registro if nome != "set"]
    assert chamadas.count("CreateRectangle2") == 3 and chamadas.count("CreateArtisticText") == 3
