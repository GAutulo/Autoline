"""Tela de Início (REDESIGN.md 2.2): cria a faca com tipo + C × L × A,
estilos e recentes; entra e sai sem mexer no trabalho."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.models import TipoCaixa  # noqa: E402
from gerador_layout.ui.main_window import JanelaPrincipal  # noqa: E402


def test_criar_faca_pelo_inicio_e_voltar():
    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    assert not j.no_inicio  # sem o main.py, começa no trabalho (como os outros testes)
    j.mostrar_inicio()
    QApplication.processEvents()
    assert j.no_inicio and not j.barra_faca.isVisible() and not j.barra_ferramentas_faca.isVisible()
    inicio = j.tela_inicio
    inicio.cartoes["Maleta transpassada"].click()
    inicio.spins["c"].setValue(54)
    inicio.spins["l"].setValue(54)
    inicio.spins["a"].setValue(38)
    inicio.botao_criar.click()
    QApplication.processEvents()
    assert not j.no_inicio and j.abas_tela.currentIndex() == 0 and j.barra_faca.isVisible()
    assert j.combo_tipo.currentData() == TipoCaixa.MALETA_TRANSPASSADA
    assert (j.spin_comprimento.value(), j.spin_largura.value(), j.spin_altura.value()) == pytest.approx((54, 54, 38))
    # o símbolo do logotipo volta pro Início; o seletor de telas sai dele
    j.barra_titulo.simbolo.ao_clicar()
    assert j.no_inicio
    j.abas_tela.tabBarClicked.emit(1)
    QApplication.processEvents()
    assert not j.no_inicio
    j.close()


def test_recentes_no_inicio(tmp_path):
    from gerador_layout.ui import configuracoes

    j = JanelaPrincipal()
    caminho = j._gravar_projeto(str(tmp_path / "32844 MESA CENTRO")) or str(tmp_path / "32844 MESA CENTRO.autoline")
    configuracoes.adicionar_projeto_recente(str(caminho))
    j.mostrar_inicio()
    lista = j.tela_inicio.lista_recentes
    textos = [lista.item(i).text() for i in range(lista.count())]
    assert any("32844 MESA CENTRO" in t for t in textos)
    j.close()


@pytest.mark.parametrize(
    "cartao, opcoes, tipo",
    [
        ("Maleta normal", ["Meia caixa"], TipoCaixa.MALETA_NORMAL_MEIA),
        ("Maleta transpassada", ["Inteira"], TipoCaixa.MALETA_TRANSPASSADA),
        ("Envoltório", ["No meio", "Sem corte"], TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_SEM_CORTE),
        ("Envoltório", ["Com corte"], TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE),
        ("Envoltório capa", [], TipoCaixa.ENVOLTORIO_CAPA),
    ],
)
def test_inicio_ja_escolhe_o_tipo_exato(cartao, opcoes, tipo):
    """O tipo exato sai do Início (meia caixa, com/sem corte, fecha no meio):
    não precisa trocar de novo na Dieline."""
    j = JanelaPrincipal()
    j.show()
    j.mostrar_inicio()
    inicio = j.tela_inicio
    inicio.cartoes[cartao].click()
    for opcao in opcoes:
        inicio.escolher_variante(opcao)
    assert inicio.tipo_escolhido == tipo
    inicio.botao_criar.click()
    QApplication.processEvents()
    assert j.combo_tipo.currentData() == tipo
    j.close()


def test_clicar_de_novo_no_cartao_escolhido_mantem_a_variante():
    j = JanelaPrincipal()
    j.show()
    j.mostrar_inicio()
    inicio = j.tela_inicio
    inicio.cartoes["Maleta normal"].click()
    inicio.escolher_variante("Meia caixa")
    inicio.cartoes["Maleta normal"].click()
    assert inicio.tipo_escolhido == TipoCaixa.MALETA_NORMAL_MEIA
    j.close()
