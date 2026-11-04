"""A cinta segue a ficha: 600X90X128 é C × L × A, o riscador sai 90 / 128 / 90
(com mais ou menos medidas se precisar) e a impressora é 600, ou os trechos
do recuo quando há recuo."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.conversao_cinta import cla_das_faixas  # noqa: E402
from gerador_layout.layout_service import ServicoLayoutCaixa  # noqa: E402
from gerador_layout.models import MedidasCaixa, TipoCaixa  # noqa: E402
from gerador_layout.paineis import calcular_paineis  # noqa: E402


def _cinta(**campos):
    base = dict(tipo=TipoCaixa.CINTA, comprimento=600.0, largura=90.0, altura=128.0, impressora_aba=0.0)
    return ServicoLayoutCaixa().calcular(MedidasCaixa(**{**base, **campos}))


def test_a_ficha_600x90x128():
    layout = _cinta()
    assert layout.segmentos_riscador == [90.0, 128.0, 90.0]
    assert layout.segmentos_impressora == [600.0]
    assert (layout.largura_total, layout.altura_total) == (600.0, 308.0)


def test_mais_medidas_no_riscador():
    assert _cinta(riscador_parte_4=20.0, riscador_parte_5=10.0).segmentos_riscador == [90.0, 128.0, 90.0, 20.0, 10.0]


def test_medida_digitada_troca_so_aquele_campo():
    assert _cinta(riscador_centro=100.0).segmentos_riscador == [90.0, 100.0, 90.0]


def test_menos_medidas_no_riscador():
    assert _cinta(faixas_zeradas=(3,)).segmentos_riscador == [90.0, 128.0]


def test_com_recuo_a_impressora_vem_nos_trechos_do_recuo():
    layout = _cinta(impressora_largura_1=5.0, faixas_recuadas=(1, 3))
    assert layout.segmentos_impressora == [5.0, 590.0, 5.0]
    assert layout.largura_total == 600.0
    paineis = calcular_paineis(
        TipoCaixa.CINTA, layout.segmentos_impressora, layout.segmentos_riscador, faixas_recuadas=layout.faixas_recuadas
    )
    assert [(p.x1, p.x2) for p in paineis] == [(5.0, 595.0), (0.0, 600.0), (5.0, 595.0)]


def test_recuo_sem_faixa_marcada_nao_corta_e_impressora_e_uma_so():
    assert _cinta(impressora_largura_1=5.0).segmentos_impressora == [600.0]


@pytest.mark.parametrize("faixas, esperado", [
    ([90.0, 128.0, 90.0], (90.0, 128.0)),
    ([90.0, 55.0, 15.0, 15.0, 90.0], (90.0, 85.0)),
    ([30.0, 50.0], (30.0, 50.0)),
    ([40.0], (0.0, 40.0)),
    ([10.0, 20.0, 30.0], (10.0, 50.0)),
])
def test_l_e_a_lidos_das_faixas(faixas, esperado):
    assert cla_das_faixas(faixas) == esperado


@pytest.fixture
def janela():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.CINTA))
    j.spin_comprimento.setValue(600.0)
    j.spin_largura.setValue(90.0)
    j.spin_altura.setValue(128.0)
    QApplication.processEvents()
    yield j
    j.canvas.pilha_desfazer.clear()
    j.close()


def _efetivos(linha, n):
    return [s.value() for s in linha._spins[:n]]


def test_tela_pede_c_l_a_como_nos_outros_tipos(janela):
    form = janela._form_medidas
    assert form.labelForField(janela.spin_comprimento).text() == "Comprimento (C):"
    assert form.isRowVisible(janela.spin_largura) and form.isRowVisible(janela.spin_altura)
    assert janela.spin_largura.isEnabled()
    assert janela._grupo_medidas_cla.title() == "Medidas C × L × A (mm)"
    assert _efetivos(janela.linha_riscador, 3) == [90.0, 128.0, 90.0]


def test_impressora_mostra_o_recuo_e_nao_se_digita(janela):
    assert not janela.linha_impressora._spins[0].isHidden()
    assert janela.linha_impressora._spins[1].isHidden()
    assert janela.linha_impressora._spins[0].isReadOnly()
    janela.spin_recuo.setValue(5.0)
    janela.checks_faixa_recuada[0].setChecked(True)
    assert not janela.linha_impressora._spins[2].isHidden()
    assert _efetivos(janela.linha_impressora, 3) == [5.0, 590.0, 5.0]
    janela.checks_faixa_recuada[0].setChecked(False)
    assert janela.linha_impressora._spins[1].isHidden()
    assert _efetivos(janela.linha_impressora, 1) == [600.0]


def test_impressora_volta_a_ser_digitada_em_outro_tipo(janela):
    janela.combo_tipo.setCurrentIndex(janela.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    assert not janela.linha_impressora._spins[0].isReadOnly()
    assert not janela.linha_impressora.botao_recalcular.isHidden()


def test_zero_no_riscador_tira_a_faixa_e_recalcular_devolve(janela):
    janela.linha_riscador._spins[2].setValue(0.0)
    assert janela.canvas.layout_efetivo.segmentos_riscador == [90.0, 128.0]
    janela.linha_riscador.botao_recalcular.click()
    assert janela.canvas.layout_efetivo.segmentos_riscador == [90.0, 128.0, 90.0]


def test_folha_sai_em_c_l_a(janela):
    from gerador_layout.ui.folha_aprovacao import texto_medidas

    texto = janela._texto_medidas_folha(janela._obter_medidas(), texto_medidas)
    assert texto == texto_medidas(600.0, 90.0, 128.0)


def test_salvar_e_abrir_guarda_a_faixa_tirada(janela):
    from gerador_layout.ui import projeto_arquivo

    janela.linha_riscador._spins[2].setValue(0.0)
    dados = projeto_arquivo.estado_da_janela(janela)
    janela.linha_riscador.botao_recalcular.click()
    projeto_arquivo.aplicar_na_janela(janela, dados)
    assert janela.canvas.layout_efetivo.segmentos_riscador == [90.0, 128.0]


def test_cinta_antiga_abre_com_a_mesma_faca(janela):
    from gerador_layout.ui import projeto_arquivo

    dados = projeto_arquivo.estado_da_janela(janela)
    dados["caixa"].update(comprimento=500.0, largura=200.0, altura=150.0)
    dados["caixa"]["impressora"] = [700.0, 0.0, 0.0, 0.0, 0.0]
    dados["caixa"]["riscador"] = [30.0, 50.0, 0.0, 0.0, 0.0]
    del dados["caixa"]["cinta"]["faixas_zeradas"]
    projeto_arquivo.aplicar_na_janela(janela, dados)
    layout = janela.canvas.layout_efetivo
    assert (layout.largura_total, layout.segmentos_riscador) == (700.0, [30.0, 50.0])
    assert (janela.spin_comprimento.value(), janela.spin_largura.value(), janela.spin_altura.value()) == (700.0, 30.0, 50.0)


def test_converter_preenche_c_l_a(janela):
    from gerador_layout.models import LinhaDesenho, TipoLinha

    c, v = TipoLinha.CORTE, TipoLinha.VINCO
    janela.combo_tipo.setCurrentIndex(janela.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    janela._faca_do_zero = True
    janela._estilo_atual = ("ULLIAN", {})
    janela.canvas._definir_linhas_editadas([
        LinhaDesenho(0, 0, 810, 0, c), LinhaDesenho(0, 140, 810, 140, c), LinhaDesenho(0, 0, 0, 140, c),
        LinhaDesenho(810, 0, 810, 140, c), LinhaDesenho(0, 90, 810, 90, v),
    ])
    assert janela.converter_em_cinta() is True
    assert (janela.spin_comprimento.value(), janela.spin_largura.value(), janela.spin_altura.value()) == (810.0, 90.0, 50.0)
    assert janela.canvas.layout_efetivo.segmentos_riscador == [90.0, 50.0]  # o campo 3 não volta sozinho


def test_converter_nao_arredonda_as_medidas(janela):
    from gerador_layout.models import LinhaDesenho, TipoLinha

    c, v = TipoLinha.CORTE, TipoLinha.VINCO
    janela._faca_do_zero = True
    janela._estilo_atual = ("ULLIAN", {})
    janela.canvas._definir_linhas_editadas([
        LinhaDesenho(0, 0, 600.25, 0, c), LinhaDesenho(0, 308.25, 600.25, 308.25, c), LinhaDesenho(0, 0, 0, 308.25, c),
        LinhaDesenho(600.25, 0, 600.25, 308.25, c), LinhaDesenho(0, 90.25, 600.25, 90.25, v), LinhaDesenho(0, 218.25, 600.25, 218.25, v),
    ])
    assert janela.converter_em_cinta() is True
    layout = janela.canvas.layout_efetivo
    assert (layout.largura_total, layout.segmentos_riscador) == (600.25, [90.25, 128.0, 90.0])


def test_folha_nao_mostra_c_l_a_que_nao_fecha_com_a_faca(janela):
    from gerador_layout.ui.folha_aprovacao import texto_medidas

    janela.linha_riscador._spins[0].setValue(100.0)
    texto = janela._texto_medidas_folha(janela._obter_medidas(), texto_medidas)
    assert texto == texto_medidas(600.0, 318.0)


def test_zero_em_outro_tipo_nao_fica_preso_ao_abrir(janela):
    from gerador_layout.ui import projeto_arquivo

    janela.combo_tipo.setCurrentIndex(janela.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    janela.linha_riscador._spins[0].setValue(0.0)
    dados = projeto_arquivo.estado_da_janela(janela)
    assert dados["caixa"]["cinta"]["faixas_zeradas"] == []
