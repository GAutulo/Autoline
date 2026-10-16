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
