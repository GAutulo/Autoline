"""Dobra 3D de QUALQUER faca — o "Converter em 3D" do ArtiosCAD (ver
REFERENCIA_ARTIOSCAD_ESTRUTURA.md): as regiões fechadas entre as linhas são
as faces, os vincos entre duas faces são as dobradiças, uma face fica parada
(a base) e as outras giram em volta dela, 90° por padrão.

Sem nada de UI, mesmo padrão de `dobra3d.py` — e devolve o mesmo
`ModeloCaixa3D`, então a tela 3D desenha igual aos modelos prontos.

Passos:
1. Corta todas as linhas nos cruzamentos (inclusive "T" e sobreposições).
2. Tira as pontas soltas (um corte que entra na chapa e para não fecha face).
3. Acha as faces pelo grafo planar (semiarestas, sempre virando pro mesmo
   lado) e liga cada contorno solto (um furo, uma janela) à face em volta.
4. Decide o que é papelão e o que é vazio por paridade, a partir de fora:
   atravessar um CORTE troca, atravessar um VINCO não (vinco só existe entre
   papelão e papelão).
5. As faces de papelão viram painéis; os vincos entre dois painéis viram
   dobradiças; uma árvore a partir da base diz quem gira em volta de quem.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass

from . import geometria_faca
from .dobra3d import ModeloCaixa3D, PainelDobravel
from .models import LinhaDesenho, TipoLinha

# Tipos que dobram (o resto corta). Meio corte e dobra auxiliar também viram
# dobradiça — no papelão eles marcam por onde a chapa dobra.
TIPOS_DOBRA = {TipoLinha.VINCO, TipoLinha.MEIO_CORTE, TipoLinha.DOBRA}

_CASAS = 3  # pontos iguais até o milésimo de mm são o mesmo nó
_AREA_MINIMA_MM2 = 1.0
ANGULO_PADRAO = 90.0

Ponto = tuple[float, float]


def _chave(x: float, y: float) -> Ponto:
    return (round(x, _CASAS), round(y, _CASAS))


def _no_segmento(p: Ponto, a: Ponto, b: Ponto, tol: float = 1e-3) -> float | None:
    """Parâmetro t (0..1) de `p` sobre o segmento ab, se estiver nele."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    comprimento2 = dx * dx + dy * dy
    if comprimento2 < 1e-12:
        return None
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / comprimento2
    if t < -1e-9 or t > 1 + 1e-9:
        return None
    qx, qy = a[0] + dx * t, a[1] + dy * t
    if math.hypot(p[0] - qx, p[1] - qy) > tol:
        return None
    return min(1.0, max(0.0, t))


