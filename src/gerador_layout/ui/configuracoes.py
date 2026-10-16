"""Preferências do usuário, persistidas via QSettings (Windows: registro
em HKEY_CURRENT_USER — não precisa de arquivo de configuração próprio).

Módulo propositalmente sem dependência de nenhum outro módulo da UI
(`estilo.py` importa daqui, não o contrário) — evita import circular,
já que a paleta de cores em `estilo.py` precisa ler o tema salvo aqui
antes mesmo da UI existir.

Tema exige reiniciar o app pra valer (ver `estilo.py`): a paleta vira
literais de cor dentro de várias strings de QSS montadas na hora que
cada tela é construída — trocar o tema em tempo real exigiria reaplicar
isso tudo de novo em cada widget já criado, então mais simples e mais
confiável salvar a escolha e aplicar no próximo início."""

from __future__ import annotations

from PySide6.QtCore import QSettings

# Muda a chave de registro onde as preferências ficam salvas (rebranding
# Autoline) — quem já tinha aberto o app antes vai ver as preferências
# (tema, DPI, traço do vinco) voltarem ao padrão uma vez, não é bug: é
# uma chave nova, a antiga (sob "LayoutCorel") só fica órfã no registro.
_ORGANIZACAO = "Autoline"
_APLICATIVO = "Autoline"

TEMA_CLARO = "claro"
TEMA_ESCURO = "escuro"

_PADRAO_DPI_JPG = 300
# Mesmo valor que já estava fixo no código (DashLength=2/GapLength=3 a
# 1,0pt de espessura de linha — o padrão real confirmado pelo usuário
# comparando direto no CorelDRAW), só que agora em mm e editável.
_PADRAO_TRACO_VINCO_MM = 0.71
_PADRAO_ESPACO_VINCO_MM = 1.06
_PADRAO_ALTURA_LEGENDA_MM = 1.5

# Parâmetros de ferramenta do modo Layout — todos eram constante fixa no
# código até virarem preferência (ver `DialogoConfiguracoes`, aba
# "Ferramentas"); os valores aqui são exatamente os que já estavam
# hard-coded antes, preservados como padrão pra ninguém sentir a telinha
# mudar sozinha na primeira vez que abrir a versão nova.
_PADRAO_SNAP_ATIVO = True
_PADRAO_LIMIAR_SNAP_MM = 3.0
_PADRAO_PASSO_GRADE_MM = 10.0
_PADRAO_PASSO_NUDGE_MM = 1.0
_PADRAO_PASSO_NUDGE_SHIFT_MM = 10.0
_PADRAO_PASSO_DUPLICAR_MM = 6.0
_PADRAO_FONTE_TEXTO = "Arial Black"
# Padrão da máquina: letra de 2 mm de altura (maiúscula), na largura de 2/3
# da normal — a Arial Black "meio esticada" (18,28 mm de "GABINETE FLORA").
_PADRAO_ALTURA_LETRA_MM = 2.0
_PADRAO_LARGURA_LETRA = 0.667


def _settings() -> QSettings:
    # Formato padrão explícito (no app é o registro do Windows): o construtor
    # curto QSettings(org, app) sempre usa o registro e ignorava o .ini
    # temporário dos testes — rodar os testes mexia nas preferências reais.
    return QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, _ORGANIZACAO, _APLICATIVO)


def tema() -> str:
    return _settings().value("tema", TEMA_CLARO, type=str)


def definir_tema(nome: str) -> None:
    _settings().setValue("tema", nome)


def dpi_exportacao_jpg() -> int:
    return int(_settings().value("dpi_exportacao_jpg", _PADRAO_DPI_JPG, type=int))


def definir_dpi_exportacao_jpg(valor: int) -> None:
    _settings().setValue("dpi_exportacao_jpg", valor)


def traco_vinco_mm() -> tuple[float, float]:
    """(comprimento do traço, comprimento do espaço), em mm."""
    s = _settings()
    traco = float(s.value("traco_vinco_mm", _PADRAO_TRACO_VINCO_MM, type=float))
    espaco = float(s.value("espaco_vinco_mm", _PADRAO_ESPACO_VINCO_MM, type=float))
    return traco, espaco


