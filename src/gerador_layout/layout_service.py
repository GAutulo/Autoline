"""Serviço de cálculo de layouts de caixas.

Porta direta do BoxLayoutService.cs original. Convenção mantida:
  X → esquerda para direita (Impressora)
  Y → cima para baixo       (Riscador)
  Unidade: milímetros
"""

from __future__ import annotations

import math

from .models import (
    TIPOS_MEIA_CAIXA,
    TIPOS_TRANSPASSADA,
    CorImpressao,
    LayoutCaixa,
    LinhaDesenho,
    MedidasCaixa,
    TipoCaixa,
    TipoLinha,
)

LARGURA_SERRA_MM = 1.0


def _valor_ou_padrao(valor: float, padrao: float) -> float:
    return valor if valor > 0 else padrao


def _copiar_cores_legenda(medidas: MedidasCaixa, layout: LayoutCaixa) -> None:
    layout.cores_legenda = [
        CorImpressao(nome=c.nome, r=c.r, g=c.g, b=c.b)
        for c in medidas.cores_legenda
        if c.nome and c.nome.strip()
    ]


def _adicionar_segmentos_horizontais_com_serra(
    linhas: list[LinhaDesenho],
    y: float,
    x_inicial: float,
    x_final: float,
    vincos_com_serra: list[float],
    meia_serra: float,
    tipo: TipoLinha,
) -> None:
    cursor = x_inicial
    for xv in sorted(vincos_com_serra):
        linhas.append(LinhaDesenho(cursor, y, xv - meia_serra, y, tipo))
        cursor = xv + meia_serra
    linhas.append(LinhaDesenho(cursor, y, x_final, y, tipo))


