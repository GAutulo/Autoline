"""Janela principal do Gerador de Layout de Caixas."""

from __future__ import annotations

from contextlib import contextmanager

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
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
    QScrollArea,
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
from . import corel_bridge, exportacao
from .dialogo_configuracoes import DialogoConfiguracoes
from .dialogo_logo import DialogoSepararCoresLogo
from .estilo import Cor
from .mockup_checklist import ElementoChecklistCores
from .mockup_formas import ElementoLinha, ElementoRetangulo
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_texto import ElementoTexto
from .painel_propriedades_mockup import PainelPropriedadesMockup
from .preview_canvas import PainelLegendaCores, PreviewCanvas
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

        self._montar_ui()
        self._montar_dock_propriedades_mockup()
        self._montar_abas_tela()
        self._montar_barra_ferramentas()
        self._montar_barra_mockup()
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
        vbox_legenda_canvas.addWidget(self.canvas, 1)
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
        self.dock_propriedades_mockup.setVisible(modo_layout)
        self.canvas.definir_modo_mockup(modo_layout)
        if not modo_layout:
            self.painel_propriedades_mockup.definir_elemento(None)
        # Mostrar/esconder os painéis ao redor muda o tamanho disponível
        # do canvas — sem reencaixar aqui, a visão que estava centralizada
        # antes da troca fica deslocada (às vezes "presa" perto do canto
        # superior esquerdo) porque o zoom/posição antigos não fazem mais
        # sentido pro novo tamanho de viewport.
        self.canvas.ajustar_a_tela()

    # ── Mockup (Fase 2): dock de propriedades, barra e criação de itens ─
    def _montar_dock_propriedades_mockup(self) -> None:
        self.painel_propriedades_mockup = PainelPropriedadesMockup(
            self._cores_impressao_ativas, self._paineis_disponiveis
        )
        self.painel_propriedades_mockup.remover_solicitado = self._remover_elemento_mockup_selecionado
        self.painel_propriedades_mockup.remapear_logo_solicitado = self._remapear_cores_logo

        # QScrollArea entre o dock e o painel: o painel cresce bastante
        # pra elementos com mais campos (ex.: checklist com várias
        # variantes) — sem rolagem, numa janela restaurada (não
        # maximizada, ver `self.resize` no __init__) o botão "Remover
        # elemento" ficava cortado embaixo, fora da área visível, sem
        # nenhum jeito de rolar até ele (achado revisando, não reportado
        # pelo usuário — mas era um bug de verdade).
        rolagem = QScrollArea()
        rolagem.setWidget(self.painel_propriedades_mockup)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.Shape.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Sem isso, o `QScrollArea` não repassa a largura preferida do
        # painel de propriedades pro dock (o `sizeHint` de um QScrollArea
        # não reflete o do widget lá dentro) — o dock encolhia pra ~140px
        # e cortava toda label/campo na horizontal. Achado revisando com
        # a rolagem vertical ligada, não é óbvio olhando só o caso feliz
        # (janela grande, nada rolando).
        rolagem.setMinimumWidth(340)

        self.dock_propriedades_mockup = QDockWidget("Propriedades", self)
        self.dock_propriedades_mockup.setWidget(rolagem)
        self.dock_propriedades_mockup.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        # Sem botão de fechar de propósito: a visibilidade já é controlada
        # pela troca de tela (ver `_trocar_tela`) — se o usuário fechasse
        # pelo X nativo, não ia ter como reabrir sem reiniciar o app.
        self.dock_propriedades_mockup.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_propriedades_mockup)
        self.dock_propriedades_mockup.hide()  # só aparece na tela de Layout (ver _trocar_tela)

    def _montar_barra_mockup(self) -> None:
        """Barra de ferramentas do mockup — só fica visível dentro do
        modo mockup (ver `_alternar_modo_mockup`), pra não poluir a
        barra principal com botões que não fazem sentido enquanto o
        usuário só está ajustando a dieline."""
        # Quebra de linha de propósito: sem isso, o Qt tenta encaixar essa
        # barra na mesma linha da barra principal (que já tem exportação +
        # zoom), e a ordem de leitura fica confusa — os botões de criar
        # elemento apareceriam DEPOIS do "Ajustar à tela". Numa linha
        # própria fica claro que são dois grupos de ferramentas diferentes.
        self.addToolBarBreak()
        barra = QToolBar("Mockup")
        barra.setMovable(False)
        barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(barra)
        self.barra_mockup = barra

        barra.addAction("Texto", self._adicionar_texto)
        barra.addAction("Retângulo", self._adicionar_retangulo)
        barra.addAction("Linha", self._adicionar_linha)
        barra.addAction("Imagem...", self._adicionar_imagem)
        barra.addAction("Logotipo...", self._adicionar_logo)
        barra.addAction("Checklist de cores", self._adicionar_checklist)
        barra.addSeparator()
        acao_agrupar = barra.addAction("Agrupar", lambda: self.canvas.agrupar_selecionados())
        acao_agrupar.setToolTip("Ctrl+G")
        acao_desagrupar = barra.addAction("Desagrupar", lambda: self.canvas.desagrupar_selecionados())
        acao_desagrupar.setToolTip("Ctrl+Shift+G")
        barra.addSeparator()
        acao_frente = barra.addAction("Trazer p/ frente", lambda: self.canvas.trazer_para_frente())
        acao_frente.setToolTip("Ctrl+Home")
        acao_tras = barra.addAction("Enviar p/ trás", lambda: self.canvas.enviar_para_tras())
        acao_tras.setToolTip("Ctrl+End")

        barra.hide()

    def _ao_selecao_mockup_mudar(self) -> None:
        selecionados = [item for item in self.canvas.cena.selectedItems() if isinstance(item, ElementoMockup)]
        self.painel_propriedades_mockup.definir_elemento(selecionados[0] if len(selecionados) == 1 else None)

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

    def _adicionar_texto(self) -> None:
        self._adicionar_elemento_mockup_e_selecionar(ElementoTexto(texto="Texto", cor_tinta=self._cor_tinta_padrao()))

    def _adicionar_retangulo(self) -> None:
        self._adicionar_elemento_mockup_e_selecionar(ElementoRetangulo(cor_tinta=self._cor_tinta_padrao()))

    def _adicionar_linha(self) -> None:
        self._adicionar_elemento_mockup_e_selecionar(ElementoLinha(cor_tinta=self._cor_tinta_padrao()))

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
