"""Barra de propriedades do elemento de mockup selecionado — uma
"property bar" horizontal (ver `_montar_barra_propriedades_mockup` em
main_window.py), no mesmo espírito da barra de propriedades contextual
de qualquer CAD/vetorial de verdade (CorelDRAW, Illustrator): fica logo
abaixo da barra de criar elemento, muda de conteúdo conforme o tipo do
elemento selecionado, e cada controle é um ÍCONE (com tooltip), não um
rótulo de texto — pedido explícito do usuário ("esse painel de
propriedades deveria ficar em cima separado por ícones igual é em
outros CAD... texto = ícone de uma letra, alinhamento = ícone de um
objeto com uma linha no local que será alinhado"). 
Arrumação (pedido do usuário: "odeio que esse espaço fique toda hora
alterando"): altura FIXA de uma linha; à esquerda, sempre no mesmo lugar,
o tipo do objeto e o que vale pra todo objeto (posição, tamanho, giro,
proporção, espelhar) — desabilitado quando não há o que editar, nunca
some; à direita, ABAS com o que é do tipo (Letra, Espaçamento, Posição...).
A aba escolhida fica lembrada por tipo de objeto.
"""

from __future__ import annotations

import warnings
from typing import Callable

from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QSizePolicy,
    QComboBox,
    QFontComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollArea,
    QSpinBox,
    QTabBar,
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