class ServicoLayoutCaixa:
    """Calcula as linhas técnicas de cada tipo de caixa suportado."""

    def calcular(self, m: MedidasCaixa) -> LayoutCaixa:
        if m.tipo == TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_SEM_CORTE:
            return self._calc_envoltorio_fechamento(m, com_corte=False, fechamento_normal=False)
        if m.tipo == TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_COM_CORTE:
            return self._calc_envoltorio_fechamento(m, com_corte=True, fechamento_normal=False)
        if m.tipo == TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_SEM_CORTE:
            return self._calc_envoltorio_fechamento(m, com_corte=False, fechamento_normal=True)
        if m.tipo == TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE:
            return self._calc_envoltorio_fechamento(m, com_corte=True, fechamento_normal=True)
        if m.tipo == TipoCaixa.MALETA_NORMAL:
            return self._calc_maleta_normal(m)
        if m.tipo == TipoCaixa.MALETA_TRANSPASSADA:
            return self._calc_maleta_transpassada(m)
        if m.tipo in TIPOS_MEIA_CAIXA:
            return self._calc_maleta_normal(m)
        if m.tipo == TipoCaixa.ENVOLTORIO_CAPA:
            return self._calc_envoltorio_capa(m)
        raise NotImplementedError(f"Tipo {m.tipo} não implementado.")

    # ════════════════════════════════════════════════════════════════
    # 1. ENVOLTÓRIO COM FECHAMENTO (no meio / normal)
    #
    #  IMPRESSORA (X): Aba × Altura × Comprimento × Altura × Aba
    #  RISCADOR   (Y): Aba × Altura × Largura × Altura × Aba
    #    - fechamento no meio: Aba = ceil((Largura/2)*10)/10
    #    - fechamento normal:  1ª parte = Largura, última = Aba impressora
    # ════════════════════════════════════════════════════════════════
    def _calc_envoltorio_fechamento(
        self, m: MedidasCaixa, *, com_corte: bool, fechamento_normal: bool
    ) -> LayoutCaixa:
        layout = LayoutCaixa()
        linhas = layout.linhas

        aba_imp = _valor_ou_padrao(m.impressora_aba, 7.0)
        imp2 = _valor_ou_padrao(m.impressora_largura_1, m.altura)
        imp3 = _valor_ou_padrao(m.impressora_comprimento_1, m.comprimento)
        imp4 = _valor_ou_padrao(m.impressora_largura_2, m.altura)
        imp5 = _valor_ou_padrao(m.impressora_comprimento_2, aba_imp)

        aba_riscador_meio = math.ceil((m.largura / 2.0) * 10.0) / 10.0
        ris1_padrao = m.largura if fechamento_normal else aba_riscador_meio
        ris5_padrao = aba_imp if fechamento_normal else aba_riscador_meio
        ris1 = _valor_ou_padrao(m.riscador_superior, ris1_padrao)
        ris2 = _valor_ou_padrao(m.riscador_centro, m.altura)
        ris3 = _valor_ou_padrao(m.riscador_inferior, m.largura)
        ris4 = _valor_ou_padrao(m.riscador_parte_4, m.altura)
        ris5 = _valor_ou_padrao(m.riscador_parte_5, ris5_padrao)

        x0 = 0.0
        x1 = x0 + aba_imp
        x2 = x1 + imp2
        x3 = x2 + imp3
        x4 = x3 + imp4
        x5 = x4 + imp5

        y0 = 0.0
        y1 = y0 + ris1
        y2 = y1 + ris2
        y3 = y2 + ris3
        y4 = y3 + ris4
        y5 = y4 + ris5

        layout.largura_total = x5
        layout.altura_total = y5
        layout.segmentos_impressora = [aba_imp, imp2, imp3, imp4, imp5]
        layout.segmentos_riscador = [ris1, ris2, ris3, ris4, ris5]
        if fechamento_normal:
            layout.descricao = (
                "Envoltório fechamento normal — com corte"
                if com_corte
                else "Envoltório fechamento normal — sem corte"
            )
        else:
            layout.descricao = (
                "Envoltório c/ fechamento no meio — com corte"
                if com_corte
                else "Envoltório c/ fechamento no meio — sem corte"
            )

        meia_serra = LARGURA_SERRA_MM / 2.0

        if not com_corte:
            # SEM CORTE: chapa inteira, vinco vertical nas abas, corte-serra
            # nos limites do painel central (só nas áreas superior/inferior).
            _adicionar_segmentos_horizontais_com_serra(
                linhas, y0, x0, x5, [x2, x3], meia_serra, TipoLinha.CORTE
            )
            _adicionar_segmentos_horizontais_com_serra(
                linhas, y5, x0, x5, [x2, x3], meia_serra, TipoLinha.CORTE
            )
            linhas.append(LinhaDesenho(x0, y0, x0, y5, TipoLinha.CORTE))
            linhas.append(LinhaDesenho(x5, y0, x5, y5, TipoLinha.CORTE))

            for xv in (x1, x4):
                linhas.append(LinhaDesenho(xv, y0, xv, y5, TipoLinha.VINCO))

            for yh in (y1, y2, y3, y4):
                linhas.append(LinhaDesenho(x0, yh, x5, yh, TipoLinha.VINCO))

            for xv in (x2, x3):
                xa, xb = xv - meia_serra, xv + meia_serra
                linhas.append(LinhaDesenho(xa, y0, xa, y2, TipoLinha.CORTE_SERRA))
                linhas.append(LinhaDesenho(xb, y0, xb, y2, TipoLinha.CORTE_SERRA))
                linhas.append(LinhaDesenho(xa, y3, xa, y5, TipoLinha.CORTE_SERRA))
                linhas.append(LinhaDesenho(xb, y3, xb, y5, TipoLinha.CORTE_SERRA))
                linhas.append(LinhaDesenho(xv, y2, xv, y3, TipoLinha.VINCO))
        else:
            # COM CORTE: remove os espaços laterais destacados, mantém só
            # uma linha vertical nas laterais do recorte (x1 e x4).
            _adicionar_segmentos_horizontais_com_serra(
                linhas, y0, x1, x4, [x2, x3], meia_serra, TipoLinha.CORTE
            )
            _adicionar_segmentos_horizontais_com_serra(
                linhas, y5, x1, x4, [x2, x3], meia_serra, TipoLinha.CORTE
            )

            linhas.append(LinhaDesenho(x0, y2, x1, y2, TipoLinha.CORTE))
            linhas.append(LinhaDesenho(x1, y2, x4, y2, TipoLinha.VINCO))
            linhas.append(LinhaDesenho(x4, y2, x5, y2, TipoLinha.CORTE))

            linhas.append(LinhaDesenho(x0, y3, x1, y3, TipoLinha.CORTE))
            linhas.append(LinhaDesenho(x1, y3, x4, y3, TipoLinha.VINCO))
            linhas.append(LinhaDesenho(x4, y3, x5, y3, TipoLinha.CORTE))

            linhas.append(LinhaDesenho(x0, y2, x0, y3, TipoLinha.CORTE))
            linhas.append(LinhaDesenho(x5, y2, x5, y3, TipoLinha.CORTE))

            linhas.append(LinhaDesenho(x1, y0, x1, y2, TipoLinha.CORTE))
            linhas.append(LinhaDesenho(x1, y2, x1, y3, TipoLinha.VINCO))
            linhas.append(LinhaDesenho(x1, y3, x1, y5, TipoLinha.CORTE))

            linhas.append(LinhaDesenho(x4, y0, x4, y2, TipoLinha.CORTE))
            linhas.append(LinhaDesenho(x4, y2, x4, y3, TipoLinha.VINCO))
            linhas.append(LinhaDesenho(x4, y3, x4, y5, TipoLinha.CORTE))

            linhas.append(LinhaDesenho(x1, y1, x4, y1, TipoLinha.VINCO))
            linhas.append(LinhaDesenho(x1, y4, x4, y4, TipoLinha.VINCO))

            for xv in (x2, x3):
                xa, xb = xv - meia_serra, xv + meia_serra
                linhas.append(LinhaDesenho(xa, y0, xa, y2, TipoLinha.CORTE_SERRA))
                linhas.append(LinhaDesenho(xb, y0, xb, y2, TipoLinha.CORTE_SERRA))
                linhas.append(LinhaDesenho(xa, y3, xa, y5, TipoLinha.CORTE_SERRA))
                linhas.append(LinhaDesenho(xb, y3, xb, y5, TipoLinha.CORTE_SERRA))
                # Vinco vertical na faixa central (y2-y3), entre o painel
                # central e as abas laterais — existia no branch "sem
                # corte" (algumas linhas acima) e faltava aqui.
                linhas.append(LinhaDesenho(xv, y2, xv, y3, TipoLinha.VINCO))

        _copiar_cores_legenda(m, layout)
        return layout

    # ════════════════════════════════════════════════════════════════
    # 2. MALETA NORMAL
    #
    #  IMPRESSORA (X): [Aba] | [L] | [C] | [L] | [C]
    #  RISCADOR   (Y): [(L/2)] | [A] | [(L/2)]
    #
    #  Corte externo = CORTE / vincos = VINCO / separação de abas = CORTE_SERRA
    # ════════════════════════════════════════════════════════════════
    def _calc_maleta_normal(self, m: MedidasCaixa) -> LayoutCaixa:
        layout = LayoutCaixa()
        linhas = layout.linhas

        aba_lat = _valor_ou_padrao(m.impressora_aba, m.aba if m.aba > 0 else 4.0)
        largura1 = _valor_ou_padrao(m.impressora_largura_1, m.largura)
        comprimento1 = _valor_ou_padrao(m.impressora_comprimento_1, m.comprimento)
        largura2 = _valor_ou_padrao(m.impressora_largura_2, m.largura)
        comprimento2 = _valor_ou_padrao(m.impressora_comprimento_2, m.comprimento)

        aba_riscador_padrao = m.largura if m.tipo in TIPOS_TRANSPASSADA else m.largura / 2.0
        meia = m.tipo in TIPOS_MEIA_CAIXA
        topo = _valor_ou_padrao(m.riscador_superior, aba_riscador_padrao)
        centro = _valor_ou_padrao(m.riscador_centro, m.altura)
        inferior = _valor_ou_padrao(m.riscador_inferior, aba_riscador_padrao)

        meia_serra = LARGURA_SERRA_MM / 2.0
        chanfro = min(aba_lat, max(0.0, centro / 2.0))

        x0 = 0.0
        x1 = x0 + aba_lat
        x2 = x1 + largura1
        x3 = x2 + comprimento1
        x4 = x3 + largura2
        x5 = x4 + comprimento2
        if meia:
            # Meia caixa: a faca acaba no primeiro C (Aba | L | C).
            x4 = x5 = x3

        y0 = 0.0
        y1 = y0 + topo
        y2 = y1 + centro
        y3 = y2 + inferior

        layout.largura_total = x5
        layout.altura_total = y3
        nome = "Maleta transpassada" if m.tipo in TIPOS_TRANSPASSADA else "Maleta normal"
        layout.descricao = f"{nome} — meia caixa (Aba × L × C)" if meia else f"{nome} — medidas por trecho"
        layout.segmentos_impressora = (
            [aba_lat, largura1, comprimento1] if meia else [aba_lat, largura1, comprimento1, largura2, comprimento2]
        )
        layout.segmentos_riscador = [topo, centro, inferior]
        serras = [x2] if meia else [x2, x3, x4]

        # ── CORTES EXTERNOS ────────────────────────────────────────
        _adicionar_segmentos_horizontais_com_serra(
            linhas, y0, x1, x5, serras, meia_serra, TipoLinha.CORTE
        )
        _adicionar_segmentos_horizontais_com_serra(
            linhas, y3, x1, x5, serras, meia_serra, TipoLinha.CORTE
        )

        linhas.append(LinhaDesenho(x5, y0, x5, y3, TipoLinha.CORTE))
        linhas.append(LinhaDesenho(x1, y0, x1, y1, TipoLinha.CORTE))
        linhas.append(LinhaDesenho(x1, y2, x1, y3, TipoLinha.CORTE))

        # Aba lateral esquerda com chanfros.
        linhas.append(LinhaDesenho(x0, y1 + chanfro, x0, y2 - chanfro, TipoLinha.CORTE))
        linhas.append(LinhaDesenho(x1, y1, x0, y1 + chanfro, TipoLinha.CORTE))
        linhas.append(LinhaDesenho(x1, y2, x0, y2 - chanfro, TipoLinha.CORTE))

        # ── VINCOS ────────────────────────────────────────────────
        for xv in (x1, x2) if meia else (x1, x2, x3, x4):
            linhas.append(LinhaDesenho(xv, y1, xv, y2, TipoLinha.VINCO))

        linhas.append(LinhaDesenho(x1, y1, x5, y1, TipoLinha.VINCO))
        linhas.append(LinhaDesenho(x1, y2, x5, y2, TipoLinha.VINCO))

        # ── CORTE SERRA ───────────────────────────────────────────
        for xv in serras:
            xa, xb = xv - meia_serra, xv + meia_serra
            linhas.append(LinhaDesenho(xa, y0, xa, y1, TipoLinha.CORTE_SERRA))
            linhas.append(LinhaDesenho(xb, y0, xb, y1, TipoLinha.CORTE_SERRA))
            linhas.append(LinhaDesenho(xa, y2, xa, y3, TipoLinha.CORTE_SERRA))
            linhas.append(LinhaDesenho(xb, y2, xb, y3, TipoLinha.CORTE_SERRA))

        _copiar_cores_legenda(m, layout)
        return layout

    # ════════════════════════════════════════════════════════════════
    # 3. MALETA TRANSPASSADA
    #
    # Mesma geometria base da maleta normal. A diferença fica no
    # RISCADOR, que na tela é Largura × Altura × Largura em vez de
    # Largura/2 × Altura × Largura/2 (ajuste tratado na camada de UI,
    # que preenche riscador_superior/inferior antes de chamar aqui).
    # ════════════════════════════════════════════════════════════════
    # ════════════════════════════════════════════════════════════════
    # 4. ENVOLTÓRIO CAPA (bandeja)
    #
    #  IMPRESSORA (X): A × C × A      RISCADOR (Y): A × L × A
    #  Mesma lógica do envoltório "sem corte": cantos presos nas laterais
    #  pelo vinco horizontal, separados das paredes por corte-serra.
    # ════════════════════════════════════════════════════════════════
    def _calc_envoltorio_capa(self, m: MedidasCaixa) -> LayoutCaixa:
        layout = LayoutCaixa()
        linhas = layout.linhas
        imp1 = _valor_ou_padrao(m.impressora_aba, m.altura)
        imp2 = _valor_ou_padrao(m.impressora_largura_1, m.comprimento)
        imp3 = _valor_ou_padrao(m.impressora_comprimento_1, m.altura)
        ris1 = _valor_ou_padrao(m.riscador_superior, m.altura)
        ris2 = _valor_ou_padrao(m.riscador_centro, m.largura)
        ris3 = _valor_ou_padrao(m.riscador_inferior, m.altura)

        x0, x1, x2, x3 = 0.0, imp1, imp1 + imp2, imp1 + imp2 + imp3
        y0, y1, y2, y3 = 0.0, ris1, ris1 + ris2, ris1 + ris2 + ris3
        layout.largura_total = x3
        layout.altura_total = y3
        layout.segmentos_impressora = [imp1, imp2, imp3]
        layout.segmentos_riscador = [ris1, ris2, ris3]
        layout.descricao = "Envoltório capa (bandeja)"

        meia_serra = LARGURA_SERRA_MM / 2.0
        _adicionar_segmentos_horizontais_com_serra(linhas, y0, x0, x3, [x1, x2], meia_serra, TipoLinha.CORTE)
        _adicionar_segmentos_horizontais_com_serra(linhas, y3, x0, x3, [x1, x2], meia_serra, TipoLinha.CORTE)
        linhas.append(LinhaDesenho(x0, y0, x0, y3, TipoLinha.CORTE))
        linhas.append(LinhaDesenho(x3, y0, x3, y3, TipoLinha.CORTE))
        for yh in (y1, y2):
            linhas.append(LinhaDesenho(x0, yh, x3, yh, TipoLinha.VINCO))
        for xv in (x1, x2):
            xa, xb = xv - meia_serra, xv + meia_serra
            linhas.append(LinhaDesenho(xa, y0, xa, y1, TipoLinha.CORTE_SERRA))
            linhas.append(LinhaDesenho(xb, y0, xb, y1, TipoLinha.CORTE_SERRA))
            linhas.append(LinhaDesenho(xa, y2, xa, y3, TipoLinha.CORTE_SERRA))
            linhas.append(LinhaDesenho(xb, y2, xb, y3, TipoLinha.CORTE_SERRA))
            linhas.append(LinhaDesenho(xv, y1, xv, y2, TipoLinha.VINCO))

        _copiar_cores_legenda(m, layout)
        return layout

    def _calc_maleta_transpassada(self, m: MedidasCaixa) -> LayoutCaixa:
        layout = self._calc_maleta_normal(m)
        layout.descricao = "Maleta transpassada — medidas por trecho"
        return layout