def definir_traco_vinco_mm(traco: float, espaco: float) -> None:
    s = _settings()
    s.setValue("traco_vinco_mm", traco)
    s.setValue("espaco_vinco_mm", espaco)


def altura_legenda_mm() -> float:
    return float(_settings().value("altura_legenda_mm", _PADRAO_ALTURA_LEGENDA_MM, type=float))


def definir_altura_legenda_mm(valor: float) -> None:
    _settings().setValue("altura_legenda_mm", valor)


# ── Parâmetros de ferramenta (modo Layout) ─────────────────────────────
# Mesmo princípio do traço do vinco/legenda acima: lidos ao vivo (sem
# cache) no ponto de uso — ver `preview_canvas.py` — então uma mudança
# aqui já vale na próxima vez que a ferramenta for usada, sem reiniciar.


def espessura_papelao_mm() -> float:
    """Papelão do 3D (mm) — lembrado entre as sessões. Padrão 0,3 mm: onda B
    na escala 1:10 em que as caixas costumam ser desenhadas. 0 = folha fina."""
    s = _settings()
    valor = float(s.value("espessura_papelao_mm", 0.3, type=float))
    if not s.value("papelao_escala_1_10_revisto", False, type=bool):
        # Uma vez só: quem tinha ficado com um papelão de tamanho real (a
        # lista antiga misturava as escalas) passa pro mesmo papelão em 1:10.
        s.setValue("papelao_escala_1_10_revisto", True)
        if any(abs(valor - mm) < 1e-6 for mm in (1.5, 3.0, 4.0, 7.0)):
            valor = round(valor / 10, 3)
            s.setValue("espessura_papelao_mm", valor)
    return valor


def definir_espessura_papelao_mm(valor: float) -> None:
    _settings().setValue("espessura_papelao_mm", float(valor))


def giro_automatico_3d() -> bool:
    """Se a caixa montada fica girando sozinha no 3D (desligado: gastava o
    processador o tempo todo com a aba 3D aberta)."""
    return bool(_settings().value("giro_automatico_3d", False, type=bool))


def definir_giro_automatico_3d(ativo: bool) -> None:
    _settings().setValue("giro_automatico_3d", bool(ativo))


def snap_ativo_padrao() -> bool:
    """Se o encaixe (snap) começa LIGADO quando o app abre — só o estado
    inicial; o usuário ainda pode ligar/desligar na hora pelo menu Exibir
    (isso não fica salvo, é por sessão de propósito, igual a grade)."""
    return bool(_settings().value("snap_ativo_padrao", _PADRAO_SNAP_ATIVO, type=bool))


def definir_snap_ativo_padrao(ativo: bool) -> None:
    _settings().setValue("snap_ativo_padrao", ativo)


def limiar_snap_mm() -> float:
    """Distância (mm) dentro da qual uma borda/centro "gruda" num alvo de
    encaixe ao soltar o arrasto — maior valor gruda mais fácil (bom pra
    trabalho rápido/impreciso no mouse), menor valor exige chegar mais
    perto (bom pra ajuste fino sem grudar à toa)."""
    return float(_settings().value("limiar_snap_mm", _PADRAO_LIMIAR_SNAP_MM, type=float))


def definir_limiar_snap_mm(valor: float) -> None:
    _settings().setValue("limiar_snap_mm", valor)


def passo_grade_mm() -> float:
    """Espaçamento (mm) da grade de fundo do canvas — também um alvo de
    encaixe quando a grade está visível (ver menu Exibir)."""
    return float(_settings().value("passo_grade_mm", _PADRAO_PASSO_GRADE_MM, type=float))


def definir_passo_grade_mm(valor: float) -> None:
    _settings().setValue("passo_grade_mm", valor)


