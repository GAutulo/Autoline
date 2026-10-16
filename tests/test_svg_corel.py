"""SVG do CorelDRAW: o 'm' relativo depois de 'z' conta do último ponto
desenhado (o bico do Blue Moby subia ~4 cm no SVG)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.svg_corel import corrigir_caminho, corrigir_svg_corel  # noqa: E402

# Tira aberta (termina em 10,100, não onde começou) + quadrado 5 abaixo do último ponto.
_CAMINHO = "M10 0 l0 100z m0 5 l20 0 0 20 -20 0z"


def test_m_depois_de_z_conta_do_ultimo_ponto():
    corrigido = corrigir_caminho(_CAMINHO)
    assert "M 10 105" in corrigido.replace("M10", "M 10")
    # o resto do caminho fica igual
    assert corrigido.endswith("l 20 0 0 20 -20 0 z") or corrigido.endswith("l20 0 0 20 -20 0z") or "20 0 0 20 -20 0" in corrigido


def test_caminho_que_fecha_no_comeco_nao_muda_de_lugar():
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    d = "M0 0 l10 0 0 10 -10 0 0 -10z m20 0 l10 0 0 10 -10 0 0 -10z"  # termina onde começou, como o Corel grava

    def caixa(caminho):
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50"><path id="p" d="{caminho}"/></svg>'
        return QSvgRenderer(QByteArray(svg.encode())).boundsOnElement("p")

    assert caixa(corrigir_caminho(d)) == caixa(d)


def test_so_mexe_em_svg_do_corel():
    outro = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="{_CAMINHO}"/></svg>'
    assert corrigir_svg_corel(outro) == outro
    corel = "<!-- Creator: CorelDRAW 2020 (64 Bit) -->\n" + outro
    assert corrigir_svg_corel(corel) != corel
    assert 'id="Camada"' in corrigir_svg_corel(corel.replace("<path", '<g id="Camada"/><path'))


def test_caminho_estranho_fica_como_esta():
    assert corrigir_caminho("M0 0 z m") == "M0 0 z m"
    assert corrigir_caminho("") == ""
    assert corrigir_caminho("M0 0 L10 10") == "M0 0 L10 10"


def test_logo_do_corel_abre_no_lugar_certo(tmp_path):
    """O bico (2º subcaminho) tem que ficar ao lado da tira, não 100 acima."""
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from gerador_layout.ui.mockup_logo import ElementoLogoVetorial

    svg = (
        "<!-- Creator: CorelDRAW 2020 (64 Bit) -->\n"
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="200mm" viewBox="0 0 100 200">'
        '<rect x="0" y="100" width="10" height="10"/>'
        f'<path d="{_CAMINHO}"/></svg>'
    )
    caminho = tmp_path / "logo.svg"
    caminho.write_text(svg, encoding="utf-8")
    el = ElementoLogoVetorial(str(caminho))
    # desenho: x 0..30, y 0..125 (com a regra da especificação o quadrado
    # ficaria em y 5..25 e a altura seria 110) — +1% de margem
    largura, altura = el.tamanho_real_mm
    assert altura - 2 * 1.25 == pytest.approx(125, abs=0.01)
    assert largura - 2 * 1.25 == pytest.approx(30, abs=0.01)
    assert "M 10 105" in el.conteudo_svg() or "M10 105" in el.conteudo_svg()
