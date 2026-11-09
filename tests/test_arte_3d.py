"""A arte no 3D fica presa dentro da face: nunca passa da borda da chapa."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.dobra3d import ModeloCaixa3D, PainelDobravel  # noqa: E402


def _arte_preta(pedidos):
    """Fonte de arte falsa: o retângulo pedido inteiro pintado de preto."""
    imagens = []
    for retangulo, px_por_mm in pedidos:
        imagem = QImage(
            max(1, round(retangulo.width() * px_por_mm)),
            max(1, round(retangulo.height() * px_por_mm)),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        imagem.fill(Qt.GlobalColor.black)
        imagem.setText("px_por_mm", f"{px_por_mm}")
        imagens.append(imagem)
    return imagens


def _vazamento(vista) -> tuple[int, int]:
    """(pixels de arte fora da caixa, pixels de arte no total)."""
    vista.definir_fonte_arte(_arte_preta)
    com = vista.renderizar_imagem(1.0, None, recortar=False)
    vista.definir_fonte_arte(None)
    sem = vista.renderizar_imagem(1.0, None, recortar=False)
    fora = total = 0
    for y in range(com.height()):
        for x in range(com.width()):
            cor = com.pixelColor(x, y)
            if cor.alpha() > 200 and cor.lightness() < 20:
                total += 1
                if sem.pixelColor(x, y).alpha() < 10:
                    fora += 1
    return fora, total


def test_arte_nao_passa_da_borda_de_face_que_nao_e_retangulo():
    # Face em triângulo (faca do Construtor): a textura cobre o retângulo
    # em volta dela, mas só o triângulo pode aparecer.
    from gerador_layout.ui.visualizacao_3d import VistaCaixa3D

    QApplication.instance() or QApplication([])
    triangulo = PainelDobravel(
        "face", "Face", 0.0, 0.0, 100.0, 100.0,
        poligono=((0.0, 0.0), (100.0, 0.0), (0.0, 100.0)),
        ponto_interno=(20.0, 20.0),
    )
    vista = VistaCaixa3D()
    vista.resize(400, 400)
    vista.definir_modelo(ModeloCaixa3D(paineis=[triangulo], solido_fechado=False))
    vista.definir_progresso(0.0)
    fora, total = _vazamento(vista)
    assert total > 1000  # a arte aparece
    assert fora == 0