def passo_nudge_mm() -> tuple[float, float]:
    """(passo normal, passo com Shift) pra mover elemento selecionado
    pelas setas do teclado — o "ajuste fino" de precisão que complementa
    o arrasto com o mouse."""
    s = _settings()
    normal = float(s.value("passo_nudge_mm", _PADRAO_PASSO_NUDGE_MM, type=float))
    com_shift = float(s.value("passo_nudge_shift_mm", _PADRAO_PASSO_NUDGE_SHIFT_MM, type=float))
    return normal, com_shift


def definir_passo_nudge_mm(normal: float, com_shift: float) -> None:
    s = _settings()
    s.setValue("passo_nudge_mm", normal)
    s.setValue("passo_nudge_shift_mm", com_shift)


def passo_duplicar_mm() -> float:
    """Deslocamento (mm, nos 2 eixos) de cada cópia feita com Ctrl+D —
    efeito "cascata" pra não empilhar as cópias exatamente uma em cima
    da outra."""
    return float(_settings().value("passo_duplicar_mm", _PADRAO_PASSO_DUPLICAR_MM, type=float))


def definir_passo_duplicar_mm(valor: float) -> None:
    _settings().setValue("passo_duplicar_mm", valor)


def fonte_padrao_texto() -> str:
    """Família de fonte usada quando um elemento de Texto/Callout/checklist
    novo é criado — o usuário ainda troca por elemento depois, na barra de
    propriedades; isso só define o ponto de partida."""
    s = _settings()
    if not s.value("texto_padrao_maquina_revisto", False, type=bool):
        # Uma vez só: o padrão antigo (Arial) passa pro da máquina.
        s.setValue("texto_padrao_maquina_revisto", True)
        if s.value("fonte_padrao_texto", "", type=str) == "Arial":
            s.setValue("fonte_padrao_texto", _PADRAO_FONTE_TEXTO)
    return str(s.value("fonte_padrao_texto", _PADRAO_FONTE_TEXTO, type=str))


def altura_letra_padrao_mm() -> float:
    """Altura da letra (maiúscula) de texto e checklist novos, em mm."""
    return float(_settings().value("altura_letra_padrao_mm", _PADRAO_ALTURA_LETRA_MM, type=float))


def definir_altura_letra_padrao_mm(valor: float) -> None:
    _settings().setValue("altura_letra_padrao_mm", float(valor))


def largura_letra_padrao() -> float:
    """Largura das letras de texto e checklist novos (1 = normal da fonte;
    0,667 = o "meio esticado" que a máquina faz)."""
    return float(_settings().value("largura_letra_padrao", _PADRAO_LARGURA_LETRA, type=float))


def definir_largura_letra_padrao(valor: float) -> None:
    _settings().setValue("largura_letra_padrao", float(valor))


def definir_fonte_padrao_texto(nome: str) -> None:
    _settings().setValue("fonte_padrao_texto", nome)


_PADRAO_PASTA_IMAGENS = r"Z:\Imagens"


def pasta_imagens_layout() -> str:
    """Onde o JPG/PDF/SVG do layout é sugerido (vazio = a última usada).
    Padrão: a pasta de imagens da empresa (Z:, pasta Imagens) — se existir."""
    valor = _settings().value("pasta_imagens_layout", None)
    if valor is None:
        from pathlib import Path

        return _PADRAO_PASTA_IMAGENS if Path(_PADRAO_PASTA_IMAGENS).is_dir() else ""
    return str(valor)


def definir_pasta_imagens_layout(pasta: str) -> None:
    _settings().setValue("pasta_imagens_layout", pasta)


def pasta_imagens_3d() -> str:
    """Onde a imagem do 3D é sugerida (vazio = a última usada)."""
    return str(_settings().value("pasta_imagens_3d", "", type=str))


def definir_pasta_imagens_3d(pasta: str) -> None:
    _settings().setValue("pasta_imagens_3d", pasta)


def pasta_ultima(chave: str) -> str:
    """Última pasta usada pra `chave` ("projetos", "exportar", "imagem_3d")."""
    return str(_settings().value(f"pasta_ultima_{chave}", "", type=str))


