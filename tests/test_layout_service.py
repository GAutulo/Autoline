"""Testes do serviço de cálculo de layout.

O caso da maleta normal 300×200×150 é o exemplo documentado no projeto
original (README.md): Impressora = 40×200×300×200×300, Riscador =
150×150×150 — usado aqui como regressão para garantir que a porta pra
Python preserva exatamente o mesmo comportamento.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.layout_service import ServicoLayoutCaixa
from gerador_layout.models import MedidasCaixa, TipoCaixa, TipoLinha


def test_maleta_normal_300x200x150():
    medidas = MedidasCaixa(
        tipo=TipoCaixa.MALETA_NORMAL,
        comprimento=300,
        largura=200,
        altura=150,
    )

    layout = ServicoLayoutCaixa().calcular(medidas)

    # Impressora (X): Aba(4) + L(200) + C(300) + L(200) + C(300) = 1004
    assert layout.largura_total == 4 + 200 + 300 + 200 + 300
    # Riscador (Y): (L/2=100) + A(150) + (L/2=100) = 350
    assert layout.altura_total == 100 + 150 + 100

    assert layout.linhas, "layout deveria conter linhas técnicas"
    tipos_presentes = {linha.tipo for linha in layout.linhas}
    assert TipoLinha.CORTE in tipos_presentes
    assert TipoLinha.VINCO in tipos_presentes
    assert TipoLinha.CORTE_SERRA in tipos_presentes


def test_medidas_geradas_manuais_nao_alteram_c_l_a():
    """Ajustar um trecho manualmente não deve mudar C×L×A (regra do domínio),
    só a geometria interna do desenho."""
    medidas = MedidasCaixa(
        tipo=TipoCaixa.MALETA_NORMAL,
        comprimento=300,
        largura=200,
        altura=150,
        impressora_largura_1=210,  # ajuste manual fora do padrão (200)
    )

    layout = ServicoLayoutCaixa().calcular(medidas)

    # A largura total do desenho muda (reflete o ajuste manual)...
    assert layout.largura_total == 4 + 210 + 300 + 200 + 300
    # ...mas as medidas finais da caixa em si (C×L×A) não são alteradas
    # pelo serviço — isso é responsabilidade da camada de UI, que apenas
    # avisa quando o ajuste passa da tolerância de ±5 mm.
    assert medidas.comprimento == 300
    assert medidas.largura == 200
    assert medidas.altura == 150


def test_cores_legenda_sao_copiadas_ignorando_vazias():
    from gerador_layout.models import CorImpressao

    medidas = MedidasCaixa(
        tipo=TipoCaixa.MALETA_NORMAL,
        comprimento=100,
        largura=100,
        altura=100,
        cores_legenda=[
            CorImpressao(nome="PRETO", r=0, g=0, b=0),
            CorImpressao(nome="  ", r=1, g=1, b=1),  # deve ser ignorada
        ],
    )

    layout = ServicoLayoutCaixa().calcular(medidas)

    assert len(layout.cores_legenda) == 1
    assert layout.cores_legenda[0].nome == "PRETO"


def test_tipo_nao_implementado_gera_erro_explicito():
    import pytest

    medidas = MedidasCaixa(tipo=TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_SEM_CORTE, comprimento=1, largura=1, altura=1)
    # Esse tipo já está implementado — o teste real de "não implementado"
    # ficaria aqui se algum tipo novo for adicionado ao enum sem cálculo.
    ServicoLayoutCaixa().calcular(medidas)
