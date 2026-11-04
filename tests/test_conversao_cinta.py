"""Converter em Cinta uma faca feita no Construtor: a leitura devolve o que
o tipo Cinta desenharia igual, e recusa o resto em vez de perder detalhe."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from gerador_layout.conversao_cinta import ler_cinta  # noqa: E402
from gerador_layout.layout_service import ServicoLayoutCaixa  # noqa: E402
from gerador_layout.models import FuroCinta, LinhaDesenho, MedidasCaixa, TipoCaixa, TipoLinha  # noqa: E402

C, V = TipoLinha.CORTE, TipoLinha.VINCO


def _construtor(largura=1010.0, faixas=(90.0, 55.0, 15.0, 15.0, 90.0), x0=0.0, y0=0.0):
    """Como o Construtor grava: laterais em pedaços, um por faixa."""
    ys = [y0]
    for f in faixas:
        ys.append(ys[-1] + f)
    linhas = []
    for x in (x0, x0 + largura):
        linhas += [LinhaDesenho(x, a, x, b, C) for a, b in zip(ys, ys[1:])]
    linhas.append(LinhaDesenho(x0, ys[0], x0 + largura, ys[0], C))
    linhas += [LinhaDesenho(x0, y, x0 + largura, y, V) for y in ys[1:-1]]
    linhas.append(LinhaDesenho(x0, ys[-1], x0 + largura, ys[-1], C))
    return linhas


def _calculada(largura, faixas, recuo=0.0, recuadas=(), furos=()):
    nomes = ("riscador_superior", "riscador_centro", "riscador_inferior", "riscador_parte_4", "riscador_parte_5")
    m = MedidasCaixa(
        tipo=TipoCaixa.CINTA, comprimento=largura, largura=0, altura=0, impressora_aba=largura,
        impressora_largura_1=recuo, faixas_recuadas=tuple(recuadas), furos=list(furos), **dict(zip(nomes, faixas)),
    )
    return ServicoLayoutCaixa().calcular(m).linhas


def test_le_a_caixa_668_do_construtor():
    lida = ler_cinta(_construtor())
    assert (lida.largura, lida.faixas) == (1010.0, [90.0, 55.0, 15.0, 15.0, 90.0])
    assert (lida.recuo, lida.faixas_recuadas, lida.furos) == (0.0, (), [])


def test_guarda_onde_a_faca_comecava():
    assert ler_cinta(_construtor(x0=30.0, y0=12.0)).origem == (30.0, 12.0)


@pytest.mark.parametrize("furo", [
    FuroCinta(2, "direita", 200.0, 30.0, 40.0),
    FuroCinta(2, "esquerda", 150.0, 30.0, 40.0, 10.0),
    FuroCinta(2, "direita", 200.0, 20.0, 40.0, 20.0),  # o arco chega no vinco
])
def test_le_o_furo(furo):
    lida = ler_cinta(_calculada(1000.0, [100.0, 80.0, 100.0], furos=[furo]))
    assert lida is not None and lida.furos == [furo]


def test_le_recuo_nas_faixas_das_pontas():
    lida = ler_cinta(_calculada(1000.0, [15.0, 100.0, 15.0], recuo=5.0, recuadas=(1, 3)))
    assert (lida.recuo, lida.faixas_recuadas, lida.faixas) == (5.0, (1, 3), [15.0, 100.0, 15.0])


def test_recuo_furo_e_varias_faixas_juntos():
    furo = FuroCinta(2, "esquerda", 120.0, 25.0, 30.0, 5.0)
    lida = ler_cinta(_calculada(800.0, [10.0, 90.0, 40.0, 90.0, 10.0], recuo=3.0, recuadas=(1, 5), furos=[furo]))
    assert lida.recuo == 3.0 and lida.faixas_recuadas == (1, 5) and lida.furos == [furo]


@pytest.mark.parametrize("extra", [
    LinhaDesenho(100, 10, 200, 60, C),  # corte inclinado
    LinhaDesenho(100, 10, 200, 10, C),  # corte solto no meio da faixa
    LinhaDesenho(300, 0, 300, 90, V),  # vinco vertical: aba, não cinta
    LinhaDesenho(100, 20, 200, 20, V),  # vinco que não vai de lado a lado
    LinhaDesenho(0, 20, 20, 0, C, 0.41),  # canto arredondado
])
def test_recusa_o_que_o_modelo_nao_desenha(extra):
    assert ler_cinta(_construtor() + [extra]) is None


def test_recusa_mais_de_cinco_faixas():
    assert ler_cinta(_construtor(faixas=(10.0,) * 6)) is None


def test_recusa_faca_aberta_ou_vazia():
    assert ler_cinta([]) is None
    assert ler_cinta(_construtor()[1:]) is None


def test_recusa_recuo_de_um_lado_so():
    linhas = _calculada(1000.0, [15.0, 100.0], recuo=5.0, recuadas=(1,))
    so_na_direita = [
        LinhaDesenho(0.0 if l.x1 == 5.0 else l.x1, l.y1, 0.0 if l.x2 == 5.0 else l.x2, l.y2, l.tipo) for l in linhas
    ]
    assert ler_cinta(so_na_direita) is None


@pytest.fixture
def janela(monkeypatch):
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    QApplication.processEvents()
    avisos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: avisos.append(a[2]))
    j.avisos = avisos
    yield j
    j.canvas.pilha_desfazer.clear()
    j.close()


def _faca_do_construtor(janela, linhas):
    janela._faca_do_zero = True
    janela._estilo_atual = ("ULLIAN", {})
    janela.canvas._definir_linhas_editadas(linhas)
    janela.canvas.definir_pagina_pela_faca(True)
    QApplication.processEvents()


def test_botao_so_aparece_na_faca_propria(janela):
    assert janela.botao_converter_cinta.isHidden()
    _faca_do_construtor(janela, _construtor())
    assert not janela.botao_converter_cinta.isHidden()


def test_converter_vira_cinta_com_as_medidas_da_faca(janela):
    _faca_do_construtor(janela, _construtor())
    assert janela.converter_em_cinta() is True
    assert janela.combo_tipo.currentData() == TipoCaixa.CINTA
    assert janela.spin_comprimento.value() == 1010.0
    assert not janela.canvas.faca_editada and not janela._faca_propria
    layout = janela.canvas.layout_efetivo
    assert (layout.largura_total, layout.altura_total) == (1010.0, 265.0)
    assert layout.segmentos_riscador == [90.0, 55.0, 15.0, 15.0, 90.0]
    assert len(janela._paineis_atuais) == 5
    assert not janela._grupo_tipo.isHidden() and not janela.grupo_cinta.isHidden()
    assert janela.aviso_faca_editada.isHidden()


def test_converter_leva_recuo_e_furo_e_mudar_medida_funciona(janela):
    furo = FuroCinta(2, "direita", 200.0, 30.0, 40.0)
    _faca_do_construtor(janela, _calculada(1000.0, [15.0, 100.0, 15.0], recuo=5.0, recuadas=(1, 3), furos=[furo]))
    assert janela.converter_em_cinta() is True
    assert janela.spin_recuo.value() == 5.0
    assert [c.isChecked() for c in janela.checks_faixa_recuada] == [True, False, True, False, False]
    assert janela._furos_cinta() == [furo]
    janela.spin_comprimento.setValue(1200.0)
    assert janela.canvas.layout_efetivo.largura_total == 1200.0


def test_a_arte_acompanha_a_faca_e_perde_a_face_que_sumiu(janela):
    from gerador_layout.ui.mockup_cota import criar_cota
    from PySide6.QtCore import QPointF

    _faca_do_construtor(janela, _construtor(x0=30.0, y0=12.0))
    objeto = criar_cota(QPointF(130, 52), QPointF(230, 52), "horizontal", 5.0)
    objeto.definir_painel("face_99")
    janela.canvas.adicionar_elemento_mockup(objeto)
    antes = objeto.pos()
    assert janela.converter_em_cinta() is True
    assert (objeto.pos().x(), objeto.pos().y()) == (antes.x() - 30.0, antes.y() - 12.0)
    assert objeto.painel_id is None


def test_faca_que_nao_cabe_avisa_e_nao_muda_nada(janela):
    linhas = _construtor() + [LinhaDesenho(300, 0, 300, 90, V)]
    _faca_do_construtor(janela, linhas)
    tipo = janela.combo_tipo.currentData()
    assert janela.converter_em_cinta() is False
    assert janela.avisos and "cinta" in janela.avisos[0].lower()
    assert janela.combo_tipo.currentData() == tipo
    assert janela.canvas.faca_editada and len(janela.canvas.linhas_faca()) == len(linhas)


@pytest.mark.parametrize("tipo_antes", [TipoCaixa.MALETA_NORMAL, TipoCaixa.CINTA])
def test_arte_nao_acompanha_as_faces_de_passagem(janela, tipo_antes):
    from gerador_layout.ui.mockup_cota import criar_cota
    from PySide6.QtCore import QPointF

    janela.combo_tipo.setCurrentIndex(janela.combo_tipo.findData(tipo_antes))
    _faca_do_construtor(janela, _construtor())
    objeto = criar_cota(QPointF(100, 95), QPointF(300, 95), "horizontal", 5.0)
    janela.canvas.adicionar_elemento_mockup(objeto)
    antes = (objeto.pos().x(), objeto.pos().y())
    assert janela.converter_em_cinta() is True
    assert (objeto.pos().x(), objeto.pos().y()) == antes


def test_medida_em_meio_decimo_nao_e_recusada():
    assert ler_cinta(_construtor(largura=1010.25, faixas=(12.25, 55.05, 12.15), x0=0.15, y0=0.35)) is not None


def test_conversao_nao_deixa_desfazer_pela_metade(janela):
    _faca_do_construtor(janela, _construtor())
    assert janela.converter_em_cinta() is True
    assert not janela.canvas.pilha_desfazer.canUndo()
