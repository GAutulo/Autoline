"""Estilos paramétricos de faca (como o Style Catalog / StyleMaker do
ArtiosCAD, feito do zero a partir da documentação pública): a faca é
descrita por VARIÁVEIS (C, L, A, espessura...) e EXPRESSÕES, então a mesma
caixa sai em qualquer medida. Cada vinco pode dizer o ângulo e o momento
em que dobra, e o 3D monta a caixa do jeito certo.

Formato (dict, igual ao JSON dos arquivos de estilo do usuário):

    {
      "codigo": "0427", "nome": "...", "descricao": "...",
      "variaveis": [{"nome": "C", "rotulo": "Comprimento", "padrao": 300,
                     "min": 20, "max": 2000}, ...],
      "derivadas": {"T": "A - E"},            # calculadas, na ordem
      "validacoes": [["A <= L", "mensagem se falhar"]],
      "linhas": [{"de": ["x", "y"], "ate": ["x", "y"], "tipo": "vinco",
                  "dobra": 90, "tempo": [0.0, 0.3]}],
      "base": ["x", "y"],                     # ponto dentro da face que fica parada
      "cotas": [{"de": [...], "ate": [...], "rotulo": "C"}]   # diagrama
    }

Coordenadas em mm, y pra baixo (como o resto da faca). As expressões só
aceitam números, as variáveis, + - * / ** e parênteses, e as funções
min, max, abs, round, sqrt, sin, cos, tan (graus)."""

from __future__ import annotations

import ast
import json
import math
import operator
from dataclasses import dataclass, field
from pathlib import Path

from .models import LinhaDesenho, TipoLinha

TIPOS = {
    "corte": TipoLinha.CORTE,
    "vinco": TipoLinha.VINCO,
    "meio_corte": TipoLinha.MEIO_CORTE,
    "serra": TipoLinha.CORTE_SERRA,
    "dobra": TipoLinha.DOBRA,
}
NOME_DO_TIPO = {v: k for k, v in TIPOS.items()}

_OPERADORES = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_COMPARACOES = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_FUNCOES = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "sin": lambda g: math.sin(math.radians(g)),
    "cos": lambda g: math.cos(math.radians(g)),
    "tan": lambda g: math.tan(math.radians(g)),
}


class ErroEstilo(ValueError):
    """Expressão inválida, variável desconhecida ou validação que falhou."""


