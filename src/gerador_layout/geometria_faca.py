"""Geometria das linhas da faca — retas e arcos — e as ferramentas de desenho
no estilo do ArtiosCAD (ver REFERENCIA_ARTIOSCAD_ESTRUTURA.md, etapa D):
paralela, aparar, estender e arredondar canto. Sem nada de UI.

Arco = `LinhaDesenho` com `bojo` diferente de zero, a mesma convenção do
"bulge" do DXF: bojo = tan(θ/4), θ = ângulo do arco. O ponto do meio do arco
fica a `bojo × corda / 2` da corda, pro lado da normal n = (−dy, dx)/corda.
Bojo 1 = meia-volta; 0 = reta.
"""

from __future__ import annotations

import math
from dataclasses import replace

from .models import LinhaDesenho

Ponto = tuple[float, float]

_EPS = 1e-6


def _sub(a: Ponto, b: Ponto) -> Ponto:
    return (a[0] - b[0], a[1] - b[1])


def _dist(a: Ponto, b: Ponto) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def inicio(l: LinhaDesenho) -> Ponto:
    return (l.x1, l.y1)


def fim(l: LinhaDesenho) -> Ponto:
    return (l.x2, l.y2)


def e_arco(l: LinhaDesenho) -> bool:
    return abs(getattr(l, "bojo", 0.0)) > 1e-9


def _normal(l: LinhaDesenho) -> tuple[Ponto, float]:
    dx, dy = l.x2 - l.x1, l.y2 - l.y1
    c = math.hypot(dx, dy)
    if c < _EPS:
        return (0.0, 0.0), 0.0
    return (-dy / c, dx / c), c


def meio_do_arco(l: LinhaDesenho) -> Ponto:
    """O ponto da linha no meio do caminho (na reta, o meio da reta)."""
    (nx, ny), c = _normal(l)
    s = l.bojo * c / 2
    return ((l.x1 + l.x2) / 2 + nx * s, (l.y1 + l.y2) / 2 + ny * s)


def _circulo(a: Ponto, b: Ponto, c: Ponto) -> tuple[Ponto, float] | None:
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2, c[0] ** 2 + c[1] ** 2
    ux = (a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d
    uy = (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d
    return (ux, uy), _dist((ux, uy), a)


def arco(l: LinhaDesenho) -> tuple[Ponto, float, float, float] | None:
    """(centro, raio, ângulo inicial, varredura) em graus — atan2 nas
    coordenadas da faca (y pra baixo), a varredura com sinal."""
    if not e_arco(l):
        return None
    m = meio_do_arco(l)
    circulo = _circulo(inicio(l), m, fim(l))
    if circulo is None:
        return None
    centro, raio = circulo

    def ang(p: Ponto) -> float:
        return math.degrees(math.atan2(p[1] - centro[1], p[0] - centro[0]))

    a1, am, a2 = ang(inicio(l)), ang(m), ang(fim(l))
    anti = (a2 - a1) % 360.0
    varredura = anti if (am - a1) % 360.0 < anti else -(360.0 - anti)
    return centro, raio, a1, varredura


def pontos(l: LinhaDesenho, passo_graus: float = 4.0) -> list[Ponto]:
    """A linha como polilinha (reta: as 2 pontas; arco: um ponto a cada
    `passo_graus`, nunca menos de 4 trechos)."""
    dados = arco(l)
    if dados is None:
        return [inicio(l), fim(l)]
    centro, raio, a1, varredura = dados
    n = max(4, math.ceil(abs(varredura) / passo_graus))
    saida = []
    for k in range(n + 1):
        a = math.radians(a1 + varredura * k / n)
        saida.append((centro[0] + raio * math.cos(a), centro[1] + raio * math.sin(a)))
    saida[0], saida[-1] = inicio(l), fim(l)  # pontas exatas
    return saida


def comprimento(l: LinhaDesenho) -> float:
    dados = arco(l)
    if dados is None:
        return _dist(inicio(l), fim(l))
    return abs(math.radians(dados[3])) * dados[1]


def bojo_por_tres_pontos(a: Ponto, passando: Ponto, b: Ponto) -> float:
    """Bojo do arco de `a` a `b` que passa por `passando` (0 se alinhados)."""
    circulo = _circulo(a, passando, b)
    if circulo is None:
        return 0.0
    centro, _r = circulo
    linha = LinhaDesenho(a[0], a[1], b[0], b[1], None, 0.0)  # type: ignore[arg-type]

    def ang(p: Ponto) -> float:
        return math.degrees(math.atan2(p[1] - centro[1], p[0] - centro[0]))

    a1, ap, a2 = ang(a), ang(passando), ang(b)
    anti = (a2 - a1) % 360.0
    varredura = anti if (ap - a1) % 360.0 < anti else 360.0 - anti
    # Lado do arco em relação à corda: o mesmo lado do ponto de passagem.
    (nx, ny), _c = _normal(linha)
    lado = (passando[0] - (a[0] + b[0]) / 2) * nx + (passando[1] - (a[1] + b[1]) / 2) * ny
    return math.copysign(math.tan(math.radians(varredura) / 4), lado)


def distancia(p: Ponto, l: LinhaDesenho) -> float:
    pts = pontos(l)
    return min(_dist_segmento(p, a, b) for a, b in zip(pts, pts[1:]))


def _dist_segmento(p: Ponto, a: Ponto, b: Ponto) -> float:
    ab = _sub(b, a)
    c2 = ab[0] ** 2 + ab[1] ** 2
    if c2 < 1e-12:
        return _dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / c2))
    return _dist(p, (a[0] + ab[0] * t, a[1] + ab[1] * t))


