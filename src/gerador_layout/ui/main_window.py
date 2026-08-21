"""Janela principal do Gerador de Layout de Caixas."""

from __future__ import annotations

import math
from contextlib import contextmanager

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..layout_service import ServicoLayoutCaixa
from ..models import CorImpressao, MedidasCaixa, NOME_EXIBICAO_TIPO_CAIXA, TipoCaixa
from ..paineis import Painel, calcular_paineis
from . import configuracoes, corel_bridge, exportacao
from .dialogo_configuracoes import DialogoConfiguracoes
from .dialogo_logo import DialogoSepararCoresLogo
from .dialogo_manual import DialogoManual
from .dialogo_tabela import DialogoTabela
from .estilo import Cor
from .mockup_acabamento import ElementoAcabamento
from .mockup_callout import ElementoCallout
from .mockup_checklist import ElementoChecklistCores
from .mockup_formas import ElementoElipse, ElementoLinha, ElementoPoligono, ElementoRetangulo
from .mockup_icones import construir_icone
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_reguas import ReguaHorizontal, ReguaVertical
from .mockup_simbolos import ElementoSimbolo
from .mockup_tabela import ElementoTabela
from .mockup_texto import ElementoTexto
from .painel_propriedades_mockup import PainelPropriedadesMockup
from .preview_canvas import FerramentaMockup, PainelLegendaCores, PreviewCanvas
from .segmented_row import LinhaTrechos

_CORES_DISPONIVEIS: list[tuple[str, tuple[int, int, int]]] = [
    ("Preto", (0, 0, 0)),
    ("Vermelho", (255, 0, 0)),
    ("Azul", (0, 0, 255)),
    ("Amarelo", (255, 220, 0)),
    ("Verde", (0, 150, 0)),
    ("Ciano", (0, 170, 220)),
    ("Magenta", (220, 0, 180)),
    ("Laranja", (255, 120, 0)),
]

# Rótulos exibidos em cada trecho, por tipo de caixa. A Impressora sempre
# tem 5 trechos; o Riscador tem 3 na maleta e 5 no envoltório.
_TIPOS_MALETA = {TipoCaixa.MALETA_NORMAL, TipoCaixa.MALETA_TRANSPASSADA}

_ROTULOS_IMPRESSORA_MALETA = ["Aba", "L", "C", "L", "C"]
_ROTULOS_IMPRESSORA_ENVOLTORIO = ["Aba", "A", "C", "A", "Aba"]
_ROTULOS_RISCADOR_MALETA = ["Sup", "Centro", "Inf", "", ""]
_ROTULOS_RISCADOR_ENVOLTORIO = ["Sup", "A", "L", "A", "Inf"]


class JanelaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # "Autoline" é o rebranding proposto (ver autoline-rebranding.html
        # / dossie_projeto.html) — nome de trabalho, ainda não fechado.
        # O nome interno do projeto/pasta/`.exe` continua o mesmo por ora
        # de propósito: trocar isso é uma decisão maior (afeta atalho,
        # instalador, histórico do repositório) que não foi pedida ainda.
        self.setWindowTitle("Autoline — Gerador de Layout de Caixas")
        # Tamanho pra quando a janela for restaurada (não-maximizada, ver
        # main.py) — cabe com folga numa tela de notebook comum de 1366×768
        # (altura útil ~728px descontando a barra de tarefas).
        self.resize(1180, 680)

        self._servico = ServicoLayoutCaixa()
        self._chips_cor: dict[str, tuple[QPushButton, tuple[int, int, int]]] = {}
        self._corel_app = None
        self._paineis_atuais: list[Painel] = []
        self._dialogo_manual: DialogoManual | None = None

        self._montar_ui()
        self._montar_abas_tela()
        self._montar_barra_ferramentas()
        self._montar_barra_mockup()
        self._montar_barra_propriedades_mockup()
        self._montar_menu()
        self._conectar_sinais()
        self._ao_trocar_tipo()
        self._trocar_tela(0)  # começa na tela de Dieline

    # ── Montagem da UI ──────────────────────────────────────────────
    def _montar_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout_raiz = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout_raiz.addWidget(splitter)

        self.painel_esquerdo = self._montar_painel_esquerdo()
        splitter.addWidget(self.painel_esquerdo)
        splitter.addWidget(self._montar_painel_direito())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        # Painel esquerdo só com tipo/medidas/cores agora — os trechos
        # (Impressora/Riscador) ficam embaixo da pré-visualização, à
        # direita, com bem mais espaço pra respirar.
        splitter.setSizes([260, 940])

    def _montar_painel_esquerdo(self) -> QWidget:
        painel = QWidget()
        painel.setObjectName("painelEsquerdo")
        painel.setMaximumWidth(320)
        vbox = QVBoxLayout(painel)
        vbox.setContentsMargins(12, 14, 12, 14)
        # Espaçamento generoso entre os 3 grupos — antes eles se juntavam
        # todos no topo com um vão vazio solto embaixo; mais respiro aqui
        # faz esse espaço parecer intencional, não sobra.
        vbox.setSpacing(20)

        grupo_tipo = QGroupBox("Tipo de caixa")
        form_tipo = QFormLayout(grupo_tipo)
        form_tipo.setVerticalSpacing(10)
        self.combo_tipo = QComboBox()
        for tipo in TipoCaixa:
            self.combo_tipo.addItem(NOME_EXIBICAO_TIPO_CAIXA[tipo], tipo)
        self.combo_tipo.setCurrentIndex(list(TipoCaixa).index(TipoCaixa.MALETA_NORMAL))
        form_tipo.addRow(self.combo_tipo)
        vbox.addWidget(grupo_tipo)

        grupo_medidas = QGroupBox("Medidas C × L × A (mm)")
        form_medidas = QFormLayout(grupo_medidas)
        form_medidas.setVerticalSpacing(12)
        self.spin_comprimento = self._criar_spin(300)
        self.spin_largura = self._criar_spin(200)
        self.spin_altura = self._criar_spin(150)
        form_medidas.addRow("Comprimento (C):", self.spin_comprimento)
        form_medidas.addRow("Largura (L):", self.spin_largura)
        form_medidas.addRow("Altura (A):", self.spin_altura)
        vbox.addWidget(grupo_medidas)

        grupo_cores = QGroupBox("Legenda de cores")
        grid_cores = QGridLayout(grupo_cores)
        grid_cores.setHorizontalSpacing(8)
        grid_cores.setVerticalSpacing(8)
        # 3 colunas — usadas normalmente só 1-2 cores por vez, então vale
        # mais compactar na vertical do que espalhar por 4 linhas (testei
        # 4 colunas antes e cortava o texto de nomes maiores).
        _COLUNAS_CORES = 3
        for i, (nome, rgb) in enumerate(_CORES_DISPONIVEIS):
            chip = self._montar_chip_cor(nome, rgb)
            self._chips_cor[nome] = (chip, rgb)
            grid_cores.addWidget(chip, i // _COLUNAS_CORES, i % _COLUNAS_CORES)
        self._chips_cor["Preto"][0].setChecked(True)
        vbox.addWidget(grupo_cores)

        vbox.addStretch(1)
        return painel

    def _montar_painel_direito(self) -> QWidget:
        # O rótulo "PRÉ-VISUALIZAÇÃO" e os controles de zoom viviam numa
        # barra própria, embaixo da barra de ferramentas — duas fileiras de
        # chrome empilhadas, com a de zoom sobrando bastante espaço vazio à
        # direita dos botões de exportar. Ver `_montar_barra_ferramentas`:
        # os controles de zoom/"Ajustar à tela" agora moram lá, preenchendo
        # esse vazio e liberando uma fileira inteira de altura pro canvas.
        painel = QWidget()
        painel.setObjectName("painelDireito")
        vbox = QVBoxLayout(painel)
        vbox.setContentsMargins(0, 0, 12, 10)
        vbox.setSpacing(8)

        legenda_e_canvas = QWidget()
        vbox_legenda_canvas = QVBoxLayout(legenda_e_canvas)
        vbox_legenda_canvas.setContentsMargins(12, 6, 0, 0)
        vbox_legenda_canvas.setSpacing(6)

        self.painel_legenda_cores = PainelLegendaCores()
        vbox_legenda_canvas.addWidget(self.painel_legenda_cores)

        self.canvas = PreviewCanvas()

        # Réguas nas bordas do canvas (mesmo lugar/formato de qualquer
        # CAD/vetorial de verdade) — arrastar a partir delas solta uma
        # guia (ver `mockup_reguas.py`). Canto vazio (0,0) fecha a grade
        # visualmente, senão sobra um buraco quadrado onde as duas réguas
        # se encontrariam.
        self.regua_horizontal = ReguaHorizontal(self.canvas)
        self.regua_vertical = ReguaVertical(self.canvas)
        self._canto_reguas = QWidget()
        self._canto_reguas.setFixedSize(self.regua_vertical.width(), self.regua_horizontal.height())
        self._canto_reguas.setStyleSheet(
            f"background: {Cor.CARTAO}; border-right: 1px solid {Cor.BORDA}; border-bottom: 1px solid {Cor.BORDA};"
        )

        grade_canvas = QGridLayout()
        grade_canvas.setContentsMargins(0, 0, 0, 0)
        grade_canvas.setSpacing(0)
        grade_canvas.addWidget(self._canto_reguas, 0, 0)
        grade_canvas.addWidget(self.regua_horizontal, 0, 1)
        grade_canvas.addWidget(self.regua_vertical, 1, 0)
        grade_canvas.addWidget(self.canvas, 1, 1)
        vbox_legenda_canvas.addLayout(grade_canvas, 1)
        vbox.addWidget(legenda_e_canvas, 1)

        # Trechos (Impressora/Riscador) embaixo da pré-visualização — mais
        # largura disponível aqui do que na barra lateral esquerda.
        # Riscador antes de Impressora (pedido do usuário) e um estilo
        # compacto (`grupoMedidasGeradas` em estilo.py) — é uma tabela de
        # números densa, não precisa do mesmo respiro dos cartões da
        # esquerda.
        #
        # Retrátil (setCheckable): o canvas ganha espaço quando o usuário
        # não precisa olhar/ajustar esses números no momento — em vez de
        # simplesmente encolher os campos até ficarem ilegíveis, ou inflar
        # a janela inteira pra "criar" espaço (as duas coisas já foram
        # tentadas e não resolveram de verdade). Começa aberto.
        self._grupo_medidas = QGroupBox("Medidas geradas / ajustáveis")
        self._grupo_medidas.setObjectName("grupoMedidasGeradas")
        self._grupo_medidas.setCheckable(True)
        self._grupo_medidas.setChecked(True)
        self._grupo_medidas.setToolTip("Clique no título pra recolher e dar mais espaço à pré-visualização")
        vbox_trechos = QVBoxLayout(self._grupo_medidas)
        vbox_trechos.setSpacing(4)
        self.linha_impressora = LinhaTrechos("Impressora", _ROTULOS_IMPRESSORA_MALETA)
        self.linha_riscador = LinhaTrechos("Riscador", _ROTULOS_RISCADOR_MALETA)
        vbox_trechos.addWidget(self.linha_riscador)
        vbox_trechos.addWidget(self.linha_impressora)
        self._grupo_medidas.toggled.connect(self.linha_riscador.setVisible)
        self._grupo_medidas.toggled.connect(self.linha_impressora.setVisible)
        margem = QHBoxLayout()
        margem.setContentsMargins(12, 0, 0, 0)
        margem.addWidget(self._grupo_medidas)
        vbox.addLayout(margem)

        return painel

    def _conectar_sinais(self) -> None:
        """Conecta todos os sinais de UI depois que toda a janela já existe,
        evitando disparar _recalcular() com widgets ainda não criados."""
        self.combo_tipo.currentIndexChanged.connect(self._ao_trocar_tipo)
        for chip, _rgb in self._chips_cor.values():
            chip.toggled.connect(self._recalcular)
        for spin in (self.spin_comprimento, self.spin_largura, self.spin_altura):
            spin.valueChanged.connect(self._recalcular)
        self.linha_impressora.valor_alterado.connect(self._recalcular)
        self.linha_riscador.valor_alterado.connect(self._recalcular)
        self.canvas.cena.selectionChanged.connect(self._ao_selecao_mockup_mudar)

    def _criar_spin(self, valor_padrao: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 100000)
        spin.setDecimals(1)
        spin.setSuffix(" mm")
        spin.setValue(valor_padrao)
        return spin

    def _montar_chip_cor(self, nome: str, rgb: tuple[int, int, int]) -> QPushButton:
        """Botão de alternância que mostra a própria cor, em vez de um
        checkbox genérico + nome em texto — remove a ambiguidade de "qual
        tom exatamente é Ciano" e deixa a legenda mais rápida de escanear.
        Cor de preenchimento/texto muda dinamicamente com o estado (ver
        `_repintar_chip_cor`), então precisa de estilo por widget — o QSS
        global só cuida do raio/peso da fonte (seletor `chipCor`)."""
        chip = QPushButton(nome)
        chip.setCheckable(True)
        chip.setProperty("chipCor", True)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.toggled.connect(lambda marcado, c=chip, rgb=rgb: self._repintar_chip_cor(c, rgb, marcado))
        self._repintar_chip_cor(chip, rgb, False)
        return chip

    @staticmethod
    def _repintar_chip_cor(chip: QPushButton, rgb: tuple[int, int, int], marcado: bool) -> None:
        r, g, b = rgb
        if marcado:
            # Texto branco ou escuro, o que for mais legível sobre a cor de
            # fundo (mesmo cálculo de luminância usado na legenda de
            # impressão em `preview_canvas.py`).
            luminancia = 0.299 * r + 0.587 * g + 0.114 * b
            cor_texto = "#1a1d29" if luminancia > 170 else "#ffffff"
            chip.setStyleSheet(
                f"background: rgb({r},{g},{b}); color: {cor_texto}; "
                f"border: 1px solid rgb({r},{g},{b});"
            )
        else:
            chip.setStyleSheet(
                f"background: transparent; color: rgb({r},{g},{b}); "
                f"border: 1px solid rgb({r},{g},{b});"
            )

    # ── Lógica ──────────────────────────────────────────────────────
    def _ao_trocar_tipo(self) -> None:
        tipo = self.combo_tipo.currentData()
        self.linha_impressora.definir_visiveis(5)
        if tipo in _TIPOS_MALETA:
            self.linha_impressora.definir_rotulos(_ROTULOS_IMPRESSORA_MALETA)
            self.linha_riscador.definir_rotulos(_ROTULOS_RISCADOR_MALETA)
            self.linha_riscador.definir_visiveis(3)
        else:
            self.linha_impressora.definir_rotulos(_ROTULOS_IMPRESSORA_ENVOLTORIO)
            self.linha_riscador.definir_rotulos(_ROTULOS_RISCADOR_ENVOLTORIO)
            self.linha_riscador.definir_visiveis(5)
        self._recalcular()

    def _cores_impressao_ativas(self) -> list[CorImpressao]:
        """As tintas marcadas na legenda agora — mesma fonte usada tanto
        pra calcular o layout (`_obter_medidas`) quanto pra escolher a
        cor de um elemento de mockup (ver `painel_propriedades_mockup.py`
        e `dialogo_logo.py`): é sempre a mesma paleta do trabalho atual,
        não faz sentido ter duas listas de cores diferentes no mesmo app."""
        return [
            CorImpressao(nome=nome.upper(), r=rgb[0], g=rgb[1], b=rgb[2])
            for nome, (chip, rgb) in self._chips_cor.items()
            if chip.isChecked()
        ]

    def _obter_medidas(self) -> MedidasCaixa:
        cores = self._cores_impressao_ativas()
        imp = self.linha_impressora.valores()
        ris = self.linha_riscador.valores()
        return MedidasCaixa(
            tipo=self.combo_tipo.currentData(),
            comprimento=self.spin_comprimento.value(),
            largura=self.spin_largura.value(),
            altura=self.spin_altura.value(),
            impressora_aba=imp[0],
            impressora_largura_1=imp[1],
            impressora_comprimento_1=imp[2],
            impressora_largura_2=imp[3],
            impressora_comprimento_2=imp[4],
            riscador_superior=ris[0],
            riscador_centro=ris[1],
            riscador_inferior=ris[2],
            riscador_parte_4=ris[3],
            riscador_parte_5=ris[4],
            cores_legenda=cores,
        )

    # ── Menu / Exportação ───────────────────────────────────────────
    def _montar_barra_ferramentas(self) -> None:
        """As ações de exportação são o motivo do app existir, mas antes
        só apareciam dentro de Arquivo > Exportar layout — uma barra de
        ferramentas sempre visível deixa isso descobrível sem precisar
        abrir menu nenhum. O menu continua existindo (ver `_montar_menu`)
        pra quem já tem o hábito, chamando exatamente os mesmos métodos.

        Zoom e "Ajustar à tela" ficam à direita, na mesma barra — viviam
        numa barra própria embaixo desta, sobrando um vão vazio enorme à
        direita dos botões de exportar (a barra de ferramentas ocupa a
        largura toda da janela, mas os botões só usam a parte esquerda).
        Juntar os dois usa esse espaço e ainda libera uma fileira inteira
        de altura pro canvas."""
        barra = QToolBar("Exportar")
        barra.setMovable(False)
        barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(barra)

        # Respiro antes da marca — sem isso ela fica encostada direto nas
        # abas Dieline/Layout (toolbars adjacentes sem borda, por causa do
        # QSS flat do app, ver `estilo.py`), lendo como se fosse só mais
        # um botão da fileira em vez de uma marca separada (achado numa
        # revisão de UI/UX).
        espaco_antes_marca = QWidget()
        espaco_antes_marca.setFixedWidth(12)
        barra.addWidget(espaco_antes_marca)
        rotulo_marca = QLabel("AUTOLINE")
        rotulo_marca.setObjectName("rotuloMarca")
        barra.addWidget(rotulo_marca)
        barra.addSeparator()

        # Símbolos simples (não emoji colorido — herdam a cor do texto do
        # botão, ficam monocromáticos como o resto do app) só pra dar um
        # pouco de caráter visual à barra e diferenciar "salvar arquivo"
        # de "mandar pra outro programa" rapidamente, sem precisar ler.
        barra.addAction("↓ SVG", self._exportar_svg)
        barra.addAction("↓ PDF", self._exportar_pdf)
        barra.addAction("↓ JPG", self._exportar_jpg)
        barra.addSeparator()
        barra.addAction("→ CorelDRAW", self._exportar_corel)

        espacador = QWidget()
        espacador.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        barra.addWidget(espacador)

        self.label_zoom = QLabel("100%")
        self.label_zoom.setObjectName("rotuloTecnico")
        self.label_zoom.setStyleSheet(f"color: {Cor.TEXTO_SECUNDARIO};")
        barra.addWidget(self.label_zoom)
        botao_ajustar = QPushButton("Ajustar à tela")
        botao_ajustar.clicked.connect(lambda: self.canvas.ajustar_a_tela())
        barra.addWidget(botao_ajustar)
        self.canvas.zoom_alterado.connect(lambda z: self.label_zoom.setText(f"{z * 100:.0f}%"))

    def _montar_menu(self) -> None:
        menu_arquivo = self.menuBar().addMenu("&Arquivo")
        menu_arquivo.addAction("Conectar ao CorelDRAW", self._conectar_corel)
        menu_arquivo.addSeparator()

        menu_exportar = menu_arquivo.addMenu("Exportar layout")
        menu_exportar.addAction("Exportar como SVG...", self._exportar_svg)
        menu_exportar.addAction("Exportar como PDF...", self._exportar_pdf)
        menu_exportar.addAction("Exportar como JPG...", self._exportar_jpg)
        menu_exportar.addSeparator()
        menu_exportar.addAction("Enviar para o CorelDRAW", self._exportar_corel)

        menu_arquivo.addSeparator()
        menu_arquivo.addAction("Configurações...", self._abrir_configuracoes)
        menu_arquivo.addSeparator()
        acao_sair = menu_arquivo.addAction("Sair")
        acao_sair.setShortcut("Alt+F4")
        acao_sair.triggered.connect(self.close)

        menu_exibir = self.menuBar().addMenu("&Exibir")
        acao_grade = menu_exibir.addAction("Grade do canvas")
        acao_grade.setCheckable(True)
        acao_grade.setChecked(True)
        acao_grade.toggled.connect(self.canvas.definir_grade_visivel)

        acao_snap = menu_exibir.addAction("Encaixe (snap) ao arrastar")
        acao_snap.setCheckable(True)
        acao_snap.setChecked(True)
        acao_snap.setToolTip("Gruda automaticamente na grade, nas bordas de outros elementos, na face e nas guias")
        acao_snap.toggled.connect(self.canvas.definir_snap_ativo)

        acao_reguas = menu_exibir.addAction("Réguas")
        acao_reguas.setCheckable(True)
        acao_reguas.setChecked(True)
        acao_reguas.toggled.connect(self._definir_reguas_visiveis)

        acao_zona_segura = menu_exibir.addAction("Zonas seguras (recuo do vinco)")
        acao_zona_segura.setCheckable(True)
        acao_zona_segura.setChecked(False)
        acao_zona_segura.setToolTip("Marca a faixa perto do vinco/corte de cada painel onde não é recomendado colocar conteúdo")
        acao_zona_segura.toggled.connect(self.canvas.definir_zona_segura_visivel)

        acao_medidas = menu_exibir.addAction("Medidas geradas / ajustáveis")
        acao_medidas.setCheckable(True)
        acao_medidas.setChecked(True)
        # Sincronização nos dois sentidos: o menu controla o grupo
        # retrátil (ver `_montar_painel_direito`) e vice-versa — clicar
        # no checkbox do título do grupo também deve marcar/desmarcar
        # aqui, senão os dois controles saem de sincronia.
        acao_medidas.toggled.connect(self._grupo_medidas.setChecked)
        self._grupo_medidas.toggled.connect(acao_medidas.setChecked)

        menu_ajuda = self.menuBar().addMenu("A&juda")
        acao_manual = menu_ajuda.addAction("Manual de uso...", self._abrir_manual)
        acao_manual.setShortcut("F1")
        menu_ajuda.addSeparator()
        menu_ajuda.addAction("Sobre...", self._mostrar_sobre)

    # ── Duas telas: Dieline (medidas/cores/preview) e Layout (mockup) ──
    def _montar_abas_tela(self) -> None:
        """Abas no topo da janela, acima de tudo — trocam qual conjunto
        de painéis fica visível ao redor do MESMO canvas (a dieline
        continua servindo de referência visual na tela de Layout, e vai
        continuar quando o 3D existir na tela de Dieline). Numa barra de
        ferramentas própria, adicionada antes de qualquer outra, pra
        ficar sempre na linha mais acima — é navegação, não uma ação, não
        faz sentido misturar com os botões de exportar/criar elemento."""
        barra = QToolBar("Tela")
        barra.setMovable(False)
        self.addToolBar(barra)

        self.abas_tela = QTabBar()
        self.abas_tela.addTab("Dieline")
        self.abas_tela.addTab("Layout")
        self.abas_tela.setToolTip("Dieline: medidas, cores e a faca de corte. Layout: texto/formas/logotipo sobre a caixa.")
        self.abas_tela.currentChanged.connect(self._trocar_tela)
        barra.addWidget(self.abas_tela)

    def _trocar_tela(self, indice: int) -> None:
        modo_layout = indice == 1
        self.painel_esquerdo.setVisible(not modo_layout)
        self._grupo_medidas.setVisible(not modo_layout)
        self.barra_mockup.setVisible(modo_layout)
        self.barra_propriedades_mockup.setVisible(modo_layout)
        self.canvas.definir_modo_mockup(modo_layout)
        if not modo_layout:
            self.painel_propriedades_mockup.definir_elemento(None)
        # Mostrar/esconder os painéis ao redor muda o tamanho disponível
        # do canvas — sem reencaixar aqui, a visão que estava centralizada
        # antes da troca fica deslocada (às vezes "presa" perto do canto
        # superior esquerdo) porque o zoom/posição antigos não fazem mais
        # sentido pro novo tamanho de viewport.
        self.canvas.ajustar_a_tela()

    # ── Mockup (Fase 2): barra de propriedades, barra e criação de itens ─
    def _montar_barra_propriedades_mockup(self) -> None:
        """Barra horizontal por baixo de `barra_mockup` — a "property
        bar" contextual do elemento selecionado, no mesmo lugar/formato
        que qualquer CAD/vetorial de verdade usa (CorelDRAW, Illustrator),
        em vez do dock lateral que tinha antes. Ver
        `painel_propriedades_mockup.py` pro conteúdo em si; aqui só
        encaixa esse widget dentro de uma QToolBar própria."""
        self.painel_propriedades_mockup = PainelPropriedadesMockup(
            self._cores_impressao_ativas, self._paineis_disponiveis
        )
        self.painel_propriedades_mockup.remover_solicitado = self._remover_elemento_mockup_selecionado
        self.painel_propriedades_mockup.remapear_logo_solicitado = self._remapear_cores_logo
        self.painel_propriedades_mockup.remover_multiplos_solicitado = self._remover_elemento_mockup_selecionado
        self.painel_propriedades_mockup.alinhar_multiplos_solicitado = self.canvas.alinhar_selecionados

        # Quebra de linha de propósito, mesmo motivo de `_montar_barra_mockup`:
        # sem isso o Qt tenta encaixar essa barra na mesma linha da barra
        # de criar elemento, em vez de ficar embaixo dela (a leitura de
        # cima pra baixo — criar elemento, depois editar propriedade dele
        # — fica confusa se as duas disputam a mesma linha).
        self.addToolBarBreak()
        barra = QToolBar("Propriedades")
        barra.setObjectName("barraPropriedadesMockup")
        barra.setMovable(False)
        self.addToolBar(barra)
        barra.addWidget(self.painel_propriedades_mockup)
        self.barra_propriedades_mockup = barra
        self.barra_propriedades_mockup.hide()  # só aparece na tela de Layout (ver _trocar_tela)

    def _montar_barra_mockup(self) -> None:
        """Paleta de ferramentas do modo Layout — horizontal, no topo da
        janela (pedido explícito do usuário — antes ficava na borda
        esquerda), só ícone com tooltip (sem texto, pedido explícito do
        usuário: "não quero nada escrito, quero ícones interativos").

        Selecionar/Texto/Retângulo/Linha são uma FERRAMENTA (ver
        `FerramentaMockup` em `preview_canvas.py`) — só uma ativa por
        vez, escolhida num `QActionGroup` exclusivo; escolher uma delas
        muda o que clicar/arrastar no canvas faz (criar o elemento ali
        na hora, em vez de sempre no centro da tela + editar depois pela
        barra de propriedades). O resto (Imagem/Logotipo/Checklist/
        Agrupar/Desagrupar/ordem) continua ação de um clique só, como
        sempre foi — não tem um gesto natural de "desenhar" pra elas."""
        # Quebra de linha de propósito: sem isso, o Qt tenta encaixar essa
        # barra na mesma linha da barra principal — numa linha própria
        # fica claro que são dois grupos de ferramentas diferentes.
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        barra = QToolBar("Ferramentas")
        barra.setObjectName("paletaFerramentasMockup")
        barra.setMovable(False)
        barra.setOrientation(Qt.Orientation.Horizontal)
        barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, barra)
        self.barra_mockup = barra

        self._acoes_ferramenta: dict[FerramentaMockup, QAction] = {}
        grupo_ferramentas = QActionGroup(self)
        grupo_ferramentas.setExclusive(True)

        def acao_ferramenta(tipo_icone: str, tooltip: str, ferramenta: FerramentaMockup) -> None:
            acao = QAction(construir_icone(tipo_icone), tooltip, self)
            acao.setCheckable(True)
            acao.triggered.connect(lambda: self.canvas.definir_ferramenta(ferramenta))
            grupo_ferramentas.addAction(acao)
            barra.addAction(acao)
            self._acoes_ferramenta[ferramenta] = acao

        acao_ferramenta(
            "selecionar",
            "Selecionar (Esc) — Alt+arrastar duplica, Shift+arrastar restringe a um eixo",
            FerramentaMockup.SELECIONAR,
        )
        acao_ferramenta(
            "ferramenta_laco",
            "Laço de seleção — clique pra cada vértice, feche perto do primeiro ponto",
            FerramentaMockup.LACO_SELECAO,
        )
        acao_ferramenta(
            "ferramenta_mover_preciso",
            "Mover de precisão — clique no ponto de pega, depois no ponto de solta (move a seleção atual)",
            FerramentaMockup.MOVER_PRECISO,
        )
        barra.addSeparator()  # fim do grupo "seleção" (Selecionar/Laço/Mover-preciso), começa "criar conteúdo"
        acao_ferramenta("ferramenta_texto", "Texto — clique no canvas e digite direto ali", FerramentaMockup.TEXTO)
        acao_ferramenta(
            "ferramenta_retangulo",
            "Retângulo — clique e arraste pra desenhar (Alt = a partir do centro)",
            FerramentaMockup.RETANGULO,
        )
        acao_ferramenta(
            "ferramenta_elipse", "Elipse — clique e arraste pra desenhar (Alt = a partir do centro)", FerramentaMockup.ELIPSE
        )
        acao_ferramenta(
            "ferramenta_poligono",
            "Polígono — clique e arraste pra desenhar (nº de lados ajustável, Alt = a partir do centro)",
            FerramentaMockup.POLIGONO,
        )
        acao_ferramenta("ferramenta_linha", "Linha — clique e arraste pra desenhar", FerramentaMockup.LINHA)
        acao_ferramenta(
            "ferramenta_callout", "Callout — clique no canvas pra anotar (aponta pra esse lugar)", FerramentaMockup.CALLOUT
        )
        acao_ferramenta("ferramenta_tabela", "Tabela — clique no canvas (ficha técnica/nutricional)", FerramentaMockup.TABELA)
        acao_ferramenta(
            "ferramenta_transparencia",
            "Acabamento de produção — clique e arraste (Alt = a partir do centro; verniz localizado, laminação, hot stamping)",
            FerramentaMockup.ACABAMENTO,
        )
        acao_ferramenta(
            "ferramenta_simbolo",
            "Símbolo de manuseio — clique no canvas (frágil, este lado para cima, reciclável...)",
            FerramentaMockup.SIMBOLO,
        )
        barra.addSeparator()  # fim de "criar conteúdo", começa "inspecionar" (não cria nada)
        acao_ferramenta(
            "conta_gotas", "Conta-gotas — clica numa cor da tela e aplica no elemento selecionado", FerramentaMockup.CONTA_GOTAS
        )
        acao_ferramenta("medida", "Medida — clique e arraste pra ver a distância entre 2 pontos", FerramentaMockup.MEDIR)
        self._acoes_ferramenta[FerramentaMockup.SELECIONAR].setChecked(True)

        barra.addSeparator()
        self._acao_icone(barra, "ferramenta_imagem", "Adicionar imagem...", self._adicionar_imagem)
        self._acao_icone(barra, "ferramenta_logo", "Adicionar logotipo...", self._adicionar_logo)
        self._acao_icone(barra, "lista", "Adicionar checklist de cores", self._adicionar_checklist)

        barra.addSeparator()
        self._acao_icone(barra, "agrupar", "Agrupar (Ctrl+G)", lambda: self.canvas.agrupar_selecionados())
        self._acao_icone(
            barra, "desagrupar", "Desagrupar (Ctrl+Shift+G)", lambda: self.canvas.desagrupar_selecionados()
        )

        barra.addSeparator()
        self._acao_icone(barra, "trazer_frente", "Trazer p/ frente (Ctrl+Home)", lambda: self.canvas.trazer_para_frente())
        self._acao_icone(barra, "enviar_tras", "Enviar p/ trás (Ctrl+End)", lambda: self.canvas.enviar_para_tras())

        barra.addSeparator()
        pilha = self.canvas.pilha_desfazer
        acao_desfazer = self._acao_icone(barra, "desfazer", "Desfazer (Ctrl+Z)", pilha.undo)
        acao_desfazer.setEnabled(False)
        pilha.canUndoChanged.connect(acao_desfazer.setEnabled)
        acao_refazer = self._acao_icone(barra, "refazer", "Refazer (Ctrl+Shift+Z)", pilha.redo)
        acao_refazer.setEnabled(False)
        pilha.canRedoChanged.connect(acao_refazer.setEnabled)

        self.canvas.ferramenta_alterada.connect(self._ao_ferramenta_alterada)
        self.canvas.retangulo_desenhado.connect(self._criar_retangulo_por_arrasto)
        self.canvas.linha_desenhada.connect(self._criar_linha_por_arrasto)
        self.canvas.texto_solicitado.connect(self._criar_texto_por_clique)
        self.canvas.cor_amostrada.connect(self._ao_cor_amostrada)
        self.canvas.elipse_desenhada.connect(self._criar_elipse_por_arrasto)
        self.canvas.poligono_desenhado.connect(self._criar_poligono_por_arrasto)
        self.canvas.acabamento_desenhado.connect(self._criar_acabamento_por_arrasto)
        self.canvas.callout_solicitado.connect(self._criar_callout_por_clique)
        self.canvas.tabela_solicitada.connect(self._criar_tabela_por_clique)
        self.canvas.simbolo_solicitado.connect(self._criar_simbolo_por_clique)

        barra.hide()

    def _acao_icone(self, barra: QToolBar, tipo_icone: str, tooltip: str, callback) -> QAction:
        acao = QAction(construir_icone(tipo_icone), tooltip, self)
        acao.triggered.connect(callback)
        barra.addAction(acao)
        return acao

    def _ao_ferramenta_alterada(self, ferramenta: FerramentaMockup) -> None:
        """Mantém o botão certo marcado na paleta mesmo quando a
        ferramenta muda por fora de um clique nela — ex.: Esc, ou voltar
        pro ponteiro sozinho depois de criar um elemento (ver
        `_selecionar_e_voltar_ao_ponteiro`)."""
        acao = self._acoes_ferramenta.get(ferramenta)
        if acao is not None:
            acao.setChecked(True)

    def _ao_selecao_mockup_mudar(self) -> None:
        selecionados = [item for item in self.canvas.cena.selectedItems() if isinstance(item, ElementoMockup)]
        if len(selecionados) > 1:
            self.painel_propriedades_mockup.definir_selecao_multipla(len(selecionados))
        else:
            self.painel_propriedades_mockup.definir_elemento(selecionados[0] if selecionados else None)

    def _posicao_central_canvas(self) -> QPointF:
        return self.canvas.mapToScene(self.canvas.viewport().rect().center())

    def _adicionar_elemento_mockup_e_selecionar(self, elemento: ElementoMockup) -> None:
        # Cada elemento novo nasce um pouco deslocado do anterior (efeito
        # "cascata", igual colar em qualquer editor vetorial) — sem isso,
        # criar vários elementos seguidos empilha tudo exatamente no
        # centro, um em cima do outro, impossível de distinguir/clicar.
        passo = 8.0 * (len(self.canvas.elementos_mockup) % 6)
        pos = self._posicao_central_canvas() + QPointF(passo, passo)
        self.canvas.adicionar_elemento_mockup(
            elemento, QPointF(pos.x() - elemento.largura / 2, pos.y() - elemento.altura / 2)
        )
        for item in self.canvas.cena.selectedItems():
            item.setSelected(False)
        elemento.setSelected(True)

    def _cor_tinta_padrao(self) -> CorImpressao:
        cores = self._cores_impressao_ativas()
        return cores[0] if cores else CorImpressao(nome="Preto", r=0, g=0, b=0)

    # ── Criar elemento direto no canvas (ferramenta ativa, ver
    # `_montar_barra_mockup`/`preview_canvas.py::FerramentaMockup`) ──────
    def _selecionar_e_voltar_ao_ponteiro(self, elemento: ElementoMockup) -> None:
        for item in self.canvas.cena.selectedItems():
            item.setSelected(False)
        elemento.setSelected(True)
        # Volta pro ponteiro depois de criar UM elemento — mais previsível
        # pra quem não é usuário assíduo de CAD do que a ferramenta ficar
        # presa até apertar Esc (convenção do CorelDRAW): sem isso, clicar
        # de novo em cima do elemento recém-criado desenharia outro em
        # cima, em vez de selecionar o que acabou de fazer.
        self.canvas.definir_ferramenta(FerramentaMockup.SELECIONAR)

    def _criar_retangulo_por_arrasto(self, rect: QRectF) -> None:
        elemento = ElementoRetangulo(largura=rect.width(), altura=rect.height(), cor_tinta=self._cor_tinta_padrao())
        self.canvas.adicionar_elemento_mockup(elemento, rect.topLeft())
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    def _criar_linha_por_arrasto(self, p1: QPointF, p2: QPointF) -> None:
        vetor = p2 - p1
        comprimento = math.hypot(vetor.x(), vetor.y())
        angulo = math.degrees(math.atan2(vetor.y(), vetor.x()))
        elemento = ElementoLinha(largura=comprimento, cor_tinta=self._cor_tinta_padrao())
        self.canvas.adicionar_elemento_mockup(elemento, p1)
        elemento.setRotation(angulo)
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    def _criar_texto_por_clique(self, pos: QPointF) -> None:
        elemento = ElementoTexto(
            texto="Texto", fonte_familia=configuracoes.fonte_padrao_texto(), cor_tinta=self._cor_tinta_padrao()
        )
        self.canvas.adicionar_elemento_mockup(elemento, pos)
        self._selecionar_e_voltar_ao_ponteiro(elemento)
        elemento.iniciar_edicao_inline()

    def _criar_elipse_por_arrasto(self, rect: QRectF) -> None:
        elemento = ElementoElipse(largura=rect.width(), altura=rect.height(), cor_tinta=self._cor_tinta_padrao())
        self.canvas.adicionar_elemento_mockup(elemento, rect.topLeft())
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    def _criar_poligono_por_arrasto(self, rect: QRectF) -> None:
        elemento = ElementoPoligono(largura=rect.width(), altura=rect.height(), cor_tinta=self._cor_tinta_padrao())
        self.canvas.adicionar_elemento_mockup(elemento, rect.topLeft())
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    def _criar_acabamento_por_arrasto(self, rect: QRectF) -> None:
        elemento = ElementoAcabamento(largura=rect.width(), altura=rect.height())
        self.canvas.adicionar_elemento_mockup(elemento, rect.topLeft())
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    def _criar_callout_por_clique(self, pos: QPointF) -> None:
        elemento = ElementoCallout(texto="Observação", cor_tinta=self._cor_tinta_padrao())
        self.canvas.adicionar_elemento_mockup(elemento, pos)
        self._selecionar_e_voltar_ao_ponteiro(elemento)
        elemento.iniciar_edicao_inline()

    def _criar_tabela_por_clique(self, pos: QPointF) -> None:
        elemento = ElementoTabela(cor_tinta=self._cor_tinta_padrao())
        self.canvas.adicionar_elemento_mockup(elemento, pos)
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    def _criar_simbolo_por_clique(self, pos: QPointF) -> None:
        elemento = ElementoSimbolo(cor_tinta=self._cor_tinta_padrao())
        self.canvas.adicionar_elemento_mockup(elemento, pos)
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    _TIPOS_COM_COR_TINTA = (
        ElementoTexto,
        ElementoRetangulo,
        ElementoLinha,
        ElementoChecklistCores,
        ElementoElipse,
        ElementoPoligono,
        ElementoCallout,
        ElementoTabela,
        ElementoSimbolo,
    )

    def _ao_cor_amostrada(self, cor: QColor) -> None:
        """Conta-gotas: aplica a cor mais PRÓXIMA entre as tintas
        marcadas na legenda ao(s) elemento(s) selecionado(s) — a caixa só
        imprime nas cores de tinta reais (ver docstring de `estilo.py`),
        então não faz sentido aplicar o RGB exato de um pixel amostrado
        (isso ia gerar uma "3ª tinta" fora do que a legenda permite)."""
        selecionados = [it for it in self.canvas.cena.selectedItems() if isinstance(it, self._TIPOS_COM_COR_TINTA)]
        if not selecionados:
            self.statusBar().showMessage(
                "Selecione um elemento com cor de tinta antes de usar o conta-gotas.", 6000
            )
            self.canvas.definir_ferramenta(FerramentaMockup.SELECIONAR)
            return

        cores_ativas = self._cores_impressao_ativas()
        if not cores_ativas:
            self.statusBar().showMessage("Marque uma cor na legenda pra poder aplicar aqui.", 6000)
            self.canvas.definir_ferramenta(FerramentaMockup.SELECIONAR)
            return

        def distancia(tinta: CorImpressao) -> int:
            return (tinta.r - cor.red()) ** 2 + (tinta.g - cor.green()) ** 2 + (tinta.b - cor.blue()) ** 2

        cor_mais_proxima = min(cores_ativas, key=distancia)
        for elemento in selecionados:
            elemento.definir_cor_tinta(cor_mais_proxima)
        if len(selecionados) == 1:
            # Reconstrói a barra de propriedades pra refletir a nova cor
            # no combo — `definir_cor_tinta` só repinta o elemento, não
            # avisa o combo sozinho.
            self.painel_propriedades_mockup.definir_elemento(selecionados[0])
        self.statusBar().showMessage(f"Cor aplicada: {cor_mais_proxima.nome}", 6000)
        self.canvas.definir_ferramenta(FerramentaMockup.SELECIONAR)

    def _adicionar_checklist(self) -> None:
        self._adicionar_elemento_mockup_e_selecionar(
            ElementoChecklistCores(variantes=["Cor 1", "Cor 2"], cor_tinta=self._cor_tinta_padrao())
        )

    def _adicionar_imagem(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Adicionar imagem", "", "Imagens (*.png)")
        if not caminho:
            return
        try:
            elemento = ElementoImagem(caminho)
        except ValueError as exc:
            QMessageBox.critical(self, "Erro ao abrir imagem", str(exc))
            return
        self._adicionar_elemento_mockup_e_selecionar(elemento)

    def _adicionar_logo(self) -> None:
        # Aceita PNG/JPG além de SVG — pra quem só tem o logotipo em
        # imagem (o caso mais comum na prática, a maioria das empresas
        # não tem versão vetorial à mão), não faz sentido travar no
        # formato: quem pediu "logotipo" quer usar o arquivo que tem, a
        # separação de cor automática só se aplica quando é SVG mesmo.
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Adicionar logotipo", "", "Logotipos (*.svg *.png *.jpg *.jpeg);;SVG (*.svg);;Imagem (*.png *.jpg *.jpeg)"
        )
        if not caminho:
            return
        try:
            if caminho.lower().endswith(".svg"):
                elemento = ElementoLogoVetorial(caminho)
            else:
                elemento = ElementoImagem(caminho)
        except ValueError as exc:
            QMessageBox.critical(self, "Erro ao abrir logotipo", str(exc))
            return
        self._adicionar_elemento_mockup_e_selecionar(elemento)
        if isinstance(elemento, ElementoLogoVetorial) and elemento.cores_detectadas:
            self._remapear_cores_logo(elemento)

    def _remapear_cores_logo(self, elemento: ElementoLogoVetorial) -> None:
        dialogo = DialogoSepararCoresLogo(elemento.cores_detectadas, self._cores_impressao_ativas(), self)
        if dialogo.exec() == DialogoSepararCoresLogo.DialogCode.Accepted:
            elemento.definir_mapa_cores(dialogo.mapa_escolhido())

    def _remover_elemento_mockup_selecionado(self) -> None:
        self.canvas.remover_selecionados()
        self.painel_propriedades_mockup.definir_elemento(None)

    def _definir_reguas_visiveis(self, visivel: bool) -> None:
        self.regua_horizontal.setVisible(visivel)
        self.regua_vertical.setVisible(visivel)
        self._canto_reguas.setVisible(visivel)

    def _abrir_configuracoes(self) -> None:
        dialogo = DialogoConfiguracoes(self)
        if dialogo.exec() == DialogoConfiguracoes.DialogCode.Accepted:
            self.statusBar().showMessage("Configurações salvas", 6000)
            if dialogo.tema_alterado:
                resposta = QMessageBox.question(
                    self,
                    "Reiniciar agora?",
                    "O novo tema só aparece depois de reiniciar o app. Fechar agora?",
                )
                if resposta == QMessageBox.StandardButton.Yes:
                    self.close()

    def _abrir_manual(self) -> None:
        # Não-modal (`show`, não `exec`) de propósito — o usuário
        # provavelmente quer consultar um tópico E continuar trabalhando
        # no canvas ao mesmo tempo (ex.: ler sobre uma ferramenta enquanto
        # testa ela), não travado numa janela até fechar.
        if self._dialogo_manual is None:
            self._dialogo_manual = DialogoManual(self)
        self._dialogo_manual.show()
        self._dialogo_manual.raise_()
        self._dialogo_manual.activateWindow()

    def _mostrar_sobre(self) -> None:
        QMessageBox.about(
            self,
            "Sobre o Autoline",
            "<b>Autoline</b> — Gerador de Layout de Caixas<br><br>"
            "Gera o layout técnico de corte/vinco de caixas e envoltórios "
            "a partir das medidas, com exportação em SVG, PDF, JPG e "
            "automação direta com o CorelDRAW.<br><br>"
            "<i>Autoline é um nome de trabalho — rebranding ainda em aberto.</i>",
        )

    @contextmanager
    def _cursor_espera(self):
        """Mostra o cursor de espera durante uma exportação/conexão com o
        CorelDRAW — sem isso a janela fica sem nenhum feedback visual
        enquanto renderiza um JPG grande ou desenha centenas de linhas no
        CorelDRAW, e passa a impressão de estar travada."""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            yield
        finally:
            QApplication.restoreOverrideCursor()

    def _layout_pronto_para_exportar(self) -> bool:
        layout = self.canvas.layout_atual
        if layout is None or not layout.linhas:
            QMessageBox.warning(self, "Nada para exportar", "Informe as medidas da caixa antes de exportar.")
            return False
        return True

    def _exportar_svg(self) -> None:
        if not self._layout_pronto_para_exportar():
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar como SVG", "layout.svg", "SVG (*.svg)")
        if not caminho:
            return
        try:
            with self._cursor_espera():
                exportacao.exportar_svg(self.canvas.cena, self.canvas.layout_atual, caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
        else:
            self.statusBar().showMessage(f"Exportado: {caminho}", 6000)

    def _exportar_pdf(self) -> None:
        if not self._layout_pronto_para_exportar():
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar como PDF", "layout.pdf", "PDF (*.pdf)")
        if not caminho:
            return
        try:
            with self._cursor_espera():
                exportacao.exportar_pdf(self.canvas.cena, self.canvas.layout_atual, caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
        else:
            self.statusBar().showMessage(f"Exportado: {caminho}", 6000)

    def _exportar_jpg(self) -> None:
        if not self._layout_pronto_para_exportar():
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar como JPG", "layout.jpg", "JPEG (*.jpg)")
        if not caminho:
            return
        try:
            with self._cursor_espera():
                exportacao.exportar_jpg(self.canvas.cena, self.canvas.layout_atual, caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
        else:
            self.statusBar().showMessage(f"Exportado: {caminho}", 6000)

    def _conectar_corel(self) -> None:
        try:
            with self._cursor_espera():
                self._corel_app = corel_bridge.conectar()
        except corel_bridge.CorelIndisponivel as exc:
            QMessageBox.critical(self, "Erro ao conectar", str(exc))
        else:
            self.statusBar().showMessage("Conectado ao CorelDRAW", 6000)

    def _exportar_corel(self) -> None:
        if not self._layout_pronto_para_exportar():
            return
        try:
            with self._cursor_espera():
                if self._corel_app is None:
                    self._corel_app = corel_bridge.conectar()
                corel_bridge.desenhar_layout(
                    self._corel_app, self.canvas.layout_atual, self.canvas.elementos_mockup
                )
        except corel_bridge.CorelIndisponivel as exc:
            self._corel_app = None
            QMessageBox.critical(self, "Erro ao conectar", str(exc))
        except Exception as exc:  # noqa: BLE001
            self._corel_app = None
            QMessageBox.critical(self, "Erro ao desenhar no CorelDRAW", str(exc))
        else:
            self.statusBar().showMessage("Novo layout desenhado no CorelDRAW", 6000)

    def _paineis_disponiveis(self) -> list[Painel]:
        return list(self._paineis_atuais)

    def _recalcular(self) -> None:
        medidas = self._obter_medidas()
        layout = self._servico.calcular(medidas)
        self.canvas.definir_layout(layout)
        self.painel_legenda_cores.definir_cores(layout.cores_legenda)
        self._paineis_atuais = calcular_paineis(medidas.tipo, layout.segmentos_impressora, layout.segmentos_riscador)
        self.canvas.definir_paineis(self._paineis_atuais)

        self.linha_impressora.atualizar_valores_efetivos(layout.segmentos_impressora)
        self.linha_impressora.definir_total(layout.largura_total)
        self.linha_riscador.atualizar_valores_efetivos(
            layout.segmentos_riscador + [0.0] * (5 - len(layout.segmentos_riscador))
        )
        self.linha_riscador.definir_total(layout.altura_total)

        self.statusBar().showMessage(layout.descricao)
