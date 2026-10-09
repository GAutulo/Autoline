"""Testes da dobra 3D: plana = dieline, fechada = sólido C × L × A."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.dobra3d import caixa_envolvente, montar_modelo, posicionar, produto_escalar
from gerador_layout.layout_service import ServicoLayoutCaixa
from gerador_layout.models import MedidasCaixa, TipoCaixa

C, L, A = 300.0, 200.0, 150.0
TOLERANCIA = 1e-6


def _modelo(tipo: TipoCaixa):
    layout = ServicoLayoutCaixa().calcular(MedidasCaixa(tipo=tipo, comprimento=C, largura=L, altura=A))
    return montar_modelo(tipo, layout.segmentos_impressora, layout.segmentos_riscador), layout


def _dimensoes(posicionados, ids):
    mn, mx = caixa_envolvente([p for p in posicionados if p.painel.id in ids])
    return sorted(round(mx[i] - mn[i], 6) for i in range(3))


@pytest.mark.parametrize("tipo", list(TipoCaixa))
def test_planificada_e_a_propria_dieline(tipo):
    modelo, layout = _modelo(tipo)
    assert not modelo.vazio
    for pp in posicionar(modelo, 0.0):
        for x, y in pp.painel.cantos:
            px, py, pz = pp.ponto(x, y)
            assert (px, py, pz) == pytest.approx((x, y, 0.0), abs=TOLERANCIA)
            assert -TOLERANCIA <= px <= layout.largura_total + TOLERANCIA
            assert -TOLERANCIA <= py <= layout.altura_total + TOLERANCIA


@pytest.mark.parametrize("tipo", [TipoCaixa.MALETA_NORMAL, TipoCaixa.MALETA_TRANSPASSADA])
def test_maleta_fechada_tem_as_medidas_da_caixa(tipo):
    modelo, _ = _modelo(tipo)
    fechada = posicionar(modelo, 1.0)
    paredes = {"frente", "verso", "lateral1", "lateral2"}
    assert _dimensoes(fechada, paredes) == sorted([C, L, A])
    # O verso fecha o anel: fica paralelo à frente, a uma Largura de distância.
    por_id = {p.painel.id: p for p in fechada}
    n_frente, n_verso = por_id["frente"].normal_externa, por_id["verso"].normal_externa
    assert produto_escalar(n_frente, n_verso) == pytest.approx(-1.0)


@pytest.mark.parametrize("tipo", [t for t in TipoCaixa if t not in (TipoCaixa.MALETA_NORMAL, TipoCaixa.MALETA_TRANSPASSADA)])
def test_envoltorio_fechado_tem_as_medidas_da_caixa(tipo):
    modelo, _ = _modelo(tipo)
    fechada = posicionar(modelo, 1.0)
    assert _dimensoes(fechada, {"base", "lateral1", "lateral2", "parede_sup", "parede_inf"}) == sorted([C, L, A])


@pytest.mark.parametrize("tipo", list(TipoCaixa))
def test_caixa_fechada_tem_faces_impressas_para_fora(tipo):
    """Toda parede termina com o lado impresso apontando pra longe do centro."""
    modelo, _ = _modelo(tipo)
    fechada = posicionar(modelo, 1.0)
    paredes = [p for p in fechada if p.painel.id in {"frente", "verso", "lateral1", "lateral2", "base", "parede_sup", "parede_inf"}]
    mn, mx = caixa_envolvente(paredes)
    centro = tuple((mn[i] + mx[i]) / 2 for i in range(3))
    for pp in paredes:
        p = pp.painel
        cx, cy, cz = pp.ponto((p.x1 + p.x2) / 2, (p.y1 + p.y2) / 2)
        para_fora = (cx - centro[0], cy - centro[1], cz - centro[2])
        assert produto_escalar(pp.normal_externa, para_fora) > 0, p.id


def test_tampa_da_maleta_fecha_no_plano_do_topo():
    modelo, _ = _modelo(TipoCaixa.MALETA_NORMAL)
    fechada = {p.painel.id: p for p in posicionar(modelo, 1.0)}
    tampa = fechada["tampa_frente"]
    p = tampa.painel
    # Aba maior fecha a 90° exatos: todos os cantos no plano da aresta de cima da frente.
    alturas = {round(tampa.ponto(x, y)[1], 6) for x, y in p.cantos}
    assert alturas == {round(p.y2, 6)}


def test_medidas_invalidas_geram_modelo_vazio():
    assert montar_modelo(TipoCaixa.MALETA_NORMAL, [4, 0, 300, 200, 300], [100, 150, 100]).vazio
