"""Catálogo embutido de estilos paramétricos (ver `estilos.py` pro
formato). Geometria desenhada a partir da descrição pública dos estilos
FEFCO — medidas internas C × L × A e espessura E do papelão."""

from __future__ import annotations


def _l(de, ate, tipo="corte", dobra=None, tempo=None) -> dict:
    item = {"de": list(de), "ate": list(ate), "tipo": tipo}
    if dobra is not None:
        item["dobra"] = dobra
        item["tempo"] = list(tempo or (0.0, 1.0))
    return item


_MEDIDAS = [
    {"nome": "C", "rotulo": "Comprimento (C)", "padrao": 300, "min": 10, "max": 3000},
    {"nome": "L", "rotulo": "Largura (L)", "padrao": 200, "min": 10, "max": 3000},
    {"nome": "A", "rotulo": "Altura (A)", "padrao": 150, "min": 5, "max": 3000},
    {"nome": "E", "rotulo": "Espessura do papelão (E)", "padrao": 3, "min": 0, "max": 15},
]


# ── FEFCO 0201: caixa normal com abas (RSC) ───────────────────────────
# x: cola | C | L | C | L      y: abas (L/2) | A | abas (L/2)
def _fefco_0201() -> dict:
    x0, x1, x2, x3, x4, x5 = "0", "G", "G + C", "G + C + L", "G + 2*C + L", "G + 2*C + 2*L"
    y0, y1, y2, y3 = "0", "F", "F + A", "2*F + A"
    linhas = [
        # contorno das abas de cima e de baixo
        _l((x1, y0), (x5, y0)),
        _l((x1, y3), (x5, y3)),
        _l((x1, y0), (x1, y1)),
        _l((x5, y0), (x5, y1)),
        _l((x1, y2), (x1, y3)),
        _l((x5, y2), (x5, y3)),
        _l((x5, y1), (x5, y2)),
        # fendas entre as abas
        *[_l((x, y0), (x, y1)) for x in (x2, x3, x4)],
        *[_l((x, y2), (x, y3)) for x in (x2, x3, x4)],
        # aba de cola (chanfrada)
        _l((x1, y1), (x0, f"{y1} + T")),
        _l((x0, f"{y1} + T"), (x0, f"{y2} - T")),
        _l((x0, f"{y2} - T"), (x1, y2)),
        # vincos das paredes
        _l((x1, y1), (x1, y2), "vinco", 90, (0.25, 0.4)),
        _l((x2, y1), (x2, y2), "vinco", 90, (0.0, 0.3)),
        _l((x3, y1), (x3, y2), "vinco", 90, (0.0, 0.3)),
        _l((x4, y1), (x4, y2), "vinco", 90, (0.0, 0.3)),
    ]
    # vincos das abas: as menores (sobre L) dobram primeiro e um pouco
    # mais (ficam por dentro); as maiores (sobre C) fecham por cima.
    for xa, xb, menor in ((x1, x2, False), (x2, x3, True), (x3, x4, False), (x4, x5, True)):
        angulo, tempo = (92, (0.45, 0.65)) if menor else (90, (0.65, 0.9))
        linhas.append(_l((xa, y1), (xb, y1), "vinco", angulo, tempo))
        linhas.append(_l((xa, y2), (xb, y2), "vinco", angulo, tempo))
    return {
        "codigo": "FEFCO 0201",
        "nome": "Caixa normal com abas",
        "descricao": "A caixa de papelão mais comum: 4 paredes, aba de cola e abas em cima e embaixo "
        "que se encontram no meio. Medidas internas.",
        "variaveis": _MEDIDAS + [{"nome": "G", "rotulo": "Aba de cola (G)", "padrao": 30, "min": 10, "max": 80}],
        "derivadas": {"F": "L / 2 + E / 2", "T": "min(G * 0.5, A / 4)"},
        "linhas": linhas,
        "base": ["G + C / 2", "F + A / 2"],
        "cotas": [
            {"de": [x1, "2*F + A + 12"], "ate": [x2, "2*F + A + 12"], "rotulo": "C"},
            {"de": [x2, "2*F + A + 12"], "ate": [x3, "2*F + A + 12"], "rotulo": "L"},
            {"de": ["G + 2*C + 2*L + 12", y1], "ate": ["G + 2*C + 2*L + 12", y2], "rotulo": "A"},
        ],
    }


