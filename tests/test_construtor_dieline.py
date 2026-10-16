"""Construtor de dieline: grade de trechos (impressora × riscador) que vira
estilo paramétrico — vincos com dobra, cortes, fendas, refugo e chanfro."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.construtor_dieline import (  # noqa: E402
    Divisa,
    Projeto,
    Trecho,
    modelo_bandeja,
    modelo_em_branco,
    modelo_maleta,
    resumir,
)
from gerador_layout.dobra_generica import achar_faces  # noqa: E402
from gerador_layout.estilos import Estilo, carregar_estilos  # noqa: E402
from gerador_layout.models import TipoLinha  # noqa: E402


def _tipos(faca):
    return {t: sum(1 for l in faca.linhas if l.tipo == t) for t in TipoLinha}


def test_maleta_no_padrao_do_autoline():
    p = modelo_maleta()
    faca = p.gerar({"C": 300, "L": 200, "A": 150, "E": 3, "G": 30})
    assert (faca.largura, faca.altura) == pytest.approx((30 + 200 + 300 + 200 + 300, 100 + 150 + 100))
    # aba de cola + 4 paredes + 8 abas
    assert len(achar_faces(faca.linhas).faces) == 13
    r = resumir(p, faca)
    assert (r.vincos, r.fendas) == (12, 6)
    # vincos das paredes dobram antes dos das abas
    paredes = [d for d in faca.dobras if d.x1 == d.x2]
    abas = [d for d in faca.dobras if d.y1 == d.y2]
    assert len(paredes) == 4 and len(abas) == 8
    assert max(d.fim for d in paredes) <= min(d.inicio for d in abas)
    # fenda de E + 2 = 5 mm entre as abas: dois cortes verticais a 2,5 mm do vinco
    x_vinco = 30 + 200
    cortes_fenda = [l for l in faca.linhas if l.tipo == TipoLinha.CORTE and l.x1 == l.x2 and l.y1 < 100 and abs(l.x1 - x_vinco) < 3]
    assert sorted(round(l.x1, 2) for l in cortes_fenda) == [x_vinco - 2.5, x_vinco + 2.5]
    # chanfro da aba de cola: diagonais
    assert any(l.x1 != l.x2 and l.y1 != l.y2 for l in faca.linhas)


def test_parametrico_em_qualquer_medida():
    estilo = Estilo(modelo_maleta().para_estilo())
    pequena = estilo.gerar({"C": 40, "L": 29, "A": 24.5, "E": 0.3, "G": 4})
    assert pequena.largura == pytest.approx(4 + 29 + 40 + 29 + 40)
    assert pequena.altura == pytest.approx(29 / 2 + 24.5 + 29 / 2)


def test_tipos_de_divisa_e_linha_inteira():
    p = modelo_bandeja()
    base = _tipos(p.gerar())
    assert base[TipoLinha.VINCO] == 4
    p.divisa(("h", 1, 1)).tipo = "meio_corte"
    p.divisa(("v", 1, 1)).tipo = "corte"
    p.divisa(("v", 2, 1)).tipo = "nada"
    t = _tipos(p.gerar())
    assert t[TipoLinha.VINCO] == 1 and t[TipoLinha.MEIO_CORTE] == 1
    assert t[TipoLinha.CORTE] == base[TipoLinha.CORTE] + 1


def test_refugo_vira_contorno_de_corte():
    p = modelo_em_branco()
    p.colunas = [Trecho("a", "100"), Trecho("b", "100")]
    p.linhas = [Trecho("x", "50"), Trecho("y", "50")]
    faca = p.gerar()
    assert _tipos(faca)[TipoLinha.VINCO] == 4  # cruz de vincos
    p.refugo.add((0, 0))  # tira o canto: vira um "L"
    faca = p.gerar()
    assert _tipos(faca)[TipoLinha.VINCO] == 2
    assert len(achar_faces(faca.linhas).faces) == 3


def test_inserir_e_remover_trecho_renumera():
    p = modelo_maleta()
    p.divisas[("v", 4, 0)] = Divisa(tipo="corte")
    p.inserir_coluna(1, Trecho("Nova", "20"))
    assert p.divisas[("v", 5, 0)].tipo == "corte"
    assert (0, 0) in p.refugo and p.base == (1, 3)
    p.remover_coluna(1)
    assert p.divisas[("v", 4, 0)].tipo == "corte" and p.base == (1, 2)
    p.inserir_linha(0, Trecho("Topo", "10"))
    assert (1, 0) in p.refugo and (0, 0) not in p.refugo
    p.remover_linha(0)
    assert p.para_estilo()["linhas"] == modelo_maleta_com_corte()["linhas"]


def modelo_maleta_com_corte():
    p = modelo_maleta()
    p.divisas[("v", 4, 0)] = Divisa(tipo="corte")
    return p.para_estilo()


def test_vai_e_volta_pelo_catalogo(tmp_path):
    from gerador_layout.estilos import salvar_estilo

    p = modelo_maleta()
    p.nome = "Maleta com tampa"
    p.divisa(("h", 1, 2)).angulo = 120
    destino = salvar_estilo(p.para_estilo(), tmp_path)
    estilos = [e for e in carregar_estilos(tmp_path) if e.caminho == destino]
    assert len(estilos) == 1 and estilos[0].nome == "Maleta com tampa"
    reaberto = Projeto.de_dict(json.loads(destino.read_text(encoding="utf-8"))["construtor"])
    assert reaberto.como_dict() == p.como_dict()
    assert reaberto.para_estilo() == p.para_estilo()


def test_tela_usa_na_faca_e_salva(tmp_path):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from gerador_layout.ui.dialogo_construtor_dieline import DialogoConstrutorDieline
    from gerador_layout.ui.main_window import JanelaPrincipal

    d = DialogoConstrutorDieline(pasta_estilos=tmp_path)
    d.resize(1200, 700)
    d.show()
    QApplication.processEvents()
    assert "12 vincos" in d.resumo.text() and "6 fendas" in d.resumo.text()
    # clique numa fenda das abas de cima → painel com o tipo; troca pra vinco na linha inteira
    g = d.grade
    g._ajustar_escala()
    item = g.item_em(g._tela(g._xs[2], (g._ys[0] + g._ys[1]) / 2))
    assert item == ("divisa", ("v", 2, 0))
    d._mostrar_selecao(item)
    from PySide6.QtWidgets import QCheckBox, QComboBox

    d.findChild(QCheckBox).setChecked(True)  # "Aplicar na linha inteira"
    combo = [c for c in d.findChildren(QComboBox) if c is not d.combo_inicio][0]
    combo.setCurrentIndex(combo.findData("corte"))
    assert all(d.projeto.divisa(("v", 2, l)).tipo == "corte" for l in (0, 2))
    assert d.projeto.divisa(("v", 2, 1)).tipo == "vinco"
    combo.setCurrentIndex(combo.findData("serra"))  # mudar de novo continua valendo pras duas
    assert all(d.projeto.divisa(("v", 2, l)).tipo == "serra" for l in (0, 2))
    # peça: vira refugo
    peca = g.item_em(g._tela((g._xs[4] + g._xs[5]) / 2, (g._ys[0] + g._ys[1]) / 2))
    assert peca == ("peca", (0, 4))
    d._mostrar_selecao(peca)
    d.findChild(QCheckBox).setChecked(False)
    assert (0, 4) in d.projeto.refugo
    # medida nova na tabela vale nas fórmulas
    d.tabela_colunas.item(0, 1).setText("G + 5")
    assert d.faca.largura == pytest.approx(35 + 5 + 200 + 300 + 200 + 300)
    # salvar e usar
    caminho = d.salvar()
    assert caminho is not None and caminho.parent == tmp_path
    d.salvar()  # de novo: regrava o mesmo arquivo
    assert len(list(tmp_path.glob("*.json"))) == 1
    d._usar()
    assert d.result() == d.DialogCode.Accepted and d.faca is not None

    j = JanelaPrincipal()
    j.aplicar_estilo(d.estilo, d.valores, d.faca)
    assert len(j.canvas.linhas_faca()) == len(d.faca.linhas)
    assert len(j._dobras_estilo) == len(d.faca.dobras) > 0
    j.close()