def em_cubicas(l: LinhaDesenho) -> list[tuple[Ponto, Ponto, Ponto, Ponto]]:
    """Arco em Béziers cúbicas (até 90° cada), pra exportar como curva."""
    dados = arco(l)
    if dados is None:
        a, b = inicio(l), fim(l)
        return [(a, a, b, b)]
    centro, raio, a1, varredura = dados
    n = max(1, math.ceil(abs(varredura) / 90.0))
    passo = math.radians(varredura / n)
    k = 4.0 / 3.0 * math.tan(passo / 4)
    saida = []
    for i in range(n):
        t0 = math.radians(a1) + passo * i
        t1 = t0 + passo
        p0 = (centro[0] + raio * math.cos(t0), centro[1] + raio * math.sin(t0))
        p3 = (centro[0] + raio * math.cos(t1), centro[1] + raio * math.sin(t1))
        c1 = (p0[0] - k * raio * math.sin(t0), p0[1] + k * raio * math.cos(t0))
        c2 = (p3[0] + k * raio * math.sin(t1), p3[1] - k * raio * math.cos(t1))
        saida.append((p0, c1, c2, p3))
    return saida


# ── Ferramentas ───────────────────────────────────────────────────────


def linha_por_medida(origem: Ponto, comprimento_mm: float, angulo_graus: float, tipo) -> LinhaDesenho:
    """Linha a partir de `origem` com comprimento e ângulo digitados — ângulo
    como no papel: 0° pra direita, 90° pra CIMA (a faca tem y pra baixo)."""
    a = math.radians(angulo_graus)
    return LinhaDesenho(
        origem[0], origem[1], origem[0] + comprimento_mm * math.cos(a), origem[1] - comprimento_mm * math.sin(a), tipo
    )


def retangulo(a: Ponto, b: Ponto, tipo) -> list[LinhaDesenho]:
    x1, x2 = sorted((a[0], b[0]))
    y1, y2 = sorted((a[1], b[1]))
    return [
        LinhaDesenho(x1, y1, x2, y1, tipo),
        LinhaDesenho(x2, y1, x2, y2, tipo),
        LinhaDesenho(x2, y2, x1, y2, tipo),
        LinhaDesenho(x1, y2, x1, y1, tipo),
    ]


