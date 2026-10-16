"""Arquivo de projeto do Autoline (``.autoline``): tudo o que é preciso pra
reabrir um modelo e só alterar — tipo de caixa e medidas (com os trechos
digitados à mão), cores da legenda, a faca (calculada ou editada, com o
estilo/dobras de onde veio), os objetos do Layout e o papelão/ângulos do 3D.

É um JSON (UTF-8) com as imagens e os logotipos DENTRO do arquivo: dá pra
salvar na pasta do cliente, copiar pra outro computador ou mandar por e-mail
sem perder nada (o caminho original do logo não precisa mais existir).

Formato (versão 1)::

    {"formato": "autoline", "versao": 1, "salvo_em": "...",
     "caixa": {...}, "cores": [...], "faca": {...}, "dobras_3d": {...},
     "papelao_mm": 0.3, "elementos": [...], "arquivos": {id: {...}}}

Cada elemento tem ``tipo`` (o nome da classe), a geometria comum (tamanho,
posição, rotação, painel, espelho, ordem) e os campos do tipo. Um tipo que
uma versão antiga não conhece é pulado (com aviso), não derruba a abertura.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QStandardPaths

from ..models import CorImpressao, LinhaDesenho, TipoCaixa, TipoLinha
from .mockup_acabamento import ElementoAcabamento, TipoAcabamento
from .mockup_callout import ElementoCallout
from .mockup_checklist import ElementoChecklistCores
from .mockup_cota import ElementoCota
from .mockup_cota_angular import ElementoCotaAngular
from .mockup_curva import ElementoCurva, No, SubCaminho
from .mockup_formas import ElementoElipse, ElementoLinha, ElementoPoligono, ElementoRetangulo
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_simbolos import ElementoSimbolo, TipoSimbolo
from .mockup_tabela import ElementoTabela
from .mockup_texto import ElementoTexto

EXTENSAO = ".autoline"
FILTRO = "Projeto do Autoline (*.autoline)"
VERSAO = 1


class ErroProjeto(ValueError):
    """Arquivo que não é projeto do Autoline, ou de uma versão mais nova."""


# ── Peças pequenas ───────────────────────────────────────────────────
def _cor(c: CorImpressao | None) -> dict | None:
    return None if c is None else {"nome": c.nome, "r": c.r, "g": c.g, "b": c.b}


def _cor_de(d: dict | None) -> CorImpressao | None:
    return None if not d else CorImpressao(nome=d["nome"], r=int(d["r"]), g=int(d["g"]), b=int(d["b"]))


def _ponto(q: QPointF) -> list[float]:
    return [q.x(), q.y()]


def _ponto_de(v) -> QPointF:
    return QPointF(float(v[0]), float(v[1]))


def pasta_arquivos_extraidos() -> Path:
    """Onde os logotipos/imagens de um projeto aberto viram arquivo de novo
    (os elementos trabalham com caminho) — um por conteúdo, reaproveitado."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "arquivos_de_projetos"


class _Arquivos:
    """Os arquivos embutidos (SVG em texto, imagem em base64), por id = hash."""

    def __init__(self, dados: dict | None = None) -> None:
        self.dados: dict[str, dict] = dict(dados or {})

    def guardar_texto(self, texto: str, extensao: str) -> str:
        chave = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]
        self.dados.setdefault(chave, {"extensao": extensao, "texto": texto})
        return chave

    def guardar_binario(self, bruto: bytes, extensao: str) -> str:
        chave = hashlib.sha1(bruto).hexdigest()[:16]
        self.dados.setdefault(chave, {"extensao": extensao, "base64": base64.b64encode(bruto).decode("ascii")})
        return chave

    def caminho(self, chave: str) -> str:
        item = self.dados[chave]
        pasta = pasta_arquivos_extraidos()
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{chave}{item['extensao']}"
        if not destino.is_file():
            if "texto" in item:
                destino.write_text(item["texto"], encoding="utf-8")
            else:
                destino.write_bytes(base64.b64decode(item["base64"]))
        return str(destino)


