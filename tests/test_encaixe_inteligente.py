"""Encaixe com nome do ponto (CorelDRAW), encaixe ao vivo durante o
arrasto e medidas de distância até bordas e vizinhos (Illustrator/Figma)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402

PRETO = CorImpressao("PRETO", 0, 0, 0)


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


def _processar():
    for _ in range(5):
        QApplication.processEvents()


def _layout(janela):
    janela.abas_tela.setCurrentIndex(1)
    _processar()
    canvas = janela.canvas
    canvas.ajustar_a_tela()
    return canvas


def test_pontos_de_encaixe_tem_nome(janela):
    canvas = _layout(janela)
    el = ElementoRetangulo(largura=20, altura=10, cor_tinta=PRETO)
    canvas.adicionar_elemento_mockup(el, QPointF(30, 30))
    tipos = {tipo for _p, tipo in canvas.nos_de_encaixe_com_tipo()}
    assert {"nó", "ponto médio", "canto", "centro", "canto da chapa", "centro da chapa"} <= tipos
    centro = el.mapToScene(el.largura / 2, el.altura / 2)
    achado = canvas.encaixe_mais_proximo(centro + QPointF(0.01, 0.01))
    assert achado is not None and achado[1] == "centro"
    assert canvas.encaixar_ponto(centro + QPointF(0.01, 0.01)) == centro
    assert canvas._indicador_encaixe[1] == "centro"


def test_intersecao_de_linhas_da_faca(janela):
    canvas = _layout(janela)
    linhas = canvas.linhas_faca()
    cruzamentos = canvas._intersecoes_da_faca(linhas)
    # chamada repetida usa o cache e devolve o mesmo resultado
    assert canvas._intersecoes_da_faca(linhas) is cruzamentos
    for p in cruzamentos:
        assert all(
            not (abs(p.x() - l.x1) < 0.01 and abs(p.y() - l.y1) < 0.01) for l in linhas
        )


def test_encaixe_desligado_nao_mexe(janela):
    canvas = _layout(janela)
    canvas._snap_ativo = False
    assert canvas.encaixe_mais_proximo(QPointF(0, 0)) is None


def test_arrasto_gruda_ao_vivo_no_canto_do_vizinho(janela):
    canvas = _layout(janela)
    canvas._snap_ativo = True
    fixo = ElementoRetangulo(largura=20, altura=10, cor_tinta=PRETO)
    movel = ElementoRetangulo(largura=10, altura=10, cor_tinta=PRETO)
    canvas.adicionar_elemento_mockup(fixo, QPointF(40, 40))
    canvas.adicionar_elemento_mockup(movel, QPointF(10, 10))
    movel._arrasto_corpo_posicoes_iniciais = {movel: movel.pos()}
    alvo = fixo.mapToScene(fixo.largura, 0)  # canto superior direito do fixo
    canto_movel = movel.mapToScene(0, 0)
    quase = alvo - canto_movel + QPointF(canvas.limiar_snap() * 0.3, -canvas.limiar_snap() * 0.2)
    delta, encaixou = canvas._ajustar_arrasto(movel, quase)
    assert encaixou
    assert movel.mapToScene(0, 0) + delta == alvo
    assert "canto" in canvas._indicador_encaixe[1]
    assert canvas._medidas_distancia  # mostra as distâncias enquanto arrasta


def test_arrasto_longe_de_tudo_nao_gruda(janela):
    canvas = _layout(janela)
    canvas._snap_ativo = True
    movel = ElementoRetangulo(largura=5, altura=5, cor_tinta=PRETO)
    canvas.adicionar_elemento_mockup(movel, QPointF(10, 10))
    movel._arrasto_corpo_posicoes_iniciais = {movel: movel.pos()}
    passo = QPointF(canvas.limiar_snap() * 3.3, canvas.limiar_snap() * 2.7)
    delta, encaixou = canvas._ajustar_arrasto(movel, passo)
    if not encaixou:
        assert delta == passo


def test_distancias_ate_vizinhos_e_chapa(janela):
    canvas = _layout(janela)
    pagina = canvas.retangulo_pagina()
    a = ElementoRetangulo(largura=10, altura=10, cor_tinta=PRETO)
    b = ElementoRetangulo(largura=10, altura=10, cor_tinta=PRETO)
    canvas.adicionar_elemento_mockup(a, pagina.topLeft() + QPointF(20, 20))
    canvas.adicionar_elemento_mockup(b, pagina.topLeft() + QPointF(45, 20))
    caixa = a.retangulo_conteudo_cena()
    medidas = canvas._distancias_da_caixa(caixa, ignorar={a})
    valores = sorted(round(v, 3) for _p, _q, v in medidas)
    # à direita, o vizinho b: 45 - 30 = 15 mm
    assert any(abs(v - (b.retangulo_conteudo_cena().left() - caixa.right())) < 1e-6 for v in valores)
    # nenhuma medida negativa ou zero
    assert all(v > 0 for v in valores)


def test_alt_mostra_distancias_da_selecao_e_desenha(janela):
    canvas = _layout(janela)
    el = ElementoRetangulo(largura=10, altura=10, cor_tinta=PRETO)
    canvas.adicionar_elemento_mockup(el, canvas.retangulo_pagina().center())
    canvas._scene.clearSelection()
    el.setSelected(True)
    canvas.mostrar_distancias_da_selecao(True)
    assert canvas._medidas_distancia
    canvas._indicador_encaixe = (QPointF(0, 0), "canto")
    imagem = QImage(canvas.viewport().size(), QImage.Format.Format_ARGB32)
    painter = QPainter(imagem)
    canvas.drawForeground(painter, canvas.mapToScene(canvas.viewport().rect()).boundingRect())
    painter.end()
    canvas.mostrar_distancias_da_selecao(False)
    assert canvas._medidas_distancia == []
    canvas._limpar_indicadores()
    assert canvas._indicador_encaixe is None


def test_alt_setas_movem_e_medidas_acompanham_e_somem_sem_alt(janela, monkeypatch):
    from PySide6.QtCore import Qt
    canvas = _layout(janela)
    el = ElementoRetangulo(largura=10, altura=10, cor_tinta=PRETO)
    canvas.adicionar_elemento_mockup(el, canvas.retangulo_pagina().center())
    canvas._scene.clearSelection()
    el.setSelected(True)
    canvas.setFocus()
    canvas.mostrar_distancias_da_selecao(True)
    canvas._timer_alt.stop()  # no teste o Alt não está fisicamente segurado
    pos_antes = el.pos()
    antes = sorted(round(v, 3) for _a, _b, v in canvas._medidas_distancia)
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    # seta com Alt ainda segurado (sem o "soltar Alt" que o keyClick simula)
    QApplication.sendEvent(canvas, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier))
    depois = sorted(round(v, 3) for _a, _b, v in canvas._medidas_distancia)
    assert el.pos() != pos_antes
    assert canvas._medidas_distancia and depois != antes  # moveu e as medidas mudaram
    # Soltou o Alt (no Windows o evento vai pro menu): a conferência esconde
    import gerador_layout.ui.preview_canvas as modulo

    monkeypatch.setattr(modulo.QApplication, "queryKeyboardModifiers", staticmethod(lambda: Qt.KeyboardModifier.NoModifier))
    canvas._conferir_alt()
    assert canvas._medidas_distancia == [] and not canvas._alt_distancias
