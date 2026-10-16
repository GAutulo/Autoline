"""Barra de propriedades do elemento de mockup selecionado — uma
"property bar" horizontal (ver `_montar_barra_propriedades_mockup` em
main_window.py), no mesmo espírito da barra de propriedades contextual
de qualquer CAD/vetorial de verdade (CorelDRAW, Illustrator): fica logo
abaixo da barra de criar elemento, muda de conteúdo conforme o tipo do
elemento selecionado, e cada controle é um ÍCONE (com tooltip), não um
rótulo de texto — pedido explícito do usuário ("esse painel de
propriedades deveria ficar em cima separado por ícones igual é em
outros CAD... texto = ícone de uma letra, alinhamento = ícone de um
objeto com uma linha no local que será alinhado"). Fica vazia quando
não há seleção ou há mais de um elemento selecionado — editar
propriedade de vários de uma vez não é um caso coberto ainda.
"""

from __future__ import annotations

import warnings
from typing import Callable

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFontComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..models import CorImpressao
from ..paineis import Painel
from . import configuracoes
from .dialogo_tabela import DialogoTabela
from .estilo import Cor
from .mockup_acabamento import ElementoAcabamento, TipoAcabamento
from .mockup_callout import ElementoCallout
from .mockup_checklist import DISPOSICOES, ElementoChecklistCores
from .mockup_cota import ElementoCota
from .mockup_cota_angular import ElementoCotaAngular
from .mockup_curva import ElementoCurva
from .mockup_formas import ElementoElipse, ElementoLinha, ElementoPoligono, ElementoRetangulo
from .mockup_icones import TAMANHO_ICONE, construir_icone
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_simbolos import ElementoSimbolo, TipoSimbolo
from .mockup_tabela import ElementoTabela
from .mockup_texto import ElementoTexto

_ROTULO_SEM_PAINEL = "Nenhum"

_FONTES_DISPONIVEIS = ["Arial", "Arial Black", "Verdana", "Times New Roman", "Impact"]

NOME_TIPO_ELEMENTO: dict[type, str] = {
    ElementoTexto: "Texto",
    ElementoRetangulo: "Retângulo",
    ElementoElipse: "Elipse",
    ElementoPoligono: "Polígono",
    ElementoLinha: "Linha",
    ElementoCallout: "Callout",
    ElementoTabela: "Tabela",
    ElementoAcabamento: "Acabamento de produção",
    ElementoSimbolo: "Símbolo de manuseio",
    ElementoImagem: "Imagem",
    ElementoLogoVetorial: "Logotipo vetorial",
    ElementoChecklistCores: "Checklist de cores",
    GrupoMockup: "Grupo",
    ElementoCota: "Cota",
    ElementoCurva: "Curva",
    ElementoCotaAngular: "Cota angular",
}