# ── Elementos ────────────────────────────────────────────────────────
def _geometria(el: ElementoMockup) -> dict:
    return {
        "largura": el.largura,
        "altura": el.altura,
        "pos": _ponto(el.pos()),
        "rotacao": el.rotation(),
        "painel": el.painel_id,
        "proporcao_travada": el.proporcao_travada,
        "espelho": [el._espelho_h, el._espelho_v],
        "z": el.zValue(),
        "visivel": el.isVisible(),
    }


def _aplicar_geometria(el: ElementoMockup, g: dict, tamanho: bool = True) -> None:
    if tamanho:
        el.definir_tamanho(float(g["largura"]), float(g["altura"]))
    el.setPos(_ponto_de(g["pos"]))
    el.setRotation(float(g.get("rotacao", 0.0)))
    el.definir_painel(g.get("painel"))
    el.definir_proporcao_travada(bool(g.get("proporcao_travada", False)))
    esp = g.get("espelho", [False, False])
    el.definir_espelho(bool(esp[0]), bool(esp[1]))
    el.setZValue(float(g.get("z", 0.0)))
    el.setVisible(bool(g.get("visivel", True)))


def _forma(el) -> dict:
    return {"cor": _cor(el.cor_tinta), "preenchido": getattr(el, "preenchido", False), "traco": el.largura_traco}


def elemento_para_dict(el: ElementoMockup, arquivos: _Arquivos) -> dict | None:
    d: dict = {"tipo": type(el).__name__, "geometria": _geometria(el)}
    if isinstance(el, GrupoMockup):
        d["elementos"] = [x for x in (elemento_para_dict(f, arquivos) for f in el.elementos) if x is not None]
    elif isinstance(el, ElementoTexto):
        d.update(texto=el.texto, fonte=el.fonte_familia, negrito=el.negrito, cor=_cor(el.cor_tinta), alinhamento=el.alinhamento)
    elif isinstance(el, ElementoChecklistCores):
        d.update(
            variantes=el.variantes, fonte=el.fonte_familia, negrito=el.negrito, cor=_cor(el.cor_tinta),
            tamanho_pt=el.tamanho_pt, disposicao=el.disposicao, largura_letra=el.largura_letra,
        )
    elif isinstance(el, (ElementoRetangulo, ElementoElipse)):
        d.update(_forma(el))
    elif isinstance(el, ElementoPoligono):
        d.update(_forma(el), lados=el.lados)
    elif isinstance(el, ElementoLinha):
        d.update(cor=_cor(el.cor_tinta), traco=el.largura_traco)
    elif isinstance(el, ElementoCurva):
        d.update(
            _forma(el),
            base=[el._base_l, el._base_a],
            subcaminhos=[
                {
                    "fechado": s.fechado,
                    "nos": [[_ponto(n.p), _ponto(n.entrada), _ponto(n.saida), n.suave] for n in s.nos],
                }
                for s in el.subcaminhos
            ],
        )
    elif isinstance(el, ElementoCota):
        d.update(ya=el._ya, yb=el._yb, tipo_cota=el._tipo, cor=_cor(el.cor_tinta), altura_texto=el._altura_texto)
    elif isinstance(el, ElementoCotaAngular):
        d.update(
            v=_ponto(el._v), a=_ponto(el._a), b=_ponto(el._b), raio=el._raio, base=[el._base_l, el._base_a],
            cor=_cor(el.cor_tinta), altura_texto=el._altura_texto,
        )
    elif isinstance(el, ElementoCallout):
        d.update(texto=el.texto, cor=_cor(el.cor_tinta))
    elif isinstance(el, ElementoTabela):
        d.update(
            linhas=el.linhas, colunas=el.colunas, celulas=el.celulas, cor=_cor(el.cor_tinta),
            fonte=el.fonte_familia, altura_letra=el.altura_letra_mm, largura_letra=el.largura_letra,
        )
    elif isinstance(el, ElementoAcabamento):
        d.update(acabamento=el.tipo.name)
    elif isinstance(el, ElementoSimbolo):
        d.update(simbolo=el.tipo.name, cor=_cor(el.cor_tinta))
    elif isinstance(el, ElementoLogoVetorial):
        d.update(
            arquivo=arquivos.guardar_texto(el._conteudo_original, ".svg"),
            nome_arquivo=getattr(el, "nome_original", None) or Path(el.caminho_arquivo).name,
            mapa_cores=el.mapa_cores,
            tinta_unica=_cor(el.tinta_unica),
        )
    elif isinstance(el, ElementoImagem):
        d.update(
            arquivo=arquivos.guardar_binario(_bytes_da_imagem(el), ".png"),
            nome_arquivo=getattr(el, "nome_original", None) or Path(el.caminho_arquivo).name,
        )
    else:
        return None
    return d