def paralela(l: LinhaDesenho, distancia_mm: float) -> LinhaDesenho:
    """Paralela a `distancia_mm` (positivo = lado da normal n da linha; no
    arco, pra fora do centro). O arco paralelo é concêntrico, mesmo ângulo."""
    dados = arco(l)
    if dados is None:
        (nx, ny), _c = _normal(l)
        d = distancia_mm
        return replace(l, x1=l.x1 + nx * d, y1=l.y1 + ny * d, x2=l.x2 + nx * d, y2=l.y2 + ny * d)
    centro, raio, _a1, _v = dados
    novo = max(0.01, raio + distancia_mm)
    fator = novo / raio

    def mover(p: Ponto) -> Ponto:
        return (centro[0] + (p[0] - centro[0]) * fator, centro[1] + (p[1] - centro[1]) * fator)

    (x1, y1), (x2, y2) = mover(inicio(l)), mover(fim(l))
    return replace(l, x1=x1, y1=y1, x2=x2, y2=y2)


def _cortes_na_reta(l: LinhaDesenho, outras: list[LinhaDesenho], infinita: bool) -> list[float]:
    """Parâmetros t (na reta de l, 0 = início, 1 = fim) onde ela cruza as
    outras linhas (arcos entram como polilinha)."""
    a, b = inicio(l), fim(l)
    r = _sub(b, a)
    ts = []
    for o in outras:
        pts = pontos(o)
        for c, d in zip(pts, pts[1:]):
            s = _sub(d, c)
            den = r[0] * s[1] - r[1] * s[0]
            if abs(den) < 1e-12:
                continue
            qp = _sub(c, a)
            t = (qp[0] * s[1] - qp[1] * s[0]) / den
            u = (qp[0] * r[1] - qp[1] * r[0]) / den
            if -1e-9 <= u <= 1 + 1e-9 and (infinita or -1e-9 <= t <= 1 + 1e-9):
                ts.append(t)
    return ts


def _parametro(l: LinhaDesenho, p: Ponto) -> float:
    a, b = inicio(l), fim(l)
    r = _sub(b, a)
    c2 = r[0] ** 2 + r[1] ** 2
    return 0.0 if c2 < 1e-12 else ((p[0] - a[0]) * r[0] + (p[1] - a[1]) * r[1]) / c2


def _no_parametro(l: LinhaDesenho, t: float) -> Ponto:
    return (l.x1 + (l.x2 - l.x1) * t, l.y1 + (l.y2 - l.y1) * t)


def aparar(linhas: list[LinhaDesenho], indice: int, clique: Ponto) -> list[LinhaDesenho] | None:
    """Tira o pedaço da linha `indice` entre as duas interseções em volta do
    clique (ou até a ponta). None se a linha não cruza nada ou é arco."""
    l = linhas[indice]
    if e_arco(l):
        return None
    outras = [o for k, o in enumerate(linhas) if k != indice]
    ts = sorted(t for t in _cortes_na_reta(l, outras, infinita=False) if 1e-6 < t < 1 - 1e-6)
    if not ts:
        return None
    tc = _parametro(l, clique)
    antes = max((t for t in ts if t < tc), default=0.0)
    depois = min((t for t in ts if t > tc), default=1.0)
    pedacos = []
    if antes > 1e-6:
        p = _no_parametro(l, antes)
        pedacos.append(replace(l, x2=p[0], y2=p[1]))
    if depois < 1 - 1e-6:
        p = _no_parametro(l, depois)
        pedacos.append(replace(l, x1=p[0], y1=p[1]))
    return linhas[:indice] + pedacos + linhas[indice + 1 :]


