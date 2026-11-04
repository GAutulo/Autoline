"""Faca que não vem de um tipo de caixa (Construtor, catálogo, em branco):
as faces, o painel, a chapa e a folha falam da faca real, não do tipo de
caixa que estava parado na tela."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from gerador_layout.models import LinhaDesenho, TipoLinha  # noqa: E402
from gerador_layout.paineis import faces_da_faca  # noqa: E402


def _faca(largura=1000.0, ys=(100.0, 200.0), altura=300.0):
    c = TipoLinha.CORTE
    linhas = [
        LinhaDesenho(0, 0, largura, 0, c),
        LinhaDesenho(0, altura, largura, altura, c),
        LinhaDesenho(0, 0, 0, altura, c),
        LinhaDesenho(largura, 0, largura, altura, c),
    ]
    return linhas + [LinhaDesenho(0, y, largura, y, TipoLinha.VINCO) for y in ys]


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


def _usar_faca(j, nome="ULLIAN", linhas=None):
    j._faca_do_zero = True
    j.canvas.definir_pagina_pela_faca(True)
    j.canvas._aplicar_faca("Estilo", linhas if linhas is not None else _faca())
    j._estilo_atual = (nome, {}) if nome else None
    j._atualizar_estado_faca()
    QApplication.processEvents()


def test_faces_saem_das_linhas_da_faca():
    faces = faces_da_faca(_faca())
    assert [f.nome for f in faces] == ["Face 1", "Face 2", "Face 3"]
    assert [(f.x1, f.y1, f.x2, f.y2) for f in faces] == [
        (0, 0, 1000, 100),
        (0, 100, 1000, 200),
        (0, 200, 1000, 300),
    ]
    assert faces_da_faca([]) == []


def test_faca_do_construtor_nao_mostra_as_faces_do_tipo(janela):
    _usar_faca(janela)
    assert [p.nome for p in janela._paineis_disponiveis()] == ["Face 1", "Face 2", "Face 3"]
    # o "Na face" e as medidas até a borda usam as mesmas
    assert [p.nome for p in janela.canvas._paineis] == ["Face 1", "Face 2", "Face 3"]


def test_faces_acompanham_a_edicao_da_faca(janela):
    _usar_faca(janela)
    janela.canvas._aplicar_faca("Vinco", _faca(ys=(100.0, 150.0, 200.0)))
    QApplication.processEvents()
    assert len(janela._paineis_disponiveis()) == 4


def test_painel_esquerdo_nao_mostra_tipo_nem_medidas_que_nao_valem(janela):
    _usar_faca(janela)
    for grupo in (janela._grupo_tipo, janela._grupo_medidas_cla, janela._grupo_medidas):
        assert grupo.isHidden()
    texto = janela.texto_aviso_faca.text()
    assert "ULLIAN" in texto and "editada à mão" not in texto
    janela.canvas.descartar_edicoes_faca()
    QApplication.processEvents()
    assert not janela._grupo_tipo.isHidden() and not janela._grupo_medidas_cla.isHidden()
    assert "Frente" in [p.nome for p in janela._paineis_disponiveis()]


def test_faca_editada_a_partir_do_tipo_continua_com_as_faces_do_tipo(janela):
    janela.canvas._aplicar_faca("Editar", list(janela.canvas.linhas_faca())[:-1])
    QApplication.processEvents()
    assert "Frente" in [p.nome for p in janela._paineis_disponiveis()]
    assert not janela._grupo_tipo.isHidden()
    assert "editada à mão" in janela.texto_aviso_faca.text()


def test_chapa_da_linha_de_contexto_e_a_da_faca(janela):
    janela.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    _usar_faca(janela)
    janela.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    rotulo = janela.painel_propriedades_mockup.findChild(QLabel, "rotuloPaginaPropriedade")
    assert "1000,0 × 300,0" in rotulo.text()


def test_folha_de_aprovacao_usa_o_nome_e_o_tamanho_da_faca(janela, tmp_path):
    _usar_faca(janela)
    vistos = {}

    def preencher(dialogo):
        vistos.update(medidas=dialogo.campo_medidas.text(), tipo=dialogo.campo_tipo.text())
        dialogo.check_3d.setChecked(False)
        return True

    assert janela.gerar_folha_aprovacao(str(tmp_path / "f.pdf"), dialogo=preencher, abrir=False)
    assert vistos == {"medidas": "10000X3000", "tipo": "ULLIAN"}


def test_faca_em_branco_nao_tem_faces_de_caixa(janela):
    janela._nova_faca_em_branco()
    QApplication.processEvents()
    assert janela._paineis_disponiveis() == []
    assert "do zero" in janela.texto_aviso_faca.text()