def _bytes_da_imagem(el: ElementoImagem) -> bytes:
    caminho = Path(el.caminho_arquivo)
    if caminho.is_file():
        return caminho.read_bytes()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    el._pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def elemento_de_dict(d: dict, arquivos: _Arquivos) -> ElementoMockup | None:
    """O elemento pronto (ainda fora da cena), ou None se o tipo é
    desconhecido. Grupo: devolve um dict com os filhos pra montar na cena."""
    tipo = d.get("tipo")
    g = d["geometria"]
    cor = _cor_de(d.get("cor"))
    if tipo == "ElementoTexto":
        el = ElementoTexto(texto=d["texto"], fonte_familia=d["fonte"], negrito=d["negrito"], cor_tinta=cor)
        el.definir_alinhamento(d.get("alinhamento", "esquerda"))
    elif tipo == "ElementoChecklistCores":
        el = ElementoChecklistCores(
            variantes=d["variantes"], fonte_familia=d["fonte"], cor_tinta=cor, tamanho_pt=d["tamanho_pt"],
            negrito=d["negrito"], disposicao=d["disposicao"], largura_letra=d.get("largura_letra", 1.0),
        )
    elif tipo == "ElementoRetangulo":
        el = ElementoRetangulo(cor_tinta=cor, preenchido=d["preenchido"], largura_traco=d["traco"])
    elif tipo == "ElementoElipse":
        el = ElementoElipse(cor_tinta=cor, preenchido=d["preenchido"], largura_traco=d["traco"])
    elif tipo == "ElementoPoligono":
        el = ElementoPoligono(lados=d["lados"], cor_tinta=cor, preenchido=d["preenchido"], largura_traco=d["traco"])
    elif tipo == "ElementoLinha":
        el = ElementoLinha(cor_tinta=cor, largura_traco=d["traco"])
    elif tipo == "ElementoCurva":
        subs = [
            SubCaminho(
                nos=[No(_ponto_de(p), _ponto_de(e), _ponto_de(s), bool(suave)) for p, e, s, suave in sub["nos"]],
                fechado=bool(sub["fechado"]),
            )
            for sub in d["subcaminhos"]
        ]
        el = ElementoCurva(subs, cor, d["preenchido"], d["traco"])
        el._base_l, el._base_a = float(d["base"][0]), float(d["base"][1])
    elif tipo == "ElementoCota":
        el = ElementoCota(
            largura=float(g["largura"]), ya=d["ya"], yb=d["yb"], tipo=d["tipo_cota"], cor_tinta=cor,
            altura_texto=d["altura_texto"],
        )
    elif tipo == "ElementoCotaAngular":
        v, a, b = _ponto_de(d["v"]), _ponto_de(d["a"]), _ponto_de(d["b"])
        el = ElementoCotaAngular(v, a, b, d["raio"], cor, d["altura_texto"])
        el._v, el._a, el._b = v, a, b
        el._base_l, el._base_a = float(d["base"][0]), float(d["base"][1])
    elif tipo == "ElementoCallout":
        el = ElementoCallout(texto=d["texto"], cor_tinta=cor)
    elif tipo == "ElementoTabela":
        el = ElementoTabela(
            linhas=d["linhas"], colunas=d["colunas"], celulas=d["celulas"], cor_tinta=cor,
            fonte_familia=d.get("fonte", ""), altura_letra_mm=d.get("altura_letra"),
            largura_letra=d.get("largura_letra", 1.0),
        )
    elif tipo == "ElementoAcabamento":
        el = ElementoAcabamento(tipo=TipoAcabamento[d["acabamento"]])
    elif tipo == "ElementoSimbolo":
        el = ElementoSimbolo(tipo=TipoSimbolo[d["simbolo"]], cor_tinta=cor)
    elif tipo == "ElementoLogoVetorial":
        el = ElementoLogoVetorial(arquivos.caminho(d["arquivo"]))
        tinta = _cor_de(d.get("tinta_unica"))
        if tinta is not None:
            el.pintar_numa_tinta(tinta)
        elif d.get("mapa_cores"):
            el.definir_mapa_cores(d["mapa_cores"])
    elif tipo == "ElementoImagem":
        el = ElementoImagem(arquivos.caminho(d["arquivo"]))
    else:
        return None
    if d.get("nome_arquivo"):
        el.nome_original = d["nome_arquivo"]  # o arquivo agora é a cópia extraída do projeto
    _aplicar_geometria(el, g)
    return el