def estender(linhas: list[LinhaDesenho], indice: int, clique: Ponto) -> list[LinhaDesenho] | None:
    """Estica a ponta da linha mais perto do clique até a primeira linha que
    ela encontraria. None se não encontra nada (ou é arco)."""
    l = linhas[indice]
    if e_arco(l):
        return None
    outras = [o for k, o in enumerate(linhas) if k != indice]
    ts = _cortes_na_reta(l, outras, infinita=True)
    pela_ponta_final = _dist(clique, fim(l)) <= _dist(clique, inicio(l))
    if pela_ponta_final:
        alvo = min((t for t in ts if t > 1 + 1e-6), default=None)
        if alvo is None:
            return None
        p = _no_parametro(l, alvo)
        nova = replace(l, x2=p[0], y2=p[1])
    else:
        alvo = max((t for t in ts if t < -1e-6), default=None)
        if alvo is None:
            return None
        p = _no_parametro(l, alvo)
        nova = replace(l, x1=p[0], y1=p[1])
    return linhas[:indice] + [nova] + linhas[indice + 1 :]


def arredondar(linhas: list[LinhaDesenho], canto: Ponto, raio: float, tolerancia: float = 0.01) -> list[LinhaDesenho] | None:
    """Arredonda o canto onde duas RETAS se encontram (ponta em comum em
    `canto`): recua as duas e põe um arco tangente de `raio` no lugar. None
    se no canto não há exatamente duas retas ou o raio não cabe."""
    tocando = []
    for k, l in enumerate(linhas):
        if e_arco(l):
            continue
        if _dist(inicio(l), canto) <= tolerancia:
            tocando.append((k, 1))
        elif _dist(fim(l), canto) <= tolerancia:
            tocando.append((k, 2))
    if len(tocando) != 2:
        return None
    (i, qi), (j, qj) = tocando
    li, lj = linhas[i], linhas[j]
    outra_i = fim(li) if qi == 1 else inicio(li)
    outra_j = fim(lj) if qj == 1 else inicio(lj)
    p = (inicio(li) if qi == 1 else fim(li))
    u1 = _sub(outra_i, p)
    u2 = _sub(outra_j, p)
    n1, n2 = math.hypot(*u1), math.hypot(*u2)
    if n1 < _EPS or n2 < _EPS:
        return None
    u1, u2 = (u1[0] / n1, u1[1] / n1), (u2[0] / n2, u2[1] / n2)
    angulo = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
    if angulo < math.radians(1) or angulo > math.radians(179):
        return None  # retas alinhadas: não há canto
    recuo = raio / math.tan(angulo / 2)
    if recuo >= n1 - 1e-6 or recuo >= n2 - 1e-6:
        return None  # o raio não cabe nas retas
    t1 = (p[0] + u1[0] * recuo, p[1] + u1[1] * recuo)
    t2 = (p[0] + u2[0] * recuo, p[1] + u2[1] * recuo)
    bissetriz = (u1[0] + u2[0], u1[1] + u2[1])
    nb = math.hypot(*bissetriz)
    bissetriz = (bissetriz[0] / nb, bissetriz[1] / nb)
    centro_dist = raio / math.sin(angulo / 2)
    centro = (p[0] + bissetriz[0] * centro_dist, p[1] + bissetriz[1] * centro_dist)
    meio = (centro[0] - bissetriz[0] * raio, centro[1] - bissetriz[1] * raio)
    nova_i = replace(li, x1=t1[0], y1=t1[1]) if qi == 1 else replace(li, x2=t1[0], y2=t1[1])
    nova_j = replace(lj, x1=t2[0], y1=t2[1]) if qj == 1 else replace(lj, x2=t2[0], y2=t2[1])
    arco_novo = LinhaDesenho(t1[0], t1[1], t2[0], t2[1], li.tipo, bojo_por_tres_pontos(t1, meio, t2))
    saida = list(linhas)
    saida[i], saida[j] = nova_i, nova_j
    saida.append(arco_novo)
    return saida
