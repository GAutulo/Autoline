"""Construtor de dieline: monta uma faca nova no padrão do Autoline — uma
grade de trechos, as COLUNAS da impressora (ex.: Aba | L | C | L | C) e as
LINHAS do riscador (ex.: Aba | A | Aba) — sem escrever fórmula de linha.

- Cada trecho tem uma medida em expressão (``C``, ``L / 2 + E``, ``30``).
- Cada peça da grade (linha × coluna) existe ou é refugo.
- Cada divisa entre duas peças tem um tipo: vinco (com ângulo e ordem de
  dobra), corte, fenda (com largura), meio-corte, serrilha ou nada (mesma
  face). Divisa entre peça e refugo, e o contorno, são sempre corte.
- Peça na primeira/última coluna pode ter chanfro nas pontas (aba de cola).

O projeto vira um ESTILO paramétrico (`estilos.py`), com as linhas em
expressões: a mesma faca sai em qualquer medida, o catálogo guarda, e o 3D
dobra com os ângulos e a ordem de cada vinco. O próprio projeto vai junto no
estilo (chave ``"construtor"``) pra reabrir e editar depois.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

from .estilos import Estilo, ErroEstilo, FacaDoEstilo, avaliar
from .models import TipoLinha

# Tipos de divisa (o que o usuário escolhe) → tipo de linha do estilo.
TIPOS_DIVISA = {
    "vinco": "Vinco",
    "corte": "Corte",
    "fenda": "Fenda",
    "meio_corte": "Meio-corte",
    "serra": "Serrilha",
    "nada": "Sem linha (mesma face)",
}


@dataclass
class Trecho:
    nome: str
    medida: str


@dataclass
class Divisa:
    tipo: str = "vinco"
    angulo: float = 90.0
    ordem: int = 1  # vincos de ordem menor dobram antes
    largura: str = "5"  # só fenda

    def como_dict(self) -> dict:
        return {"tipo": self.tipo, "angulo": self.angulo, "ordem": self.ordem, "largura": self.largura}


@dataclass
class Projeto:
    nome: str = "Minha faca"
    variaveis: list[dict] = field(default_factory=list)  # formato do estilo: nome, rotulo, padrao, min, max
    colunas: list[Trecho] = field(default_factory=list)
    linhas: list[Trecho] = field(default_factory=list)
    refugo: set[tuple[int, int]] = field(default_factory=set)  # (linha, coluna) sem peça
    # ("v", i, linha): divisa vertical à esquerda da coluna i (1..n-1), naquela linha.
    # ("h", j, coluna): divisa horizontal acima da linha j (1..m-1), naquela coluna.
    divisas: dict[tuple[str, int, int], Divisa] = field(default_factory=dict)
    chanfros: dict[tuple[int, int], str] = field(default_factory=dict)  # (linha, coluna) → mm
    base: tuple[int, int] | None = None  # peça que fica parada no 3D

    # ── Grade ────────────────────────────────────────────────────────
    def tem_peca(self, linha: int, coluna: int) -> bool:
        return 0 <= linha < len(self.linhas) and 0 <= coluna < len(self.colunas) and (linha, coluna) not in self.refugo

    def divisa(self, chave: tuple[str, int, int]) -> Divisa:
        """A divisa guardada, ou a padrão: vinco (vertical dobra primeiro,
        horizontal depois — paredes antes das abas)."""
        if chave not in self.divisas:
            self.divisas[chave] = Divisa(ordem=1 if chave[0] == "v" else 2)
        return self.divisas[chave]

    def divisa_entre_pecas(self, chave: tuple[str, int, int]) -> bool:
        """Se a divisa separa duas peças (só aí o tipo dela vale)."""
        orient, k, outro = chave
        if orient == "v":
            return self.tem_peca(outro, k - 1) and self.tem_peca(outro, k)
        return self.tem_peca(k - 1, outro) and self.tem_peca(k, outro)

    def _fenda(self, k: int, linha: int) -> Divisa | None:
        chave = ("v", k, linha)
        if 0 < k < len(self.colunas) and self.divisa_entre_pecas(chave) and self.divisa(chave).tipo == "fenda":
            return self.divisa(chave)
        return None

    # ── Edição (o diálogo usa) ───────────────────────────────────────
    def inserir_coluna(self, indice: int, trecho: Trecho) -> None:
        self._deslocar("coluna", indice, +1)
        self.colunas.insert(indice, trecho)

    def remover_coluna(self, indice: int) -> None:
        self.refugo = {(l, c) for l, c in self.refugo if c != indice}
        self.chanfros = {k: v for k, v in self.chanfros.items() if k[1] != indice}
        self.divisas = {k: v for k, v in self.divisas.items() if not (k[0] == "h" and k[2] == indice) and not (k[0] == "v" and k[1] == indice)}
        del self.colunas[indice]
        self._deslocar("coluna", indice + 1, -1)

    def inserir_linha(self, indice: int, trecho: Trecho) -> None:
        self._deslocar("linha", indice, +1)
        self.linhas.insert(indice, trecho)

    def remover_linha(self, indice: int) -> None:
        self.refugo = {(l, c) for l, c in self.refugo if l != indice}
        self.chanfros = {k: v for k, v in self.chanfros.items() if k[0] != indice}
        self.divisas = {k: v for k, v in self.divisas.items() if not (k[0] == "v" and k[2] == indice) and not (k[0] == "h" and k[1] == indice)}
        del self.linhas[indice]
        self._deslocar("linha", indice + 1, -1)

    def _deslocar(self, eixo: str, a_partir: int, passo: int) -> None:
        """Renumera peças, divisas e chanfros quando entra/sai coluna ou linha."""

        def peca(p):
            l, c = p
            if eixo == "coluna" and c >= a_partir:
                return (l, c + passo)
            if eixo == "linha" and l >= a_partir:
                return (l + passo, c)
            return p

        self.refugo = {peca(p) for p in self.refugo}
        self.chanfros = {peca(p): v for p, v in self.chanfros.items()}
        if self.base is not None:
            self.base = peca(self.base)
        novas = {}
        for (orient, k, outro), d in self.divisas.items():
            if eixo == "coluna":
                if orient == "v" and k >= a_partir:
                    k += passo
                elif orient == "h" and outro >= a_partir:
                    outro += passo
            else:
                if orient == "h" and k >= a_partir:
                    k += passo
                elif orient == "v" and outro >= a_partir:
                    outro += passo
            novas[(orient, k, outro)] = d
        self.divisas = novas

    # ── Coordenadas (expressões) ─────────────────────────────────────
    def _xs(self) -> list[str]:
        return ["0"] + [f"X{i}" for i in range(1, len(self.colunas) + 1)]

    def _ys(self) -> list[str]:
        return ["0"] + [f"Y{j}" for j in range(1, len(self.linhas) + 1)]

    def _derivadas(self) -> dict[str, str]:
        derivadas = {}
        anterior = "0"
        for i, trecho in enumerate(self.colunas, start=1):
            derivadas[f"X{i}"] = f"{anterior} + ({trecho.medida})" if anterior != "0" else f"({trecho.medida})"
            anterior = f"X{i}"
        anterior = "0"
        for j, trecho in enumerate(self.linhas, start=1):
            derivadas[f"Y{j}"] = f"{anterior} + ({trecho.medida})" if anterior != "0" else f"({trecho.medida})"
            anterior = f"Y{j}"
        return derivadas

    # ── Estilo ───────────────────────────────────────────────────────
    def para_estilo(self) -> dict:
        if not self.colunas or not self.linhas:
            raise ErroEstilo("A faca precisa de pelo menos uma coluna e uma linha.")
        xs, ys = self._xs(), self._ys()
        n, m = len(self.colunas), len(self.linhas)
        itens: list[dict] = []

        def linha(de, ate, tipo="corte", divisa: Divisa | None = None):
            item = {"de": list(de), "ate": list(ate), "tipo": tipo}
            if divisa is not None and tipo == "vinco":
                item["dobra"] = divisa.angulo
                item["ordem"] = divisa.ordem
            itens.append(item)

        def meia(d: Divisa) -> str:
            return f"(({d.largura}) / 2)"

        def chanfro(l: int, c: int) -> str | None:
            if c not in (0, n - 1) or not self.tem_peca(l, c):
                return None
            valor = self.chanfros.get((l, c), "").strip()
            return valor if valor and valor != "0" else None

        # Divisas verticais (inclui o contorno da esquerda e da direita).
        for i in range(n + 1):
            x = xs[i]
            for l in range(m):
                esq, dir_ = self.tem_peca(l, i - 1), self.tem_peca(l, i)
                y0, y1 = ys[l], ys[l + 1]
                if not esq and not dir_:
                    continue
                if esq != dir_:
                    c = i if dir_ else i - 1
                    t = chanfro(l, c)
                    externo = i in (0, n)
                    if t and externo:
                        # Ponta chanfrada: a borda de fora encolhe e as quinas viram diagonal.
                        xi = xs[1] if i == 0 else xs[n - 1]
                        cima_livre = not self.tem_peca(l - 1, c)
                        baixo_livre = not self.tem_peca(l + 1, c)
                        ya = f"{y0} + ({t})" if cima_livre else y0
                        yb = f"{y1} - ({t})" if baixo_livre else y1
                        if cima_livre:
                            linha((xi, y0), (x, ya))
                        linha((x, ya), (x, yb))
                        if baixo_livre:
                            linha((x, yb), (xi, y1))
                        continue
                    linha((x, y0), (x, y1))
                    continue
                d = self.divisa(("v", i, l))
                if d.tipo == "nada":
                    continue
                if d.tipo == "fenda":
                    for lado in ("-", "+"):
                        linha((f"{x} {lado} {meia(d)}", y0), (f"{x} {lado} {meia(d)}", y1))
                    # Fecha a fenda onde ela encosta numa peça inteira (sem fenda ali).
                    for vizinha, y in ((l - 1, y0), (l + 1, y1)):
                        if self.tem_peca(vizinha, i - 1) and self.tem_peca(vizinha, i) and self._fenda(i, vizinha) is None:
                            linha((f"{x} - {meia(d)}", y), (f"{x} + {meia(d)}", y))
                    continue
                linha((x, y0), (x, y1), d.tipo, d)

        # Divisas horizontais (inclui o contorno de cima e de baixo).
        for j in range(m + 1):
            y = ys[j]
            for c in range(n):
                cima, baixo = self.tem_peca(j - 1, c), self.tem_peca(j, c)
                if not cima and not baixo:
                    continue
                x0, x1 = xs[c], xs[c + 1]
                if cima != baixo:
                    peca_l = j - 1 if cima else j
                    if chanfro(peca_l, c):
                        continue  # a diagonal do chanfro já fecha esta borda
                    tipo, d = "corte", None
                else:
                    d = self.divisa(("h", j, c))
                    if d.tipo == "nada":
                        continue
                    tipo = d.tipo
                    if tipo == "fenda":
                        tipo = "corte"  # fenda só faz sentido entre colunas
                # Fenda vertical encostando nesta borda: a linha para na beira dela.
                for k, ponta in ((c, "ini"), (c + 1, "fim")):
                    fendas = [f for f in (self._fenda(k, j - 1), self._fenda(k, j)) if f is not None]
                    if fendas:
                        recuo = meia(fendas[0])
                        if ponta == "ini":
                            x0 = f"{x0} + {recuo}"
                        else:
                            x1 = f"{x1} - {recuo}"
                linha((x0, y), (x1, y), tipo, d)

        # Ordem das dobras → janela de montagem (0 = plana, 1 = montada).
        ordens = sorted({it["ordem"] for it in itens if "ordem" in it})
        for it in itens:
            if "ordem" in it:
                k = ordens.index(it.pop("ordem"))
                passo = 1.0 / len(ordens)
                it["tempo"] = [round(k * passo, 4), round((k + 1) * passo, 4)]

        base = self.base if self.base is not None and self.tem_peca(*self.base) else self._base_padrao()
        dados = {
            "codigo": "",
            "nome": self.nome,
            "descricao": f"Feita no construtor de dieline: {n} colunas × {m} linhas.",
            "variaveis": copy.deepcopy(self.variaveis),
            "derivadas": self._derivadas(),
            "linhas": itens,
            "cotas": [
                *[
                    {"de": [xs[c], f"{ys[m]} + 12"], "ate": [xs[c + 1], f"{ys[m]} + 12"], "rotulo": t.nome}
                    for c, t in enumerate(self.colunas)
                ],
                *[
                    {"de": [f"{xs[n]} + 12", ys[l]], "ate": [f"{xs[n]} + 12", ys[l + 1]], "rotulo": t.nome}
                    for l, t in enumerate(self.linhas)
                ],
            ],
            "construtor": self.como_dict(),
        }
        if base is not None:
            l, c = base
            dados["base"] = [f"({xs[c]} + {xs[c + 1]}) / 2", f"({ys[l]} + {ys[l + 1]}) / 2"]
        return dados

    def _base_padrao(self) -> tuple[int, int] | None:
        """A maior peça (com as medidas padrão) — normalmente o fundo/frente."""
        try:
            valores = {v["nome"]: float(v.get("padrao", 0)) for v in self.variaveis}
            larguras = [avaliar(t.medida, valores) for t in self.colunas]
            alturas = [avaliar(t.medida, valores) for t in self.linhas]
        except ErroEstilo:
            return None
        pecas = [(l, c) for l in range(len(self.linhas)) for c in range(len(self.colunas)) if self.tem_peca(l, c)]
        return max(pecas, key=lambda p: alturas[p[0]] * larguras[p[1]], default=None)

    def gerar(self, valores: dict[str, float] | None = None) -> FacaDoEstilo:
        return Estilo(self.para_estilo()).gerar(valores)

    # ── Guardar / abrir ──────────────────────────────────────────────
    def como_dict(self) -> dict:
        return {
            "nome": self.nome,
            "variaveis": copy.deepcopy(self.variaveis),
            "colunas": [[t.nome, t.medida] for t in self.colunas],
            "linhas": [[t.nome, t.medida] for t in self.linhas],
            "refugo": sorted([list(p) for p in self.refugo]),
            "divisas": [[o, k, x, d.como_dict()] for (o, k, x), d in sorted(self.divisas.items())],
            "chanfros": [[l, c, v] for (l, c), v in sorted(self.chanfros.items())],
            "base": list(self.base) if self.base is not None else None,
        }

    @classmethod
    def de_dict(cls, dados: dict) -> "Projeto":
        p = cls(
            nome=dados.get("nome", "Minha faca"),
            variaveis=copy.deepcopy(dados.get("variaveis", [])),
            colunas=[Trecho(n, str(m)) for n, m in dados.get("colunas", [])],
            linhas=[Trecho(n, str(m)) for n, m in dados.get("linhas", [])],
            refugo={(int(l), int(c)) for l, c in dados.get("refugo", [])},
            chanfros={(int(l), int(c)): str(v) for l, c, v in dados.get("chanfros", [])},
        )
        for o, k, x, d in dados.get("divisas", []):
            p.divisas[(o, int(k), int(x))] = Divisa(
                tipo=d.get("tipo", "vinco"), angulo=float(d.get("angulo", 90)), ordem=int(d.get("ordem", 1)),
                largura=str(d.get("largura", "5")),
            )
        if dados.get("base") is not None:
            p.base = (int(dados["base"][0]), int(dados["base"][1]))
        return p


# ── Resumo pra quem faz a faca ───────────────────────────────────────
@dataclass
class Resumo:
    vincos: int
    cortes: int
    fendas: int
    outros: int
    metros_vinco: float
    metros_corte: float
    largura: float
    altura: float


def resumir(projeto: Projeto, faca: FacaDoEstilo) -> Resumo:
    def comprimento(l) -> float:
        return math.hypot(l.x2 - l.x1, l.y2 - l.y1)

    vincos = [l for l in faca.linhas if l.tipo == TipoLinha.VINCO]
    cortes = [l for l in faca.linhas if l.tipo == TipoLinha.CORTE]
    outros = [l for l in faca.linhas if l.tipo not in (TipoLinha.VINCO, TipoLinha.CORTE)]
    fendas = sum(
        1 for chave, d in projeto.divisas.items() if chave[0] == "v" and d.tipo == "fenda" and projeto.divisa_entre_pecas(chave)
    )
    return Resumo(
        vincos=len(vincos),
        cortes=len(cortes),
        fendas=fendas,
        outros=len(outros),
        metros_vinco=sum(map(comprimento, vincos)) / 1000,
        metros_corte=sum(map(comprimento, cortes)) / 1000,
        largura=faca.largura,
        altura=faca.altura,
    )


# ── Modelos pra começar ──────────────────────────────────────────────
_MEDIDAS = [
    {"nome": "C", "rotulo": "Comprimento (C)", "padrao": 300, "min": 1, "max": 5000},
    {"nome": "L", "rotulo": "Largura (L)", "padrao": 200, "min": 1, "max": 5000},
    {"nome": "A", "rotulo": "Altura (A)", "padrao": 150, "min": 1, "max": 5000},
    {"nome": "E", "rotulo": "Espessura do papelão (E)", "padrao": 3, "min": 0, "max": 20},
]


def modelo_em_branco() -> Projeto:
    return Projeto(nome="Minha faca", variaveis=copy.deepcopy(_MEDIDAS), colunas=[Trecho("C", "C")], linhas=[Trecho("L", "L")])


def modelo_maleta() -> Projeto:
    """Maleta normal: Aba | L | C | L | C na impressora e Aba | A | Aba no
    riscador, aba de cola chanfrada e fendas entre as abas."""
    p = Projeto(
        nome="Maleta (base)",
        variaveis=copy.deepcopy(_MEDIDAS) + [{"nome": "G", "rotulo": "Aba de cola (G)", "padrao": 35, "min": 1, "max": 100}],
        colunas=[Trecho("Aba", "G"), Trecho("L", "L"), Trecho("C", "C"), Trecho("L", "L"), Trecho("C", "C")],
        linhas=[Trecho("Aba", "L / 2"), Trecho("A", "A"), Trecho("Aba", "L / 2")],
        refugo={(0, 0), (2, 0)},
        chanfros={(1, 0): "G / 3"},
        base=(1, 2),
    )
    for k in range(2, 5):
        for l in (0, 2):
            p.divisas[("v", k, l)] = Divisa(tipo="fenda", largura="E + 2")
    return p


def modelo_bandeja() -> Projeto:
    """Bandeja/capa: A | C | A × A | L | A, cantos de refugo."""
    p = Projeto(
        nome="Bandeja (base)",
        variaveis=copy.deepcopy(_MEDIDAS),
        colunas=[Trecho("A", "A"), Trecho("C", "C"), Trecho("A", "A")],
        linhas=[Trecho("A", "A"), Trecho("L", "L"), Trecho("A", "A")],
        refugo={(0, 0), (0, 2), (2, 0), (2, 2)},
        base=(1, 1),
    )
    return p


MODELOS = {
    "Em branco": modelo_em_branco,
    "Maleta (Aba | L | C | L | C)": modelo_maleta,
    "Bandeja / capa": modelo_bandeja,
}
