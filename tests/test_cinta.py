"""Cinta: uma medida só na impressora (largura total), faixas só no
riscador, recuo opcional dos dois lados em faixas escolhidas e furos de
pega (3 lados de corte + 1 de vinco) em qualquer faixa."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.dobra3d import montar_modelo  # noqa: E402
from gerador_layout.geometria_faca import e_arco  # noqa: E402
from gerador_layout.layout_service import ServicoLayoutCaixa  # noqa: E402
from gerador_layout.models import FuroCinta, MedidasCaixa, TipoCaixa, TipoLinha  # noqa: E402
from gerador_layout.paineis import calcular_paineis  # noqa: E402


def _cinta(largura=120.0, faixas=(30.0, 2.0, 25.0, 30.0), recuo=0.0, recuadas=(), furos=()):
    riscador = list(faixas) + [0.0] * (5 - len(faixas))
    medidas = MedidasCaixa(
        tipo=TipoCaixa.CINTA,
        comprimento=largura,
        altura=40.0,
        impressora_aba=0.0,
        impressora_largura_1=recuo,
        riscador_superior=riscador[0],
        riscador_centro=riscador[1],
        riscador_inferior=riscador[2],
        riscador_parte_4=riscador[3],
        riscador_parte_5=riscador[4],
        faixas_recuadas=tuple(recuadas),
        furos=list(furos),
    )
    return ServicoLayoutCaixa().calcular(medidas)


def _horizontais(layout, tipo, y):
    return sorted(
        (min(l.x1, l.x2), max(l.x1, l.x2))
        for l in layout.linhas
        if l.tipo == tipo and not e_arco(l) and l.y1 == pytest.approx(y) and l.y2 == pytest.approx(y)
    )


def _verticais(layout, tipo, x):
    return sorted(
        (min(l.y1, l.y2), max(l.y1, l.y2))
        for l in layout.linhas
        if l.tipo == tipo and not e_arco(l) and l.x1 == pytest.approx(x) and l.x2 == pytest.approx(x)
    )


def test_uma_medida_na_impressora_e_faixas_no_riscador():
    layout = _cinta()
    assert layout.largura_total == 120
    assert layout.altura_total == 30 + 2 + 25 + 30
    assert layout.segmentos_impressora == [120.0, 0.0]  # total | recuo
    assert layout.segmentos_riscador == [30.0, 2.0, 25.0, 30.0]
    # Vincos só no riscador: horizontais, de lado a lado, entre as faixas.
    for y in (30, 32, 57):
        assert _horizontais(layout, TipoLinha.VINCO, y) == [(0, 120)]
    assert not any(l.tipo == TipoLinha.VINCO and l.x1 != l.x2 and l.y1 != l.y2 for l in layout.linhas)
    # Contorno de corte: o retângulo da chapa.
    assert _horizontais(layout, TipoLinha.CORTE, 0) == [(0, 120)]
    assert _horizontais(layout, TipoLinha.CORTE, 87) == [(0, 120)]
    assert _verticais(layout, TipoLinha.CORTE, 0) == [(0, 87)]
    assert _verticais(layout, TipoLinha.CORTE, 120) == [(0, 87)]


def test_sem_faixas_digitadas_usa_a_altura_como_uma_faixa():
    layout = _cinta(faixas=())
    assert layout.segmentos_riscador == [40.0]
    assert layout.altura_total == 40


def test_recuo_dos_dois_lados_nas_faixas_escolhidas():
    layout = _cinta(recuo=10.0, recuadas=(2, 3))
    assert layout.segmentos_impressora == [120.0, 10.0]
    # Faixas 2 e 3 (y 30 → 57) entram 10 mm de cada lado.
    assert _verticais(layout, TipoLinha.CORTE, 10) == [(30, 57)]
    assert _verticais(layout, TipoLinha.CORTE, 110) == [(30, 57)]
    assert _verticais(layout, TipoLinha.CORTE, 0) == [(0, 30), (57, 87)]
    # Onde a largura muda, o degrau é corte e o vinco fica só na parte em comum.
    assert _horizontais(layout, TipoLinha.CORTE, 30) == [(0, 10), (110, 120)]
    assert _horizontais(layout, TipoLinha.VINCO, 30) == [(10, 110)]
    assert _horizontais(layout, TipoLinha.VINCO, 32) == [(10, 110)]  # entre duas recuadas
    assert _horizontais(layout, TipoLinha.CORTE, 57) == [(0, 10), (110, 120)]


def test_recuo_zero_ignora_as_faixas_marcadas():
    assert _verticais(_cinta(recuo=0.0, recuadas=(2,)), TipoLinha.CORTE, 0) == [(0, 87)]


def test_furo_de_pega_pela_distancia_ate_o_topo():
    # Faixa 3 (y 32 → 57, meio em 44,5), 45 mm da borda direita até o topo
    # (lado curvo); o vinco fica no lado voltado para a borda.
    furo = FuroCinta(faixa=3, borda="direita", distancia=45.0, largura=8.0, altura=9.0, raio=1.0)
    layout = _cinta(furos=[furo])
    topo, vinco = 120 - 45, 120 - 45 + 8
    assert _verticais(layout, TipoLinha.VINCO, vinco) == [(40, 49)]
    assert _verticais(layout, TipoLinha.CORTE, topo) == [(41, 48)]  # entre os arcos
    assert _horizontais(layout, TipoLinha.CORTE, 40) == [(topo + 1, vinco)]
    assert _horizontais(layout, TipoLinha.CORTE, 49) == [(topo + 1, vinco)]
    arcos = [l for l in layout.linhas if e_arco(l)]
    assert len(arcos) == 2 and all(l.tipo == TipoLinha.CORTE for l in arcos)


def test_furo_pela_borda_esquerda():
    furo = FuroCinta(faixa=1, borda="esquerda", distancia=30.0, largura=8.0, altura=10.0, raio=0.0)
    layout = _cinta(furos=[furo])
    assert _verticais(layout, TipoLinha.VINCO, 22) == [(10, 20)]  # vinco voltado para a esquerda
    assert _verticais(layout, TipoLinha.CORTE, 30) == [(10, 20)]
    assert not any(e_arco(l) for l in layout.linhas)


def test_furo_em_faixa_que_nao_existe_e_ignorado():
    furo = FuroCinta(faixa=5, borda="direita", distancia=45.0, largura=8.0, altura=9.0)
    assert len(_cinta(furos=[furo]).linhas) == len(_cinta().linhas)


def test_faces_sao_as_faixas_com_o_recuo():
    layout = _cinta(recuo=10.0, recuadas=(2,))
    assert layout.faixas_recuadas == (2,)
    paineis = calcular_paineis(
        TipoCaixa.CINTA, layout.segmentos_impressora, layout.segmentos_riscador, faixas_recuadas=layout.faixas_recuadas
    )
    assert [p.nome for p in paineis] == ["Faixa 1", "Faixa 2", "Faixa 3", "Faixa 4"]
    faixa2 = paineis[1]
    assert (faixa2.x1, faixa2.x2, faixa2.y1, faixa2.y2) == (10, 110, 30, 32)


def test_3d_da_cinta_fica_vazio_por_enquanto():
    layout = _cinta()
    assert montar_modelo(TipoCaixa.CINTA, layout.segmentos_impressora, layout.segmentos_riscador).vazio