class PainelPropriedadesMockup(QWidget):
    def __init__(
        self,
        obter_tintas_disponiveis: Callable[[], list[CorImpressao]],
        obter_paineis_disponiveis: Callable[[], list[Painel]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._obter_tintas = obter_tintas_disponiveis
        self._obter_paineis = obter_paineis_disponiveis
        self._elemento: ElementoMockup | None = None
        # Só o elemento cujo sinal foi de fato ligado — desligar um que não
        # foi (troca de seleção no meio da montagem da barra) gerava aviso.
        self._elemento_conectado: ElementoMockup | None = None
        self._modo_multiplo = False
        self._spins_geometria: dict[str, QDoubleSpinBox] = {}
        self._rotulo_posicao_painel: QLabel | None = None

        # Callbacks ligados de fora (main_window.py) — este painel não
        # sabe mexer na cena/canvas, só nas propriedades do próprio
        # elemento, então ações que afetam a cena (remover, reabrir o
        # diálogo de separação de cor) sobem por aqui.
        self.remover_solicitado: Callable[[], None] | None = None
        self.remapear_logo_solicitado: Callable[[ElementoLogoVetorial], None] | None = None
        self.alinhar_multiplos_solicitado: Callable[[str], None] | None = None
        self.remover_multiplos_solicitado: Callable[[], None] | None = None
        self.modelar_solicitado: Callable[[str], None] | None = None
        # Tamanho da página (chapa da dieline) em mm, pro estado "nada
        # selecionado" da barra — ligado de fora, como os callbacks acima.
        self.obter_tamanho_pagina: Callable[[], tuple[float, float] | None] | None = None

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(2, 0, 2, 0)
        raiz.setSpacing(8)

        self._rotulo_vazio = QLabel("Nada selecionado")
        self._rotulo_vazio.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};")
        raiz.addWidget(self._rotulo_vazio)

        self._rotulo_tipo = QLabel()
        self._rotulo_tipo.setStyleSheet("font-weight: 700;")
        self._rotulo_tipo.setVisible(False)
        raiz.addWidget(self._rotulo_tipo)

        self._container_campos = QWidget()
        self._layout_campos = QHBoxLayout(self._container_campos)
        self._layout_campos.setContentsMargins(0, 0, 0, 0)
        self._layout_campos.setSpacing(5)
        self._container_campos.setVisible(False)
        raiz.addWidget(self._container_campos)

        raiz.addStretch(1)

        self._botao_remover = QToolButton()
        self._botao_remover.setObjectName("botaoIconePropriedade")
        self._botao_remover.setIcon(construir_icone("remover"))
        self._botao_remover.setToolTip("Remover elemento")
        self._botao_remover.setVisible(False)
        self._botao_remover.clicked.connect(self._ao_clicar_remover)
        raiz.addWidget(self._botao_remover)

    # ── Peça básica: ícone + widget lado a lado, sem rótulo de texto ──
    def _grupo(self, tipo_icone: str, widget: QWidget, tooltip: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        icone = QLabel()
        icone.setObjectName("iconeCampoPropriedade")
        icone.setPixmap(construir_icone(tipo_icone).pixmap(TAMANHO_ICONE, TAMANHO_ICONE))
        icone.setToolTip(tooltip)
        widget.setToolTip(tooltip)
        layout.addWidget(icone)
        layout.addWidget(widget)
        self._layout_campos.addWidget(container)
        return container

    def _botao_icone(self, tipo_icone: str, tooltip: str, checkable: bool = False) -> QToolButton:
        botao = QToolButton()
        botao.setObjectName("botaoIconePropriedade")
        botao.setIcon(construir_icone(tipo_icone))
        botao.setToolTip(tooltip)
        botao.setCheckable(checkable)
        self._layout_campos.addWidget(botao)
        return botao

    def _separador(self, forte: bool = False) -> QFrame:
        """`forte=True` só na fronteira mais importante de escanear: onde
        os campos universais (geometria/painel, sempre presentes) acabam e
        os campos do TIPO selecionado começam (ver `definir_elemento`) —
        um respiro maior aqui ajuda a olhar "o que muda a cada seleção" de
        relance, sem precisar virar cards cheios (achado numa revisão de
        UI/UX: a barra inteira troca de conteúdo a cada seleção, então não
        dá pra aprender "onde fica cada coisa" com o tempo só de cor)."""
        if forte:
            self._layout_campos.addSpacing(4)
        linha = QFrame()
        linha.setFrameShape(QFrame.Shape.VLine)
        linha.setFrameShadow(QFrame.Shadow.Sunken)
        if forte:
            linha.setObjectName("separadorForte")
        self._layout_campos.addWidget(linha)
        if forte:
            self._layout_campos.addSpacing(4)
        return linha

    def _ao_clicar_remover(self) -> None:
        if self._modo_multiplo:
            if self.remover_multiplos_solicitado is not None:
                self.remover_multiplos_solicitado()
        elif self.remover_solicitado is not None:
            self.remover_solicitado()

    # ── API pública ─────────────────────────────────────────────────
    def _desconectar_elemento(self) -> None:
        elemento, self._elemento_conectado = self._elemento_conectado, None
        if elemento is None:
            return
        # Na destruição da janela o Qt ainda emite troca de seleção; aí o
        # desligamento pode falhar só com aviso (não exceção) — inofensivo.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                elemento.geometria_alterada.disconnect(self._atualizar_campos_geometria)
            except (TypeError, RuntimeError):
                pass

    def definir_elemento(self, elemento: ElementoMockup | None) -> None:
        self._modo_multiplo = False
        # Desliga o elemento ANTERIOR antes de trocar — sem isso, quando
        # ele mudasse de novo (ex.: desfazer), o sinal ia atualizar
        # spinboxes já destruídos com a barra (ver `_limpar_barra`).
        self._desconectar_elemento()

        self._elemento = elemento
        self._spins_geometria = {}
        self._rotulo_posicao_painel = None
        self._limpar_barra()

        if elemento is None:
            self._rotulo_vazio.setVisible(False)
            self._rotulo_tipo.setVisible(False)
            self._botao_remover.setVisible(False)
            self._montar_estado_sem_selecao()
            self._container_campos.setVisible(True)
            return

        self._rotulo_vazio.setVisible(False)
        self._rotulo_tipo.setText(NOME_TIPO_ELEMENTO.get(type(elemento), "Elemento"))
        self._rotulo_tipo.setVisible(True)
        self._container_campos.setVisible(True)
        self._botao_remover.setVisible(True)

        self._montar_campos_geometria(elemento)
        self._separador()
        self._montar_campos_painel(elemento)
        self._separador(forte=True)

        if isinstance(elemento, ElementoTexto):
            self._montar_campos_texto(elemento)
        elif isinstance(elemento, ElementoChecklistCores):
            self._montar_campos_checklist(elemento)
        elif isinstance(elemento, ElementoRetangulo):
            self._montar_campos_retangulo(elemento)
        elif isinstance(elemento, ElementoElipse):
            self._montar_campos_elipse(elemento)
        elif isinstance(elemento, ElementoPoligono):
            self._montar_campos_poligono(elemento)
        elif isinstance(elemento, ElementoLinha):
            self._montar_campos_linha(elemento)
        elif isinstance(elemento, ElementoCota):
            self._montar_campos_cota(elemento)
        elif isinstance(elemento, ElementoCotaAngular):
            self._montar_campos_cota_angular(elemento)
        elif isinstance(elemento, ElementoCurva):
            self._montar_campos_retangulo(elemento)  # mesmos campos: preenchido, traço e tinta
        elif isinstance(elemento, ElementoCallout):
            self._montar_campos_callout(elemento)
        elif isinstance(elemento, ElementoTabela):
            self._montar_campos_tabela(elemento)
        elif isinstance(elemento, ElementoAcabamento):
            self._montar_campos_acabamento(elemento)
        elif isinstance(elemento, ElementoSimbolo):
            self._montar_campos_simbolo(elemento)
        elif isinstance(elemento, ElementoLogoVetorial):
            self._montar_campos_logo(elemento)
        elif isinstance(elemento, ElementoImagem):
            nome = QLabel(getattr(elemento, "nome_original", None) or elemento.caminho_arquivo.rsplit("\\", 1)[-1])
            nome.setMaximumWidth(160)
            nome.setToolTip(elemento.caminho_arquivo)
            self._layout_campos.addWidget(nome)
        elif isinstance(elemento, GrupoMockup):
            aviso = QLabel("Sem aparência própria")
            aviso.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};")
            aviso.setToolTip("Grupo não tem aparência própria — edite os elementos individualmente.")
            self._layout_campos.addWidget(aviso)

        elemento.geometria_alterada.connect(self._atualizar_campos_geometria)
        self._elemento_conectado = elemento

    def _montar_estado_sem_selecao(self) -> None:
        """Barra de propriedades sem nada selecionado, como no CorelDRAW:
        tamanho da página, unidade e as distâncias de deslocamento
        (setas) e de duplicação (Ctrl+D) — que aqui são as mesmas
        preferências de Configurações > Ferramentas."""
        tamanho = self.obter_tamanho_pagina() if self.obter_tamanho_pagina is not None else None
        texto = "Chapa —" if tamanho is None else f"Chapa  {tamanho[0]:.1f} × {tamanho[1]:.1f} mm".replace(".", ",")
        rotulo = QLabel(texto)
        rotulo.setObjectName("rotuloPaginaPropriedade")
        rotulo.setStyleSheet("font-weight: 700;")
        rotulo.setToolTip("Tamanho da página — a chapa da dieline")
        self._layout_campos.addWidget(rotulo)
        unidade = QLabel("Unidade: mm")
        unidade.setStyleSheet(f"color: {Cor.TEXTO_SECUNDARIO};")
        self._layout_campos.addWidget(unidade)
        self._separador()

        normal, com_shift = configuracoes.passo_nudge_mm()

        def spin(valor: float, maximo: float) -> QDoubleSpinBox:
            campo = QDoubleSpinBox()
            campo.setRange(0.01, maximo)
            campo.setDecimals(2)
            campo.setSuffix(" mm")
            campo.setValue(valor)
            campo.setMaximumWidth(84)
            campo.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            campo.setKeyboardTracking(False)
            return campo

        spin_nudge = spin(normal, 100.0)
        spin_nudge.setObjectName("spinDeslocamento")
        spin_super = spin(com_shift, 1000.0)
        spin_super.setObjectName("spinSuperDeslocamento")
        spin_nudge.valueChanged.connect(lambda v: configuracoes.definir_passo_nudge_mm(v, spin_super.value()))
        spin_super.valueChanged.connect(lambda v: configuracoes.definir_passo_nudge_mm(spin_nudge.value(), v))
        self._grupo("x", spin_nudge, "Deslocamento com as setas (Ctrl+seta = um décimo)")
        self._grupo("largura", spin_super, "Super deslocamento (Shift+seta)")

        spin_duplicar = spin(configuracoes.passo_duplicar_mm(), 1000.0)
        spin_duplicar.setObjectName("spinDistanciaDuplicar")
        spin_duplicar.valueChanged.connect(configuracoes.definir_passo_duplicar_mm)
        self._grupo("mais", spin_duplicar, "Distância de duplicação (Ctrl+D e colar)")

    def definir_selecao_multipla(self, quantidade: int) -> None:
        """Estado intermediário entre "nada selecionado" (`definir_elemento(None)`)
        e "um elemento selecionado" — antes, selecionar vários elementos
        só deixava a barra inteira vazia (editar vários de uma vez não
        era um caso coberto), o que na prática parecia "não dá pra
        selecionar mais de um item", já que não tinha nenhum jeito de ver
        OU agir sobre a seleção múltipla. Não tenta editar propriedade
        (fonte, cor...) de vários — só alinhar/remover, os dois únicos
        casos que fazem sentido pra um grupo heterogêneo de elementos."""
        self._modo_multiplo = True
        # Desliga o elemento ANTERIOR antes de trocar — sem isso, quando
        # ele mudasse de novo (ex.: desfazer), o sinal ia atualizar
        # spinboxes já destruídos com a barra (ver `_limpar_barra`).
        self._desconectar_elemento()
        self._elemento = None
        self._spins_geometria = {}
        self._rotulo_posicao_painel = None
        self._limpar_barra()

        self._rotulo_vazio.setVisible(False)
        self._rotulo_tipo.setText(f"{quantidade} selecionados")
        self._rotulo_tipo.setVisible(True)
        self._container_campos.setVisible(True)
        self._botao_remover.setVisible(True)

        disposicao = (
            ("alinhar_esquerda", "esquerda", "Alinhar bordas esquerdas entre si"),
            ("alinhar_centro_h", "centro_h", "Centralizar horizontalmente entre si"),
            ("alinhar_direita", "direita", "Alinhar bordas direitas entre si"),
            ("alinhar_topo", "topo", "Alinhar topos entre si"),
            ("alinhar_centro_v", "centro_v", "Centralizar verticalmente entre si"),
            ("alinhar_base", "base", "Alinhar bases entre si"),
        )
        for tipo_icone, alinhamento, tooltip in disposicao:
            botao = self._botao_icone(tipo_icone, tooltip)
            botao.clicked.connect(
                lambda _c=False, a=alinhamento: self.alinhar_multiplos_solicitado and self.alinhar_multiplos_solicitado(a)
            )

        # Modelar, como na barra de propriedades do CorelDRAW com vários
        # objetos selecionados (ver `modelagem.py`).
        self._separador(forte=True)
        for operacao, dica in (
            ("soldar", "Soldar — junta as formas numa só"),
            ("aparar", "Aparar — recorta o objeto de baixo com os de cima (os de cima ficam)"),
            ("intersecao", "Interseção — cria a forma da área em comum (os originais ficam)"),
            ("frente_menos_atras", "Frente menos atrás — o de cima menos os de baixo"),
            ("atras_menos_frente", "Atrás menos frente — o de baixo menos os de cima"),
        ):
            botao = self._botao_icone(f"modelar_{operacao}", dica)
            botao.setObjectName(f"modelar_{operacao}")
            botao.clicked.connect(lambda _c=False, op=operacao: self.modelar_solicitado and self.modelar_solicitado(op))

    # ── Posição/tamanho/rotação — comuns a todo elemento ──────────────
    def _montar_campos_geometria(self, elemento: ElementoMockup) -> None:
        campos = (
            ("x", "x", "Posição X", " mm", -100000.0, 100000.0),
            ("y", "y", "Posição Y", " mm", -100000.0, 100000.0),
            ("largura", "largura", "Largura", " mm", 0.1, 100000.0),
            ("altura", "altura", "Altura", " mm", 0.1, 100000.0),
            ("angulo", "angulo", "Ângulo de rotação", " °", -3600.0, 3600.0),
        )
        for chave, tipo_icone, tooltip, sufixo, minimo, maximo in campos:
            spin = QDoubleSpinBox()
            spin.setRange(minimo, maximo)
            spin.setDecimals(2)
            spin.setSuffix(sufixo)
            spin.setMaximumWidth(92)
            # Campo de texto sem setinhas, como na barra do CorelDRAW — as
            # setas comiam a largura e cortavam o número ("120,0(").
            spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            # Sem isso, `valueChanged` dispara a CADA TECLA digitada, não
            # só ao terminar — digitar "20" aplicava primeiro "2" (vira
            # "4" por causa do mínimo de 4mm), a tela atualizava o campo
            # PRA ESSE VALOR ERRADO no meio da digitação, e o "0" seguinte
            # continuava a partir do "4" em vez do "2" que a pessoa
            # realmente digitou — resultado "40" em vez de "20". Só
            # aplicar ao confirmar (Enter/Tab/perder o foco) resolve.
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda valor, c=chave: self._ao_editar_geometria(c, valor))
            self._spins_geometria[chave] = spin
            self._grupo(tipo_icone, spin, tooltip)

        # Fator de escala em %, como na barra do CorelDRAW: digitar 150 e
        # confirmar escala o objeto em 150% e o campo volta pra 100.
        for chave, tipo_icone, tooltip in (
            ("escala_l", "escala_l", "Escala da largura (%)"),
            ("escala_a", "escala_a", "Escala da altura (%)"),
        ):
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 10000.0)
            spin.setDecimals(0)
            spin.setSuffix(" %")
            spin.setValue(100.0)
            spin.setMaximumWidth(66)
            spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda valor, c=chave, s=spin: self._ao_editar_escala(c, valor, s))
            self._grupo(tipo_icone, spin, tooltip)

        botao_trava = self._botao_icone("trava", "Travar proporção largura/altura", checkable=True)
        botao_trava.setChecked(elemento.proporcao_travada)
        botao_trava.toggled.connect(elemento.definir_proporcao_travada)

        if not isinstance(elemento, GrupoMockup):
            botao_h = self._botao_icone("espelho_h", "Espelhar na horizontal", checkable=True)
            botao_h.setChecked(elemento.espelho_h)
            botao_v = self._botao_icone("espelho_v", "Espelhar na vertical", checkable=True)
            botao_v.setChecked(elemento.espelho_v)
            botao_h.toggled.connect(lambda marcado: elemento.definir_espelho(marcado, elemento.espelho_v))
            botao_v.toggled.connect(lambda marcado: elemento.definir_espelho(elemento.espelho_h, marcado))

        self._atualizar_campos_geometria()

    def _ao_editar_escala(self, chave: str, valor: float, spin: QDoubleSpinBox) -> None:
        elemento = self._elemento
        if elemento is not None and valor != 100.0:
            fator = valor / 100.0
            largura, altura = elemento.largura, elemento.altura
            if elemento.proporcao_travada:
                nova = (largura * fator, altura * fator)
            elif chave == "escala_l":
                nova = (largura * fator, altura)
            else:
                nova = (largura, altura * fator)
            # Escala em torno do centro (ponto de referência padrão do
            # CorelDRAW): a origem de transformação é o centro, então
            # basta compensar a meia diferença de tamanho na posição.
            pos = elemento.pos()
            elemento.definir_tamanho(*nova)
            elemento.setPos(
                pos.x() + (largura - elemento.largura) / 2, pos.y() + (altura - elemento.altura) / 2
            )
        spin.blockSignals(True)
        spin.setValue(100.0)
        spin.blockSignals(False)

    def _atualizar_campos_geometria(self) -> None:
        """Reflete a geometria atual do elemento nos campos — chamado na
        montagem E toda vez que `geometria_alterada` dispara (arrastar,
        redimensionar ou girar na tela, ver `mockup_itens.py`), pra não
        deixar os números desatualizados enquanto o usuário edita pelo
        canvas em vez de pelos campos."""
        elemento = self._elemento
        if elemento is None or not self._spins_geometria:
            return
        valores = {
            "x": elemento.pos().x(),
            "y": elemento.pos().y(),
            "largura": elemento.largura,
            "altura": elemento.altura,
            "angulo": elemento.rotation(),
        }
        for chave, valor in valores.items():
            spin = self._spins_geometria.get(chave)
            if spin is None:
                continue
            spin.blockSignals(True)  # senão setValue() aqui disparava _ao_editar_geometria de volta
            spin.setValue(valor)
            spin.blockSignals(False)
        self._atualizar_rotulo_posicao_painel()

    # ── Painel (face da caixa) + alinhamento ─────────────────────────
    def _montar_campos_painel(self, elemento: ElementoMockup) -> None:
        paineis = self._obter_paineis()
        combo = QComboBox()
        combo.setObjectName("comboPainel")  # pra achar de forma confiável (ex.: em teste), não por posição
        combo.setMaximumWidth(110)
        combo.addItem(_ROTULO_SEM_PAINEL, None)
        indice_atual = 0
        for i, painel in enumerate(paineis, start=1):
            combo.addItem(painel.nome, painel.id)
            if painel.id == elemento.painel_id:
                indice_atual = i
        combo.setCurrentIndex(indice_atual)
        self._grupo("face", combo, "Face da caixa a que este elemento pertence")

        disposicao = (
            ("alinhar_esquerda", "esquerda", "Alinhar à esquerda da face"),
            ("alinhar_centro_h", "centro_h", "Centralizar horizontalmente na face"),
            ("alinhar_direita", "direita", "Alinhar à direita da face"),
            ("alinhar_topo", "topo", "Alinhar ao topo da face"),
            ("alinhar_centro_v", "centro_v", "Centralizar verticalmente na face"),
            ("alinhar_base", "base", "Alinhar à base da face"),
        )
        # Um botão só com menu (em vez de 6 botões soltos) — a barra no
        # padrão CorelDRAW ganhou escala/espelhar e precisa caber.
        botao_alinhar = self._botao_icone("alinhar_centro_h", "Alinhar na face escolhida")
        botao_alinhar.setObjectName("botaoAlinharFace")
        botao_alinhar.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_alinhar = QMenu(botao_alinhar)
        for tipo_icone, alinhamento, tooltip in disposicao:
            acao = menu_alinhar.addAction(construir_icone(tipo_icone), tooltip)
            acao.triggered.connect(lambda _c=False, a=alinhamento: self._alinhar_ao_painel(a))
        botao_alinhar.setMenu(menu_alinhar)
        botoes: list[QToolButton] = [botao_alinhar]

        # Sempre ativo: sem face escolhida, alinhar usa a face onde o objeto
        # está (e ela passa a aparecer escolhida aqui).
        self._combo_painel = combo

        def atualizar_habilitado() -> None:
            for botao in botoes:
                botao.setEnabled(bool(paineis))

        def ao_mudar(_indice: int) -> None:
            elemento.definir_painel(combo.currentData())
            atualizar_habilitado()
            self._atualizar_rotulo_posicao_painel()

        combo.currentIndexChanged.connect(ao_mudar)
        atualizar_habilitado()

        # Leitura de onde o elemento está DENTRO da face escolhida — a
        # mesma pergunta que se faz olhando o desenho de perto ("está bem
        # no meio? quão perto da borda?"), só que em número. Barra
        # horizontal não tem espaço pra escrever isso sempre visível
        # (era um QLabel de texto no dock antigo) — vira ícone com
        # tooltip dinâmico, igual qualquer indicador de status de CAD.
        self._rotulo_posicao_painel = QLabel()
        self._rotulo_posicao_painel.setObjectName("iconeCampoPropriedade")
        self._rotulo_posicao_painel.setPixmap(construir_icone("medida").pixmap(TAMANHO_ICONE, TAMANHO_ICONE))
        self._layout_campos.addWidget(self._rotulo_posicao_painel)
        self._atualizar_rotulo_posicao_painel()

    _TOLERANCIA_CENTRALIZADO_MM = 0.5

    def _atualizar_rotulo_posicao_painel(self) -> None:
        """Distância das 4 bordas da face até o elemento, mais se está
        centralizado (dentro de uma tolerância pequena) em cada eixo —
        substitui ter que estimar isso olhando o desenho. Fica só no
        tooltip do ícone "medida" (ver `_montar_campos_painel`)."""
        rotulo = self._rotulo_posicao_painel
        if rotulo is None:
            return
        elemento = self._elemento
        painel = None
        if elemento is not None and elemento.painel_id is not None:
            painel = next((p for p in self._obter_paineis() if p.id == elemento.painel_id), None)
        if elemento is None or painel is None:
            rotulo.setToolTip("Posição na face: sem face escolhida.")
            return

        x, y = elemento.pos().x(), elemento.pos().y()
        esq = x - painel.x1
        dir_ = painel.x2 - (x + elemento.largura)
        topo = y - painel.y1
        base = painel.y2 - (y + elemento.altura)
        centralizado_h = abs(esq - dir_) <= self._TOLERANCIA_CENTRALIZADO_MM
        centralizado_v = abs(topo - base) <= self._TOLERANCIA_CENTRALIZADO_MM

        partes = [
            f"Esq. {esq:.1f} / Dir. {dir_:.1f} mm" + (" (centralizado H)" if centralizado_h else ""),
            f"Topo {topo:.1f} / Base {base:.1f} mm" + (" (centralizado V)" if centralizado_v else ""),
        ]
        rotulo.setToolTip("\n".join(partes))

    def _alinhar_ao_painel(self, alinhamento: str) -> None:
        elemento = self._elemento
        if elemento is None:
            return
        paineis = self._obter_paineis()
        painel = next((p for p in paineis if p.id == elemento.painel_id), None)
        if painel is None:
            # Sem face escolhida: a face onde está o centro do objeto (antes
            # o botão ficava cinza até escolher a face — parecia quebrado).
            centro = elemento.mapToScene(elemento.largura / 2, elemento.altura / 2)
            dentro = [p for p in paineis if p.x1 <= centro.x() <= p.x2 and p.y1 <= centro.y() <= p.y2]
            if not dentro:
                return
            painel = min(dentro, key=lambda p: p.largura * p.altura)
            combo = getattr(self, "_combo_painel", None)
            indice = combo.findData(painel.id) if combo is not None else -1
            if indice >= 0:
                combo.setCurrentIndex(indice)  # dispara definir_painel
            else:
                elemento.definir_painel(painel.id)

        x, y = elemento.pos().x(), elemento.pos().y()
        if alinhamento == "esquerda":
            x = painel.x1
        elif alinhamento == "direita":
            x = painel.x2 - elemento.largura
        elif alinhamento == "centro_h":
            x = painel.x1 + (painel.largura - elemento.largura) / 2
        elif alinhamento == "topo":
            y = painel.y1
        elif alinhamento == "base":
            y = painel.y2 - elemento.altura
        elif alinhamento == "centro_v":
            y = painel.y1 + (painel.altura - elemento.altura) / 2
        elemento.setPos(x, y)

    def _ao_editar_geometria(self, chave: str, valor: float) -> None:
        elemento = self._elemento
        if elemento is None:
            return
        if chave == "x":
            elemento.setPos(valor, elemento.pos().y())
        elif chave == "y":
            elemento.setPos(elemento.pos().x(), valor)
        elif chave == "largura":
            elemento.definir_largura(valor)
        elif chave == "altura":
            elemento.definir_altura(valor)
        elif chave == "angulo":
            elemento.setRotation(valor)

    # ── Construção dos campos por tipo ────────────────────────────────
    def _combo_de_fonte(self) -> QFontComboBox:
        """Um seletor de fonte só, reaproveitado: criar um `QFontComboBox`
        custa ~150 ms (lista e desenha todas as fontes instaladas) e ele era
        criado de novo a cada clique num texto — a seleção travava."""
        combo = getattr(self, "_combo_fonte_guardado", None)
        if combo is None:
            combo = QFontComboBox()
            combo.setMaximumWidth(170)
            self._combo_fonte_guardado = combo
        self._desligar_combo_fonte()
        return combo

    def _desligar_combo_fonte(self) -> None:
        """Solta o seletor de fonte do texto que estava selecionado antes."""
        slot = getattr(self, "_slot_fonte", None)
        if slot is not None:
            self._combo_fonte_guardado.currentFontChanged.disconnect(slot)
            self._slot_fonte = None

    def _limpar_barra(self) -> None:
        combo = getattr(self, "_combo_fonte_guardado", None)
        while self._layout_campos.count():
            item = self._layout_campos.takeAt(0)
            widget = item.widget()
            if widget is not None:
                if combo is not None and widget.isAncestorOf(combo):
                    # Tira o seletor de fonte antes de apagar o grupo dele.
                    self._desligar_combo_fonte()
                    combo.hide()
                    combo.setParent(self)
                # `takeAt` só desliga o item do LAYOUT — o widget continua
                # filho de `_container_campos` e visível na posição antiga
                # até o `deleteLater()` ser processado (evento adiado, não
                # imediato). Sem o `setParent(None)`, sobra widget "morto"
                # flutuando/sobrepondo o conteúdo novo por um instante toda
                # vez que troca de elemento — achado testando de verdade,
                # não só teórico (mostrava várias trava-de-proporção juntas
                # ao selecionar elementos em sequência rápida).
                # `hide()` ANTES de tirar o pai: o layout agenda um "mostrar
                # se não estiver escondido" pra cada widget que entra nele; se
                # a barra é refeita duas vezes no mesmo clique (seleção muda
                # 2x), esse aviso chegava com o widget já sem pai e ele
                # aparecia como janela solta piscando na tela. Escondido de
                # propósito, o Qt não mostra mais.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _combo_cor(self, cor_atual: CorImpressao, ao_mudar: Callable[[CorImpressao], None]) -> QComboBox:
        combo = QComboBox()
        indice_atual = 0
        for i, tinta in enumerate(self._obter_tintas()):
            combo.addItem(tinta.nome, tinta)
            if tinta.nome == cor_atual.nome:
                indice_atual = i
        combo.setObjectName("comboCorTinta")  # pra achar de forma confiável, não por posição
        combo.setMaximumWidth(100)
        combo.setCurrentIndex(indice_atual)
        # `currentData()` pode vir None em situações que não deviam
        # acontecer no fluxo normal (ex.: índice inválido) — guarda aqui
        # em vez de deixar propagar um `cor_tinta=None` pro elemento, que
        # derruba a próxima repintura (`self._cor_tinta.r` em cima de
        # `None`). Achado testando, não só teórico.
        combo.currentIndexChanged.connect(
            lambda _i: combo.currentData() is not None and ao_mudar(combo.currentData())
        )
        return combo

    def _linha_cor_tinta(self, cor_atual: CorImpressao, ao_mudar: Callable[[CorImpressao], None]) -> None:
        if self._obter_tintas():
            self._grupo("tinta", self._combo_cor(cor_atual, ao_mudar), "Cor de tinta")
        else:
            aviso = QLabel("Marque uma cor na legenda pra poder escolher aqui.")
            aviso.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};")
            self._layout_campos.addWidget(aviso)

    def _campo_espessura_traco(self, valor_atual: float, ao_mudar: Callable[[float], None]) -> None:
        spin = QDoubleSpinBox()
        spin.setRange(0.05, 20.0)
        spin.setDecimals(2)
        spin.setSuffix(" mm")
        spin.setMaximumWidth(78)
        spin.setValue(valor_atual)
        spin.setKeyboardTracking(False)  # mesmo motivo do campo de geometria — ver comentário lá
        spin.valueChanged.connect(ao_mudar)
        self._grupo("espessura", spin, "Espessura do traço")

    def _montar_campos_texto(self, el: ElementoTexto) -> None:
        # Como no CorelDRAW: o texto se edita no desenho (duplo clique ou
        # ferramenta Texto); aqui ficam fonte (todas as instaladas), tamanho
        # em pontos e negrito.
        combo_fonte = self._combo_de_fonte()
        combo_fonte.setCurrentFont(QFont(el.fonte_familia))
        self._slot_fonte = lambda fonte: el.definir_fonte(fonte.family())
        combo_fonte.currentFontChanged.connect(self._slot_fonte)
        self._grupo("fonte_aa", combo_fonte, "Fonte")
        combo_fonte.show()  # reaproveitado: estava escondido fora da barra

        tamanho = QDoubleSpinBox()
        tamanho.setRange(0.5, 2000.0)
        tamanho.setDecimals(1)
        tamanho.setSuffix(" pt")
        tamanho.setValue(el.tamanho_pt)
        tamanho.setKeyboardTracking(False)
        tamanho.setMaximumWidth(78)
        tamanho.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        tamanho.valueChanged.connect(el.definir_tamanho_pt)
        self._grupo("letra_a", tamanho, "Tamanho da fonte (pontos)")

        botao_negrito = self._botao_icone("negrito", "Negrito", checkable=True)
        botao_negrito.setChecked(el.negrito)
        botao_negrito.toggled.connect(el.definir_negrito)

        # Alinhamento das linhas do texto (como no CorelDRAW): esquerda,
        # centro, direita.
        self._separador()
        botoes_alinhamento = []
        for chave, icone, dica in (
            ("esquerda", "alinhar_esquerda", "Texto alinhado à esquerda"),
            ("centro", "alinhar_centro_h", "Texto centralizado"),
            ("direita", "alinhar_direita", "Texto alinhado à direita"),
        ):
            botao = self._botao_icone(icone, dica, checkable=True)
            botao.setObjectName(f"alinhar_texto_{chave}")
            botao.setChecked(el.alinhamento == chave)
            botoes_alinhamento.append((chave, botao))

        def escolher(chave_escolhida: str) -> None:
            el.definir_alinhamento(chave_escolhida)
            for chave, botao in botoes_alinhamento:
                botao.blockSignals(True)
                botao.setChecked(chave == chave_escolhida)
                botao.blockSignals(False)

        for chave, botao in botoes_alinhamento:
            botao.clicked.connect(lambda _c=False, c=chave: escolher(c))

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_retangulo(self, el: ElementoRetangulo) -> None:
        botao_preenchido = self._botao_icone("preenchido", "Preenchido", checkable=True)
        botao_preenchido.setChecked(el.preenchido)
        botao_preenchido.toggled.connect(el.definir_preenchido)

        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_linha(self, el: ElementoLinha) -> None:
        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_cota_angular(self, el: ElementoCotaAngular) -> None:
        valor = QLabel(el.texto_valor())
        valor.setStyleSheet("font-weight: 700;")
        valor.setToolTip("Ângulo medido — muda sozinho ao esticar a cota")
        el.geometria_alterada.connect(lambda: valor.setText(el.texto_valor()) if valor.parent() else None)
        self._layout_campos.addWidget(valor)
        for minimo, maximo, atual, ao_mudar, icone, dica in (
            (2.0, 500.0, el.raio, el.definir_raio, "angulo", "Raio do arco"),
            (0.5, 50.0, el.altura_texto, el.definir_altura_texto, "fonte_aa", "Altura do texto da cota"),
        ):
            campo = QDoubleSpinBox()
            campo.setRange(minimo, maximo)
            campo.setSuffix(" mm")
            campo.setValue(atual)
            campo.setKeyboardTracking(False)
            campo.setMaximumWidth(84)
            campo.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            campo.valueChanged.connect(ao_mudar)
            self._grupo(icone, campo, dica)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_cota(self, el: ElementoCota) -> None:
        valor = QLabel(el.texto_valor())
        valor.setStyleSheet("font-weight: 700;")
        valor.setToolTip("Medida — muda sozinha ao redimensionar a cota")
        el.geometria_alterada.connect(lambda: valor.setText(el.texto_valor()) if valor.parent() else None)
        self._layout_campos.addWidget(valor)
        afastamento = QDoubleSpinBox()
        afastamento.setRange(2.0, 500.0)
        afastamento.setSuffix(" mm")
        afastamento.setValue(el.afastamento)
        afastamento.setKeyboardTracking(False)
        afastamento.setMaximumWidth(84)
        afastamento.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        afastamento.valueChanged.connect(el.definir_afastamento)
        self._grupo("altura", afastamento, "Afastamento da linha de cota até os pontos medidos")
        texto = QDoubleSpinBox()
        texto.setRange(0.5, 50.0)
        texto.setSuffix(" mm")
        texto.setValue(el.altura_texto)
        texto.setKeyboardTracking(False)
        texto.setMaximumWidth(78)
        texto.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        texto.valueChanged.connect(el.definir_altura_texto)
        self._grupo("fonte_aa", texto, "Altura do texto da cota")
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_elipse(self, el: ElementoElipse) -> None:
        botao_preenchido = self._botao_icone("preenchido", "Preenchido", checkable=True)
        botao_preenchido.setChecked(el.preenchido)
        botao_preenchido.toggled.connect(el.definir_preenchido)

        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_poligono(self, el: ElementoPoligono) -> None:
        spin_lados = QSpinBox()
        spin_lados.setRange(3, 20)
        spin_lados.setValue(el.lados)
        spin_lados.setMaximumWidth(56)
        spin_lados.setKeyboardTracking(False)  # mesmo motivo do campo de geometria — ver comentário lá
        spin_lados.valueChanged.connect(el.definir_lados)
        self._grupo("ferramenta_poligono", spin_lados, "Número de lados")

        botao_preenchido = self._botao_icone("preenchido", "Preenchido", checkable=True)
        botao_preenchido.setChecked(el.preenchido)
        botao_preenchido.toggled.connect(el.definir_preenchido)

        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_callout(self, el: ElementoCallout) -> None:
        campo_texto = QLineEdit(el.texto)
        campo_texto.setMaximumWidth(160)
        campo_texto.textChanged.connect(el.definir_texto)
        self._grupo("letra_a", campo_texto, "Texto da anotação")

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_tabela(self, el: ElementoTabela) -> None:
        botao_editar = self._botao_icone("ferramenta_tabela", f"Editar tabela ({el.linhas}×{el.colunas})...")
        botao_editar.clicked.connect(lambda: self._abrir_dialogo_tabela(el, botao_editar))

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _abrir_dialogo_tabela(self, el: ElementoTabela, botao: QToolButton) -> None:
        dialogo = DialogoTabela(el.linhas, el.colunas, el.celulas, parent=self)
        if dialogo.exec() == DialogoTabela.DialogCode.Accepted:
            el.definir_dimensoes(dialogo.linhas(), dialogo.colunas())
            el.definir_celulas(dialogo.celulas())
            botao.setToolTip(f"Editar tabela ({el.linhas}×{el.colunas})...")

    def _montar_campos_acabamento(self, el: ElementoAcabamento) -> None:
        # Sem cor de tinta de propósito — acabamento de produção usa
        # sempre a mesma cor de marcação técnica (ver docstring do
        # módulo), não uma das tintas do trabalho.
        combo_tipo = QComboBox()
        combo_tipo.setMaximumWidth(150)
        for tipo in TipoAcabamento:
            combo_tipo.addItem(tipo.value, tipo)
        combo_tipo.setCurrentIndex(list(TipoAcabamento).index(el.tipo))
        combo_tipo.currentIndexChanged.connect(lambda _i: el.definir_tipo(combo_tipo.currentData()))
        self._grupo("ferramenta_transparencia", combo_tipo, "Tipo de acabamento")

    def _montar_campos_simbolo(self, el: ElementoSimbolo) -> None:
        combo_tipo = QComboBox()
        combo_tipo.setMaximumWidth(170)
        for tipo in TipoSimbolo:
            combo_tipo.addItem(tipo.value, tipo)
        combo_tipo.setCurrentIndex(list(TipoSimbolo).index(el.tipo))
        combo_tipo.currentIndexChanged.connect(lambda _i: el.definir_tipo(combo_tipo.currentData()))
        self._grupo("ferramenta_simbolo", combo_tipo, "Símbolo de manuseio/transporte")

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_checklist(self, el: ElementoChecklistCores) -> None:
        # Como um texto: fonte, tamanho em pontos e negrito; e o arranjo dos
        # itens. As cores se editam no desenho (duplo clique: uma por linha).
        combo_fonte = self._combo_de_fonte()
        combo_fonte.setCurrentFont(QFont(el.fonte_familia))
        self._slot_fonte = lambda fonte: el.definir_fonte(fonte.family())
        combo_fonte.currentFontChanged.connect(self._slot_fonte)
        self._grupo("fonte_aa", combo_fonte, "Fonte")
        combo_fonte.show()  # reaproveitado: estava escondido fora da barra

        tamanho = QDoubleSpinBox()
        tamanho.setRange(0.5, 2000.0)
        tamanho.setDecimals(1)
        tamanho.setSuffix(" pt")
        tamanho.setValue(el.tamanho_pt)
        tamanho.setKeyboardTracking(False)
        tamanho.setMaximumWidth(78)
        tamanho.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        tamanho.valueChanged.connect(el.definir_tamanho_pt)
        self._grupo("letra_a", tamanho, "Tamanho da letra (pontos)")

        altura = QDoubleSpinBox()
        altura.setRange(0.1, 500.0)
        altura.setDecimals(2)
        altura.setSuffix(" mm")
        altura.setValue(el.altura_letra_mm)
        altura.setKeyboardTracking(False)
        altura.setMaximumWidth(78)
        altura.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        altura.setObjectName("alturaLetraChecklist")

        def mudar_altura(mm: float) -> None:
            el.definir_altura_letra_mm(mm)
            tamanho.blockSignals(True)
            tamanho.setValue(el.tamanho_pt)
            tamanho.blockSignals(False)

        altura.valueChanged.connect(mudar_altura)
        tamanho.valueChanged.connect(lambda _pt: (altura.blockSignals(True), altura.setValue(el.altura_letra_mm), altura.blockSignals(False)))
        self._grupo("altura", altura, "Altura da letra (maiúscula), em mm — o padrão da máquina é 2 mm")

        largura = QDoubleSpinBox()
        largura.setRange(20.0, 200.0)
        largura.setDecimals(1)
        largura.setSuffix(" %")
        largura.setValue(el.largura_letra * 100)
        largura.setKeyboardTracking(False)
        largura.setMaximumWidth(70)
        largura.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        largura.setObjectName("larguraLetraChecklist")
        largura.valueChanged.connect(lambda v: el.definir_largura_letra(v / 100))
        self._grupo("largura", largura, "Largura das letras (100% = normal; 66,7% = meio esticada, o padrão da máquina)")

        botao_negrito = self._botao_icone("negrito", "Negrito", checkable=True)
        botao_negrito.setChecked(el.negrito)
        botao_negrito.toggled.connect(el.definir_negrito)

        disposicao = QComboBox()
        for chave, nome in DISPOSICOES.items():
            disposicao.addItem(nome, chave)
        disposicao.setCurrentIndex(max(0, disposicao.findData(el.disposicao)))
        disposicao.currentIndexChanged.connect(lambda _i: el.definir_disposicao(disposicao.currentData()))
        self._grupo("lista", disposicao, "Arranjo das cores: empilhadas ou lado a lado (quebra na largura da caixa)")

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_logo(self, el: ElementoLogoVetorial) -> None:
        # Uma tinta pro desenho todo (o normal num símbolo de manuseio) — ou
        # as cores do arquivo. A paleta da direita faz o mesmo.
        combo = QComboBox()
        combo.setObjectName("comboTintaLogo")
        combo.addItem("Cores originais", None)
        for tinta in self._obter_tintas():
            combo.addItem(tinta.nome, tinta)
        atual = el.tinta_unica
        if atual is not None:
            indice = combo.findText(atual.nome)
            if indice < 0:
                combo.addItem(atual.nome, atual)
                indice = combo.count() - 1
            combo.setCurrentIndex(indice)
        elif el.mapa_cores:
            combo.addItem("Separada por cor", "separada")
            combo.setCurrentIndex(combo.count() - 1)
        combo.setMaximumWidth(130)
        combo.currentIndexChanged.connect(
            lambda _i: combo.currentData() != "separada" and el.pintar_numa_tinta(combo.currentData())
        )
        self._grupo("tinta", combo, "Cor: o desenho todo numa tinta do trabalho (o branco continua branco), ou as cores do arquivo")
        botao = self._botao_icone("remapear", f"{len(el.cores_detectadas)} cor(es) no arquivo — separar cor a cor")
        botao.clicked.connect(lambda: self.remapear_logo_solicitado and self.remapear_logo_solicitado(el))
