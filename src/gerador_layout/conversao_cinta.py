"""Lê uma faca desenhada (Construtor, catálogo) e diz se ela é uma cinta:
largura total, faixas separadas por vincos horizontais, recuo igual dos
dois lados e furos de pega. Sem interface: a janela só aplica o resultado.

Só vale o que o tipo Cinta desenharia igual. A leitura termina recalculando
a cinta e comparando com a faca: qualquer detalhe a mais (canto arredondado,
corte solto) recusa a conversão em vez de sumir sem aviso."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .geometria_faca import e_arco
from .layout_service import ServicoLayoutCaixa
from .models import FuroCinta, LinhaDesenho, MedidasCaixa, TipoCaixa, TipoLinha

_TOL = 0.05
_TOL_FORMA = 0.15
_MAX_FAIXAS = 5
_CAMPOS_FAIXA = ("riscador_superior", "riscador_centro", "riscador_inferior", "riscador_parte_4", "riscador_parte_5")


@dataclass
class CintaLida:
    largura: float
    faixas: list[float]
    recuo: float = 0.0
    faixas_recuadas: tuple[int, ...] = ()
    furos: list[FuroCinta] = field(default_factory=list)
    origem: tuple[float, float] = (0.0, 0.0)  # onde a faca começava na chapa


def cla_das_faixas(faixas: list[float]) -> tuple[float, float]:
    """L e A da ficha a partir do riscador: as pontas são L; o que sobra é A."""
    if len(faixas) < 2:
        return 0.0, sum(faixas)
    largura = faixas[0]
    simetrica = len(faixas) > 2 and _igual(faixas[0], faixas[-1])
    return largura, round(sum(faixas) - largura * (2 if simetrica else 1), 3)


def _igual(a: float, b: float) -> bool:
    return abs(a - b) <= _TOL


def _unicos(valores: list[float]) -> list[float]:
    saida: list[float] = []
    for v in sorted(valores):
        if not saida or v - saida[-1] > _TOL:
            saida.append(v)
    return saida


def _horizontal(l: LinhaDesenho) -> bool:
    return not e_arco(l) and _igual(l.y1, l.y2)


def _vertical(l: LinhaDesenho) -> bool:
    return not e_arco(l) and _igual(l.x1, l.x2)


def _proximo_da_borda(ponto, cortes: list[LinhaDesenho], usadas: list[LinhaDesenho]):
    """A reta horizontal ou o arco que sai de `ponto`, e onde ela termina."""
    for l in cortes:
        if l in usadas or not (e_arco(l) or _horizontal(l)):
            continue
        if _igual(l.x1, ponto[0]) and _igual(l.y1, ponto[1]):
            return l, (l.x2, l.y2)
        if _igual(l.x2, ponto[0]) and _igual(l.y2, ponto[1]):
            return l, (l.x1, l.y1)
    return None


def _ler_furo(vinco: LinhaDesenho, cortes: list[LinhaDesenho], ys: list[float], largura: float) -> FuroCinta | None:
    """Vinco vertical só existe em furo: anda do vinco até o topo pela borda
    de cima (reta, depois o arco do canto, se houver)."""
    y1, y2 = sorted((vinco.y1, vinco.y2))
    ponto = (vinco.x1, y1)
    usadas: list[LinhaDesenho] = []
    while (passo := _proximo_da_borda(ponto, cortes, usadas)) is not None:
        usadas.append(passo[0])
        ponto = passo[1]
        if e_arco(passo[0]):
            break
    x_topo = ponto[0]
    meio = (y1 + y2) / 2
    faixa = next((i for i in range(1, len(ys)) if ys[i - 1] <= meio <= ys[i]), None)
    if faixa is None or _igual(x_topo, vinco.x1):
        return None
    direita = vinco.x1 > x_topo  # o vinco fica voltado pra borda
    return FuroCinta(
        faixa=faixa,
        borda="direita" if direita else "esquerda",
        distancia=round(largura - x_topo if direita else x_topo, 3),
        largura=round(abs(vinco.x1 - x_topo), 3),
        altura=round(y2 - y1, 3),
        raio=round(abs(ponto[1] - y1), 3),
    )


def _emendar(trechos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    saida: list[list[float]] = []
    for ini, fim in sorted(trechos):
        if saida and ini <= saida[-1][1] + _TOL:
            saida[-1][1] = max(saida[-1][1], fim)
        else:
            saida.append([ini, fim])
    return [(a, b) for a, b in saida]


def _forma(linhas: list[LinhaDesenho]) -> list[tuple]:
    """A faca sem depender de como foi riscada: retas emendadas (a lateral
    em 5 pedaços ou inteira é a mesma) e arcos numa direção só."""
    retas: dict[tuple, list[tuple[float, float]]] = {}
    resto = []
    for l in linhas:
        if _horizontal(l):
            retas.setdefault((l.tipo.name, "h", round(l.y1, 1)), []).append((min(l.x1, l.x2), max(l.x1, l.x2)))
        elif _vertical(l):
            retas.setdefault((l.tipo.name, "v", round(l.x1, 1)), []).append((min(l.y1, l.y2), max(l.y1, l.y2)))
        else:
            a, b, bojo = (l.x1, l.y1), (l.x2, l.y2), l.bojo
            if b < a:
                a, b, bojo = b, a, -bojo
            resto.append((l.tipo.name, "arco", a[0], a[1], b[0], b[1], bojo * 100))  # bojo é bem menor que mm
    return [(*chave, a, b) for chave, t in sorted(retas.items()) for a, b in _emendar(t)] + sorted(resto)


def _mesma_forma(a: list[tuple], b: list[tuple]) -> bool:
    """Compara número a número: arredondar antes separaria 12,25 de 12,2500001."""
    if len(a) != len(b):
        return False
    return all(
        len(p) == len(q) and all(x == y if isinstance(x, str) else abs(x - y) <= _TOL_FORMA for x, y in zip(p, q))
        for p, q in zip(a, b)
    )


def _desenho_da_cinta(c: CintaLida) -> list[LinhaDesenho]:
    medidas = MedidasCaixa(
        tipo=TipoCaixa.CINTA, comprimento=c.largura, largura=0.0, altura=0.0, impressora_aba=c.largura,
        impressora_largura_1=c.recuo, faixas_recuadas=c.faixas_recuadas, furos=list(c.furos),
        **dict(zip(_CAMPOS_FAIXA, c.faixas)),
    )
    return ServicoLayoutCaixa().calcular(medidas).linhas


def ler_cinta(linhas: list[LinhaDesenho]) -> CintaLida | None:
    """A cinta que esta faca é, ou None se o tipo Cinta não a desenharia igual."""
    if not linhas:
        return None
    origem = (min(min(l.x1, l.x2) for l in linhas), min(min(l.y1, l.y2) for l in linhas))
    faca = [
        replace(l, x1=l.x1 - origem[0], y1=l.y1 - origem[1], x2=l.x2 - origem[0], y2=l.y2 - origem[1]) for l in linhas
    ]
    largura = max(max(l.x1, l.x2) for l in faca)
    altura = max(max(l.y1, l.y2) for l in faca)
    vincos = [l for l in faca if l.tipo == TipoLinha.VINCO]
    cortes = [l for l in faca if l.tipo == TipoLinha.CORTE]
    ys = _unicos([0.0, altura] + [l.y1 for l in vincos if _horizontal(l)])
    if largura <= _TOL or altura <= _TOL or len(ys) - 1 > _MAX_FAIXAS:
        return None

    furos = []
    for vinco in filter(_vertical, vincos):
        furo = _ler_furo(vinco, cortes, ys, largura)
        if furo is None:
            return None
        furos.append(furo)

    recuos = {}
    for n, (a, b) in enumerate(zip(ys, ys[1:]), start=1):
        meio = (a + b) / 2
        bordas = [l.x1 for l in filter(_vertical, cortes) if min(l.y1, l.y2) <= meio <= max(l.y1, l.y2)]
        if not bordas:
            return None
        recuos[n] = min(bordas)
    recuadas = tuple(n for n, r in recuos.items() if r > _TOL)

    cinta = CintaLida(
        round(largura, 3), [round(b - a, 3) for a, b in zip(ys, ys[1:])],
        round(max(recuos.values()), 3), recuadas, furos, origem,
    )
    return cinta if _mesma_forma(_forma(_desenho_da_cinta(cinta)), _forma(faca)) else None
