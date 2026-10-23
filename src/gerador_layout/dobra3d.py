"""Dobra 3D da caixa — transforma a dieline plana num sólido montado.

Não depende de nada de UI, mesmo padrão de `layout_service.py` e
`paineis.py`: recebe os `segmentos_impressora`/`segmentos_riscador`
efetivos (os mesmos números usados pra desenhar a faca) e devolve cada
painel da chapa como um retângulo rígido pendurado no painel vizinho por
uma dobradiça (o vinco). `posicionar(modelo, t)` aplica as dobras:

  t = 0 → chapa plana, idêntica à dieline (plano z = 0, X/Y em mm)
  t = 1 → caixa fechada

Convenção das dobras: o lado +z da chapa plana é o lado de DENTRO da
caixa (o lado impresso fica virado pra -z). Toda dobra gira o painel
filho pra +z do pai, então a caixa sempre fecha pro mesmo lado e a face
impressa termina pra fora.

Cada dobra tem uma janela de tempo (`inicio`, `fim`) dentro de 0..1 —
é o que dá a sequência de montagem de verdade (primeiro as paredes,
depois as abas menores, por último as maiores) em vez de tudo dobrar
junto.

Abas que no mundo real ficam sobrepostas (aba de cola sobre o verso,
abas menores por baixo das maiores) fecham alguns graus além de 90°,
inclinando pra dentro da caixa — sem isso duas faces ficariam no mesmo
plano exato e a pintura por profundidade não saberia qual vem na frente.

Simplificações deliberadas: a espessura do papelão e a folga do corte
serra são ignoradas, a aba de cola é tratada como retângulo (sem os
chanfros) e, no envoltório, só entram os painéis que existem nas quatro
variantes (mesmo critério de `paineis.py`); os recortes de canto que
mudam entre "com corte" e "sem corte" ficam de fora.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from .models import TIPOS_MALETA as _TIPOS_MALETA
from .models import TIPOS_MEIA_CAIXA as _TIPOS_MEIA
from .models import TIPOS_TRANSPASSADA as _TIPOS_TRANSPASSADA
from .models import TipoCaixa

Vetor = tuple[float, float, float]

_TIPOS_FECHAMENTO_NORMAL = {
    TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_SEM_CORTE,
    TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE,
}

# Quanto uma aba que fica por baixo de outra passa de 90° (ver docstring).
_FOLGA_ABA_GRAUS = 3.0


# ── Álgebra mínima (sem numpy: são poucas dezenas de painéis) ──────────


def _sub(a: Vetor, b: Vetor) -> Vetor:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _soma(a: Vetor, b: Vetor) -> Vetor:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _escala(a: Vetor, k: float) -> Vetor:
    return (a[0] * k, a[1] * k, a[2] * k)


def produto_escalar(a: Vetor, b: Vetor) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def produto_vetorial(a: Vetor, b: Vetor) -> Vetor:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def normalizar(a: Vetor) -> Vetor:
    n = math.sqrt(produto_escalar(a, a))
    return (0.0, 0.0, 0.0) if n == 0 else (a[0] / n, a[1] / n, a[2] / n)


Matriz = tuple[Vetor, Vetor, Vetor]  # linhas


def _mat_vet(m: Matriz, v: Vetor) -> Vetor:
    return (produto_escalar(m[0], v), produto_escalar(m[1], v), produto_escalar(m[2], v))


def _mat_mat(a: Matriz, b: Matriz) -> Matriz:
    colunas = [(b[0][j], b[1][j], b[2][j]) for j in range(3)]
    return tuple(tuple(produto_escalar(a[i], colunas[j]) for j in range(3)) for i in range(3))  # type: ignore[return-value]


_IDENTIDADE: Matriz = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _rotacao_eixo(eixo: Vetor, angulo_rad: float) -> Matriz:
    x, y, z = normalizar(eixo)
    c, s = math.cos(angulo_rad), math.sin(angulo_rad)
    k = 1.0 - c
    return (
        (c + x * x * k, x * y * k - z * s, x * z * k + y * s),
        (y * x * k + z * s, c + y * y * k, y * z * k - x * s),
        (z * x * k - y * s, z * y * k + x * s, c + z * z * k),
    )


@dataclass(frozen=True)
class Transformacao:
    """Transformação rígida p → R·p + t."""

    r: Matriz = _IDENTIDADE
    t: Vetor = (0.0, 0.0, 0.0)

    def aplicar(self, p: Vetor) -> Vetor:
        return _soma(_mat_vet(self.r, p), self.t)

    def girar_vetor(self, v: Vetor) -> Vetor:
        return _mat_vet(self.r, v)

    def compor(self, interna: "Transformacao") -> "Transformacao":
        """self ∘ interna (aplica `interna` primeiro)."""
        return Transformacao(_mat_mat(self.r, interna.r), _soma(_mat_vet(self.r, interna.t), self.t))


def _rotacao_em_torno(ponto: Vetor, eixo: Vetor, angulo_rad: float) -> Transformacao:
    r = _rotacao_eixo(eixo, angulo_rad)
    return Transformacao(r, _sub(ponto, _mat_vet(r, ponto)))


# ── Modelo ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PainelDobravel:
    """Um retângulo da chapa (coordenadas da dieline, em mm) e a dobra
    que o liga ao painel pai. O painel raiz (`pai is None`) não se mexe."""

    id: str
    nome: str
    x1: float
    y1: float
    x2: float
    y2: float
    pai: str | None = None
    # Dobradiça: dois pontos sobre a aresta compartilhada com o pai.
    dobradica: tuple[tuple[float, float], tuple[float, float]] | None = None
    angulo_fechado: float = 90.0  # graus
    inicio: float = 0.0
    fim: float = 1.0
    # Quantas camadas de papelão ficam por cima deste painel na caixa
    # fechada (0 = face externa). A pintura por profundidade usa isso pra
    # não deixar uma aba de baixo vazar por cima da face que a cobre.
    camada: int = 0
    # Faces que não são retângulo (dobra genérica, ver `dobra_generica.py`):
    # o contorno real, os furos e um ponto garantidamente dentro. Sem isso
    # o painel é o retângulo x1..x2 × y1..y2.
    poligono: tuple[tuple[float, float], ...] | None = None
    furos: tuple[tuple[tuple[float, float], ...], ...] = ()
    ponto_interno: tuple[float, float] | None = None
    linha_origem: int | None = None  # índice da linha da faca que é a dobradiça
    # Painel que só existe no 3D (a outra metade da meia caixa, fora da faca):
    # mostra a arte do painel `arte_de`, deslocada `arte_dx` mm na chapa.
    arte_de: str | None = None
    arte_dx: float = 0.0

    @property
    def cantos(self) -> list[tuple[float, float]]:
        if self.poligono is not None:
            return list(self.poligono)
        return [(self.x1, self.y1), (self.x2, self.y1), (self.x2, self.y2), (self.x1, self.y2)]


@dataclass
class ModeloCaixa3D:
    paineis: list[PainelDobravel] = field(default_factory=list)
    # Referências da caixa montada (no espaço do mundo), usadas pela
    # câmera: `cima` aponta pra tampa, `frente` é a normal externa da
    # face tratada como frente.
    cima: Vetor = (0.0, -1.0, 0.0)
    frente: Vetor = (0.0, 0.0, -1.0)
    # Pitch da câmera (graus, em relação a `cima`) que mostra a chapa
    # plana de frente, pelo lado impresso — ver `ui/visualizacao_3d.py`.
    pitch_planificada: float = 0.0
    descricao: str = ""
    # Caixa fechada vira sólido (lado de dentro nunca aparece montada). Faca
    # livre pode ser aberta (bandeja, display), então desliga isso.
    solido_fechado: bool = True

    @property
    def vazio(self) -> bool:
        return not self.paineis


@dataclass(frozen=True)
class PainelPosicionado:
    painel: PainelDobravel
    transformacao: Transformacao

    def ponto(self, x: float, y: float) -> Vetor:
        return self.transformacao.aplicar((x, y, 0.0))

    @property
    def normal_externa(self) -> Vetor:
        """Normal do lado impresso (o lado -z da chapa plana)."""
        return self.transformacao.girar_vetor((0.0, 0.0, -1.0))


def _suavizar(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def posicionar(modelo: ModeloCaixa3D, t: float) -> list[PainelPosicionado]:
    """Posição de cada painel com a montagem em `t` (0 = plana, 1 = fechada)."""
    por_id = {p.id: p for p in modelo.paineis}
    transformacoes: dict[str, Transformacao] = {}

    def resolver(painel: PainelDobravel) -> Transformacao:
        if painel.id in transformacoes:
            return transformacoes[painel.id]
        if painel.pai is None or painel.dobradica is None:
            tr = Transformacao()
        else:
            pai = resolver(por_id[painel.pai])
            janela = max(painel.fim - painel.inicio, 1e-9)
            fracao = _suavizar((t - painel.inicio) / janela)
            angulo = math.radians(painel.angulo_fechado) * fracao
            (ax, ay), (bx, by) = painel.dobradica
            a: Vetor = (ax, ay, 0.0)
            eixo = _eixo_para_cima(a, (bx, by, 0.0), painel)
            tr = pai.compor(_rotacao_em_torno(a, eixo, angulo))
        transformacoes[painel.id] = tr
        return tr

    return [PainelPosicionado(p, resolver(p)) for p in modelo.paineis]


def _eixo_para_cima(a: Vetor, b: Vetor, painel: PainelDobravel) -> Vetor:
    """Orienta o eixo da dobradiça de modo que um ângulo positivo leve o
    painel pra +z (regra da mão direita), seja qual for o lado do pai em
    que ele está."""
    d = normalizar(_sub(b, a))
    if painel.ponto_interno is not None:
        # Face não retangular: o centro da caixa envolvente pode cair fora
        # dela (do outro lado da dobradiça); o ponto interno nunca cai.
        centro: Vetor = (painel.ponto_interno[0], painel.ponto_interno[1], 0.0)
    else:
        centro = ((painel.x1 + painel.x2) / 2.0, (painel.y1 + painel.y2) / 2.0, 0.0)
    rel = _sub(centro, a)
    radial = _sub(rel, _escala(d, produto_escalar(rel, d)))
    return d if produto_vetorial(d, radial)[2] >= 0 else _escala(d, -1.0)


def caixa_envolvente(posicionados: list[PainelPosicionado]) -> tuple[Vetor, Vetor]:
    """(mínimo, máximo) de todos os cantos — usado pra enquadrar a câmera."""
    pontos = [pp.ponto(x, y) for pp in posicionados for (x, y) in pp.painel.cantos]
    if not pontos:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return (
        (min(p[0] for p in pontos), min(p[1] for p in pontos), min(p[2] for p in pontos)),
        (max(p[0] for p in pontos), max(p[1] for p in pontos), max(p[2] for p in pontos)),
    )


# ── Construção por tipo de caixa ──────────────────────────────────────


def _bordas(segmentos: list[float]) -> list[float]:
    bordas = [0.0]
    for s in segmentos:
        bordas.append(bordas[-1] + s)
    return bordas


def montar_modelo(
    tipo: TipoCaixa, segmentos_impressora: list[float], segmentos_riscador: list[float]
) -> ModeloCaixa3D:
    """Recebe os segmentos efetivos de `LayoutCaixa` (com os padrões já
    aplicados) — os mesmos que desenham a faca."""
    if any(s <= 0 for s in segmentos_impressora + segmentos_riscador):
        return ModeloCaixa3D()
    if tipo == TipoCaixa.ENVOLTORIO_CAPA:
        return _modelo_capa(segmentos_impressora, segmentos_riscador)
    if tipo in _TIPOS_MALETA:
        return _modelo_maleta(tipo, segmentos_impressora, segmentos_riscador)
    return _modelo_envoltorio(tipo, segmentos_impressora, segmentos_riscador)


def _vertical(x: float, y1: float, y2: float) -> tuple[tuple[float, float], tuple[float, float]]:
    return ((x, y1), (x, y2))


def _horizontal(y: float, x1: float, x2: float) -> tuple[tuple[float, float], tuple[float, float]]:
    return ((x1, y), (x2, y))


def _modelo_maleta(tipo: TipoCaixa, imp: list[float], ris: list[float]) -> ModeloCaixa3D:
    # Impressora (X): Aba | L | C | L | C    Riscador (Y): Sup | A | Inf
    xs, ys = _bordas(imp), _bordas(ris)
    meia = tipo in _TIPOS_MEIA
    if len(xs) < (4 if meia else 6) or len(ys) < 4:
        return ModeloCaixa3D()
    if meia:
        # Meia caixa: no 3D ela aparece INTEIRA (a outra metade é igual: mesma
        # L e C, mesma arte) — só o modelo ganha a metade, a faca não.
        x0, x1, x2, x3 = xs[:4]
        x4 = x3 + (x2 - x1)
        x5 = x4 + (x3 - x2)
    else:
        x0, x1, x2, x3, x4, x5 = xs[:6]
    y0, y1, y2, y3 = ys[:4]
    transpassada = tipo in _TIPOS_TRANSPASSADA
    folga = _FOLGA_ABA_GRAUS

    paineis = [
        PainelDobravel("frente", "Frente", x2, y1, x3, y2),
        PainelDobravel("lateral1", "Lateral 1", x1, y1, x2, y2, "frente", _vertical(x2, y1, y2), 90.0, 0.0, 0.40),
        # A aba de cola fecha por dentro do verso.
        PainelDobravel(
            "aba_cola", "Aba de cola", x0, y1, x1, y2, "lateral1", _vertical(x1, y1, y2),
            90.0 + folga, 0.20, 0.50, camada=1,
        ),
        PainelDobravel("lateral2", "Lateral 2", x3, y1, x4, y2, "frente", _vertical(x3, y1, y2), 90.0, 0.0, 0.40),
        PainelDobravel("verso", "Verso", x4, y1, x5, y2, "lateral2", _vertical(x4, y1, y2), 90.0, 0.10, 0.48),
    ]

    # Abas de fundo (riscador inferior) e de tampa (superior): as menores
    # (nas laterais) dobram antes e ficam por baixo das maiores (frente e
    # verso). Na transpassada as maiores se sobrepõem por inteiro, então a
    # do verso fecha primeiro e fica por dentro da da frente.
    colunas = [
        ("lateral1", "Lateral 1", x1, x2, False),
        ("frente", "Frente", x2, x3, True),
        ("lateral2", "Lateral 2", x3, x4, False),
        ("verso", "Verso", x4, x5, True),
    ]
    for lado, y_aba1, y_aba2, y_dobra, base in (
        ("fundo", y2, y3, y2, 0.50),
        ("tampa", y0, y1, y1, 0.75),
    ):
        for pai, nome_pai, xa, xb, maior in colunas:
            if maior:
                por_dentro = transpassada and pai == "verso"
                angulo = 90.0 + (folga if por_dentro else 0.0)
                camada = 1 if por_dentro else 0
                inicio, fim = (base + 0.10, base + 0.20) if pai == "verso" else (base + 0.15, base + 0.25)
            else:
                angulo = 90.0 + 2 * folga
                camada = 2
                inicio, fim = base, base + 0.12
            paineis.append(
                PainelDobravel(
                    f"{lado}_{pai}",
                    f"Aba de {lado} — {nome_pai}",
                    xa, y_aba1, xb, y_aba2,
                    pai, _horizontal(y_dobra, xa, xb), angulo, inicio, fim, camada,
                )
            )

    if meia:
        # A metade que só existe no 3D leva a arte da metade desenhada.
        copia = {"lateral2": ("lateral1", x3 - x1), "verso": ("frente", x4 - x2)}
        for lado in ("fundo", "tampa"):
            copia[f"{lado}_lateral2"] = (f"{lado}_lateral1", x3 - x1)
            copia[f"{lado}_verso"] = (f"{lado}_frente", x4 - x2)
        paineis = [replace(p, arte_de=copia[p.id][0], arte_dx=copia[p.id][1]) if p.id in copia else p for p in paineis]

    return ModeloCaixa3D(
        paineis=paineis,
        cima=(0.0, -1.0, 0.0),  # o riscador superior vira a tampa
        frente=(0.0, 0.0, -1.0),  # a frente não se mexe: segue virada pro lado impresso
        pitch_planificada=0.0,
        descricao=("Maleta transpassada" if transpassada else "Maleta normal") + (" — meia caixa" if meia else ""),
    )


def _modelo_capa(imp: list[float], ris: list[float]) -> ModeloCaixa3D:
    # Impressora (X): A | C | A    Riscador (Y): A | L | A — bandeja sem tampa.
    xs, ys = _bordas(imp), _bordas(ris)
    if len(xs) < 4 or len(ys) < 4:
        return ModeloCaixa3D()
    x0, x1, x2, x3 = xs[:4]
    y0, y1, y2, y3 = ys[:4]
    folga = _FOLGA_ABA_GRAUS
    paineis = [
        PainelDobravel("centro", "Centro", x1, y1, x2, y2),
        PainelDobravel("lateral1", "Lateral 1", x0, y1, x1, y2, "centro", _vertical(x1, y1, y2), 90.0, 0.0, 0.5),
        PainelDobravel("lateral2", "Lateral 2", x2, y1, x3, y2, "centro", _vertical(x2, y1, y2), 90.0, 0.0, 0.5),
        PainelDobravel("parede_sup", "Parede superior", x1, y0, x2, y1, "centro", _horizontal(y1, x1, x2), 90.0, 0.3, 1.0),
        PainelDobravel("parede_inf", "Parede inferior", x1, y2, x2, y3, "centro", _horizontal(y2, x1, x2), 90.0, 0.3, 1.0),
        # Cantos presos nas laterais, fecham por dentro das paredes.
        PainelDobravel("canto_1s", "Canto", x0, y0, x1, y1, "lateral1", _horizontal(y1, x0, x1), 90.0 + folga, 0.0, 0.5, camada=1),
        PainelDobravel("canto_1i", "Canto", x0, y2, x1, y3, "lateral1", _horizontal(y2, x0, x1), 90.0 + folga, 0.0, 0.5, camada=1),
        PainelDobravel("canto_2s", "Canto", x2, y0, x3, y1, "lateral2", _horizontal(y1, x2, x3), 90.0 + folga, 0.0, 0.5, camada=1),
        PainelDobravel("canto_2i", "Canto", x2, y2, x3, y3, "lateral2", _horizontal(y2, x2, x3), 90.0 + folga, 0.0, 0.5, camada=1),
    ]
    return ModeloCaixa3D(
        paineis=paineis,
        cima=(0.0, 0.0, 1.0),
        frente=(0.0, -1.0, 0.0),
        pitch_planificada=-90.0,
        descricao="Envoltório capa (bandeja)",
        solido_fechado=False,  # aberta: o fundo de dentro aparece
    )


def _modelo_envoltorio(tipo: TipoCaixa, imp: list[float], ris: list[float]) -> ModeloCaixa3D:
    # Impressora (X): Aba | A | C | A | Aba    Riscador (Y): Sup | A | L | A | Inf
    xs, ys = _bordas(imp), _bordas(ris)
    if len(xs) < 6 or len(ys) < 6:
        return ModeloCaixa3D()
    x0, x1, x2, x3, x4, x5 = xs[:6]
    y0, y1, y2, y3, y4, y5 = ys[:6]
    fechamento_normal = tipo in _TIPOS_FECHAMENTO_NORMAL
    folga = _FOLGA_ABA_GRAUS

    paineis = [
        PainelDobravel("base", "Base", x2, y2, x3, y3),
        PainelDobravel("lateral1", "Lateral 1", x1, y2, x2, y3, "base", _vertical(x2, y2, y3), 90.0, 0.0, 0.35),
        PainelDobravel("lateral2", "Lateral 2", x3, y2, x4, y3, "base", _vertical(x3, y2, y3), 90.0, 0.0, 0.35),
        PainelDobravel("parede_sup", "Parede superior", x2, y1, x3, y2, "base", _horizontal(y2, x2, x3), 90.0, 0.12, 0.45),
        PainelDobravel("parede_inf", "Parede inferior", x2, y3, x3, y4, "base", _horizontal(y3, x2, x3), 90.0, 0.12, 0.45),
        # Orelhas de canto: presas nas laterais, fecham por dentro das paredes.
        PainelDobravel("canto_1s", "Canto", x1, y1, x2, y2, "lateral1", _horizontal(y2, x1, x2), 90.0 + folga, 0.0, 0.35, camada=1),
        PainelDobravel("canto_1i", "Canto", x1, y3, x2, y4, "lateral1", _horizontal(y3, x1, x2), 90.0 + folga, 0.0, 0.35, camada=1),
        PainelDobravel("canto_2s", "Canto", x3, y1, x4, y2, "lateral2", _horizontal(y2, x3, x4), 90.0 + folga, 0.0, 0.35, camada=1),
        PainelDobravel("canto_2i", "Canto", x3, y3, x4, y4, "lateral2", _horizontal(y3, x3, x4), 90.0 + folga, 0.0, 0.35, camada=1),
        # Prolongamento dos cantos nas linhas da tampa e da aba de fechamento:
        # na faca é a mesma coluna do canto (vinco na altura da parede, corte-
        # serra separando da tampa). Preso na borda de dentro do canto, vira uma
        # divisória que atravessa a caixa; 90° − folga deixa em esquadro (o
        # canto já entra com a folga). Sem isso o 3D mostrava um "degrau".
        PainelDobravel("canto_1s_tampa", "Prolongamento do canto", x1, y0, x2, y1, "canto_1s", _horizontal(y1, x1, x2), 90.0 - folga, 0.40, 0.55, camada=2),
        PainelDobravel("canto_1i_tampa", "Prolongamento do canto", x1, y4, x2, y5, "canto_1i", _horizontal(y4, x1, x2), 90.0 - folga, 0.40, 0.55, camada=2),
        PainelDobravel("canto_2s_tampa", "Prolongamento do canto", x3, y0, x4, y1, "canto_2s", _horizontal(y1, x3, x4), 90.0 - folga, 0.40, 0.55, camada=2),
        PainelDobravel("canto_2i_tampa", "Prolongamento do canto", x3, y4, x4, y5, "canto_2i", _horizontal(y4, x3, x4), 90.0 - folga, 0.40, 0.55, camada=2),
        # Abas da Impressora nas pontas das laterais: dobram pra dentro, por baixo da tampa.
        PainelDobravel("aba_lat1", "Aba lateral", x0, y2, x1, y3, "lateral1", _vertical(x1, y2, y3), 90.0 + folga, 0.45, 0.58, camada=1),
        PainelDobravel("aba_lat2", "Aba lateral", x4, y2, x5, y3, "lateral2", _vertical(x4, y2, y3), 90.0 + folga, 0.45, 0.58, camada=1),
    ]

    if fechamento_normal:
        # Tampa inteira (L) por cima, aba curta da outra ponta por baixo dela.
        paineis.append(PainelDobravel("tampa", "Tampa", x2, y0, x3, y1, "parede_sup", _horizontal(y1, x2, x3), 90.0, 0.80, 1.0))
        paineis.append(PainelDobravel("aba_tampa", "Aba de fechamento", x2, y4, x3, y5, "parede_inf", _horizontal(y4, x2, x3), 90.0 + folga, 0.60, 0.78, camada=1))
    else:
        # Fechamento no meio: duas metades (L/2) que se encontram no centro.
        paineis.append(PainelDobravel("tampa_1", "Tampa", x2, y0, x3, y1, "parede_sup", _horizontal(y1, x2, x3), 90.0, 0.62, 0.82))
        paineis.append(PainelDobravel("tampa_2", "Tampa", x2, y4, x3, y5, "parede_inf", _horizontal(y4, x2, x3), 90.0, 0.80, 1.0))

    return ModeloCaixa3D(
        paineis=paineis,
        cima=(0.0, 0.0, 1.0),  # as paredes sobem pra +z a partir da base
        frente=(0.0, -1.0, 0.0),  # normal externa da parede superior (riscador)
        # Chapa plana vista pelo lado impresso = câmera por baixo da base.
        pitch_planificada=-90.0,
        descricao="Envoltório",
    )