def _cruzamento(a: Ponto, b: Ponto, c: Ponto, d: Ponto) -> tuple[float, float] | None:
    """(t, u) do cruzamento próprio dos segmentos ab e cd, se houver."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12:
        return None
    qp = (c[0] - a[0], c[1] - a[1])
    t = (qp[0] * s[1] - qp[1] * s[0]) / den
    u = (qp[0] * r[1] - qp[1] * r[0]) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return t, u
    return None


@dataclass
class _Aresta:
    u: Ponto
    v: Ponto
    corte: bool
    origem: int  # índice da linha da faca de onde veio


def _arestas_planas(linhas: list[LinhaDesenho]) -> list[_Aresta]:
    # Arco vira polilinha fina (cada trecho lembra de qual linha veio).
    segmentos: list[tuple[Ponto, Ponto]] = []
    origem_de: list[int] = []
    for i, l in enumerate(linhas):
        pts = geometria_faca.pontos(l, 3.0)
        for a, b in zip(pts, pts[1:]):
            segmentos.append((a, b))
            origem_de.append(i)
    cortes_em: list[set[float]] = [{0.0, 1.0} for _ in segmentos]
    for i, (a, b) in enumerate(segmentos):
        for j in range(i + 1, len(segmentos)):
            c, d = segmentos[j]
            cruz = _cruzamento(a, b, c, d)
            if cruz is not None:
                cortes_em[i].add(cruz[0])
                cortes_em[j].add(cruz[1])
            # Pontas de um encostadas no meio do outro (T e sobreposição).
            for p, (k, outro) in ((c, (i, (a, b))), (d, (i, (a, b))), (a, (j, (c, d))), (b, (j, (c, d)))):
                t = _no_segmento(p, *outro)
                if t is not None:
                    cortes_em[k].add(t)
    arestas: dict[tuple[Ponto, Ponto], _Aresta] = {}
    for s_i, ((a, b), ts) in enumerate(zip(segmentos, cortes_em)):
        i = origem_de[s_i]
        pontos = [_chave(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in sorted(ts)]
        corte = linhas[i].tipo not in TIPOS_DOBRA
        for p, q in zip(pontos, pontos[1:]):
            if p == q:
                continue
            chave = (p, q) if p < q else (q, p)
            existente = arestas.get(chave)
            if existente is None:
                arestas[chave] = _Aresta(chave[0], chave[1], corte, i)
            elif corte and not existente.corte:
                arestas[chave] = _Aresta(chave[0], chave[1], True, i)  # corte vence vinco sobreposto
    # Pontas soltas não fecham face: tira até não sobrar nenhuma.
    lista = list(arestas.values())
    while True:
        grau: dict[Ponto, int] = defaultdict(int)
        for a in lista:
            grau[a.u] += 1
            grau[a.v] += 1
        restante = [a for a in lista if grau[a.u] > 1 and grau[a.v] > 1]
        if len(restante) == len(lista):
            return lista
        lista = restante


def _area(poligono: list[Ponto]) -> float:
    return 0.5 * sum(
        poligono[i][0] * poligono[(i + 1) % len(poligono)][1] - poligono[(i + 1) % len(poligono)][0] * poligono[i][1]
        for i in range(len(poligono))
    )


def _dentro(p: Ponto, poligono: list[Ponto]) -> bool:
    dentro = False
    n = len(poligono)
    for i in range(n):
        (x1, y1), (x2, y2) = poligono[i], poligono[(i + 1) % n]
        if (y1 > p[1]) != (y2 > p[1]):
            x = x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1)
            if x > p[0]:
                dentro = not dentro
    return dentro


def ponto_interno(poligono: list[Ponto], furos: list[list[Ponto]] = ()) -> Ponto:
    """Um ponto garantidamente dentro do polígono (e fora dos furos): o meio
    do trecho mais largo de uma reta horizontal que corta a face."""
    ys = sorted({p[1] for p in poligono})
    candidatas = [(ys[i] + ys[i + 1]) / 2 for i in range(len(ys) - 1)] or [ys[0]]
    melhor, maior = poligono[0], -1.0
    for y in candidatas:
        xs = []
        for contorno in [poligono, *furos]:
            n = len(contorno)
            for i in range(n):
                (x1, y1), (x2, y2) = contorno[i], contorno[(i + 1) % n]
                if (y1 > y) != (y2 > y):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            if xs[k + 1] - xs[k] > maior:
                maior, melhor = xs[k + 1] - xs[k], ((xs[k] + xs[k + 1]) / 2, y)
    return melhor


@dataclass
class Face:
    poligono: list[Ponto]
    furos: list[list[Ponto]]
    area: float


@dataclass
class ResultadoFaces:
    faces: list[Face]
    # (face a, face b, ponta 1, ponta 2, linha de origem) de cada vinco entre papelões
    dobradicas: list[tuple[int, int, Ponto, Ponto, int]]


def achar_faces(linhas: list[LinhaDesenho]) -> ResultadoFaces:
    arestas = _arestas_planas(linhas)
    if not arestas:
        return ResultadoFaces([], [])
    saidas: dict[Ponto, list[Ponto]] = defaultdict(list)
    tipo: dict[tuple[Ponto, Ponto], _Aresta] = {}
    for a in arestas:
        saidas[a.u].append(a.v)
        saidas[a.v].append(a.u)
        tipo[(a.u, a.v)] = tipo[(a.v, a.u)] = a
    for p, vizinhos in saidas.items():
        vizinhos.sort(key=lambda q: math.atan2(q[1] - p[1], q[0] - p[0]))

    face_de: dict[tuple[Ponto, Ponto], int] = {}
    ciclos: list[list[Ponto]] = []
    for u in saidas:
        for v in saidas[u]:
            if (u, v) in face_de:
                continue
            indice = len(ciclos)
            ciclo = []
            a, b = u, v
            while (a, b) not in face_de:
                face_de[(a, b)] = indice
                ciclo.append(a)
                vizinhos = saidas[b]
                k = vizinhos.index(a)
                a, b = b, vizinhos[(k - 1) % len(vizinhos)]  # próxima no sentido horário
            ciclos.append(ciclo)

    areas = [_area(c) for c in ciclos]
    # Com y pra baixo e esse giro, faces internas saem com área POSITIVA e o
    # contorno de fora de cada pedaço solto, negativa.
    externos = [i for i, a in enumerate(areas) if a < -1e-9]
    internos = [i for i, a in enumerate(areas) if a > 1e-9]
    externo_global = min(externos, key=lambda i: areas[i]) if externos else None
    # Contorno de fora de um pedaço solto dentro de outro (furo, janela):
    # pertence à face interna que o contém (a menor que contém um ponto dele).
    dono: dict[int, int] = {}
    for i in externos:
        if i == externo_global:
            continue
        contem = [j for j in internos if _dentro(_ponto_medio_de(ciclos[i]), ciclos[j]) and abs(areas[j]) > abs(areas[i])]
        if contem:
            dono[i] = min(contem, key=lambda j: abs(areas[j]))
        else:
            dono[i] = externo_global

    def raiz(i: int | None) -> int | None:
        while i in dono:
            i = dono[i]
        return i

    # Papelão ou vazio, em duas fases (a ordem de visita não pode decidir):
    # 1) só pelos CORTES, a partir de fora — atravessar um corte troca;
    # 2) quem só encosta nos outros por VINCO é papelão se algum vizinho de
    #    vinco for papelão (vinco só existe entre papelão e papelão). Um vinco
    #    desenhado atravessando uma fenda aberta não "puxa" o vazio pra dentro.
    vizinhas_corte: dict[int, set[int]] = defaultdict(set)
    vizinhas_vinco: dict[int, set[int]] = defaultdict(set)
    for (a, b), f in face_de.items():
        fa, fb = raiz(f), raiz(face_de[(b, a)])
        if fa != fb:
            (vizinhas_corte if tipo[(a, b)].corte else vizinhas_vinco)[fa].add(fb)
    papelao: dict[int, bool] = {externo_global: False}
    fila = deque([externo_global])
    while True:
        while fila:  # cortes primeiro: é a evidência mais forte
            f = fila.popleft()
            for g in vizinhas_corte[f]:
                if g not in papelao:
                    papelao[g] = not papelao[f]
                    fila.append(g)
        # Uma rodada de vincos, só a partir de quem JÁ é papelão; depois volta
        # pros cortes (assim a lasca de uma fenda vira vazio pelo corte antes
        # de algum vinco vizinho chamá-la de papelão).
        novos = [
            f
            for f in set(vizinhas_vinco) | set(vizinhas_corte)
            if f not in papelao and any(papelao.get(g) for g in vizinhas_vinco[f])
        ]
        if not novos:
            break
        for f in novos:
            papelao[f] = True
            fila.append(f)

    faces: list[Face] = []
    indice_face: dict[int, int] = {}
    for i in internos:
        if not papelao.get(i, False) or abs(areas[i]) < _AREA_MINIMA_MM2:
            continue
        furos = [list(ciclos[k]) for k, d in dono.items() if d == i]
        area = abs(areas[i]) - sum(abs(_area(f)) for f in furos)
        indice_face[i] = len(faces)
        faces.append(Face(list(ciclos[i]), furos, area))

    dobradicas: dict[tuple[int, int], list] = {}
    for (a, b), f in face_de.items():
        aresta = tipo[(a, b)]
        if aresta.corte:
            continue
        g = face_de[(b, a)]
        if f in indice_face and g in indice_face and indice_face[f] < indice_face[g]:
            par = (indice_face[f], indice_face[g])
            atual = dobradicas.get(par)
            comprimento = math.dist(a, b)
            if atual is None or comprimento > math.dist(atual[0], atual[1]):
                dobradicas[par] = [a, b, aresta.origem]
    # Junta os pedaços colineares de um mesmo vinco (cortado por um "T"):
    # a dobradiça é a reta inteira entre as duas faces.
    for (fa, fb), (a, b, origem) in list(dobradicas.items()):
        pontos = [a, b]
        for (p, q), f in face_de.items():
            if tipo[(p, q)].corte or {indice_face.get(f), indice_face.get(face_de[(q, p)])} != {fa, fb}:
                continue
            pontos.extend((p, q))
        direcao = (b[0] - a[0], b[1] - a[1])
        pontos.sort(key=lambda p: (p[0] - a[0]) * direcao[0] + (p[1] - a[1]) * direcao[1])
        dobradicas[(fa, fb)] = [pontos[0], pontos[-1], origem]
    return ResultadoFaces(faces, [(fa, fb, a, b, o) for (fa, fb), (a, b, o) in dobradicas.items()])


def _ponto_medio_de(ciclo: list[Ponto]) -> Ponto:
    a, b = ciclo[0], ciclo[1 % len(ciclo)]
    return ((a[0] + b[0]) / 2 + 1e-4, (a[1] + b[1]) / 2 + 1e-4)


def _painel_de_referencia(ponto: Ponto, referencia: ModeloCaixa3D) -> PainelDobravel | None:
    """Painel do modelo calculado onde cai o ponto (o menor que o contém)."""
    candidatos = []
    for p in referencia.paineis:
        if p.poligono:
            dentro = _dentro(ponto, list(p.poligono))
        else:
            dentro = p.x1 - 1e-6 <= ponto[0] <= p.x2 + 1e-6 and p.y1 - 1e-6 <= ponto[1] <= p.y2 + 1e-6
        if dentro:
            candidatos.append(p)
    return min(candidatos, key=lambda p: (p.x2 - p.x1) * (p.y2 - p.y1), default=None)


def _dobra_do_estilo(a: Ponto, b: Ponto, dobras: list):
    """O vinco do estilo que contém a dobradiça a–b (colinear e cobrindo)."""
    for d in dobras:
        dx, dy = d.x2 - d.x1, d.y2 - d.y1
        n = math.hypot(dx, dy)
        if n < 1e-9:
            continue
        ok = True
        for px, py in (a, b):
            # distância à reta e posição ao longo do vinco
            dist = abs((px - d.x1) * dy - (py - d.y1) * dx) / n
            t = ((px - d.x1) * dx + (py - d.y1) * dy) / (n * n)
            if dist > 0.05 or not (-1e-3 <= t <= 1 + 1e-3):
                ok = False
                break
        if ok:
            return d
    return None


def montar_modelo_generico(
    linhas: list[LinhaDesenho],
    angulos: dict[int, float] | None = None,
    base: int | None = None,
    descricao: str = "Faca livre",
    referencia: ModeloCaixa3D | None = None,
    dobras_estilo: list | None = None,
    ponto_base: Ponto | None = None,
) -> ModeloCaixa3D:
    """`angulos`: ângulo por índice de linha da faca (padrão 90°; negativo
    dobra pro outro lado; 0 deixa plano). `base`: índice da face base
    (padrão: a que tem mais vincos; empate, a maior).

    `referencia`: o modelo calculado do tipo de caixa de onde a faca veio.
    Mexer na faca (o formato de uma aba, um corte) não muda o fechamento:
    cada face herda do painel onde está a face base, o ângulo de cada dobra
    e a ordem de montagem. Vinco novo (sem par no modelo) dobra 90°; aba
    que ficou solta por um corte não aparece.

    `dobras_estilo` (ver `estilos.DobraDoEstilo`): ângulo e janela de
    montagem de cada vinco de um estilo paramétrico, casados pela
    GEOMETRIA (o vinco da faca que está em cima do vinco do estilo), então
    continuam valendo depois de editar a faca. `ponto_base`: ponto dentro
    da face que fica parada."""
    resultado = achar_faces(linhas)
    faces = resultado.faces
    if not faces:
        return ModeloCaixa3D(descricao=descricao)
    angulos = angulos or {}
    vizinhos: dict[int, list[tuple[int, Ponto, Ponto, int]]] = defaultdict(list)
    for fa, fb, a, b, origem in resultado.dobradicas:
        vizinhos[fa].append((fb, a, b, origem))
        vizinhos[fb].append((fa, a, b, origem))

    ref_de: dict[int, PainelDobravel] = {}
    if referencia is not None and referencia.paineis:
        for i, face in enumerate(faces):
            achado = _painel_de_referencia(ponto_interno(face.poligono, face.furos), referencia)
            if achado is not None:
                ref_de[i] = achado

    def herdado(f: int, g: int) -> PainelDobravel | None:
        """Painel filho do modelo calculado na dobra entre as faces f e g
        (a dobra existe lá: um é pai do outro)."""
        pf, pg = ref_de.get(f), ref_de.get(g)
        if pf is None or pg is None or pf is pg:
            return None
        if pg.pai == pf.id:
            return pg
        if pf.pai == pg.id:
            return pf
        return None

    if (base is None or not (0 <= base < len(faces))) and ponto_base is not None:
        dentro = [
            i for i, f in enumerate(faces)
            if _dentro(ponto_base, f.poligono) and not any(_dentro(ponto_base, furo) for furo in f.furos)
        ]
        if dentro:
            base = dentro[0]
    if base is None or not (0 <= base < len(faces)):
        raiz_ref = [i for i, p in ref_de.items() if p.pai is None]
        if raiz_ref:
            base = max(raiz_ref, key=lambda i: faces[i].area)
        else:
            # A face com mais vincos é a mais "central" da faca (o fundo da
            # cruz de um cubo, a frente de uma maleta); empate: a maior.
            base = max(range(len(faces)), key=lambda i: (len(vizinhos[i]), faces[i].area))
    # Árvore das dobradiças a partir da base. Dobras que existem no modelo
    # calculado vêm primeiro (custo 0), pra árvore seguir a da caixa; um
    # vinco novo que divide um painel também (a parte nova dobra nele).
    pai: dict[int, tuple[int, Ponto, Ponto, int]] = {}
    profundidade = {base: 0}
    custo = {base: 0}
    fila = deque([base])
    while fila:
        f = fila.popleft()
        for g, a, b, origem in sorted(vizinhos[f], key=lambda item: item[0]):
            mesmo_painel = ref_de.get(f) is not None and ref_de.get(f) is ref_de.get(g)
            c = custo[f] + (0 if mesmo_painel or herdado(f, g) is not None else 1)
            if g not in custo or c < custo[g]:
                custo[g] = c
                profundidade[g] = profundidade[f] + 1
                pai[g] = (f, a, b, origem)
                if c == custo[f]:
                    fila.appendleft(g)
                else:
                    fila.append(g)
    maior = max(profundidade.values()) or 1

    paineis = []
    for i, face in enumerate(faces):
        if i not in profundidade:
            continue  # pedaço solto, sem vinco com o resto: fica de fora
        xs = [p[0] for p in face.poligono]
        ys = [p[1] for p in face.poligono]
        comum = dict(
            id=f"face_{i}",
            nome="Face base" if i == base else f"Face {i + 1}",
            x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys),
            poligono=tuple(face.poligono),
            furos=tuple(tuple(f) for f in face.furos),
            ponto_interno=ponto_interno(face.poligono, face.furos),
        )
        if i == base:
            paineis.append(PainelDobravel(**comum))
            continue
        f_pai, a, b, origem = pai[i]
        d = profundidade[i]
        modelo_ref = herdado(f_pai, i)
        do_estilo = _dobra_do_estilo(a, b, dobras_estilo) if dobras_estilo else None
        if do_estilo is not None:
            angulo, inicio, fim = do_estilo.angulo, do_estilo.inicio, do_estilo.fim
        elif modelo_ref is not None:
            angulo, inicio, fim = modelo_ref.angulo_fechado, modelo_ref.inicio, modelo_ref.fim
        else:
            angulo, inicio, fim = ANGULO_PADRAO, (d - 1) / maior, d / maior
        # Quem fica por cima de quem na caixa fechada (abas sobrepostas).
        camada = ref_de[i].camada if i in ref_de else 0
        paineis.append(
            PainelDobravel(
                **comum,
                pai=f"face_{f_pai}",
                dobradica=(a, b),
                angulo_fechado=angulos.get(origem, angulo),
                inicio=inicio,
                fim=fim,
                linha_origem=origem,
                camada=camada,
            )
        )
    # Ordem dos painéis: pais antes dos filhos (posicionar() resolve, mas
    # assim a lista sai legível).
    paineis.sort(key=lambda p: profundidade[int(p.id.split("_")[1])])
    if ref_de.get(base) is not None and ref_de[base].pai is None:
        # Mesma base do modelo calculado: mesma câmera da caixa.
        return ModeloCaixa3D(
            paineis=paineis,
            cima=referencia.cima,
            frente=referencia.frente,
            pitch_planificada=referencia.pitch_planificada,
            descricao=descricao,
            solido_fechado=referencia.solido_fechado,
        )
    return ModeloCaixa3D(
        paineis=paineis,
        cima=(0.0, -1.0, 0.0),  # "cima" da faca na tela
        frente=(0.0, 0.0, -1.0),  # a face base continua olhando pra quem vê, pelo lado impresso
        pitch_planificada=0.0,
        descricao=descricao,
        solido_fechado=False,  # faca livre pode ser aberta (bandeja, display): lado de dentro aparece
    )
