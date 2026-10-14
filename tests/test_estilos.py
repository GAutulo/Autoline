"""Estilos paramétricos (catálogo FEFCO e estilos do usuário): expressões
seguras, validação, geração da faca, dobra no 3D e uso pela janela."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.dobra3d import caixa_envolvente, posicionar  # noqa: E402
from gerador_layout.dobra_generica import achar_faces, montar_modelo_generico  # noqa: E402
from gerador_layout.estilos import (  # noqa: E402
    ErroEstilo,
    Estilo,
    avaliar,
    carregar_estilos,
    estilo_da_faca,
    salvar_estilo,
)
from gerador_layout.estilos_catalogo import CATALOGO  # noqa: E402
from gerador_layout.models import LinhaDesenho, TipoLinha  # noqa: E402


def _estilo(codigo: str) -> Estilo:
    return next(Estilo(d) for d in CATALOGO if d["codigo"] == codigo)


def _dimensoes(faca):
    modelo = montar_modelo_generico(faca.linhas, dobras_estilo=faca.dobras, ponto_base=faca.ponto_base)
    mn, mx = caixa_envolvente(posicionar(modelo, 1.0))
    return modelo, sorted(mx[i] - mn[i] for i in range(3))


# ── expressões ────────────────────────────────────────────────────────
def test_expressoes_aritmetica_e_funcoes():
    v = {"C": 300, "L": 200, "E": 3}
    assert avaliar("C + 2*L - E", v) == 697
    assert avaliar("min(C, L) / 2", v) == 100
    assert avaliar("C > L and L > E", v) == 1.0
    assert avaliar(12, v) == 12.0
    assert avaliar("cos(60) * 2", v) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "perigosa",
    ["__import__('os').system('x')", "C.__class__", "(lambda: 1)()", "open('x')", "[1, 2]", "'texto'", "X + 1"],
)
def test_expressoes_perigosas_ou_invalidas_sao_recusadas(perigosa):
    with pytest.raises(ErroEstilo):
        avaliar(perigosa, {"C": 1})


# ── catálogo ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("medidas", [(300, 200, 150), (120, 80, 60), (60.5, 32, 19), (500, 400, 120)])
def test_fefco_0201_fecha_na_medida_digitada(medidas):
    c, l, a = medidas
    faca = _estilo("FEFCO 0201").gerar({"C": c, "L": l, "A": a, "E": 3})
    modelo, dims = _dimensoes(faca)
    assert len(achar_faces(faca.linhas).faces) == 13
    assert dims == pytest.approx(sorted([c, l, a]), abs=1.0)
    base = [p for p in modelo.paineis if p.pai is None][0]
    assert (base.x2 - base.x1, base.y2 - base.y1) == pytest.approx((c, a))


@pytest.mark.parametrize("medidas", [(300, 200, 150), (220, 160, 60), (400, 300, 100)])
def test_fefco_0427_fecha_e_tem_todas_as_partes(medidas):
    c, l, a = medidas
    faca = _estilo("FEFCO 0427").gerar({"C": c, "L": l, "A": a, "E": 3})
    modelo, dims = _dimensoes(faca)
    # aba de encaixe, tampa, 2 abinhas, trás, 2 orelhas, fundo, 2 laterais x2, frente, 2 orelhas, frente interna
    assert len(modelo.paineis) == 16
    assert dims[0] == pytest.approx(a, abs=1.0)  # altura
    assert dims[1] == pytest.approx(l, abs=4.0)  # tampa um pouco maior (L + E)
    assert dims[2] == pytest.approx(c, abs=1.0)
    base = [p for p in modelo.paineis if p.pai is None][0]
    assert (base.x2 - base.x1, base.y2 - base.y1) == pytest.approx((c, l))  # o fundo fica parado
    angulos = sorted({round(p.angulo_fechado) for p in modelo.paineis if p.pai})
    assert angulos == [90, 92, 178]


def test_validacao_barra_medida_que_nao_cabe():
    estilo = _estilo("FEFCO 0427")
    problemas = estilo.validar({"C": 300, "L": 900, "A": 100, "E": 3})
    assert problemas and "orelhas" in problemas[0]
    with pytest.raises(ErroEstilo):
        estilo.gerar({"C": 300, "L": 900, "A": 100, "E": 3})
    assert estilo.validar({"C": 5, "L": 200, "A": 100, "E": 3})  # abaixo do mínimo


def test_faca_do_estilo_comeca_em_zero_e_cotas_acompanham():
    faca = _estilo("FEFCO 0201").gerar({"C": 300, "L": 200, "A": 150, "E": 3, "G": 30})
    assert min(min(l.x1, l.x2) for l in faca.linhas) == pytest.approx(0)
    assert min(min(l.y1, l.y2) for l in faca.linhas) == pytest.approx(0)
    rotulos = {r for _a, _b, r in faca.cotas}
    assert rotulos == {"C", "L", "A"}


# ── estilos do usuário ────────────────────────────────────────────────
def test_salvar_e_carregar_estilo_do_usuario(tmp_path):
    linhas = [
        LinhaDesenho(0, 0, 100, 0, TipoLinha.CORTE),
        LinhaDesenho(100, 0, 100, 50, TipoLinha.CORTE),
        LinhaDesenho(100, 50, 0, 50, TipoLinha.CORTE),
        LinhaDesenho(0, 50, 0, 0, TipoLinha.CORTE),
        LinhaDesenho(50, 0, 50, 50, TipoLinha.VINCO),
        LinhaDesenho(0, 0, 10, 10, TipoLinha.CORTE, 0.4),
    ]
    destino = salvar_estilo(estilo_da_faca(linhas, "Minha bandeja"), tmp_path)
    salvar_estilo(estilo_da_faca(linhas, "Minha bandeja"), tmp_path)  # mesmo nome: não sobrescreve
    assert len(list(tmp_path.glob("*.json"))) == 2
    (tmp_path / "quebrado.json").write_text("{ isso não é json", encoding="utf-8")
    estilos = carregar_estilos(tmp_path)
    meus = [e for e in estilos if e.caminho is not None]
    assert len(meus) == 2 and destino in [e.caminho for e in meus]  # o quebrado é pulado
    faca = meus[0].gerar()
    assert [(l.x1, l.y1, l.x2, l.y2, l.tipo, l.bojo) for l in faca.linhas] == [
        (l.x1, l.y1, l.x2, l.y2, l.tipo, l.bojo) for l in linhas
    ]


def test_estilo_do_usuario_com_expressoes(tmp_path):
    dados = {
        "codigo": "MEU 01",
        "nome": "Envelope",
        "variaveis": [{"nome": "C", "padrao": 100, "min": 10}, {"nome": "L", "padrao": 60, "min": 10}],
        "linhas": [
            {"de": [0, 0], "ate": ["C", 0]},
            {"de": ["C", 0], "ate": ["C", "L"]},
            {"de": ["C", "L"], "ate": [0, "L"]},
            {"de": [0, "L"], "ate": [0, 0]},
            {"de": ["C/2", 0], "ate": ["C/2", "L"], "tipo": "vinco", "dobra": 180, "tempo": [0, 1]},
        ],
        "base": ["C/4", "L/2"],
    }
    (tmp_path / "envelope.json").write_text(json.dumps(dados), encoding="utf-8")
    estilo = [e for e in carregar_estilos(tmp_path) if e.codigo == "MEU 01"][0]
    faca = estilo.gerar({"C": 200})
    assert faca.largura == pytest.approx(200) and faca.altura == pytest.approx(60)
    modelo = montar_modelo_generico(faca.linhas, dobras_estilo=faca.dobras, ponto_base=faca.ponto_base)
    dobrada = [p for p in modelo.paineis if p.pai][0]
    assert dobrada.angulo_fechado == 180


# ── na janela ─────────────────────────────────────────────────────────
@pytest.fixture
def janela():
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    QApplication.processEvents()
    yield j
    j.close()


def test_catalogo_gera_e_janela_aplica(janela, tmp_path, monkeypatch):
    from gerador_layout.ui import dialogo_estilos

    monkeypatch.setattr(dialogo_estilos, "pasta_estilos_usuario", lambda: tmp_path)
    dialogo = dialogo_estilos.DialogoEstilos(janela)
    nomes = [e.nome_exibicao for e in dialogo.estilos]
    dialogo._lista.setCurrentRow(nomes.index(_estilo("FEFCO 0427").nome_exibicao))
    dialogo._spins["C"].setValue(250)
    dialogo._spins["L"].setValue(900)  # inválido: botão desliga
    assert not dialogo._botoes.button(dialogo._botoes.StandardButton.Ok).isEnabled()
    dialogo._spins["L"].setValue(180)
    assert dialogo._botoes.button(dialogo._botoes.StandardButton.Ok).isEnabled()
    dialogo.grab()  # diagrama cotado desenha sem erro
    dialogo._aceitar()
    assert dialogo.faca is not None

    canvas = janela.canvas
    janela.aplicar_estilo(dialogo.estilo_escolhido, dialogo.valores, dialogo.faca)
    assert canvas.faca_editada
    pagina = canvas.retangulo_pagina()
    assert (pagina.width(), pagina.height()) == pytest.approx((dialogo.faca.largura, dialogo.faca.altura))
    assert canvas.layout_efetivo.linhas == canvas.linhas_faca()
    janela.abas_tela.setCurrentIndex(2)
    modelo = janela.visualizacao_3d.vista._modelo
    assert modelo.descricao.startswith("FEFCO 0427") and len(modelo.paineis) == 16
    # refazer: o catálogo abre no mesmo estilo e medidas
    de_novo = dialogo_estilos.DialogoEstilos(
        janela, estilo_inicial=janela._estilo_atual[0], valores_iniciais=janela._estilo_atual[1]
    )
    assert de_novo.estilo_escolhido.codigo == "FEFCO 0427" and de_novo._spins["C"].value() == 250
    # descartar volta pra caixa calculada, chapa e 3D de antes
    canvas.descartar_edicoes_faca()
    assert not canvas.faca_editada and janela._estilo_atual is None
    assert canvas.retangulo_pagina().width() == pytest.approx(canvas.layout_atual.largura_total)