# ── Janela inteira ───────────────────────────────────────────────────
def _linha(l: LinhaDesenho) -> list:
    return [l.x1, l.y1, l.x2, l.y2, l.tipo.name, l.bojo]


def _linha_de(v) -> LinhaDesenho:
    return LinhaDesenho(float(v[0]), float(v[1]), float(v[2]), float(v[3]), TipoLinha[v[4]], float(v[5]))


def estado_da_janela(janela, com_arquivos: bool = True) -> dict:
    canvas = janela.canvas
    arquivos = _Arquivos()

    def trechos(linha) -> list[float]:
        return [spin.value() if tocado else 0.0 for spin, tocado in zip(linha._spins, linha._tocados)]

    dobras_estilo = getattr(janela, "_dobras_estilo", None)
    base_estilo = getattr(janela, "_base_estilo", None)
    estilo_atual = getattr(janela, "_estilo_atual", None)
    elementos = []
    for el in sorted(canvas.elementos_mockup, key=lambda e: e.zValue()):
        d = elemento_para_dict(el, arquivos)
        if d is not None:
            elementos.append(d)
    dados = {
        "formato": "autoline",
        "versao": VERSAO,
        "salvo_em": _dt.datetime.now().isoformat(timespec="seconds"),
        "caixa": {
            "tipo": janela.combo_tipo.currentData().name,
            "comprimento": janela.spin_comprimento.value(),
            "largura": janela.spin_largura.value(),
            "altura": janela.spin_altura.value(),
            "impressora": trechos(janela.linha_impressora),
            "riscador": trechos(janela.linha_riscador),
        },
        "cores": [nome for nome, (chip, _rgb) in janela._chips_cor.items() if chip.isChecked()],
        "faca": {
            "editada": canvas.faca_editada,
            "linhas": [_linha(l) for l in canvas.linhas_faca()] if canvas.faca_editada else [],
            "pagina_pela_faca": bool(getattr(canvas, "_pagina_pela_faca", False)),
            "do_zero": bool(getattr(janela, "_faca_do_zero", False)),
            "estilo": [estilo_atual[0], estilo_atual[1]] if estilo_atual else None,
            "dobras_estilo": [
                [d.x1, d.y1, d.x2, d.y2, d.angulo, d.inicio, d.fim] for d in dobras_estilo
            ] if dobras_estilo else None,
            "base_estilo": list(base_estilo) if base_estilo else None,
        },
        "dobras_3d": {
            "angulos": {str(k): v for k, v in (getattr(janela, "_angulos_dobra", None) or {}).items()},
            "face_base": getattr(janela, "_face_base_3d", None),
        },
        "papelao_mm": janela.visualizacao_3d.vista.espessura,
        "elementos": elementos,
        "aprovacao": dict(getattr(janela, "_aprovacao", {}) or {}),
    }
    if com_arquivos:
        dados["arquivos"] = arquivos.dados
    else:
        dados["arquivos"] = sorted(arquivos.dados)  # só os ids (pra comparar se mudou)
        dados.pop("salvo_em")
    return dados


