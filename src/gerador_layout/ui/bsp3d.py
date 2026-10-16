"""Ordem de pintura exata pro 3D: árvore BSP (binary space partitioning).

A pintura por profundidade (ordenar pedaços pela distância do centro) erra
sempre que duas superfícies estão perto uma da outra — aba de cola por dentro
da parede, abas sobrepostas, a borda do papelão na quina. A BSP não chuta:
cada nó é o plano de um polígono; o que está de um lado dele é desenhado
antes do que está do outro, conforme o lado em que o olho está, e polígono
que cruza o plano é cortado em dois. A árvore depende só da geometria (não da
câmera): girar a vista só percorre a árvore de novo.

Polígonos no MESMO plano (aba colada na parede, sem espessura) vão juntos no
nó e são pintados pela `prioridade` (quem está por cima por último).

Cada polígono carrega, além dos pontos no mundo, as coordenadas "locais" de
cada vértice (na superfície de origem), interpoladas junto quando corta — o
desenho usa isso pra saber que pedaço da superfície é.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Vetor = tuple[float, float, float]

_EPS = 1e-4  # mm: abaixo disso o ponto está NO plano


def _sub(a: Vetor, b: Vetor) -> Vetor:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vetor, b: Vetor) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vetor, b: Vetor) -> Vetor:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


@dataclass
class Poligono:
    pontos: list[Vetor]  # mundo, convexo ou não (só precisa ser plano)
    locais: list[tuple]  # mesmas posições na superfície de origem
    superficie: object  # quem desenha (a vista sabe o que é)
    normal: Vetor = (0.0, 0.0, 1.0)  # unitária, lado que "vê" (pintado só se o olho estiver desse lado)
    prioridade: float = 0.0  # empate no mesmo plano: maior pinta por último
    inteiro: bool = True  # False = pedaço de um polígono cortado pela árvore
    d: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self.d = _dot(self.normal, self.pontos[0])

    def area(self) -> float:
        total = (0.0, 0.0, 0.0)
        p0 = self.pontos[0]
        for a, b in zip(self.pontos[1:], self.pontos[2:]):
            c = _cross(_sub(a, p0), _sub(b, p0))
            total = (total[0] + c[0], total[1] + c[1], total[2] + c[2])
        return 0.5 * abs(_dot(total, self.normal))

    def ve(self, olho: Vetor) -> bool:
        return _dot(self.normal, olho) - self.d > 0.0


@dataclass
class _No:
    normal: Vetor
    d: float
    no_plano: list[Poligono]
    frente: "_No | None" = None
    tras: "_No | None" = None


def _dividir(p: Poligono, normal: Vetor, d: float):
    """(frente, trás, no_plano) de `p` em relação ao plano normal·x = d."""
    dist = [_dot(normal, q) - d for q in p.pontos]
    if all(abs(x) <= _EPS for x in dist):
        return None, None, p
    if all(x >= -_EPS for x in dist):
        return p, None, None
    if all(x <= _EPS for x in dist):
        return None, p, None
    f_pts, f_loc, t_pts, t_loc = [], [], [], []
    n = len(p.pontos)
    for i in range(n):
        j = (i + 1) % n
        a, b = p.pontos[i], p.pontos[j]
        la, lb = p.locais[i], p.locais[j]
        da, db = dist[i], dist[j]
        if da >= -_EPS:
            f_pts.append(a)
            f_loc.append(la)
        if da <= _EPS:
            t_pts.append(a)
            t_loc.append(la)
        if (da > _EPS and db < -_EPS) or (da < -_EPS and db > _EPS):
            t = da / (da - db)
            q, lq = _lerp(a, b, t), _lerp(la, lb, t)
            f_pts.append(q)
            f_loc.append(lq)
            t_pts.append(q)
            t_loc.append(lq)
    frente = Poligono(f_pts, f_loc, p.superficie, p.normal, p.prioridade, False) if len(f_pts) >= 3 else None
    tras = Poligono(t_pts, t_loc, p.superficie, p.normal, p.prioridade, False) if len(t_pts) >= 3 else None
    return frente, tras, None


def construir(poligonos: list[Poligono]) -> _No | None:
    """Árvore BSP. Os maiores viram plano primeiro (menos cortes: as faces
    grandes da caixa separam bem o resto)."""
    lista = sorted(poligonos, key=lambda p: -p.area())
    return _construir(lista)


def _construir(lista: list[Poligono]) -> _No | None:
    if not lista:
        return None
    raiz = lista[0]
    no = _No(raiz.normal, raiz.d, [raiz])
    frente, tras = [], []
    for p in lista[1:]:
        f, t, plano = _dividir(p, raiz.normal, raiz.d)
        if plano is not None:
            no.no_plano.append(plano)
        if f is not None:
            frente.append(f)
        if t is not None:
            tras.append(t)
    no.frente = _construir(frente)
    no.tras = _construir(tras)
    return no


def de_tras_pra_frente(no: _No | None, olho: Vetor, saida: list[Poligono]) -> list[Poligono]:
    """Os polígonos VISÍVEIS (virados pro olho) na ordem de pintura."""
    pilha = [(no, False)]
    while pilha:
        atual, expandido = pilha.pop()
        if atual is None:
            continue
        if expandido:
            visiveis = [p for p in atual.no_plano if p.ve(olho)]
            visiveis.sort(key=lambda p: p.prioridade)
            saida.extend(visiveis)
            continue
        olho_na_frente = _dot(atual.normal, olho) - atual.d >= 0.0
        perto, longe = (atual.frente, atual.tras) if olho_na_frente else (atual.tras, atual.frente)
        # Pilha: o que sai primeiro é pintado primeiro → longe, nó, perto.
        pilha.append((perto, False))
        pilha.append((atual, True))
        pilha.append((longe, False))
    return saida