def avaliar(expressao, valores: dict[str, float]) -> float:
    """Calcula uma expressão do estilo sem `eval`: só a aritmética permitida."""
    if isinstance(expressao, (int, float)):
        return float(expressao)
    try:
        arvore = ast.parse(str(expressao), mode="eval")
    except SyntaxError as exc:
        raise ErroEstilo(f"Expressão inválida: {expressao!r}") from exc

    def no(n):
        if isinstance(n, ast.Expression):
            return no(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id not in valores:
                raise ErroEstilo(f"Variável desconhecida: {n.id} (em {expressao!r})")
            return float(valores[n.id])
        if isinstance(n, ast.BinOp) and type(n.op) in _OPERADORES:
            return _OPERADORES[type(n.op)](no(n.left), no(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPERADORES:
            return _OPERADORES[type(n.op)](no(n.operand))
        if isinstance(n, ast.Compare) and all(type(o) in _COMPARACOES for o in n.ops):
            esquerda = no(n.left)
            for op, direita_no in zip(n.ops, n.comparators):
                direita = no(direita_no)
                if not _COMPARACOES[type(op)](esquerda, direita):
                    return 0.0
                esquerda = direita
            return 1.0
        if isinstance(n, ast.BoolOp):
            itens = [no(v) for v in n.values]
            return float(all(itens) if isinstance(n.op, ast.And) else any(itens))
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in _FUNCOES
            and not n.keywords
        ):
            return float(_FUNCOES[n.func.id](*[no(a) for a in n.args]))
        raise ErroEstilo(f"Expressão não permitida: {expressao!r}")

    try:
        return no(arvore)
    except ZeroDivisionError as exc:
        raise ErroEstilo(f"Divisão por zero em {expressao!r}") from exc


@dataclass
class DobraDoEstilo:
    """Um vinco do estilo com o ângulo e a janela de montagem dele (0 =
    plana, 1 = montada) — o 3D usa pra fechar a caixa como ela fecha."""

    x1: float
    y1: float
    x2: float
    y2: float
    angulo: float
    inicio: float
    fim: float


@dataclass
class FacaDoEstilo:
    linhas: list[LinhaDesenho]
    dobras: list[DobraDoEstilo]
    ponto_base: tuple[float, float] | None
    cotas: list[tuple[tuple[float, float], tuple[float, float], str]]
    valores: dict[str, float]
    largura: float
    altura: float


@dataclass
class Estilo:
    dados: dict
    origem: str = "catálogo"  # "catálogo" ou o caminho do arquivo do usuário
    caminho: Path | None = field(default=None, repr=False)

    @property
    def codigo(self) -> str:
        return str(self.dados.get("codigo", ""))

    @property
    def nome(self) -> str:
        return str(self.dados.get("nome", "Estilo sem nome"))

    @property
    def nome_exibicao(self) -> str:
        return f"{self.codigo} — {self.nome}" if self.codigo else self.nome

    @property
    def descricao(self) -> str:
        return str(self.dados.get("descricao", ""))

    @property
    def variaveis(self) -> list[dict]:
        return list(self.dados.get("variaveis", []))

    def valores_padrao(self) -> dict[str, float]:
        return {v["nome"]: float(v.get("padrao", 0.0)) for v in self.variaveis}

    def validar(self, valores: dict[str, float]) -> list[str]:
        """Problemas com os valores (vazio = pode gerar)."""
        problemas = []
        for v in self.variaveis:
            valor = valores.get(v["nome"])
            rotulo = v.get("rotulo", v["nome"])
            if valor is None:
                problemas.append(f"Falta {rotulo}.")
                continue
            if "min" in v and valor < float(v["min"]):
                problemas.append(f"{rotulo} precisa ser pelo menos {float(v['min']):g}.")
            if "max" in v and valor > float(v["max"]):
                problemas.append(f"{rotulo} pode ser no máximo {float(v['max']):g}.")
        if problemas:
            return problemas
        try:
            completos = self._com_derivadas(valores)
            for condicao, mensagem in self.dados.get("validacoes", []):
                if not avaliar(condicao, completos):
                    problemas.append(mensagem)
        except ErroEstilo as exc:
            problemas.append(str(exc))
        return problemas

    def _com_derivadas(self, valores: dict[str, float]) -> dict[str, float]:
        completos = dict(valores)
        for nome, expressao in self.dados.get("derivadas", {}).items():
            completos[nome] = avaliar(expressao, completos)
        return completos

    def gerar(self, valores: dict[str, float] | None = None) -> FacaDoEstilo:
        """Faca nas medidas dadas (faltando, usa o padrão). Levanta
        `ErroEstilo` se a validação falhar."""
        completos = self.valores_padrao()
        completos.update(valores or {})
        problemas = self.validar(completos)
        if problemas:
            raise ErroEstilo(" ".join(problemas))
        completos = self._com_derivadas(completos)

        def ponto(par) -> tuple[float, float]:
            return (avaliar(par[0], completos), avaliar(par[1], completos))

        linhas: list[LinhaDesenho] = []
        dobras: list[DobraDoEstilo] = []
        for item in self.dados.get("linhas", []):
            (x1, y1), (x2, y2) = ponto(item["de"]), ponto(item["ate"])
            if math.hypot(x2 - x1, y2 - y1) < 1e-6:
                continue  # trecho que zerou com estas medidas (ex.: aba de 0 mm)
            tipo = TIPOS.get(item.get("tipo", "corte"), TipoLinha.CORTE)
            linhas.append(LinhaDesenho(x1, y1, x2, y2, tipo, avaliar(item.get("bojo", 0), completos)))
            if "dobra" in item:
                inicio, fim = item.get("tempo", [0.0, 1.0])
                dobras.append(
                    DobraDoEstilo(x1, y1, x2, y2, avaliar(item["dobra"], completos), float(inicio), float(fim))
                )
        base = ponto(self.dados["base"]) if "base" in self.dados else None
        cotas = [(ponto(c["de"]), ponto(c["ate"]), str(c.get("rotulo", ""))) for c in self.dados.get("cotas", [])]
        xs = [x for l in linhas for x in (l.x1, l.x2)] or [0.0]
        ys = [y for l in linhas for y in (l.y1, l.y2)] or [0.0]
        if min(xs) != 0 or min(ys) != 0:
            # Faca sempre começando em (0, 0), como as calculadas.
            dx, dy = -min(xs), -min(ys)
            linhas = [LinhaDesenho(l.x1 + dx, l.y1 + dy, l.x2 + dx, l.y2 + dy, l.tipo, l.bojo) for l in linhas]
            dobras = [DobraDoEstilo(d.x1 + dx, d.y1 + dy, d.x2 + dx, d.y2 + dy, d.angulo, d.inicio, d.fim) for d in dobras]
            base = (base[0] + dx, base[1] + dy) if base else None
            cotas = [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), r) for a, b, r in cotas]
        return FacaDoEstilo(
            linhas=linhas,
            dobras=dobras,
            ponto_base=base,
            cotas=cotas,
            valores=completos,
            largura=max(xs) - min(xs),
            altura=max(ys) - min(ys),
        )


def estilo_da_faca(linhas: list[LinhaDesenho], nome: str, descricao: str = "") -> dict:
    """A faca atual como estilo (coordenadas fixas): pra reaproveitar uma
    faca desenhada à mão. Dá pra trocar números por expressões depois,
    editando o arquivo."""
    return {
        "codigo": "",
        "nome": nome,
        "descricao": descricao or "Faca salva do Autoline (medidas fixas).",
        "variaveis": [],
        "linhas": [
            {
                "de": [round(l.x1, 4), round(l.y1, 4)],
                "ate": [round(l.x2, 4), round(l.y2, 4)],
                "tipo": NOME_DO_TIPO.get(l.tipo, "corte"),
                **({"bojo": round(l.bojo, 6)} if l.bojo else {}),
            }
            for l in linhas
        ],
    }


def carregar_estilos(pasta_usuario: Path | None = None) -> list[Estilo]:
    """Catálogo embutido + os .json da pasta do usuário (arquivo com erro é
    pulado — não derruba o catálogo inteiro)."""
    from .estilos_catalogo import CATALOGO

    estilos = [Estilo(dados) for dados in CATALOGO]
    if pasta_usuario is not None and pasta_usuario.is_dir():
        for arquivo in sorted(pasta_usuario.glob("*.json")):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
                Estilo(dados).gerar()  # confere que gera com os valores padrão
            except (OSError, ValueError, KeyError, TypeError):
                continue
            estilos.append(Estilo(dados, origem=str(arquivo), caminho=arquivo))
    return estilos


def salvar_estilo(dados: dict, pasta_usuario: Path) -> Path:
    pasta_usuario.mkdir(parents=True, exist_ok=True)
    base = "".join(c if c.isalnum() or c in "-_ " else "_" for c in dados.get("nome", "estilo")).strip() or "estilo"
    destino = pasta_usuario / f"{base}.json"
    n = 2
    while destino.exists():
        destino = pasta_usuario / f"{base} ({n}).json"
        n += 1
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino
