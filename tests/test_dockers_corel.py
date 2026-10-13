"""Dockers do CorelDRAW: Objetos, Alinhar e distribuir, Transformações."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402


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


def _ret(janela, x, y, largura=40.0):
    el = ElementoRetangulo(largura=largura, altura=20, cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    janela.canvas.adicionar_elemento_mockup(el, QPointF(x, y))
    return el


def _selecionar(janela, *els):
    janela.canvas.cena.clearSelection()
    for el in els:
        el.setSelected(True)


def test_docker_objetos_lista_e_sincroniza_selecao(janela, app):
    a = _ret(janela, 10, 10)
    b = _ret(janela, 100, 10)
    docker = janela.docker_objetos
    docker.reconstruir()
    itens = {id(it.data(0, Qt.ItemDataRole.UserRole)): it for it in docker._itens() if it.data(0, Qt.ItemDataRole.UserRole)}
    assert id(a) in itens and id(b) in itens
    itens[id(b)].setSelected(True)
    assert b.isSelected() and not a.isSelected()
    _selecionar(janela, a)
    assert itens[id(a)].isSelected()
    itens[id(a)].setCheckState(0, Qt.CheckState.Unchecked)
    assert not a.isVisible() and not a.isSelected()


def test_alinhar_com_pagina_e_distribuir(janela):
    a, b, c = _ret(janela, 0, 10), _ret(janela, 30, 50), _ret(janela, 200, 90)
    _selecionar(janela, a, b, c)
    janela.docker_alinhar.definir_referencia("pagina")
    janela.docker_alinhar._alinhar("base")
    base = janela.canvas.retangulo_pagina().bottom()
    assert all(el.pos().y() + el.altura == pytest.approx(base) for el in (a, b, c))
    janela.canvas.distribuir("h", "centros")
    assert b.pos().x() + 20 == pytest.approx((20 + 220) / 2)
    janela.canvas.pilha_desfazer.undo()
    assert b.pos().x() == pytest.approx(30)


def test_distribuir_espacos(janela):
    a, b, c = _ret(janela, 0, 10, 20), _ret(janela, 25, 10, 40), _ret(janela, 200, 10, 20)
    _selecionar(janela, a, b, c)
    janela.canvas.distribuir("h", "espacos")
    vao1 = b.pos().x() - (a.pos().x() + a.largura)
    vao2 = c.pos().x() - (b.pos().x() + b.largura)
    assert vao1 == pytest.approx(vao2)


def test_transformacoes_com_copias_e_desfazer(janela):
    el = _ret(janela, 10, 10)
    _selecionar(janela, el)
    antes = len(janela.canvas.elementos_mockup)
    docker = janela.docker_transformacoes
    docker.mostrar_aba("posicao")
    docker.dx.setValue(50)
    docker.dy.setValue(0)
    docker.copias.setValue(3)
    docker.aplicar()
    elementos = janela.canvas.elementos_mockup
    assert len(elementos) == antes + 3
    assert el.pos().x() == pytest.approx(10)  # original fica
    assert elementos[-1].pos().x() == pytest.approx(160) and elementos[-1].isSelected()
    janela.canvas.pilha_desfazer.undo()  # um passo desfaz as 3 cópias
    assert len(janela.canvas.elementos_mockup) == antes


def test_transformacao_rotacao_e_espelho_desfaz(janela):
    el = _ret(janela, 10, 10)
    _selecionar(janela, el)
    docker = janela.docker_transformacoes
    docker.copias.setValue(0)
    docker.mostrar_aba("rotacao")
    docker.angulo.setValue(30)
    docker.aplicar()
    assert el.rotation() == pytest.approx(30)
    docker.mostrar_aba("escala")
    docker.espelhar_h.setChecked(True)
    docker.aplicar()
    assert el.espelho_h
    janela.canvas.pilha_desfazer.undo()
    assert not el.espelho_h


def test_atalhos_abrem_docker_so_no_layout(janela):
    janela.show()
    janela.abrir_docker("transformacoes", "escala")
    assert janela._docks["transformacoes"].isVisible()
    assert janela.docker_transformacoes.abas.currentIndex() == 2
    janela.abas_tela.setCurrentIndex(0)
    assert not janela._docks["transformacoes"].isVisible()
    assert not any(a.isEnabled() for a in janela._acoes_docker)
    janela.abas_tela.setCurrentIndex(1)
    assert janela._docks["transformacoes"].isVisible()  # reabre o que estava aberto
