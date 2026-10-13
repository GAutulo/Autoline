"""Modelar (CorelDRAW): Soldar, Aparar, Interseção, Frente/Atrás."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_curva import ElementoCurva  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoElipse, ElementoRetangulo  # noqa: E402
from gerador_layout.ui.modelagem import modelar  # noqa: E402

VERMELHO = CorImpressao("VERMELHO", 255, 0, 0)
AZUL = CorImpressao("AZUL", 0, 0, 255)


def _ret(x, y, l, a):
    c = QPainterPath()
    c.addRect(QRectF(x, y, l, a))
    return c


@pytest.mark.parametrize(
    "op, dentro, fora",
    [
        ("soldar", [(10, 5), (30, 20), (50, 20)], [(50, 5)]),
        ("aparar", [(10, 5)], [(30, 20), (50, 20)]),
        ("intersecao", [(30, 20)], [(10, 5), (50, 20)]),
        ("frente_menos_atras", [(50, 20)], [(30, 20), (10, 5)]),
        ("atras_menos_frente", [(10, 5)], [(30, 20), (50, 20)]),
    ],
)
def test_operacoes(op, dentro, fora):
    # Baixo: quadrado 0..40; cima: retângulo 20..60 x 10..30.
    r = modelar(op, [_ret(0, 0, 40, 40), _ret(20, 10, 40, 20)])
    assert all(r.contains(QPointF(*p)) for p in dentro)
    assert not any(r.contains(QPointF(*p)) for p in fora)


def test_limpa_nos_colineares():
    r = modelar("soldar", [_ret(0, 0, 40, 40), _ret(0, 40, 40, 40)])  # dois quadrados empilhados
    pontos = r.toSubpathPolygons()[0]
    assert pontos.count() == 5  # retângulo 40x80: 4 cantos + fechamento, sem o nó do meio


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(1)
    yield j
    j.close()


def _dois(janela):
    baixo = ElementoRetangulo(largura=40, altura=40, cor_tinta=VERMELHO, preenchido=True)
    cima = ElementoElipse(largura=40, altura=20, cor_tinta=AZUL, preenchido=True)
    janela.canvas.adicionar_elemento_mockup(baixo, QPointF(100, 100))
    janela.canvas.adicionar_elemento_mockup(cima, QPointF(120, 110))
    baixo.setZValue(1)
    cima.setZValue(2)
    janela.canvas.cena.clearSelection()
    baixo.setSelected(True)
    cima.setSelected(True)
    return baixo, cima


def test_soldar_substitui_e_desfaz(janela):
    canvas = janela.canvas
    baixo, cima = _dois(janela)
    resultado = canvas.modelar_selecionados("soldar")
    assert isinstance(resultado, ElementoCurva) and resultado.isSelected()
    assert baixo not in canvas.elementos_mockup and cima not in canvas.elementos_mockup
    assert resultado.cor_tinta.nome == "VERMELHO"  # aparência do de baixo
    assert resultado.caminho_cena().contains(QPointF(155, 120))  # pedaço da elipse
    canvas.pilha_desfazer.undo()
    assert baixo in canvas.elementos_mockup and cima in canvas.elementos_mockup
    assert resultado not in canvas.elementos_mockup


def test_aparar_mantem_o_de_cima(janela):
    canvas = janela.canvas
    baixo, cima = _dois(janela)
    resultado = canvas.modelar_selecionados("aparar")
    assert cima in canvas.elementos_mockup and baixo not in canvas.elementos_mockup
    assert not resultado.caminho_cena().contains(QPointF(130, 120))  # recortado pela elipse
    assert resultado.caminho_cena().contains(QPointF(105, 135))


def test_intersecao_mantem_os_dois_e_fica_por_cima(janela):
    canvas = janela.canvas
    baixo, cima = _dois(janela)
    resultado = canvas.modelar_selecionados("intersecao")
    assert baixo in canvas.elementos_mockup and cima in canvas.elementos_mockup
    assert resultado.zValue() > cima.zValue()
    assert resultado.caminho_cena().contains(QPointF(130, 120))
    assert not resultado.caminho_cena().contains(QPointF(155, 120))


def test_frente_menos_atras_usa_a_aparencia_do_de_cima(janela):
    canvas = janela.canvas
    _dois(janela)
    resultado = canvas.modelar_selecionados("frente_menos_atras")
    assert resultado.cor_tinta.nome == "AZUL"
    assert resultado.caminho_cena().contains(QPointF(155, 120))
    assert not resultado.caminho_cena().contains(QPointF(130, 120))


def test_sem_sobreposicao_nao_faz_nada(janela):
    canvas = janela.canvas
    a = ElementoRetangulo(largura=10, altura=10, cor_tinta=VERMELHO, preenchido=True)
    b = ElementoRetangulo(largura=10, altura=10, cor_tinta=VERMELHO, preenchido=True)
    canvas.adicionar_elemento_mockup(a, QPointF(0, 0))
    canvas.adicionar_elemento_mockup(b, QPointF(300, 300))
    canvas.cena.clearSelection()
    a.setSelected(True)
    b.setSelected(True)
    mensagens = []
    canvas.mensagem_status.connect(mensagens.append)
    assert canvas.modelar_selecionados("intersecao") is None
    assert mensagens and "não se sobrepõem" in mensagens[-1]


def test_botoes_na_barra_com_varios_selecionados(janela):
    _dois(janela)
    janela._ao_selecao_mockup_mudar()
    botao = next(b for b in janela.painel_propriedades_mockup.findChildren(QToolButton) if b.objectName() == "modelar_soldar")
    antes = len(janela.canvas.elementos_mockup)
    botao.click()
    assert len(janela.canvas.elementos_mockup) == antes - 1