# ── Recuperação (cópia automática) ──────────────────────────────────
INTERVALO_RECUPERACAO_MS = 2 * 60 * 1000


def pasta_recuperacao() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "recuperacao"


def salvar_recuperacao(janela, caminho_original: str | None) -> Path:
    """Cópia do projeto aberto na pasta de recuperação (uma só, sobrescrita),
    com o caminho do arquivo de verdade dentro — pra voltar pro lugar certo."""
    pasta = pasta_recuperacao()
    pasta.mkdir(parents=True, exist_ok=True)
    dados = estado_da_janela(janela)
    dados["recuperacao"] = {"caminho_original": caminho_original}
    destino = pasta / f"recuperacao{EXTENSAO}"
    temporario = destino.with_name(destino.name + ".salvando")
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    temporario.replace(destino)
    return destino


def recuperacao_pendente() -> Path | None:
    destino = pasta_recuperacao() / f"recuperacao{EXTENSAO}"
    return destino if destino.is_file() else None


def apagar_recuperacao() -> None:
    destino = pasta_recuperacao() / f"recuperacao{EXTENSAO}"
    destino.unlink(missing_ok=True)


def assinatura(janela) -> str:
    """Resumo do estado (sem o conteúdo dos arquivos embutidos): igual ao
    do último salvar = nada a salvar."""
    return hashlib.sha1(json.dumps(estado_da_janela(janela, com_arquivos=False), sort_keys=True).encode()).hexdigest()


def salvar(janela, caminho: str | Path) -> Path:
    caminho = Path(caminho)
    if caminho.suffix.lower() != EXTENSAO:
        caminho = caminho.with_name(caminho.name + EXTENSAO)
    texto = json.dumps(estado_da_janela(janela), ensure_ascii=False, indent=1)
    temporario = caminho.with_name(caminho.name + ".salvando")
    temporario.write_text(texto, encoding="utf-8")
    temporario.replace(caminho)  # nunca deixa o arquivo pela metade se algo falhar no meio
    return caminho


def ler(caminho: str | Path) -> dict:
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ErroProjeto(f"Não consegui ler o arquivo:\n{exc}") from exc
    if not isinstance(dados, dict) or dados.get("formato") != "autoline":
        raise ErroProjeto("Esse arquivo não é um projeto do Autoline.")
    if int(dados.get("versao", 0)) > VERSAO:
        raise ErroProjeto("Esse projeto foi salvo numa versão mais nova do Autoline. Atualize o programa pra abrir.")
    return dados