# ── FEFCO 0427: caixa de e-commerce (tampa com aba de encaixe) ────────
# Coluna do meio, de cima pra baixo: aba de encaixe | tampa | parede de
# trás | fundo | frente | frente interna. Dos lados do fundo: parede
# lateral dupla (externa + interna, que dobra 180° pra dentro). Orelhas nas
# pontas da parede de trás e da frente, presas dentro da lateral dupla.
def _fefco_0427() -> dict:
    xa, xb = "S", "S + C"
    xl1, xr1, xr0 = "S - A", "S + C + A", "S + C + A + I"
    y0, y1, y2, y3, y4, y5, y6 = "0", "P", "P + L + E", "P + L + E + A", "P + 2*L + E + A", "P + 2*L + E + 2*A", "P + 2*L + E + 2*A + I"
    linhas = [
        # aba de encaixe da tampa
        _l((xa, y0), (xb, y0)),
        _l((xa, y0), (xa, y1)),
        _l((xb, y0), (xb, y1)),
        _l((xa, y1), (xb, y1), "vinco", 90, (0.85, 1.0)),
        # tampa e as abinhas laterais dela
        _l((xa, y1), (xa, f"{y1} + E")),
        _l((xb, y1), (xb, f"{y1} + E")),
        _l((xa, f"{y2} - E"), (xa, y2)),
        _l((xb, f"{y2} - E"), (xb, y2)),
        _l((xa, f"{y1} + E"), (xa, f"{y2} - E"), "vinco", 92, (0.6, 0.75)),
        _l((xb, f"{y1} + E"), (xb, f"{y2} - E"), "vinco", 92, (0.6, 0.75)),
        _l(("S - D", f"{y1} + E"), (xa, f"{y1} + E")),
        _l(("S - D", f"{y1} + E"), ("S - D", f"{y2} - E")),
        _l(("S - D", f"{y2} - E"), (xa, f"{y2} - E")),
        _l((xb, f"{y1} + E"), ("S + C + D", f"{y1} + E")),
        _l(("S + C + D", f"{y1} + E"), ("S + C + D", f"{y2} - E")),
        _l((xb, f"{y2} - E"), ("S + C + D", f"{y2} - E")),
        _l((xa, y2), (xb, y2), "vinco", 90, (0.7, 0.9)),
        # parede de trás e as orelhas dela
        _l((xa, y2), (xa, f"{y2} + E")),
        _l((xb, y2), (xb, f"{y2} + E")),
        # (folga de E entre a orelha e a lateral: as duas não dividem corte)
        _l((xa, f"{y2} + E"), (xa, f"{y3} - E"), "vinco", 90, (0.25, 0.4)),
        _l((xb, f"{y2} + E"), (xb, f"{y3} - E"), "vinco", 90, (0.25, 0.4)),
        _l((xa, f"{y3} - E"), (xa, y3)),
        _l((xb, f"{y3} - E"), (xb, y3)),
        _l(("S - W", f"{y2} + E"), (xa, f"{y2} + E")),
        _l(("S - W", f"{y2} + E"), ("S - W", f"{y3} - E")),
        _l(("S - W", f"{y3} - E"), (xa, f"{y3} - E")),
        _l((xb, f"{y2} + E"), ("S + C + W", f"{y2} + E")),
        _l(("S + C + W", f"{y2} + E"), ("S + C + W", f"{y3} - E")),
        _l((xb, f"{y3} - E"), ("S + C + W", f"{y3} - E")),
        _l((xa, y3), (xb, y3), "vinco", 90, (0.0, 0.25)),
        # fundo e laterais duplas
        _l(("0", y3), (xa, y3)),
        _l((xb, y3), (xr0, y3)),
        _l(("0", y4), (xa, y4)),
        _l((xb, y4), (xr0, y4)),
        _l(("0", y3), ("0", y4)),
        _l((xr0, y3), (xr0, y4)),
        _l((xa, y3), (xa, y4), "vinco", 90, (0.0, 0.25)),
        _l((xb, y3), (xb, y4), "vinco", 90, (0.0, 0.25)),
        _l((xl1, y3), (xl1, y4), "vinco", 178, (0.4, 0.6)),
        _l((xr1, y3), (xr1, y4), "vinco", 178, (0.4, 0.6)),
        _l((xa, y4), (xb, y4), "vinco", 90, (0.0, 0.25)),
        # frente, orelhas dela e a frente interna
        _l((xa, f"{y4} + E"), (xa, f"{y5} - E"), "vinco", 90, (0.25, 0.4)),
        _l((xb, f"{y4} + E"), (xb, f"{y5} - E"), "vinco", 90, (0.25, 0.4)),
        _l((xa, y4), (xa, f"{y4} + E")),
        _l((xb, y4), (xb, f"{y4} + E")),
        _l(("S - W", f"{y4} + E"), (xa, f"{y4} + E")),
        _l(("S - W", f"{y4} + E"), ("S - W", f"{y5} - E")),
        _l(("S - W", f"{y5} - E"), (xa, f"{y5} - E")),
        _l((xb, f"{y4} + E"), ("S + C + W", f"{y4} + E")),
        _l(("S + C + W", f"{y4} + E"), ("S + C + W", f"{y5} - E")),
        _l((xb, f"{y5} - E"), ("S + C + W", f"{y5} - E")),
        _l((xa, f"{y5} - E"), (xa, y5)),
        _l((xb, f"{y5} - E"), (xb, y5)),
        _l((xa, y5), (xb, y5), "vinco", 178, (0.4, 0.6)),
        _l((xa, y5), (xa, y6)),
        _l((xb, y5), (xb, y6)),
        _l((xa, y6), (xb, y6)),
    ]
    return {
        "codigo": "FEFCO 0427",
        "nome": "Caixa e-commerce (tampa com encaixe)",
        "descricao": "Caixa de correio/e-commerce de uma peça só, sem cola: laterais e frente duplas, "
        "orelhas presas dentro das laterais e tampa com aba de encaixe. Medidas internas.",
        "variaveis": _MEDIDAS,
        "derivadas": {
            "I": "A - E",
            "S": "2*A - E",
            "P": "A - 2*E",
            "W": "L / 2 - E",
            "D": "A - 2*E",
        },
        "validacoes": [
            ["A > 3*E", "A altura precisa ser maior que 3 espessuras do papelão."],
            ["L > 4*E", "A largura precisa ser maior que 4 espessuras do papelão."],
            ["L / 2 - E <= 2*A - E", "Largura grande demais para a altura: as orelhas não cabem na lateral (L até 4 × A)."],
        ],
        "linhas": linhas,
        "base": ["S + C / 2", "P + L + E + A + L / 2"],
        "cotas": [
            {"de": [xa, "P + 2*L + E + A - 6"], "ate": [xb, "P + 2*L + E + A - 6"], "rotulo": "C"},
            {"de": ["S + 6", y3], "ate": ["S + 6", y4], "rotulo": "L"},
            {"de": ["S + C - 6", y2], "ate": ["S + C - 6", y3], "rotulo": "A"},
        ],
    }


CATALOGO: list[dict] = [_fefco_0201(), _fefco_0427()]
