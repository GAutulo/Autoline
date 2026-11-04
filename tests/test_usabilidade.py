"""Revisão de usabilidade: um lugar só pra alinhar (com referência
escolhida), inspetor sem campos mortos, face automática, cores do logotipo
editáveis, tinta nova sem sair do Layout e 3D com a tela toda."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QToolButton  # noqa: E402

from gerador_layout.models import CorImpressao, TipoCaixa  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402

PRETO = CorImpressao("PRETO", 0, 0, 0)


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


def _ret(j, x, y, largura=20.0, altura=10.0):
    el = ElementoRetangulo(largura=largura, altura=altura, cor_tinta=PRETO)
    j.canvas.adicionar_elemento_mockup(el, QPointF(x, y))
    return el


def _selecionar(j, *els):
    j.canvas.cena.clearSelection()
    for el in els:
        el.setSelected(True)
    QApplication.processEvents()


def test_alinhar_mora_so_na_aba_alinhar(janela):
    painel = janela.painel_propriedades_mockup
    a, b = _ret(janela, 10, 10), _ret(janela, 60, 40)
    _selecionar(janela, a)
    assert not [x for x in painel.inspetor.findChildren(QToolButton) if x.objectName() == "botaoAlinharFace"]
    _selecionar(janela, a, b)
    assert not [x for x in painel.findChildren(QToolButton) if "Alinhar" in x.toolTip()]
    assert not [x for x in janela.barra_organizar.actions() if "Alinhar" in x.text()]


def test_escolher_o_objeto_de_referencia_do_alinhamento(janela):
    a, b, c = _ret(janela, 10, 10), _ret(janela, 60, 40), _ret(janela, 120, 70)
    _selecionar(janela, a, b, c)
    docker = janela.docker_alinhar
    assert docker.combo_referencia.count() == 4  # os 3 e a área da seleção
    docker.combo_referencia.setCurrentIndex(2)  # o 3º selecionado fica parado
    referencia = docker.objeto_referencia()
    x = referencia.pos().x()
    docker._alinhar_com("selecao", "esquerda")
    assert all(el.pos().x() == pytest.approx(x) for el in (a, b, c))
    janela.canvas.pilha_desfazer.undo()
    assert a.pos().x() == pytest.approx(10)


def test_alinhar_na_area_da_selecao(janela):
    a, b = _ret(janela, 10, 10), _ret(janela, 60, 40)
    _selecionar(janela, a, b)
    docker = janela.docker_alinhar
    docker.combo_referencia.setCurrentIndex(docker.combo_referencia.count() - 1)
    docker._alinhar_com("selecao", "direita")
    assert a.pos().x() == pytest.approx(60) and b.pos().x() == pytest.approx(60)


def test_inspetor_sem_selecao_nao_mostra_campos_mortos(janela):
    painel = janela.painel_propriedades_mockup
    _selecionar(janela)
    assert painel._fixo.isHidden() and painel._botao_remover.isHidden()
    assert "Clique" in painel.dica_inspetor.text() and not painel.dica_inspetor.isHidden()
    a, b = _ret(janela, 10, 10), _ret(janela, 60, 40)
    _selecionar(janela, a)
    assert not painel._fixo.isHidden() and painel.dica_inspetor.isHidden()
    _selecionar(janela, a, b)
    assert painel._fixo.isHidden() and not painel._botao_remover.isHidden()
    assert "Alinhar" in painel.dica_inspetor.text()


def test_aba_alinhar_sem_selecao_so_tem_a_dica(janela):
    docker = janela.docker_alinhar
    _selecionar(janela)
    assert docker.conteudo.isHidden() and not docker.dica_vazia.isHidden()
    _selecionar(janela, _ret(janela, 10, 10))
    assert not docker.conteudo.isHidden() and docker.dica_vazia.isHidden()


def test_face_automatica_pela_posicao(janela):
    painel = janela.painel_propriedades_mockup
    frente = next(p for p in janela._paineis_disponiveis() if p.id == "frente")
    el = _ret(janela, frente.x1 + 10, frente.y1 + 10)
    el.definir_painel(None)
    _selecionar(janela, el)
    combo = painel.inspetor.findChild(QComboBox, "comboPainel")
    assert combo.itemText(0) == "Automática" and combo.maximumWidth() > 1000
    assert painel._subtitulo_inspetor.text() == "Frente"
    assert "Na face Frente" in painel._caixa_info.text()


def test_nova_tinta_nao_sai_do_layout(janela, monkeypatch):
    chamou = []
    monkeypatch.setattr(janela, "_nova_cor_personalizada", lambda: chamou.append(1) or True)
    janela._nova_tinta_inspetor()
    assert chamou and janela.abas_tela.currentIndex() == 1


def test_organizar_so_liga_com_algo_selecionado(janela):
    _selecionar(janela)
    assert not any(a.isEnabled() for a in janela._acoes_organizar)
    _selecionar(janela, _ret(janela, 10, 10))
    assert all(a.isEnabled() for a in janela._acoes_organizar)


def test_3d_usa_a_tela_toda(janela):
    janela.abas_tela.setCurrentIndex(2)
    QApplication.processEvents()
    assert janela.painel_esquerdo.isHidden() and janela._grupo_medidas.isHidden()
    janela.abas_tela.setCurrentIndex(0)
    QApplication.processEvents()
    assert not janela.painel_esquerdo.isHidden() and not janela._grupo_medidas.isHidden()


def test_cinta_esconde_l_e_a(janela):
    janela.abas_tela.setCurrentIndex(0)
    janela.combo_tipo.setCurrentIndex(janela.combo_tipo.findData(TipoCaixa.CINTA))
    assert not janela._form_medidas.isRowVisible(janela.spin_largura)
    assert not janela._form_medidas.isRowVisible(janela.spin_altura)
    janela.combo_tipo.setCurrentIndex(janela.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    assert janela._form_medidas.isRowVisible(janela.spin_largura)
    janela.mostrar_inicio()
    janela.tela_inicio.cartoes["Cinta"].click()
    assert not janela.tela_inicio.spins["l"].isEnabled() and not janela.tela_inicio.spins["a"].isEnabled()
    janela.tela_inicio.cartoes["Maleta normal"].click()
    assert janela.tela_inicio.spins["l"].isEnabled()


SVG_DUAS_CORES = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10">'
    '<rect width="10" height="10" fill="#ff0000"/><rect x="10" width="10" height="10" fill="#0000ff"/></svg>'
)


def _combos_de_cor(painel) -> dict:
    return {c.property("corOriginal"): c for c in painel.inspetor.findChildren(QComboBox) if c.property("corOriginal")}


def test_cores_do_logo_editaveis_depois_de_pronto(janela, tmp_path):
    from gerador_layout.ui.mockup_logo import ElementoLogoVetorial

    arquivo = tmp_path / "logo.svg"
    arquivo.write_text(SVG_DUAS_CORES, encoding="utf-8")
    logo = ElementoLogoVetorial(str(arquivo))
    janela.canvas.adicionar_elemento_mockup(logo, QPointF(20, 20))
    janela._chips_cor["Vermelho"][0].setChecked(True)
    _selecionar(janela, logo)
    painel = janela.painel_propriedades_mockup
    combos = _combos_de_cor(painel)
    assert set(combos) == {"#ff0000", "#0000ff"}
    combos["#0000ff"].setCurrentIndex(combos["#0000ff"].findText("PRETO"))
    assert logo.mapa_cores == {"#0000ff": "#000000"}
    # selecionar de novo mostra o que foi escolhido, e mudar a outra não apaga
    _selecionar(janela)
    _selecionar(janela, logo)
    combos = _combos_de_cor(painel)
    assert combos["#0000ff"].currentText() == "PRETO"
    combos["#ff0000"].setCurrentIndex(combos["#ff0000"].findText("VERMELHO"))
    assert logo.mapa_cores == {"#0000ff": "#000000", "#ff0000": "#ff0000"}
    janela.canvas.pilha_desfazer.undo()  # trocas seguidas: um passo só, como nas outras propriedades
    assert logo.mapa_cores == {}
