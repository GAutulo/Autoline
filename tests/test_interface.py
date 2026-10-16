"""Revisão de interface: seleção visível, cadeado com dois estados, nome
das cores legível no tema."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.ui import estilo  # noqa: E402


def _contraste(a, b):
    def lum(c):
        def canal(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * canal(c[0]) + 0.7152 * canal(c[1]) + 0.0722 * canal(c[2])

    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _rgb(hexa):
    return tuple(int(hexa[i : i + 2], 16) for i in (1, 3, 5))


def test_cores_legiveis_nos_dois_temas():
    for fundo in ("#1E1A16", "#EAE1CC"):  # escuro e claro
        for cor in ((0, 0, 0), (0, 0, 255), (255, 0, 255), (255, 230, 0), (0, 160, 227)):
            assert _contraste(estilo.cor_legivel_sobre(*cor, fundo=fundo), _rgb(fundo)) >= 3.0
    # cor que já lê bem fica como está (vermelho continua vermelho no claro)
    assert estilo.cor_legivel_sobre(200, 0, 0, fundo="#EAE1CC") == (200, 0, 0)


def test_selecao_destaca_do_campo_e_do_cartao():
    for paleta in (estilo._PALETA_CLARA, estilo._PALETA_ESCURA):
        selecao = _rgb(paleta["SELECAO"])
        assert _contraste(selecao, _rgb(paleta["CAMPO"])) >= 1.5
        assert _contraste(selecao, _rgb(paleta["CARTAO"])) >= 1.5
        assert _contraste(_rgb(paleta["TEXTO"]), selecao) >= 3.0  # texto selecionado legível
    assert "selection-background-color: {Cor.SELECAO}".replace("{Cor.SELECAO}", estilo.Cor.SELECAO) in estilo.FOLHA_DE_ESTILO


def test_cadeado_aberto_e_fechado():
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QToolButton

    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_formas import ElementoRetangulo

    j = JanelaPrincipal()
    j.show()
    j.abas_tela.setCurrentIndex(1)
    el = ElementoRetangulo()
    j.canvas.adicionar_elemento_mockup(el, QPointF(100, 100))
    j.canvas.cena.clearSelection()
    el.setSelected(True)
    QApplication.processEvents()
    trava = next(b for b in j.painel_propriedades_mockup.findChildren(QToolButton) if "Propor" in b.toolTip())
    icone_aberto = trava.icon().pixmap(18, 18).toImage()
    assert not el.proporcao_travada and "livre" in trava.toolTip()
    trava.setChecked(True)
    assert el.proporcao_travada and "travada" in trava.toolTip()
    assert trava.icon().pixmap(18, 18).toImage() != icone_aberto  # outro desenho
    j.close()


def test_mais_tintas_e_tinta_criada_pelo_usuario(tmp_path):
    from gerador_layout.ui import configuracoes, projeto_arquivo
    from gerador_layout.ui.main_window import JanelaPrincipal

    configuracoes.definir_cores_personalizadas([])
    j = JanelaPrincipal()
    nomes = list(j._chips_cor)
    assert nomes[:8] == ["Preto", "Vermelho", "Azul", "Amarelo", "Verde", "Ciano", "Magenta", "Laranja"]  # as de antes
    assert {"Azul Escuro", "Verde Escuro", "Vinho", "Marrom", "Cinza", "Branco", "Dourado"} <= set(nomes)
    # criar uma tinta: entra marcada, vai pra legenda, pra paleta e pras próximas vezes
    assert j._nova_cor_personalizada("Pantone 286", (0, 51, 160))
    assert j._chips_cor["Pantone 286"][0].isChecked()
    assert any(c.nome == "PANTONE 286" for c in j._cores_impressao_ativas())
    assert ("Pantone 286", (0, 51, 160)) in configuracoes.cores_personalizadas()
    assert not j._nova_cor_personalizada("pantone 286", (1, 2, 3))  # nome repetido não duplica
    # o projeto leva o tom junto: abre noutro computador sem a tinta cadastrada
    destino = projeto_arquivo.salvar(j, tmp_path / "x.autoline")
    j.close()
    configuracoes.definir_cores_personalizadas([])
    k = JanelaPrincipal()
    assert "Pantone 286" not in k._chips_cor
    projeto_arquivo.aplicar_na_janela(k, projeto_arquivo.ler(destino))
    assert k._chips_cor["Pantone 286"][0].isChecked() and k._chips_cor["Pantone 286"][1] == (0, 51, 160)
    # tirar a tinta criada
    assert k._remover_cor_personalizada("Pantone 286", confirmar=lambda: True)
    assert "Pantone 286" not in k._chips_cor
    k.close()
    configuracoes.definir_cores_personalizadas([])