def definir_pasta_ultima(chave: str, pasta: str) -> None:
    _settings().setValue(f"pasta_ultima_{chave}", pasta)


_PADRAO_PASTA_FOLHAS = "F:\\GUILHERME AUTULO\\APROVAÇÃO LAYOUTS"


def pasta_folhas_aprovacao() -> str:
    """Onde a folha de aprovação (PDF) é sugerida. Padrão: a pasta de
    aprovações de layout, se existir; senão a última usada."""
    valor = _settings().value("pasta_folhas_aprovacao", None)
    if valor is None:
        from pathlib import Path

        return _PADRAO_PASTA_FOLHAS if Path(_PADRAO_PASTA_FOLHAS).is_dir() else ""
    return str(valor)


def definir_pasta_folhas_aprovacao(pasta: str) -> None:
    _settings().setValue("pasta_folhas_aprovacao", pasta)


def logo_folha_aprovacao() -> str:
    """SVG/PNG do logotipo da empresa no cabeçalho da folha de aprovação."""
    return str(_settings().value("logo_folha_aprovacao", "", type=str))


def definir_logo_folha_aprovacao(caminho: str) -> None:
    _settings().setValue("logo_folha_aprovacao", caminho)


def desenvolvido_por() -> str:
    """Nome no "Desenvolvido por" da folha de aprovação."""
    return str(_settings().value("desenvolvido_por", "", type=str))


def definir_desenvolvido_por(nome: str) -> None:
    _settings().setValue("desenvolvido_por", nome)


def cores_personalizadas() -> list[tuple[str, tuple[int, int, int]]]:
    """Tintas criadas pelo usuário ("+ Nova cor" na legenda): nome e RGB."""
    import json

    try:
        lista = json.loads(_settings().value("cores_personalizadas", "[]", type=str) or "[]")
    except ValueError:
        return []
    return [(str(nome), (int(r), int(g), int(b))) for nome, r, g, b in lista]


def definir_cores_personalizadas(cores: list[tuple[str, tuple[int, int, int]]]) -> None:
    import json

    _settings().setValue("cores_personalizadas", json.dumps([[n, *rgb] for n, rgb in cores], ensure_ascii=False))


def projetos_recentes() -> list[str]:
    valor = _settings().value("projetos_recentes", [])
    if isinstance(valor, str):
        valor = [valor]
    return [str(v) for v in (valor or [])]


def adicionar_projeto_recente(caminho: str) -> None:
    lista = [c for c in projetos_recentes() if c.lower() != caminho.lower()]
    _settings().setValue("projetos_recentes", ([caminho] + lista)[:10])


def restaurar_padroes() -> None:
    s = _settings()
    s.setValue("dpi_exportacao_jpg", _PADRAO_DPI_JPG)
    s.setValue("traco_vinco_mm", _PADRAO_TRACO_VINCO_MM)
    s.setValue("espaco_vinco_mm", _PADRAO_ESPACO_VINCO_MM)
    s.setValue("altura_legenda_mm", _PADRAO_ALTURA_LEGENDA_MM)
    s.setValue("snap_ativo_padrao", _PADRAO_SNAP_ATIVO)
    s.setValue("limiar_snap_mm", _PADRAO_LIMIAR_SNAP_MM)
    s.setValue("passo_grade_mm", _PADRAO_PASSO_GRADE_MM)
    s.setValue("passo_nudge_mm", _PADRAO_PASSO_NUDGE_MM)
    s.setValue("passo_nudge_shift_mm", _PADRAO_PASSO_NUDGE_SHIFT_MM)
    s.setValue("passo_duplicar_mm", _PADRAO_PASSO_DUPLICAR_MM)
    s.setValue("fonte_padrao_texto", _PADRAO_FONTE_TEXTO)
    s.setValue("altura_letra_padrao_mm", _PADRAO_ALTURA_LETRA_MM)
    s.setValue("largura_letra_padrao", _PADRAO_LARGURA_LETRA)
