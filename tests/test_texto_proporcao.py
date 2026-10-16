"""O texto não pode sair esticado depois de ficar vazio: com a letra
pequena, a caixa do texto vazio batia no tamanho mínimo e a próxima letra
herdava essa largura (um "C" largo)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.ui.mockup_texto import ElementoTexto  # noqa: E402


def _proporcao(el: ElementoTexto) -> float:
    ex, ey = el._escalas()
    return ex / ey


@pytest.mark.parametrize("pt", [24.0, 8.0, 4.0, 1.0])
def test_apagar_tudo_e_digitar_de_novo_nao_estica(pt):
    el = ElementoTexto("CUIDADO")
    el.definir_tamanho_pt(pt)
    el.definir_texto("")
    el.definir_texto("C")
    assert _proporcao(el) == pytest.approx(1.0)
    assert el.tamanho_pt == pytest.approx(pt)


@pytest.mark.parametrize("pt", [24.0, 6.0, 1.0])
def test_texto_novo_pequeno_nao_estica(pt):
    el = ElementoTexto("")
    el.definir_tamanho_pt(pt)
    el._inserir("C")  # o que a tecla digitada faz
    assert el.texto == "C"
    assert _proporcao(el) == pytest.approx(1.0)
    assert el.tamanho_pt == pytest.approx(pt)


def test_esticar_a_caixa_continua_valendo():
    el = ElementoTexto("AB")
    el.definir_tamanho(el.largura * 2, el.altura)
    el.definir_texto("ABC")
    assert _proporcao(el) == pytest.approx(2.0)
    # desfazer/refazer volta a escala junto com o tamanho
    antes = el.estado_texto()
    el.definir_texto("")
    el.definir_estado_texto(antes)
    assert _proporcao(el) == pytest.approx(2.0)
    assert el.pos() == QPointF(antes[3])


def test_espaco_entre_letras_e_linhas_como_o_f10():
    el = ElementoTexto("ABCD\nEFGH", fonte_familia="Arial Black")
    el.aplicar_letra(2.0, 0.667)
    largura, altura = el.largura, el.altura
    el.definir_espaco_letras(0.2)  # afasta 20%
    assert el.largura > largura and el.altura == pytest.approx(altura)
    assert el.altura_letra_mm == pytest.approx(2.0) and el.largura_letra == pytest.approx(0.667, abs=1e-3)
    el.definir_espaco_letras(-0.1)  # aproxima
    assert el.largura < largura
    el.definir_espaco_letras(0.0)
    assert el.largura == pytest.approx(largura)
    el.definir_espaco_linhas(0.8)  # linhas mais perto
    assert el.altura < altura and el.altura_letra_mm == pytest.approx(2.0)
    copia = el.clonar()
    assert (copia.espaco_letras, copia.espaco_linhas) == (0.0, pytest.approx(0.8))


def test_espaco_no_checklist_e_no_projeto():
    from gerador_layout.ui import projeto_arquivo
    from gerador_layout.ui.mockup_checklist import ElementoChecklistCores

    c = ElementoChecklistCores(["20 UN.", "30 UN."], fonte_familia="Arial Black", largura_letra=0.667)
    c.definir_altura_letra_mm(2.0)
    c.definir_espaco_letras(0.0)  # largura natural do texto, sem espaço extra
    altura, largura = c.altura, c.largura
    c.definir_espaco_linhas(0.7)
    assert c.altura < altura
    c.definir_espaco_letras(0.15)
    assert c.largura > largura
    d = projeto_arquivo.elemento_para_dict(c, projeto_arquivo._Arquivos())
    volta = projeto_arquivo.elemento_de_dict(d, projeto_arquivo._Arquivos())
    assert (volta.espaco_letras, volta.espaco_linhas) == (pytest.approx(0.15), pytest.approx(0.7))
    t = ElementoTexto("AB")
    t.definir_espaco_letras(0.3)
    t.definir_espaco_linhas(1.5)
    d = projeto_arquivo.elemento_para_dict(t, projeto_arquivo._Arquivos())
    volta = projeto_arquivo.elemento_de_dict(d, projeto_arquivo._Arquivos())
    assert (volta.espaco_letras, volta.espaco_linhas) == (pytest.approx(0.3), pytest.approx(1.5))
    assert volta.largura == pytest.approx(t.largura)
