"""Janela principal do Gerador de Layout de Caixas."""

from __future__ import annotations

import dataclasses
import math
from contextlib import contextmanager

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
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
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..layout_service import ServicoLayoutCaixa
from ..models import CorImpressao, MedidasCaixa, NOME_EXIBICAO_TIPO_CAIXA, TipoCaixa, TipoLinha
from ..paineis import Painel, calcular_paineis
from . import configuracoes, corel_bridge, exportacao
from .area_trabalho_corel import BotaoFlyout, PainelStatus, PaletaCores
from .dialogo_configuracoes import DialogoConfiguracoes
from .dockers_corel import DockerAlinhar, DockerObjetos, DockerTransformacoes
from .dialogo_logo import DialogoSepararCoresLogo
from .dialogo_manual import DialogoManual
from .dialogo_tabela import DialogoTabela
from .estilo import Cor
from .mockup_acabamento import ElementoAcabamento
from .mockup_callout import ElementoCallout
from .mockup_checklist import ElementoChecklistCores
from .mockup_cota import ElementoCota, criar_cota
from .mockup_curva import curva_de_caminho_cena
from .mockup_formas import ElementoElipse, ElementoLinha, ElementoPoligono, ElementoRetangulo
from .mockup_icones import construir_icone
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_reguas import ReguaHorizontal, ReguaVertical
from .mockup_simbolos import ElementoSimbolo
from .mockup_tabela import ElementoTabela
from .mockup_texto import ElementoTexto
from .painel_propriedades_mockup import NOME_TIPO_ELEMENTO, PainelPropriedadesMockup
from .preview_canvas import AJUSTAR_A, FerramentaMockup, PainelLegendaCores, PreviewCanvas
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
        self._montar_painel_status()
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

        # Aviso de faca editada à mão (ver `_ao_faca_editada`): as medidas
        # ficam travadas até descartar as edições.
        self.aviso_faca_editada = QWidget()
        aviso = QVBoxLayout(self.aviso_faca_editada)
        aviso.setContentsMargins(0, 0, 0, 0)
        texto_aviso = QLabel("Faca editada à mão. As medidas estão travadas pra não desfazer a edição.")
        texto_aviso.setWordWrap(True)
        texto_aviso.setStyleSheet(f"color: {Cor.ERRO}; font-weight: 600;")
        botao_descartar = QPushButton("Descartar edições da faca")
        botao_descartar.clicked.connect(lambda: self.canvas.descartar_edicoes_faca())
        aviso.addWidget(texto_aviso)
        aviso.addWidget(botao_descartar)
        self.aviso_faca_editada.hide()
        vbox.addWidget(self.aviso_faca_editada)

        grupo_tipo = QGroupBox("Tipo de caixa")
        self._grupo_tipo = grupo_tipo
        form_tipo = QFormLayout(grupo_tipo)
        form_tipo.setVerticalSpacing(10)
        self.combo_tipo = QComboBox()
        for tipo in TipoCaixa:
            self.combo_tipo.addItem(NOME_EXIBICAO_TIPO_CAIXA[tipo], tipo)
        self.combo_tipo.setCurrentIndex(list(TipoCaixa).index(TipoCaixa.MALETA_NORMAL))
        form_tipo.addRow(self.combo_tipo)
        vbox.addWidget(grupo_tipo)

        grupo_medidas = QGroupBox("Medidas C × L × A (mm)")
        self._grupo_medidas_cla = grupo_medidas
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
        menu_exibir.addMenu(self._menu_ajustar_a)
        menu_dockers = menu_exibir.addMenu("Janelas de encaixe (Layout)")
        for dock in self._docks.values():
            menu_dockers.addAction(dock.toggleViewAction())
        self._menu_dockers = menu_dockers

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
        self.barra_faca.setVisible(indice == 0)
        self._atalho_editar_faca.setEnabled(indice == 0)  # no Layout, F10 é a Forma de curvas
        if indice != 0:
            self._acoes_faca["navegar"].setChecked(True)
            self.canvas.definir_edicao_faca(False)
        self.barra_organizar.setVisible(modo_layout)
        self.barra_paleta.setVisible(modo_layout)
        # Dockers só na tela de Layout: ao sair, lembra quais estavam
        # abertos pra reabrir na volta.
        if modo_layout:
            for chave in self._docks_abertos_layout:
                self._docks[chave].show()
        else:
            if self._estava_no_layout:
                self._docks_abertos_layout = {chave for chave, dock in self._docks.items() if dock.isVisible()}
            for dock in self._docks.values():
                dock.hide()
        self._estava_no_layout = modo_layout
        self._menu_dockers.setEnabled(modo_layout)
        for acao in self._acoes_docker:
            acao.setEnabled(modo_layout)
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
        self.painel_propriedades_mockup.obter_tamanho_pagina = self._tamanho_pagina

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

    def _tamanho_pagina(self) -> tuple[float, float] | None:
        pagina = self.canvas.retangulo_pagina()
        return None if pagina is None else (pagina.width(), pagina.height())

    def _montar_barra_mockup(self) -> None:
        """Caixa de ferramentas do modo Layout no estilo CorelDRAW (ver
        REFERENCIA_CORELDRAW.md, seção 2): vertical, na borda ESQUERDA,
        só ícone com tooltip, com ferramentas irmãs agrupadas em
        *flyouts* (`BotaoFlyout`) — segurar o clique ou clicar no
        triângulo do canto abre o grupo.

        Selecionar/Texto/Retângulo/Linha... são uma FERRAMENTA (ver
        `FerramentaMockup` em `preview_canvas.py`) — só uma ativa por
        vez, num `QActionGroup` exclusivo. Inserir imagem/logotipo/
        checklist continuam ações de um clique, no último flyout.
        Desfazer/agrupar/ordem ficam na barra "Organizar" do topo, como
        na barra padrão do CorelDRAW (ver `_montar_barra_organizar`)."""
        barra = QToolBar("Caixa de ferramentas")
        barra.setObjectName("paletaFerramentasMockup")
        barra.setMovable(False)
        barra.setOrientation(Qt.Orientation.Vertical)
        barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, barra)
        self.barra_mockup = barra

        self._acoes_ferramenta: dict[FerramentaMockup, QAction] = {}
        self._botoes_flyout: list[BotaoFlyout] = []
        grupo_ferramentas = QActionGroup(self)
        grupo_ferramentas.setExclusive(True)

        def ferramenta(tipo_icone: str, tooltip: str, f: FerramentaMockup) -> QAction:
            acao = QAction(construir_icone(tipo_icone), tooltip, self)
            acao.setCheckable(True)
            acao.triggered.connect(lambda: self.canvas.definir_ferramenta(f))
            grupo_ferramentas.addAction(acao)
            self._acoes_ferramenta[f] = acao
            return acao

        def acao_simples(tipo_icone: str, tooltip: str, callback) -> QAction:
            acao = QAction(construir_icone(tipo_icone), tooltip, self)
            acao.triggered.connect(callback)
            return acao

        def flyout(*acoes: QAction) -> None:
            botao = BotaoFlyout(list(acoes))
            barra.addWidget(botao)
            self._botoes_flyout.append(botao)

        flyout(
            ferramenta(
                "selecionar",
                "Seleção (Espaço) — clique direito durante o arrasto deixa uma cópia, Ctrl ou Shift restringe a um eixo",
                FerramentaMockup.SELECIONAR,
            ),
            ferramenta(
                "ferramenta_laco",
                "Seleção à mão livre — clique pra cada vértice, feche perto do primeiro ponto",
                FerramentaMockup.LACO_SELECAO,
            ),
            ferramenta(
                "ferramenta_mover_preciso",
                "Mover de precisão — clique no ponto de pega, depois no ponto de solta",
                FerramentaMockup.MOVER_PRECISO,
            ),
        )
        flyout(
            ferramenta(
                "ferramenta_forma",
                "Forma (F10) — edita os nós de uma curva: arraste nó/alça; duplo clique na curva adiciona nó, "
                "no nó remove; S alterna canto/suave; Delete remove o nó",
                FerramentaMockup.FORMA,
            )
        )
        barra.addSeparator()
        flyout(
            ferramenta("ferramenta_mao_livre", "Mão livre (F5) — arraste pra desenhar à mão", FerramentaMockup.MAO_LIVRE),
            ferramenta("ferramenta_linha", "Linha de 2 pontos — clique e arraste (Ctrl = ângulo em passos de 15°)", FerramentaMockup.LINHA),
            ferramenta(
                "ferramenta_bezier",
                "Bézier — clique = nó de canto, clique e arraste = nó suave; clique no 1º nó fecha, "
                "duplo clique/Enter termina aberta, Esc cancela",
                FerramentaMockup.BEZIER,
            ),
        )
        flyout(
            ferramenta(
                "ferramenta_retangulo",
                "Retângulo (F6) — clique e arraste (Ctrl = quadrado, Shift = a partir do centro)",
                FerramentaMockup.RETANGULO,
            )
        )
        flyout(
            ferramenta(
                "ferramenta_elipse", "Elipse (F7) — clique e arraste (Ctrl = círculo, Shift = a partir do centro)", FerramentaMockup.ELIPSE
            )
        )
        flyout(
            ferramenta(
                "ferramenta_poligono",
                "Polígono (Y) — clique e arraste (nº de lados ajustável; Ctrl = lados iguais, Shift = do centro)",
                FerramentaMockup.POLIGONO,
            ),
            ferramenta("ferramenta_tabela", "Tabela — clique no canvas (ficha técnica/nutricional)", FerramentaMockup.TABELA),
            ferramenta(
                "ferramenta_simbolo",
                "Símbolo de manuseio — clique no canvas (frágil, este lado para cima, reciclável...)",
                FerramentaMockup.SIMBOLO,
            ),
        )
        flyout(ferramenta("ferramenta_texto", "Texto (F8) — clique no canvas e digite direto ali", FerramentaMockup.TEXTO))
        barra.addSeparator()
        flyout(
            ferramenta(
                "cota_paralela",
                "Cota paralela — arraste de um ponto a outro; gruda nos cantos da faca e dos objetos (Ctrl = 15°)",
                FerramentaMockup.COTA_PARALELA,
            ),
            ferramenta("cota_horizontal", "Cota horizontal — mede só a distância na horizontal", FerramentaMockup.COTA_HORIZONTAL),
            ferramenta("cota_vertical", "Cota vertical — mede só a distância na vertical", FerramentaMockup.COTA_VERTICAL),
            ferramenta("medida", "Medida — leitura temporária entre 2 pontos (não fica no desenho)", FerramentaMockup.MEDIR),
            ferramenta("ferramenta_callout", "Chamada (callout) — clique no canvas pra anotar", FerramentaMockup.CALLOUT),
        )
        flyout(
            ferramenta(
                "ferramenta_transparencia",
                "Acabamento de produção — clique e arraste (Shift = a partir do centro; verniz, laminação, hot stamping)",
                FerramentaMockup.ACABAMENTO,
            )
        )
        flyout(
            ferramenta(
                "conta_gotas", "Conta-gotas — clica numa cor da tela e aplica no elemento selecionado", FerramentaMockup.CONTA_GOTAS
            )
        )
        barra.addSeparator()
        flyout(
            acao_simples("ferramenta_imagem", "Importar imagem...", self._adicionar_imagem),
            acao_simples("ferramenta_logo", "Importar logotipo...", self._adicionar_logo),
            acao_simples("lista", "Checklist de cores", self._adicionar_checklist),
        )
        self._acoes_ferramenta[FerramentaMockup.SELECIONAR].setChecked(True)

        self.canvas.ferramenta_alterada.connect(self._ao_ferramenta_alterada)
        self.canvas.retangulo_desenhado.connect(self._criar_retangulo_por_arrasto)
        self.canvas.linha_desenhada.connect(self._criar_linha_por_arrasto)
        self.canvas.cota_desenhada.connect(self._criar_cota_por_arrasto)
        self.canvas.curva_desenhada.connect(self._criar_curva)
        self.canvas.mensagem_status.connect(lambda texto: self.statusBar().showMessage(texto, 6000))
        self.canvas.texto_solicitado.connect(self._criar_texto_por_clique)
        self.canvas.cor_amostrada.connect(self._ao_cor_amostrada)
        self.canvas.elipse_desenhada.connect(self._criar_elipse_por_arrasto)
        self.canvas.poligono_desenhado.connect(self._criar_poligono_por_arrasto)
        self.canvas.acabamento_desenhado.connect(self._criar_acabamento_por_arrasto)
        self.canvas.callout_solicitado.connect(self._criar_callout_por_clique)
        self.canvas.tabela_solicitada.connect(self._criar_tabela_por_clique)
        self.canvas.simbolo_solicitado.connect(self._criar_simbolo_por_clique)

        barra.hide()

        self._montar_barra_organizar()
        self._montar_paleta_cores()
        self._montar_dockers()
        self._montar_barra_faca()

    def _montar_barra_faca(self) -> None:
        """Edição da faca na tela Dieline (o "ajuste à mão com a ferramenta
        Forma" que antes era feito no CorelDRAW): navegar, editar
        linhas/pontas, desenhar linha nova de corte ou vinco, mudar o tipo
        da linha selecionada e remover. Só aparece na tela Dieline."""
        barra = QToolBar("Faca")
        barra.setObjectName("paletaFerramentasMockup")
        barra.setMovable(False)
        barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, barra)
        self.barra_faca = barra

        grupo = QActionGroup(self)
        grupo.setExclusive(True)
        self._acoes_faca: dict[str, QAction] = {}

        def modo(chave: str, icone: str, dica: str) -> None:
            acao = QAction(construir_icone(icone), dica, self)
            acao.setCheckable(True)
            acao.triggered.connect(lambda: self._definir_modo_faca(chave))
            grupo.addAction(acao)
            barra.addAction(acao)
            self._acoes_faca[chave] = acao

        modo("navegar", "navegar", "Navegar — arrastar move a visão (a faca não muda)")
        modo(
            "forma",
            "ferramenta_forma",
            "Editar faca (F10) — clique numa linha; arraste a linha ou uma ponta (as linhas ligadas acompanham; "
            "Alt solta a ponta, Shift trava na horizontal/vertical). Delete remove a linha",
        )
        modo("corte", "linha_corte", "Nova linha de corte — arraste de um ponto a outro (Ctrl = 15°)")
        modo("vinco", "linha_vinco", "Nova linha de vinco — arraste de um ponto a outro (Ctrl = 15°)")
        self._acoes_faca["navegar"].setChecked(True)
        barra.addSeparator()

        self.combo_tipo_linha = QComboBox()
        self.combo_tipo_linha.setToolTip("Tipo da linha selecionada")
        for tipo, nome in (
            (TipoLinha.CORTE, "Corte"),
            (TipoLinha.VINCO, "Vinco"),
            (TipoLinha.MEIO_CORTE, "Meio corte"),
            (TipoLinha.CORTE_SERRA, "Corte de serra"),
            (TipoLinha.DOBRA, "Dobra (auxiliar)"),
        ):
            self.combo_tipo_linha.addItem(nome, tipo)
        self.combo_tipo_linha.setEnabled(False)
        self.combo_tipo_linha.activated.connect(
            lambda _i: self.canvas.definir_tipo_linha_selecionada(self.combo_tipo_linha.currentData())
        )
        barra.addWidget(self.combo_tipo_linha)
        self._acao_remover_linha = self._acao_icone(
            barra, "remover", "Remover a linha selecionada (Delete)", lambda: self.canvas.remover_linha_faca_selecionada()
        )
        self._acao_remover_linha.setEnabled(False)

        self.canvas.linha_faca_selecionada.connect(self._ao_selecionar_linha_faca)
        self.canvas.faca_editada_alterada.connect(self._ao_faca_editada)
        atalho = QAction(self)
        atalho.setShortcut(QKeySequence("F10"))
        atalho.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        atalho.triggered.connect(lambda: self._acoes_faca["forma"].trigger())
        self.addAction(atalho)
        self._atalho_editar_faca = atalho

    def _definir_modo_faca(self, chave: str) -> None:
        if chave == "navegar":
            self.canvas.definir_edicao_faca(False)
        else:
            self.canvas.definir_edicao_faca(True, chave)

    def _ao_selecionar_linha_faca(self, tipo) -> None:
        self.combo_tipo_linha.setEnabled(tipo is not None)
        self._acao_remover_linha.setEnabled(tipo is not None)
        if tipo is not None:
            indice = self.combo_tipo_linha.findData(tipo)
            if indice >= 0:
                self.combo_tipo_linha.setCurrentIndex(indice)

    def _ao_faca_editada(self, editada: bool) -> None:
        """Faca editada à mão: trava tipo e medidas (mudar qualquer uma
        recalcularia a faca e jogaria a edição fora sem aviso)."""
        self.aviso_faca_editada.setVisible(editada)
        for widget in (self._grupo_tipo, self._grupo_medidas_cla, self._grupo_medidas):
            widget.setEnabled(not editada)
        if editada:
            self.statusBar().showMessage("Faca editada à mão — medidas travadas até descartar as edições.", 6000)

    def _montar_barra_organizar(self) -> None:
        """Desfazer/refazer, agrupar e ordem — no topo, como a barra
        padrão do CorelDRAW (não na caixa de ferramentas)."""
        barra = QToolBar("Organizar")
        barra.setObjectName("paletaFerramentasMockup")
        barra.setMovable(False)
        barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, barra)
        self.barra_organizar = barra

        self._montar_menu_ajustar_a()
        botao_ajustar = QToolButton()
        botao_ajustar.setText("Ajustar a")
        botao_ajustar.setToolTip("Onde os objetos grudam ao arrastar (como o \"Ajustar a\" do CorelDRAW)")
        botao_ajustar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        botao_ajustar.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        botao_ajustar.setMenu(self._menu_ajustar_a)
        barra.addWidget(botao_ajustar)
        barra.addSeparator()

        pilha = self.canvas.pilha_desfazer
        acao_desfazer = self._acao_icone(barra, "desfazer", "Desfazer (Ctrl+Z)", pilha.undo)
        acao_desfazer.setEnabled(False)
        pilha.canUndoChanged.connect(acao_desfazer.setEnabled)
        acao_refazer = self._acao_icone(barra, "refazer", "Refazer (Ctrl+Shift+Z)", pilha.redo)
        acao_refazer.setEnabled(False)
        pilha.canRedoChanged.connect(acao_refazer.setEnabled)
        barra.addSeparator()
        self._acao_icone(barra, "agrupar", "Agrupar (Ctrl+G)", lambda: self.canvas.agrupar_selecionados())
        self._acao_icone(barra, "desagrupar", "Desagrupar (Ctrl+U)", lambda: self.canvas.desagrupar_selecionados())
        barra.addSeparator()
        self._acao_icone(barra, "converter_curvas", "Converter em curvas (Ctrl+Q)", lambda: self.canvas.converter_selecionados_em_curvas())
        self._acao_icone(barra, "combinar", "Combinar (Ctrl+L)", lambda: self.canvas.combinar_selecionados())
        self._acao_icone(barra, "separar", "Separar (Ctrl+K)", lambda: self.canvas.separar_selecionados())
        barra.addSeparator()
        self._acao_icone(barra, "trazer_frente", "Para a frente da página (Shift+PgUp)", lambda: self.canvas.trazer_para_frente())
        self._acao_icone(barra, "enviar_tras", "Para trás da página (Shift+PgDn)", lambda: self.canvas.enviar_para_tras())
        barra.hide()

    def _montar_dockers(self) -> None:
        """Janelas de encaixe do CorelDRAW (ver `dockers_corel.py`), em
        abas na borda direita, entre o desenho e a paleta. Começam
        fechadas, como no CorelDRAW, e só existem na tela de Layout."""
        self.docker_objetos = DockerObjetos(self.canvas)
        self.docker_alinhar = DockerAlinhar(self.canvas)
        self.docker_transformacoes = DockerTransformacoes(self.canvas)
        self._docks: dict[str, QDockWidget] = {}
        anterior = None
        for chave, titulo, conteudo in (
            ("objetos", "Objetos", self.docker_objetos),
            ("alinhar", "Alinhar e distribuir", self.docker_alinhar),
            ("transformacoes", "Transformações", self.docker_transformacoes),
        ):
            dock = QDockWidget(titulo, self)
            dock.setObjectName(f"docker_{chave}")
            dock.setWidget(conteudo)
            dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            if anterior is not None:
                self.tabifyDockWidget(anterior, dock)
            anterior = dock
            dock.hide()
            self._docks[chave] = dock
        self._docks_abertos_layout: set[str] = set()
        self._estava_no_layout = False

        # Atalhos do CorelDRAW pra abrir cada docker (só na tela de Layout).
        self._acoes_docker: list[QAction] = []

        def atalho(texto: str, tecla: str, callback) -> None:
            acao = QAction(texto, self)
            acao.setShortcut(QKeySequence(tecla))
            acao.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            acao.triggered.connect(callback)
            acao.setEnabled(False)
            self.addAction(acao)
            self._acoes_docker.append(acao)

        atalho("Alinhar e distribuir", "Ctrl+Shift+A", lambda: self.abrir_docker("alinhar"))
        for tecla, aba in (("Alt+F7", "posicao"), ("Alt+F8", "rotacao"), ("Alt+F9", "escala"), ("Alt+F10", "tamanho")):
            atalho(f"Transformações ({aba})", tecla, lambda _c=False, a=aba: self.abrir_docker("transformacoes", a))

    def abrir_docker(self, chave: str, aba_transformacao: str | None = None) -> None:
        dock = self._docks[chave]
        dock.show()
        dock.raise_()
        if aba_transformacao is not None:
            self.docker_transformacoes.mostrar_aba(aba_transformacao)

    def _montar_menu_ajustar_a(self) -> None:
        """Menu "Ajustar a" (CorelDRAW): uma opção por fonte de encaixe.
        Fica no topo (barra Organizar) e em Exibir; Alt+Z e Ctrl+Y no
        canvas mudam o mesmo estado, e os dois menus acompanham."""
        menu = QMenu("Ajustar a", self)
        atalhos = {"objetos": "Alt+Z", "grade": "Ctrl+Y"}
        self._acoes_ajustar_a: dict[str, QAction] = {}
        for chave, rotulo in AJUSTAR_A.items():
            texto = rotulo + (" (quando visível)" if chave == "grade" else "")
            if chave in atalhos:
                texto += f"	{atalhos[chave]}"
            acao = menu.addAction(texto)
            acao.setCheckable(True)
            acao.setChecked(self.canvas.ajustar_a(chave))
            acao.toggled.connect(lambda ligado, c=chave: self.canvas.definir_ajustar_a(c, ligado))
            self._acoes_ajustar_a[chave] = acao
        self.canvas.ajustar_a_alterado.connect(self._ao_ajustar_a_alterado)
        self._menu_ajustar_a = menu

    def _ao_ajustar_a_alterado(self, chave: str, ligado: bool) -> None:
        acao = self._acoes_ajustar_a[chave]
        if acao.isChecked() != ligado:
            acao.setChecked(ligado)
        estado = "ligado" if ligado else "desligado"
        self.statusBar().showMessage(f"Ajustar a {AJUSTAR_A[chave].lower()}: {estado}", 4000)

    def _montar_paleta_cores(self) -> None:
        """Paleta vertical na borda DIREITA, como no CorelDRAW: clique
        esquerdo = preenchimento, direito = contorno, X = nenhum."""
        barra = QToolBar("Paleta de cores")
        barra.setObjectName("paletaCores")
        barra.setMovable(False)
        barra.setOrientation(Qt.Orientation.Vertical)
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, barra)
        paleta = PaletaCores(_CORES_DISPONIVEIS)
        paleta.preenchimento_escolhido.connect(lambda cor: self._aplicar_cor_paleta(cor, contorno=False))
        paleta.contorno_escolhido.connect(lambda cor: self._aplicar_cor_paleta(cor, contorno=True))
        barra.addWidget(paleta)
        self.barra_paleta = barra
        barra.hide()

    def _aplicar_cor_paleta(self, cor, contorno: bool) -> None:
        """Clique na paleta. O Autoline guarda UMA tinta por forma e uma
        chave "preenchido" — então esquerdo = tinta + preenchida, direito
        = tinta + só contorno, X esquerdo = tira o preenchimento. A tinta
        usada entra na legenda de cores se ainda não estava."""
        selecionados = [it for it in self.canvas.cena.selectedItems() if isinstance(it, ElementoMockup)]
        if not selecionados:
            self.statusBar().showMessage("Selecione um objeto pra aplicar a cor.", 5000)
            return
        if cor is None:
            if contorno:
                self.statusBar().showMessage("Contorno não pode ser removido — toda forma impressa tem traço.", 5000)
                return
            for el in selecionados:
                if hasattr(el, "definir_preenchido"):
                    el.definir_preenchido(False)
        else:
            nome, rgb = cor
            chip = self._chips_cor.get(nome, (None,))[0]
            if chip is not None and not chip.isChecked():
                chip.setChecked(True)
            tinta = CorImpressao(nome=nome.upper(), r=rgb[0], g=rgb[1], b=rgb[2])
            for el in selecionados:
                if hasattr(el, "definir_cor_tinta"):
                    el.definir_cor_tinta(tinta)
                if hasattr(el, "definir_preenchido"):
                    el.definir_preenchido(not contorno)
        self._ao_selecao_mockup_mudar()

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
            for botao in self._botoes_flyout:
                botao.mostrar(acao)

    def _montar_painel_status(self) -> None:
        """Barra de status do CorelDRAW: posição do cursor, objeto
        selecionado e amostras de preenchimento/contorno."""
        self.painel_status = PainelStatus()
        self.statusBar().addPermanentWidget(self.painel_status)
        self.canvas.cursor_movido.connect(self.painel_status.definir_posicao)
        self.painel_status.definir_objeto("", None, None, False)

    def _atualizar_status_objeto(self, selecionados: list[ElementoMockup]) -> None:
        if not selecionados:
            self.painel_status.definir_objeto("", None, None, False)
            return
        if len(selecionados) > 1:
            self.painel_status.definir_objeto(f"{len(selecionados)} objetos selecionados", None, None, False)
            return
        el = selecionados[0]
        nome = NOME_TIPO_ELEMENTO.get(type(el), "Objeto")
        descricao = f"{nome}  ·  {el.largura:.1f} × {el.altura:.1f} mm".replace(".", ",")
        cor_tinta = getattr(el, "cor_tinta", None)
        if cor_tinta is None:
            self.painel_status.definir_objeto(descricao, None, None, False)
            return
        cor = QColor(cor_tinta.r, cor_tinta.g, cor_tinta.b)
        if isinstance(el, ElementoLinha):
            preenchimento, contorno = None, cor
        elif hasattr(el, "preenchido"):
            preenchimento, contorno = (cor if el.preenchido else None), cor
        else:
            preenchimento, contorno = cor, None
        self.painel_status.definir_objeto(descricao, preenchimento, contorno, True)

    def _ao_selecao_mockup_mudar(self) -> None:
        selecionados = [item for item in self.canvas.cena.selectedItems() if isinstance(item, ElementoMockup)]
        self._atualizar_status_objeto(selecionados)
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
        # A rotação é em torno do CENTRO do elemento: posicionar pelo meio
        # do segmento (e não por p1) faz as pontas caírem em p1 e p2.
        origem = QPointF(elemento.largura / 2, elemento.altura / 2)
        self.canvas.adicionar_elemento_mockup(elemento, (p1 + p2) / 2 - origem)
        elemento.setRotation(angulo)
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    def _criar_curva(self, caminho_cena) -> None:
        curva = curva_de_caminho_cena(caminho_cena, cor_tinta=self._cor_tinta_padrao())
        if curva is None:
            return
        pos = curva.pos()
        self.canvas.adicionar_elemento_mockup(curva, pos)
        self.canvas.cena.clearSelection()
        curva.setSelected(True)
        # Continua na ferramenta (Bézier/Mão livre), como no CorelDRAW.

    def _criar_cota_por_arrasto(self, p1: QPointF, p2: QPointF, tipo: str) -> None:
        pagina = self.canvas.retangulo_pagina()
        cota = criar_cota(p1, p2, tipo, centro_referencia=None if pagina is None else pagina.center())
        if cota is None:
            return
        pos, rotacao = cota.pos(), cota.rotation()
        self.canvas.adicionar_elemento_mockup(cota, pos)
        cota.setRotation(rotacao)
        self.canvas.cena.clearSelection()
        cota.setSelected(True)
        # Diferente das outras formas, a cota NÃO volta pro ponteiro: o
        # normal é cotar várias medidas em seguida, como no CorelDRAW.

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
                # Oculto no docker Objetos não sai, como no CorelDRAW.
                visiveis = [el for el in self.canvas.elementos_mockup if el.isVisible()]
                # Faca editada à mão vai como está na tela, não a calculada.
                layout = dataclasses.replace(self.canvas.layout_atual, linhas=list(self.canvas.linhas_faca()))
                corel_bridge.desenhar_layout(self._corel_app, layout, visiveis)
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
        if not self.canvas.cena.selectedItems():
            self.painel_propriedades_mockup.definir_elemento(None)  # tamanho da chapa no estado "nada selecionado"

        self.linha_impressora.atualizar_valores_efetivos(layout.segmentos_impressora)
        self.linha_impressora.definir_total(layout.largura_total)
        self.linha_riscador.atualizar_valores_efetivos(
            layout.segmentos_riscador + [0.0] * (5 - len(layout.segmentos_riscador))
        )
        self.linha_riscador.definir_total(layout.altura_total)

        self.statusBar().showMessage(layout.descricao)
