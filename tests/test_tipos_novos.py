"""Meia caixa (maleta normal/transpassada só com Aba | L | C) e envoltório
capa (bandeja: A | C | A × A | L | A), mais a lista de tipos na tela."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.dobra3d import caixa_envolvente, montar_modelo, posicionar  # noqa: E402
from gerador_layout.dobra_generica import achar_faces  # noqa: E402
from gerador_layout.layout_service import ServicoLayoutCaixa  # noqa: E402
from gerador_layout.models import (  # noqa: E402
    NOME_EXIBICAO_TIPO_CAIXA,
    ORDEM_TIPOS_CAIXA,
    MedidasCaixa,
    TipoCaixa,
    TipoLinha,
)
from gerador_layout.paineis import calcular_paineis  # noqa: E402


def _layout(tipo, **kw):
    kw.setdefault("impressora_aba", 0.0)  # como a tela manda: 0 = trecho automático
    return ServicoLayoutCaixa().calcular(MedidasCaixa(tipo=tipo, **kw))


@pytest.mark.parametrize("tipo", [TipoCaixa.MALETA_NORMAL_MEIA, TipoCaixa.MALETA_TRANSPASSADA_MEIA])
def test_meia_caixa_so_tem_aba_l_c(tipo):
    # o exemplo: impressora 40 × 240 × 590
    layout = _layout(tipo, comprimento=590, largura=240, altura=300, impressora_aba=40)
    assert layout.segmentos_impressora == pytest.approx([40, 240, 590])
    assert layout.largura_total == pytest.approx(40 + 240 + 590)
    assert max(max(l.x1, l.x2) for l in layout.linhas) == pytest.approx(870)
    assert "meia caixa" in layout.descricao
    # riscador: normal = L/2 nas abas; transpassada = L inteiro
    aba = 240 if tipo == TipoCaixa.MALETA_TRANSPASSADA_MEIA else 120
    assert layout.segmentos_riscador == pytest.approx([aba, 300, aba])
    # faca fechada: aba de cola, lateral, frente e as 4 abas de cima/baixo
    assert len(achar_faces(layout.linhas).faces) == 3 + 4
    paineis = calcular_paineis(tipo, layout.segmentos_impressora, layout.segmentos_riscador)
    # as 3 da faixa do meio + as abas de tampa e de fundo da lateral e da frente
    assert [p.id for p in paineis] == [
        "aba_cola", "lateral1", "frente", "tampa_lateral1", "fundo_lateral1", "tampa_frente", "fundo_frente",
    ]


def test_meia_caixa_no_3d_aparece_inteira():
    """No 3D a meia caixa aparece como a caixa inteira (a outra metade igual:
    mesma L, mesmo C, a mesma arte) — só no modelo; a faca continua meia."""
    layout = _layout(TipoCaixa.MALETA_NORMAL_MEIA, comprimento=300, largura=200, altura=150)
    assert layout.segmentos_impressora == pytest.approx([4, 200, 300])  # a faca não muda
    modelo = montar_modelo(TipoCaixa.MALETA_NORMAL_MEIA, layout.segmentos_impressora, layout.segmentos_riscador)
    assert not modelo.vazio and modelo.solido_fechado
    por_id = {p.id: p for p in modelo.paineis}
    assert {"frente", "lateral1", "lateral2", "verso", "aba_cola", "tampa_verso", "fundo_lateral2"} <= set(por_id)
    # a metade repetida mostra a arte da metade desenhada
    assert (por_id["verso"].arte_de, por_id["lateral2"].arte_de) == ("frente", "lateral1")
    assert por_id["verso"].x1 - por_id["verso"].arte_dx == pytest.approx(por_id["frente"].x1)
    assert por_id["frente"].arte_de is None
    paredes = {"frente", "verso", "lateral1", "lateral2"}
    mn, mx = caixa_envolvente([p for p in posicionar(modelo, 1.0) if p.painel.id in paredes])
    assert sorted(round(mx[i] - mn[i], 3) for i in range(3)) == pytest.approx([150, 200, 300])


def test_capa_tres_por_tres_com_cantos_do_envoltorio():
    layout = _layout(TipoCaixa.ENVOLTORIO_CAPA, comprimento=300, largura=200, altura=40)
    assert layout.segmentos_impressora == pytest.approx([40, 300, 40])
    assert layout.segmentos_riscador == pytest.approx([40, 200, 40])
    assert (layout.largura_total, layout.altura_total) == pytest.approx((380, 280))
    # fundo + 2 laterais + 2 paredes + 4 cantos
    assert len(achar_faces(layout.linhas).faces) == 9
    assert sum(1 for l in layout.linhas if l.tipo == TipoLinha.CORTE_SERRA) == 8  # 2 fendas × 2 lados × 2 bordas
    # trechos digitados valem (aqui: paredes mais baixas no riscador)
    menor = _layout(TipoCaixa.ENVOLTORIO_CAPA, comprimento=300, largura=200, altura=40, riscador_superior=30, riscador_inferior=30)
    assert menor.segmentos_riscador == pytest.approx([30, 200, 30])
    paineis = calcular_paineis(TipoCaixa.ENVOLTORIO_CAPA, layout.segmentos_impressora, layout.segmentos_riscador)
    assert {p.id for p in paineis} == {"centro", "lateral1", "lateral2", "parede_sup", "parede_inf"}


def test_capa_no_3d_vira_bandeja():
    layout = _layout(TipoCaixa.ENVOLTORIO_CAPA, comprimento=300, largura=200, altura=40)
    modelo = montar_modelo(TipoCaixa.ENVOLTORIO_CAPA, layout.segmentos_impressora, layout.segmentos_riscador)
    assert not modelo.solido_fechado
    mn, mx = caixa_envolvente(posicionar(modelo, 1.0))
    assert sorted(round(mx[i] - mn[i], 3) for i in range(3)) == pytest.approx([40, 200, 300], abs=0.5)
    plana = posicionar(modelo, 0.0)
    assert all(abs(pp.ponto(p.x1, p.y1)[2]) < 1e-6 for pp in plana for p in [pp.painel])


def test_nomes_curtos_e_agrupados():
    assert set(ORDEM_TIPOS_CAIXA) == set(TipoCaixa)  # todo tipo aparece na lista
    assert all(len(NOME_EXIBICAO_TIPO_CAIXA[t]) <= 36 for t in TipoCaixa)
    assert len(set(NOME_EXIBICAO_TIPO_CAIXA.values())) == len(TipoCaixa)  # nenhum nome repetido
    familias = ["Maleta" if NOME_EXIBICAO_TIPO_CAIXA[t].startswith("Maleta") else "Envoltório" for t in ORDEM_TIPOS_CAIXA]
    assert familias == sorted(familias, key=lambda f: f != "Maleta")  # maletas juntas, depois envoltórios


def test_tela_mostra_tres_trechos_e_lista_inteira():
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.show()
    combo = j.combo_tipo
    assert combo.view().minimumWidth() >= combo.view().sizeHintForColumn(0)  # a lista aberta não corta
    combo.setCurrentIndex(combo.findData(TipoCaixa.MALETA_NORMAL_MEIA))
    QApplication.processEvents()
    visiveis = [c.isVisibleTo(j.linha_impressora) for c in j.linha_impressora._colunas]
    assert visiveis == [True, True, True, False, False]
    assert "Aba | L | C" in combo.toolTip()
    assert j.canvas.layout_atual.segmentos_impressora == pytest.approx([4.0, 200.0, 300.0])
    combo.setCurrentIndex(combo.findData(TipoCaixa.ENVOLTORIO_CAPA))
    QApplication.processEvents()
    assert [c.isVisibleTo(j.linha_riscador) for c in j.linha_riscador._colunas] == [True, True, True, False, False]
    assert len(j._paineis_disponiveis()) == 5
    assert j.canvas.layout_atual.segmentos_impressora == pytest.approx([150.0, 300.0, 150.0])  # A | C | A
    assert j.canvas.layout_atual.segmentos_riscador == pytest.approx([150.0, 200.0, 150.0])  # A | L | A
    j.abas_tela.setCurrentIndex(2)
    QApplication.processEvents()
    assert j.visualizacao_3d.vista._modelo.descricao == "Envoltório capa (bandeja)"
    j.close()


@pytest.mark.parametrize("tipo", [TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE, TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_SEM_CORTE])
def test_envoltorio_tampa_cantos_e_abas_sao_faces(tipo):
    """A tampa/fechamento, os cantos e as abas também são caixa: a malha e
    as medidas até a borda da face apareciam só na cruz do meio."""
    layout = _layout(tipo, comprimento=300, largura=200, altura=150)
    paineis = {p.id: p for p in calcular_paineis(tipo, layout.segmentos_impressora, layout.segmentos_riscador)}
    assert {"frente", "tampa", "fundo", "lateral1", "lateral2", "fechamento_sup", "fechamento_inf"} <= set(paineis)
    assert paineis["fechamento_sup"].y1 == pytest.approx(0) and paineis["fechamento_inf"].y2 == pytest.approx(layout.altura_total)
    assert sum(p.id.startswith("canto_") for p in paineis.values()) == 8
    abas = [p for p in paineis.values() if p.id.startswith("aba_lateral")]
    assert len(abas) == (2 if tipo == TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE else 10)
    # nada fica fora da chapa e nenhuma face se sobrepõe
    for p in paineis.values():
        assert 0 <= p.x1 < p.x2 <= layout.largura_total + 1e-6 and 0 <= p.y1 < p.y2 <= layout.altura_total + 1e-6
    lista = list(paineis.values())
    for i, a in enumerate(lista):
        for b in lista[i + 1:]:
            assert min(a.x2, b.x2) - max(a.x1, b.x1) <= 1e-6 or min(a.y2, b.y2) - max(a.y1, b.y1) <= 1e-6
