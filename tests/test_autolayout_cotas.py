"""Autolayout (etapa 1): a arte acompanha a face quando as medidas mudam.
Cotas automáticas: um clique cota a faca; saem na folha de aprovação."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao, TipoCaixa  # noqa: E402
from gerador_layout.paineis import Painel, deslocamento_na_face  # noqa: E402
from gerador_layout.ui.mockup_cota import ElementoCota  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402


def _face(x1, y1, x2, y2):
    return Painel("f", "F", x1, y1, x2, y2, eh_aba=False)


def test_mantem_a_distancia_da_borda_mais_proxima():
    velha, nova = _face(0, 0, 100, 100), _face(10, 0, 210, 150)
    assert deslocamento_na_face(5, 5, 15, 15, velha, nova) == pytest.approx((10, 0))  # perto da esquerda e do topo
    assert deslocamento_na_face(80, 80, 95, 95, velha, nova) == pytest.approx((110, 50))  # direita e base
    assert deslocamento_na_face(40, 40, 60, 60, velha, nova) == pytest.approx((60, 25))  # centralizado continua


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


def _ret(j, x, y):
    el = ElementoRetangulo(largura=20, altura=10, cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    j.canvas.adicionar_elemento_mockup(el, QPointF(x, y))
    return el


def _frente(j):
    return next(p for p in j._paineis_disponiveis() if p.id == "frente")


def test_arte_acompanha_a_face_quando_o_comprimento_muda(janela):
    f = _frente(janela)
    direita = _ret(janela, f.x2 - 25, f.y1 + 20)  # 5 mm da borda direita
    meio = _ret(janela, (f.x1 + f.x2) / 2 - 10, f.y1 + 60)
    fora = _ret(janela, -100, -100)
    janela.spin_comprimento.setValue(400)
    QApplication.processEvents()
    g = _frente(janela)
    assert g.x2 - (direita.pos().x() + 20) == pytest.approx(5)
    assert meio.pos().x() + 10 == pytest.approx((g.x1 + g.x2) / 2)
    assert (fora.pos().x(), fora.pos().y()) == (-100, -100)


def test_cotas_automaticas_pelos_vincos_e_apagaveis(janela):
    canvas = janela.canvas
    assert canvas.gerar_cotas_automaticas() == 10  # 5 colunas + total, 3 linhas + total
    cotas = [e for e in canvas.elementos_mockup if isinstance(e, ElementoCota)]
    assert len(cotas) == 10
    assert canvas.gerar_cotas_automaticas() == 10  # gerar de novo não duplica
    assert len([e for e in canvas.elementos_mockup if isinstance(e, ElementoCota)]) == 10
    canvas.pilha_desfazer.undo()
    canvas.pilha_desfazer.undo()
    assert not [e for e in canvas.elementos_mockup if isinstance(e, ElementoCota)]


def test_folha_inclui_as_cotas(janela, tmp_path, monkeypatch):
    from gerador_layout.ui import folha_aprovacao

    canvas = janela.canvas
    pagina = canvas.retangulo_pagina()
    canvas.gerar_cotas_automaticas()
    area = canvas.retangulo_com_cotas()
    assert area.top() < pagina.top() and area.left() < pagina.left()
    visto = {}
    original = folha_aprovacao.gerar_pdf

    def espiao(*args, **kwargs):
        visto.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(folha_aprovacao, "gerar_pdf", espiao)

    def preencher(dialogo):
        dialogo.check_3d.setChecked(False)
        return True

    assert janela.gerar_folha_aprovacao(str(tmp_path / "f.pdf"), dialogo=preencher, abrir=False)
    assert visto["area_desenho"] == area


def test_centro_da_face_e_alvo_de_encaixe_mesmo_em_automatica(janela):
    canvas = janela.canvas
    f = _frente(janela)
    el = _ret(janela, f.x1 + 5, f.y1 + 5)
    el.definir_painel(None)
    assert (f.x1 + f.x2) / 2 in canvas._alvos_snap_x(el)
    assert (f.y1 + f.y2) / 2 in canvas._alvos_snap_y(el)
    rotulos = [nome for _p, nome in canvas.nos_de_encaixe_com_tipo()]
    assert "centro da face" in rotulos