class _Paginas(QWidget):
    """As páginas das abas, uma à mostra. Não é um QStackedWidget porque ele
    mede pela MAIOR página (escondida inclusive) e a área rolava à toa."""

    def __init__(self) -> None:
        super().__init__()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._lista: list[QWidget] = []

    def addWidget(self, pagina: QWidget) -> None:  # noqa: N802
        pagina.setVisible(not self._lista)
        self._lista.append(pagina)
        self._layout.addWidget(pagina)

    def setCurrentIndex(self, indice: int) -> None:  # noqa: N802
        for i, pagina in enumerate(self._lista):
            pagina.setVisible(i == indice)

    def count(self) -> int:
        return len(self._lista)

    def widget(self, indice: int) -> QWidget:
        return self._lista[indice]

    def removeWidget(self, pagina: QWidget) -> None:  # noqa: N802
        self._lista.remove(pagina)
        self._layout.removeWidget(pagina)


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
        self.agrupar_solicitado: Callable[[], None] | None = None
        self.desagrupar_solicitado: Callable[[], None] | None = None
        self.desagrupar_tudo_solicitado: Callable[[], None] | None = None
        self.modelar_solicitado: Callable[[str], None] | None = None
        # Tamanho da página (chapa da dieline) em mm, pro estado "nada
        # selecionado" da barra — ligado de fora, como os callbacks acima.
        self.obter_tamanho_pagina: Callable[[], tuple[float, float] | None] | None = None
        # Desfazer do que se muda por esta barra (fonte, cor, letra...):
        # (elemento, foto antes, foto depois) — ver projeto_arquivo.foto_elemento.
        self.propriedades_alteradas: Callable[[ElementoMockup, dict, dict], None] | None = None
        self._foto_base: dict | None = None

        self._aba_por_tipo: dict[str, str] = {}
        self._chave_tipo = ""
        self._paginas_layout: list[QHBoxLayout] = []

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(4, 2, 4, 2)
        raiz.setSpacing(6)

        self._rotulo_tipo = QLabel("Nada selecionado")
        self._rotulo_tipo.setObjectName("rotuloTipoPropriedade")
        self._rotulo_tipo.setFixedWidth(120)  # largura fixa: o resto não anda ao trocar de objeto
        self._rotulo_tipo.setWordWrap(True)  # nome comprido ("Acabamento de produção") em 2 linhas
        raiz.addWidget(self._rotulo_tipo)

        # Fixo: o que vale pra todo objeto.
        self._fixo = QWidget()
        self._layout_campos = QHBoxLayout(self._fixo)
        self._layout_campos.setContentsMargins(0, 0, 0, 0)
        self._layout_campos.setSpacing(5)
        self._montar_fixo()
        raiz.addWidget(self._fixo)
        raiz.addWidget(self._linha_vertical(forte=True))

        # Abas com o que é do tipo do objeto.
        self._abas = QTabBar()
        self._abas.setObjectName("abasPropriedades")
        self._abas.setDrawBase(False)
        self._abas.setExpanding(False)
        self._abas.setUsesScrollButtons(False)
        self._abas.currentChanged.connect(self._ao_trocar_aba)
        self._paginas = _Paginas()
        # Abas + página na mesma área que rola: numa tela estreita rola, em
        # vez de forçar a janela a ficar mais larga que a tela.
        area = QWidget()
        linha_area = QHBoxLayout(area)
        linha_area.setContentsMargins(0, 0, 0, 0)
        linha_area.setSpacing(8)
        linha_area.addWidget(self._abas)
        linha_area.addWidget(self._paginas, 1)
        rolagem = QScrollArea()
        rolagem.setObjectName("rolagemPropriedades")
        rolagem.setWidget(area)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)
        rolagem.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        rolagem.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rolagem.setMinimumWidth(80)
        raiz.addWidget(rolagem, 1)

        self._botao_remover = QToolButton()
        self._botao_remover.setObjectName("botaoIconePropriedade")
        self._botao_remover.setIcon(construir_icone("remover"))
        self._botao_remover.setToolTip("Remover (Delete)")
        self._botao_remover.clicked.connect(self._ao_clicar_remover)
        raiz.addWidget(self._botao_remover)

        self.setFixedHeight(self._ALTURA)
        rolagem.setFixedHeight(self._ALTURA)
        self._definir_campos(None)

    _ALTURA = 44

    _largura_preferida = 0

    def definir_largura_preferida(self, largura: int) -> None:
        """A janela diz quanto sobra na linha de contexto (descontado o
        Organizar à direita) — ver `JanelaPrincipal._dividir_linha_de_contexto`."""
        if largura != self._largura_preferida:
            self._largura_preferida = largura
            self.updateGeometry()

    def sizeHint(self):  # noqa: N802
        """O que sobra na linha (nunca menos que o mínimo; as abas rolam)."""
        dica = super().sizeHint()
        dica.setWidth(max(self.minimumSizeHint().width(), self._largura_preferida))
        return dica

    def _linha_vertical(self, forte: bool = False) -> QFrame:
        linha = QFrame()
        linha.setFrameShape(QFrame.Shape.VLine)
        linha.setFrameShadow(QFrame.Shadow.Sunken)
        if forte:
            linha.setObjectName("separadorForte")
        return linha

    # ── Abas ─────────────────────────────────────────────────────────
    def _nova_aba(self, nome: str) -> None:
        """Os campos montados daqui em diante vão pra uma aba nova."""
        pagina = QWidget()
        layout = QHBoxLayout(pagina)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(5)
        self._paginas.addWidget(pagina)
        self._paginas_layout.append(layout)
        self._abas.blockSignals(True)
        self._abas.addTab(nome)
        self._abas.blockSignals(False)
        self._layout_campos = layout

    def _finalizar_abas(self, chave_tipo: str) -> None:
        for layout in self._paginas_layout:
            layout.addStretch(1)
        self._chave_tipo = chave_tipo
        nomes = [self._abas.tabText(i) for i in range(self._abas.count())]
        lembrada = self._aba_por_tipo.get(chave_tipo)
        indice = nomes.index(lembrada) if lembrada in nomes else 0
        self._abas.blockSignals(True)
        self._abas.setCurrentIndex(indice)
        self._abas.blockSignals(False)
        self._paginas.setCurrentIndex(indice)

    def _ao_trocar_aba(self, indice: int) -> None:
        if indice < 0:
            return
        self._paginas.setCurrentIndex(indice)
        self._aba_por_tipo[self._chave_tipo] = self._abas.tabText(indice)

    def mostrar_aba(self, nome: str) -> bool:
        for i in range(self._abas.count()):
            if self._abas.tabText(i) == nome:
                self._abas.setCurrentIndex(i)
                return True
        return False

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

    def _juntar_ultimos(self, quantidade: int) -> None:
        """Os últimos `quantidade` itens da barra num bloco só — botões que
        andam juntos (alinhamento, espelhar) não se separam quando a barra
        quebra de linha."""
        itens = [self._layout_campos.takeAt(self._layout_campos.count() - 1) for _ in range(quantidade)][::-1]
        bloco = QWidget()
        linha = QHBoxLayout(bloco)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(3)
        for item in itens:
            if item.widget() is not None:
                linha.addWidget(item.widget())
            elif item.spacerItem() is not None:
                linha.addSpacing(item.spacerItem().sizeHint().width())
        self._layout_campos.addWidget(bloco)

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

    # ── Desfazer das mudanças feitas por esta barra ─────────────────
    def _vigiar_campos(self) -> None:
        """Toda mudança feita por um campo da barra vira um passo de desfazer:
        tira a foto do objeto ao mostrá-lo e compara depois de cada edição.
        Ligado DEPOIS dos campos, então roda depois de o campo aplicar."""
        self.rebasear_foto()
        if self._elemento is None:
            return
        for w in self._paginas.findChildren(QWidget):
            for nome in ("valueChanged", "currentIndexChanged", "toggled", "editingFinished", "clicked", "currentFontChanged"):
                sinal = getattr(w, nome, None)
                if sinal is not None and hasattr(sinal, "connect"):
                    sinal.connect(self._conferir_mudanca)

    def rebasear_foto(self) -> None:
        """O objeto mudou por fora (desfazer, arrasto no canvas): nova foto-base."""
        from .projeto_arquivo import foto_elemento

        try:
            self._foto_base = foto_elemento(self._elemento) if self._elemento is not None else None
        except RuntimeError:  # objeto já destruído (janela fechando)
            self._foto_base = None

    def _conferir_mudanca(self, *_args) -> None:
        from .projeto_arquivo import foto_elemento

        if self._elemento is None or self._foto_base is None:
            return
        depois = foto_elemento(self._elemento)
        if depois is None or depois == self._foto_base:
            return
        antes, self._foto_base = self._foto_base, depois
        if self.propriedades_alteradas is not None:
            self.propriedades_alteradas(self._elemento, antes, depois)

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
        self._definir_campos(elemento)
        self._vigiar_campos()

    _ABA_PRINCIPAL: dict[type, str] = {
        ElementoTexto: "Texto",
        ElementoChecklistCores: "Letra",
        ElementoTabela: "Tabela",
        ElementoRetangulo: "Forma",
        ElementoElipse: "Forma",
        ElementoPoligono: "Forma",
        ElementoCurva: "Forma",
        ElementoLinha: "Linha",
        ElementoCota: "Cota",
        ElementoCotaAngular: "Cota",
        ElementoCallout: "Callout",
        ElementoAcabamento: "Acabamento",
        ElementoSimbolo: "Símbolo",
        ElementoLogoVetorial: "Cores",
        ElementoImagem: "Imagem",
        GrupoMockup: "Grupo",
    }

    def _definir_campos(self, elemento: ElementoMockup | None) -> None:
        self._modo_multiplo = False
        # Desliga o elemento ANTERIOR antes de trocar — sem isso, quando
        # ele mudasse de novo (ex.: desfazer), o sinal ia atualizar
        # spinboxes já destruídos com a barra (ver `_limpar_barra`).
        self._desconectar_elemento()

        self._elemento = elemento
        self._rotulo_posicao_painel = None
        self._limpar_barra()
        self._atualizar_fixo(elemento)

        if elemento is None:
            self._definir_rotulo_tipo("Nada selecionado", apagado=True)
            self._botao_remover.setEnabled(False)
            self._nova_aba("Página")
            self._montar_estado_sem_selecao()
            self._finalizar_abas("nada")
            return

        nome_tipo = NOME_TIPO_ELEMENTO.get(type(elemento), "Elemento")
        self._definir_rotulo_tipo(nome_tipo)
        self._botao_remover.setEnabled(True)
        self._nova_aba(self._ABA_PRINCIPAL.get(type(elemento), "Objeto"))

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
            nome.setMaximumWidth(260)
            nome.setToolTip(elemento.caminho_arquivo)
            self._layout_campos.addWidget(nome)
        elif isinstance(elemento, GrupoMockup):
            # Opções de grupo do CorelDRAW. Um objeto de dentro se edita com Ctrl+clique.
            botao = self._botao_icone("desagrupar", "Desagrupar (Ctrl+U)")
            botao.clicked.connect(lambda: self.desagrupar_solicitado and self.desagrupar_solicitado())
            botao_tudo = QToolButton()
            botao_tudo.setText("Desagrupar tudo")
            botao_tudo.setToolTip("Desfaz este grupo e os grupos que estão dentro dele")
            botao_tudo.clicked.connect(lambda: self.desagrupar_tudo_solicitado and self.desagrupar_tudo_solicitado())
            self._layout_campos.addWidget(botao_tudo)
            dica = QLabel(f"{len(elemento.elementos)} objetos · Ctrl+clique edita um só")
            dica.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};")
            self._layout_campos.addWidget(dica)

        # Onde fica na caixa: face, alinhar na face, distâncias, escala.
        self._nova_aba("Posição")
        self._montar_campos_painel(elemento)
        self._finalizar_abas(nome_tipo)

        elemento.geometria_alterada.connect(self._atualizar_campos_geometria)
        self._elemento_conectado = elemento

    def _definir_rotulo_tipo(self, texto: str, apagado: bool = False) -> None:
        self._rotulo_tipo.setText(texto)
        self._rotulo_tipo.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};" if apagado else "font-weight: 700;")

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
        self._desconectar_elemento()
        self._elemento = None
        self._rotulo_posicao_painel = None
        self._limpar_barra()
        self._atualizar_fixo(None)
        self._definir_rotulo_tipo(f"{quantidade} selecionados")
        self._botao_remover.setEnabled(True)
        self._nova_aba("Organizar")

        disposicao = (
            ("alinhar_esquerda", "esquerda", "Alinhar bordas esquerdas entre si"),
            ("alinhar_centro_h", "centro_h", "Centralizar horizontalmente entre si"),
            ("alinhar_direita", "direita", "Alinhar bordas direitas entre si"),
            ("alinhar_topo", "topo", "Alinhar topos entre si"),
            ("alinhar_centro_v", "centro_v", "Centralizar verticalmente entre si"),
            ("alinhar_base", "base", "Alinhar bases entre si"),
        )
        botao_agrupar = self._botao_icone("agrupar", "Agrupar (Ctrl+G)")
        botao_agrupar.setObjectName("botaoAgrupar")
        botao_agrupar.clicked.connect(lambda: self.agrupar_solicitado and self.agrupar_solicitado())
        self._separador()
        rotulo = QLabel("Alinhar ao 1º selecionado:")
        rotulo.setStyleSheet(f"color: {Cor.TEXTO_SECUNDARIO};")
        self._layout_campos.addWidget(rotulo)
        for tipo_icone, alinhamento, tooltip in disposicao:
            botao = self._botao_icone(tipo_icone, tooltip)
            botao.clicked.connect(
                lambda _c=False, a=alinhamento: self.alinhar_multiplos_solicitado and self.alinhar_multiplos_solicitado(a)
            )

        # Modelar, como na barra de propriedades do CorelDRAW com vários
        # objetos selecionados (ver `modelagem.py`).
        self._nova_aba("Modelar")
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
        self._finalizar_abas("varios")

    # ── Posição/tamanho/rotação — comuns a todo elemento ──────────────
    def _montar_fixo(self) -> None:
        """Posição, tamanho, giro, proporção e espelhar — montados UMA vez e
        sempre no mesmo lugar; só os valores mudam com a seleção."""
        campos = (
            ("x", "x", "Posição X", " mm", -100000.0, 100000.0),
            ("y", "y", "Posição Y", " mm", -100000.0, 100000.0),
            ("largura", "largura", "Largura", " mm", 0.1, 100000.0),
            ("altura", "altura", "Altura", " mm", 0.1, 100000.0),
            ("angulo", "angulo", "Ângulo de rotação", " °", -3600.0, 3600.0),
        )
        for chave, tipo_icone, tooltip, sufixo, minimo, maximo in campos:
            spin = QDoubleSpinBox()
            spin.setObjectName(f"geometria_{chave}")
            spin.setRange(minimo, maximo)
            spin.setDecimals(2)
            spin.setSuffix(sufixo)
            spin.setFixedWidth(96)
            # Campo de texto sem setinhas, como na barra do CorelDRAW — as
            # setas comiam a largura e cortavam o número ("120,0(").
            spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            # Só aplica ao confirmar (Enter/Tab/perder o foco): aplicando a
            # cada tecla, digitar "20" virava "40" (o "2" batia no mínimo).
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda valor, c=chave: self._ao_editar_geometria(c, valor))
            spin.valueChanged.connect(self._conferir_mudanca)  # desfazer (depois de aplicar)
            self._spins_geometria[chave] = spin
            self._grupo(tipo_icone, spin, tooltip)

        self._botao_trava = self._botao_icone("trava", "Travar proporção largura/altura", checkable=True)
        self._botao_trava.toggled.connect(self._ao_trocar_trava)
        self._botao_espelho_h = self._botao_icone("espelho_h", "Espelhar na horizontal", checkable=True)
        self._botao_espelho_v = self._botao_icone("espelho_v", "Espelhar na vertical", checkable=True)
        for botao in (self._botao_espelho_h, self._botao_espelho_v):
            botao.toggled.connect(self._ao_trocar_espelho)
            botao.toggled.connect(self._conferir_mudanca)

        # Alinhar na face da caixa: um botão com menu, sempre aqui (é o que
        # mais se usa depois de posicionar).
        self._layout_campos.addSpacing(4)
        botao_alinhar = self._botao_icone("alinhar_centro_h", "Alinhar na face da caixa")
        botao_alinhar.setObjectName("botaoAlinharFace")
        botao_alinhar.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_alinhar = QMenu(botao_alinhar)
        for tipo_icone, alinhamento, tooltip in (
            ("alinhar_esquerda", "esquerda", "Alinhar à esquerda da face"),
            ("alinhar_centro_h", "centro_h", "Centralizar horizontalmente na face"),
            ("alinhar_direita", "direita", "Alinhar à direita da face"),
            ("alinhar_topo", "topo", "Alinhar ao topo da face"),
            ("alinhar_centro_v", "centro_v", "Centralizar verticalmente na face"),
            ("alinhar_base", "base", "Alinhar à base da face"),
        ):
            acao = menu_alinhar.addAction(construir_icone(tipo_icone), tooltip)
            acao.triggered.connect(lambda _c=False, a=alinhamento: self._alinhar_ao_painel(a))
            acao.triggered.connect(self._conferir_mudanca)
        botao_alinhar.setMenu(menu_alinhar)
        self._botao_alinhar_face = botao_alinhar

    def _mostrar_trava(self, travada: bool) -> None:
        # Dois desenhos, como no CorelDRAW: cadeado fechado = proporção travada.
        self._botao_trava.setIcon(construir_icone("trava" if travada else "trava_aberta"))
        self._botao_trava.setToolTip(
            "Proporção travada — clique pra destravar" if travada else "Proporção livre — clique pra travar"
        )

    def _ao_trocar_trava(self, travada: bool) -> None:
        self._mostrar_trava(travada)
        if self._elemento is not None:
            self._elemento.definir_proporcao_travada(travada)

    def _ao_trocar_espelho(self, _marcado: bool) -> None:
        if self._elemento is not None and not isinstance(self._elemento, GrupoMockup):
            self._elemento.definir_espelho(self._botao_espelho_h.isChecked(), self._botao_espelho_v.isChecked())

    def _atualizar_fixo(self, elemento: ElementoMockup | None) -> None:
        """Valores do objeto nos campos fixos; sem objeto, ficam desabilitados
        com um traço (não somem: a barra não muda de lugar)."""
        tem = elemento is not None
        for spin in self._spins_geometria.values():
            spin.setEnabled(tem)
            spin.blockSignals(True)
            if tem:
                spin.setSpecialValueText("")
            else:
                spin.setSpecialValueText("—")
                spin.setValue(spin.minimum())
            spin.blockSignals(False)
        botoes = (self._botao_trava, self._botao_espelho_h, self._botao_espelho_v)
        for botao in botoes:
            botao.blockSignals(True)
        self._botao_trava.setEnabled(tem)
        self._botao_trava.setChecked(bool(tem and elemento.proporcao_travada))
        self._mostrar_trava(self._botao_trava.isChecked())
        espelhavel = tem and not isinstance(elemento, GrupoMockup)
        self._botao_espelho_h.setEnabled(espelhavel)
        self._botao_espelho_v.setEnabled(espelhavel)
        self._botao_espelho_h.setChecked(bool(espelhavel and elemento.espelho_h))
        self._botao_espelho_v.setChecked(bool(espelhavel and elemento.espelho_v))
        for botao in botoes:
            botao.blockSignals(False)
        self._botao_alinhar_face.setEnabled(tem and bool(self._obter_paineis()))
        if tem:
            self._atualizar_campos_geometria()

    def _montar_campos_escala(self) -> None:
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
        combo.setMaximumWidth(100)
        combo.addItem(_ROTULO_SEM_PAINEL, None)
        indice_atual = 0
        for i, painel in enumerate(paineis, start=1):
            combo.addItem(painel.nome, painel.id)
            if painel.id == elemento.painel_id:
                indice_atual = i
        combo.setCurrentIndex(indice_atual)
        self._grupo("face", combo, "Face da caixa a que este elemento pertence")

        # Sem face escolhida, "alinhar na face" (na parte fixa) usa a face
        # onde o objeto está (e ela passa a aparecer escolhida aqui).
        self._combo_painel = combo

        def ao_mudar(_indice: int) -> None:
            elemento.definir_painel(combo.currentData())
            self._atualizar_rotulo_posicao_painel()

        combo.currentIndexChanged.connect(ao_mudar)

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
        self._separador()
        self._montar_campos_escala()

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
            combo.setMaximumWidth(140)
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
        self._abas.blockSignals(True)
        while self._abas.count():
            self._abas.removeTab(0)
        self._abas.blockSignals(False)
        while self._paginas.count():
            pagina = self._paginas.widget(0)
            self._paginas.removeWidget(pagina)
            if combo is not None and pagina.isAncestorOf(combo):
                # Tira o seletor de fonte (reaproveitado) antes de apagar a aba dele.
                self._desligar_combo_fonte()
                combo.hide()
                combo.setParent(self)
            # `hide()` antes de tirar o pai: senão o widget podia aparecer
            # um instante como janela solta antes do `deleteLater`.
            pagina.hide()
            pagina.setParent(None)
            pagina.deleteLater()
        self._paginas_layout = []

    def _combo_cor(self, cor_atual: CorImpressao, ao_mudar: Callable[[CorImpressao], None]) -> QComboBox:
        combo = QComboBox()
        indice_atual = 0
        for i, tinta in enumerate(self._obter_tintas()):
            combo.addItem(tinta.nome, tinta)
            if tinta.nome == cor_atual.nome:
                indice_atual = i
        combo.setObjectName("comboCorTinta")  # pra achar de forma confiável, não por posição
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)  # "AZUL ROYAL" inteiro
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
        spin.setMaximumWidth(88)
        spin.setValue(valor_atual)
        spin.setKeyboardTracking(False)  # mesmo motivo do campo de geometria — ver comentário lá
        spin.valueChanged.connect(ao_mudar)
        self._grupo("espessura", spin, "Espessura do traço")

    def _campos_espacamento(self, el) -> None:
        """Entre letras e entre linhas (o que o F10 do CorelDRAW ajusta no
        texto), em %: letras 0 = normal (+ afasta, − aproxima); linhas 100 =
        normal. As setas do campo andam de 1 em 1; Shift+roda, de 10."""
        letras = QDoubleSpinBox()
        letras.setRange(-50.0, 200.0)
        letras.setDecimals(0)
        letras.setSuffix(" %")
        letras.setValue(el.espaco_letras * 100)
        letras.setKeyboardTracking(False)
        letras.setFixedWidth(74)
        letras.setObjectName("espacoLetras")
        letras.valueChanged.connect(lambda v: el.definir_espaco_letras(v / 100))
        self._grupo("espaco_letras", letras, "Espaço entre letras (0% = normal; mais afasta, menos aproxima)")
        linhas = QDoubleSpinBox()
        linhas.setRange(30.0, 500.0)
        linhas.setDecimals(0)
        linhas.setSuffix(" %")
        linhas.setValue(el.espaco_linhas * 100)
        linhas.setKeyboardTracking(False)
        linhas.setFixedWidth(74)
        linhas.setObjectName("espacoLinhas")
        linhas.valueChanged.connect(lambda v: el.definir_espaco_linhas(v / 100))
        self._grupo("espaco_linhas", linhas, "Espaço entre linhas (100% = normal; menos aproxima, mais afasta)")

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
            botao.setProperty("alinharTexto", chave)  # nome do objeto fica o do estilo dos botões da barra
            botao.setChecked(el.alinhamento == chave)
            botoes_alinhamento.append((chave, botao))
        self._juntar_ultimos(3)  # os 3 de alinhamento não se separam

        def escolher(chave_escolhida: str) -> None:
            el.definir_alinhamento(chave_escolhida)
            for chave, botao in botoes_alinhamento:
                botao.blockSignals(True)
                botao.setChecked(chave == chave_escolhida)
                botao.blockSignals(False)

        for chave, botao in botoes_alinhamento:
            botao.clicked.connect(lambda _c=False, c=chave: escolher(c))

        self._separador()
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

        self._nova_aba("Espaçamento")
        self._campos_espacamento(el)

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

        combo_fonte = self._combo_de_fonte()
        if el.fonte_familia:
            combo_fonte.setCurrentFont(QFont(el.fonte_familia))
        self._slot_fonte = lambda fonte: el.definir_fonte(fonte.family())
        combo_fonte.currentFontChanged.connect(self._slot_fonte)
        self._grupo("fonte_aa", combo_fonte, "Fonte")
        combo_fonte.show()

        altura = QDoubleSpinBox()
        altura.setRange(0.0, 500.0)
        altura.setDecimals(2)
        altura.setSuffix(" mm")
        altura.setSpecialValueText("cabe")
        altura.setValue(el.altura_letra_mm or 0.0)
        altura.setKeyboardTracking(False)
        altura.setMaximumWidth(78)
        altura.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        altura.setObjectName("alturaLetraTabela")
        altura.valueChanged.connect(lambda mm: el.definir_altura_letra_mm(mm or None))
        self._grupo("altura", altura, "Altura da letra (maiúscula), em mm — 0 = a maior que cabe na célula")

        largura = QDoubleSpinBox()
        largura.setRange(20.0, 200.0)
        largura.setDecimals(1)
        largura.setSuffix(" %")
        largura.setValue(el.largura_letra * 100)
        largura.setKeyboardTracking(False)
        largura.setMaximumWidth(80)
        largura.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        largura.setObjectName("larguraLetraTabela")
        largura.valueChanged.connect(lambda v: el.definir_largura_letra(v / 100))
        self._grupo("largura", largura, "Largura das letras (100% = normal; 66,7% = meio esticada, o padrão da máquina)")

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
        largura.setMaximumWidth(80)
        largura.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        largura.setObjectName("larguraLetraChecklist")
        largura.valueChanged.connect(lambda v: el.definir_largura_letra(v / 100))
        self._grupo("largura", largura, "Largura das letras (100% = normal; 66,7% = meio esticada, o padrão da máquina)")

        botao_negrito = self._botao_icone("negrito", "Negrito", checkable=True)
        botao_negrito.setChecked(el.negrito)
        botao_negrito.toggled.connect(el.definir_negrito)
        self._separador()
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

        self._nova_aba("Espaçamento")
        self._campos_espacamento(el)
        disposicao = QComboBox()
        for chave, nome in DISPOSICOES.items():
            disposicao.addItem(nome, chave)
        disposicao.setCurrentIndex(max(0, disposicao.findData(el.disposicao)))
        disposicao.currentIndexChanged.connect(lambda _i: el.definir_disposicao(disposicao.currentData()))
        self._grupo("lista", disposicao, "Arranjo das cores: empilhadas ou lado a lado (quebra na largura da caixa)")

        self._nova_aba("Quadro")
        quadro = QDoubleSpinBox()
        quadro.setRange(0.1, 20.0)
        quadro.setDecimals(2)
        quadro.setSingleStep(0.25)
        quadro.setSuffix(" pt")
        quadro.setValue(el.espessura_quadro_pt)
        quadro.setKeyboardTracking(False)
        quadro.setFixedWidth(78)
        quadro.setObjectName("espessuraQuadro")
        quadro.valueChanged.connect(el.definir_espessura_quadro_pt)
        tamanho.valueChanged.connect(lambda _pt: (quadro.blockSignals(True), quadro.setValue(el.espessura_quadro_pt), quadro.blockSignals(False)))
        self._grupo("espessura", quadro, "Espessura do traço do quadrinho (padrão: 1 pt com letra de 2 mm; acompanha o tamanho da letra)")

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