def aplicar_na_janela(janela, dados: dict) -> list[str]:
    """Troca o projeto aberto pelo do arquivo. Devolve avisos (ex.: objeto
    de tipo desconhecido, pulado)."""
    avisos: list[str] = []
    canvas = janela.canvas
    caixa = dados["caixa"]

    # Limpa o projeto atual.
    for el in list(canvas.elementos_mockup):
        canvas._retirar_elemento(el)
    canvas.definir_layout(None)
    canvas._linhas_editadas = None

    # Caixa e medidas (sem recalcular a cada campo).
    controles = [janela.combo_tipo, janela.spin_comprimento, janela.spin_largura, janela.spin_altura]
    for c in controles:
        c.blockSignals(True)
    try:
        janela.combo_tipo.setCurrentIndex(max(0, janela.combo_tipo.findData(TipoCaixa[caixa["tipo"]])))
        janela.spin_comprimento.setValue(float(caixa["comprimento"]))
        janela.spin_largura.setValue(float(caixa["largura"]))
        janela.spin_altura.setValue(float(caixa["altura"]))
    finally:
        for c in controles:
            c.blockSignals(False)
    janela._ao_trocar_tipo()  # rótulos/trechos do tipo + recalcula
    for linha, valores in ((janela.linha_impressora, caixa["impressora"]), (janela.linha_riscador, caixa["riscador"])):
        linha.definir_valores_manuais(valores)
    ativas = set(dados.get("cores", []))
    for nome, (chip, _rgb) in janela._chips_cor.items():
        chip.blockSignals(True)
        chip.setChecked(nome in ativas)
        chip.blockSignals(False)
        janela._repintar_chip_cor(chip, _rgb, nome in ativas)
    janela._recalcular()

    # Faca.
    faca = dados.get("faca", {})
    janela._faca_do_zero = bool(faca.get("do_zero", False))
    estilo = faca.get("estilo")
    janela._estilo_atual = (estilo[0], dict(estilo[1])) if estilo else None
    from ..estilos import DobraDoEstilo as _Dobra

    janela._dobras_estilo = [_Dobra(*map(float, d[:5]), float(d[5]), float(d[6])) for d in faca["dobras_estilo"]] if faca.get("dobras_estilo") else None
    janela._base_estilo = tuple(faca["base_estilo"]) if faca.get("base_estilo") else None
    if faca.get("editada"):
        canvas._definir_linhas_editadas([_linha_de(v) for v in faca["linhas"]])
        canvas.definir_pagina_pela_faca(bool(faca.get("pagina_pela_faca", False)))
    else:
        canvas._definir_linhas_editadas(None)
    janela._assinatura_faca_3d = (
        tuple((l.x1, l.y1, l.x2, l.y2, l.tipo, l.bojo) for l in canvas.linhas_faca()) if canvas.faca_editada else None
    )

    # Objetos do Layout.
    arquivos = _Arquivos(dados.get("arquivos"))
    for d in dados.get("elementos", []):
        el = _montar_na_cena(canvas, d, arquivos, avisos)
        del el

    # Folha de aprovação (cliente, referência, código e datas).
    janela._aprovacao = dict(dados.get("aprovacao") or {})

    # 3D.
    dobras = dados.get("dobras_3d", {})
    janela._angulos_dobra = {int(k): float(v) for k, v in dobras.get("angulos", {}).items()}
    janela._face_base_3d = dobras.get("face_base")
    if "papelao_mm" in dados:
        janela.visualizacao_3d.definir_espessura(float(dados["papelao_mm"]))
    janela._atualizar_modelo_3d()

    canvas.pilha_desfazer.clear()
    canvas.ajustar_a_tela()
    return avisos


def _montar_na_cena(canvas, d: dict, arquivos: _Arquivos, avisos: list[str]):
    el = _criar_na_cena(canvas, d, arquivos, avisos, QPointF(0.0, 0.0))
    if el is not None:
        canvas._registrar_elemento_mockup(el)
    return el


def _criar_na_cena(canvas, d: dict, arquivos: _Arquivos, avisos: list[str], origem: QPointF):
    """O elemento já na cena (sem cadastrar no canvas: filho de grupo não é
    cadastrado, como no `agrupar_selecionados`). `origem` = posição do
    grupo-pai (os filhos são salvos em coordenadas do grupo)."""
    if d.get("tipo") == "GrupoMockup":
        g = d["geometria"]
        pos_grupo = origem + _ponto_de(g["pos"])
        pares = [(_criar_na_cena(canvas, x, arquivos, avisos, pos_grupo), x) for x in d.get("elementos", [])]
        pares = [(f, x) for f, x in pares if f is not None]
        if not pares:
            return None
        grupo = GrupoMockup([f for f, _x in pares])
        # Reposiciona exatamente como estava (o agrupar acha a caixa pelos filhos).
        grupo.setPos(pos_grupo)
        for f, x in pares:
            f.setPos(_ponto_de(x["geometria"]["pos"]))
        grupo.setRotation(float(g.get("rotacao", 0.0)))
        grupo.definir_painel(g.get("painel"))
        grupo.setZValue(float(g.get("z", 0.0)))
        return grupo
    try:
        el = elemento_de_dict(d, arquivos)
    except (KeyError, ValueError, TypeError) as exc:
        avisos.append(f"Um objeto ({d.get('tipo', '?')}) não abriu: {exc}")
        return None
    if el is None:
        avisos.append(f"Tipo de objeto desconhecido, pulado: {d.get('tipo', '?')}")
        return None
    pos = el.pos() + origem
    canvas.cena.addItem(el)
    el.setPos(pos)
    return el
