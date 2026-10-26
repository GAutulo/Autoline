"""Logotipo "Dobra" (REDESIGN.md, seção 3) e ícone do app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.ui.marca import AssinaturaMarca, pixmap_simbolo  # noqa: E402


def _cor(img, x, y):
    c = img.pixelColor(round(x), round(y))
    return (c.red(), c.green(), c.blue(), c.alpha())


def test_simbolo_com_as_duas_faces_e_travessa():
    img = pixmap_simbolo(120).toImage()
    k = img.width() / 120
    assert _cor(img, 30 * k, 90 * k)[:3] == (0xE7, 0xE9, 0xEB)  # face de dentro, clara
    assert _cor(img, 90 * k, 90 * k)[:3] == (0xF0, 0xA0, 0x4B)  # face de fora, âmbar
    assert _cor(img, 5 * k, 5 * k)[3] == 0  # fundo transparente
    # grande: travessa tracejada (tem vão); pequeno: traço cheio
    vaos = [_cor(img, x * k, 80 * k)[3] for x in range(46, 75)]
    assert 0 in vaos and 255 in vaos
    pequeno = pixmap_simbolo(32).toImage()
    kp = pequeno.width() / 120
    assert all(_cor(pequeno, x * kp, 80 * kp)[3] > 200 for x in range(48, 73, 4))


def test_versao_clara_pros_impressos_e_tema_claro():
    img = pixmap_simbolo(120, claro=True).toImage()
    k = img.width() / 120
    assert _cor(img, 30 * k, 90 * k)[:3] == (0x15, 0x18, 0x1B)
    assert _cor(img, 90 * k, 90 * k)[:3] == (0xB4, 0x63, 0x0F)


def test_assinatura_simbolo_mais_nome():
    so = AssinaturaMarca(altura=24, so_simbolo=True)
    inteira = AssinaturaMarca(altura=24)
    assert so.sizeHint().width() == 26 and inteira.sizeHint().width() > 60
    imagem = inteira.grab().toImage()
    assert not imagem.isNull()


def test_icone_do_app_tem_todos_os_tamanhos():
    from PIL import Image

    ico = Image.open(Path(__file__).resolve().parents[1] / "assets" / "icon.ico")
    assert {(t, t) for t in (16, 24, 32, 48, 64, 128, 256)} <= set(ico.info["sizes"])
    ico.size = (256, 256)
    grande = ico.convert("RGBA")
    assert grande.getpixel((128, 20))[:3] == (0x1D, 0x21, 0x25)  # cartão grafite
    assert QColor(*grande.getpixel((170, 170))[:3]).name() == "#f0a04b"  # face âmbar (90,90 do símbolo)


def test_icones_do_redesign_e_estado_ativo_ambar():
    """Conjunto 2.5: SVG em grade 24 com traço 1.5, na cor do tema; o estado
    "ligado" (ferramenta ativa) sai em âmbar."""
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon

    from gerador_layout.ui.estilo import Cor
    from gerador_layout.ui.icones_svg import CORPOS, svg
    from gerador_layout.ui.mockup_icones import construir_icone

    assert {"navegar", "editar_faca", "linha_corte", "selecionar", "agrupar", "desfazer", "conta_gotas"} <= set(CORPOS)
    assert 'stroke-width="1.5"' in svg("selecionar", "#000000") and 'stroke-linecap="round"' in svg("selecionar", "#000000")
    icone = construir_icone("selecionar")
    desligado = icone.pixmap(QSize(36, 36), QIcon.Mode.Normal, QIcon.State.Off).toImage()
    ligado = icone.pixmap(QSize(36, 36), QIcon.Mode.Normal, QIcon.State.On).toImage()

    def cores(img):
        return {img.pixelColor(x, y).name() for x in range(img.width()) for y in range(img.height()) if img.pixelColor(x, y).alpha() > 250}

    assert QColor(Cor.PRIMARIA).name() in cores(ligado)
    assert QColor(Cor.PRIMARIA).name() not in cores(desligado)
