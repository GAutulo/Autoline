"""Janela principal do Gerador de Layout de Caixas."""

from __future__ import annotations

import math
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTabBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..dobra3d import montar_modelo
from ..dobra_generica import montar_modelo_generico
from ..layout_service import ServicoLayoutCaixa
from ..models import (
    DESCRICAO_TIPO_CAIXA,
    NOME_EXIBICAO_TIPO_CAIXA,
    ORDEM_TIPOS_CAIXA,
    TIPOS_MALETA,
    TIPOS_MEIA_CAIXA,
    CorImpressao,
    MedidasCaixa,
    TipoCaixa,
    TipoLinha,
)
from ..paineis import Painel, calcular_paineis
from . import configuracoes, corel_bridge, exportacao
from .area_trabalho_corel import BotaoFlyout, PainelStatus, PaletaCores
from .dialogo_configuracoes import DialogoConfiguracoes
from ..simbologias import tamanho_mm
from . import projeto_arquivo
from .dialogo_construtor_dieline import DialogoConstrutorDieline
from .docker_simbologias import DockerSimbologias
from .dockers_corel import DockerAlinhar, DockerObjetos, DockerTransformacoes
from .dialogo_logo import DialogoSepararCoresLogo
from .dialogo_manual import DialogoManual
from .dialogo_tabela import DialogoTabela
from .estilo import cor_legivel_sobre
from .estilo import Cor
from .mockup_acabamento import ElementoAcabamento
from .mockup_callout import ElementoCallout
from .dialogo_estilos import DialogoEstilos, pasta_estilos_usuario
from ..estilos import carregar_estilos, estilo_da_faca, salvar_estilo
from .mockup_checklist import ElementoChecklistCores
from .mockup_cota import ElementoCota, criar_cota
from .mockup_cota_angular import ElementoCotaAngular
from .mockup_curva import curva_de_caminho_cena
from .mockup_formas import ElementoElipse, ElementoLinha, ElementoPoligono, ElementoRetangulo
from .mockup_icones import construir_icone
from .mockup_imagem import ElementoImagem
from .arquivo_destino import esta_preso, proximo_nome_livre
from .dialogo_exportar import Destino, DialogoExportar
from .tela_inicio import Cartao, TelaInicio
from .moldura import ALTURA_CONTEXTO, ALTURA_STATUS, LARGURA_COLUNA_FERRAMENTAS, BarraStatus, BarraTitulo, PonteCorel, divisoria_status
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_reguas import ReguaHorizontal, ReguaVertical
from .mockup_simbolos import ElementoSimbolo
from .mockup_tabela import ElementoTabela
from .mockup_texto import ElementoTexto
from .painel_propriedades_mockup import NOME_TIPO_ELEMENTO, PainelPropriedadesMockup
from .modelagem import OPERACOES
from .preview_canvas import AJUSTAR_A, FerramentaMockup, PainelLegendaCores, PreviewCanvas
from .segmented_row import LinhaTrechos
from .visualizacao_3d import Visualizacao3D, renderizar_arte_regioes

# Tintas de impressão (flexo em papelão): as de sempre + as mais pedidas.
# As 8 primeiras mantêm nome e tom de antes (projetos salvos usam o nome).
_CORES_PADRAO: list[tuple[str, tuple[int, int, int]]] = [
    ("Preto", (0, 0, 0)),
    ("Vermelho", (255, 0, 0)),
    ("Azul", (0, 0, 255)),
    ("Amarelo", (255, 220, 0)),
    ("Verde", (0, 150, 0)),
    ("Ciano", (0, 170, 220)),
    ("Magenta", (220, 0, 180)),
    ("Laranja", (255, 120, 0)),
    ("Azul Escuro", (0, 40, 110)),
    ("Azul Royal", (0, 80, 180)),
    ("Verde Escuro", (0, 90, 45)),
    ("Verde Limão", (140, 200, 0)),
    ("Vinho", (120, 0, 40)),
    ("Marrom", (110, 60, 20)),
    ("Roxo", (110, 30, 140)),
    ("Rosa", (240, 110, 170)),
    ("Cinza", (128, 128, 128)),
    ("Dourado", (196, 156, 48)),
    ("Branco", (255, 255, 255)),
]


def _cores_disponiveis() -> list[tuple[str, tuple[int, int, int]]]:
    """As padrão + as criadas pelo usuário (Configurações guarda)."""
    nomes = {nome for nome, _rgb in _CORES_PADRAO}
    return _CORES_PADRAO + [(n, rgb) for n, rgb in configuracoes.cores_personalizadas() if n not in nomes]

# Rótulos exibidos em cada trecho, por tipo de caixa. A Impressora sempre
# tem 5 trechos; o Riscador tem 3 na maleta e 5 no envoltório.
_TIPOS_MALETA = TIPOS_MALETA

_ROTULOS_IMPRESSORA_MALETA = ["Aba", "L", "C", "L", "C"]
_ROTULOS_IMPRESSORA_ENVOLTORIO = ["Aba", "A", "C", "A", "Aba"]
_ROTULOS_RISCADOR_MALETA = ["Sup", "Centro", "Inf", "", ""]
_ROTULOS_RISCADOR_ENVOLTORIO = ["Sup", "A", "L", "A", "Inf"]
_ROTULOS_IMPRESSORA_MEIA = ["Aba", "L", "C", "", ""]
_ROTULOS_IMPRESSORA_CAPA = ["A", "C", "A", "", ""]
_ROTULOS_RISCADOR_CAPA = ["A", "L", "A", "", ""]



def _folhas_coloriveis(itens) -> list:
    """Os objetos que recebem cor: grupos entram com todos os de dentro."""
    folhas: list = []
    for it in itens:
        if isinstance(it, GrupoMockup):
            folhas += _folhas_coloriveis(it.elementos)
        elif isinstance(it, ElementoLogoVetorial) or hasattr(it, "definir_cor_tinta"):
            folhas.append(it)
    return folhas

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
        barra_status = BarraStatus()
        # Como a barra que o QMainWindow cria sozinho: a largura dela não
        # pode ditar a mínima da janela.
        barra_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setStatusBar(barra_status)

        self._servico = ServicoLayoutCaixa()
        self._chips_cor: dict[str, tuple[QPushButton, tuple[int, int, int]]] = {}
        self._corel_app = None
        self._paineis_atuais: list[Painel] = []
        # Dobra genérica (faca editada/em branco): ângulo por linha e face base.
        self._angulos_dobra: dict[int, float] = {}
        self._face_base_3d: int | None = None
        self._assinatura_faca_3d: tuple = ()
        self._dialogo_manual: DialogoManual | None = None
        # Projeto (.autoline) aberto: caminho e o estado salvo (pra saber se mudou).
        self._caminho_projeto: str | None = None
        self._largura_antes_de_alargar: int | None = None  # ver `_trocar_tela`
        # Folha de aprovação: cliente, referência, código e as datas (vão no projeto).
        self._aprovacao: dict = {}
        self._assinatura_salva: str | None = None

        # Menus dentro da barra de título (ver `menuBar` e `_montar_moldura`).
        self._barra_menus = QMenuBar()
        self._montar_ui()
        self._montar_abas_tela()
        self._montar_barra_ferramentas()
        self._montar_barra_mockup()
        self._montar_barra_propriedades_mockup()
        self._montar_menu()
        self._montar_painel_status()
        self._montar_moldura()
        self._montar_inicio()
        self._conectar_sinais()
        self._ao_trocar_tipo()
        self._trocar_tela(0)  # começa na tela de Dieline
        self._estado_novo = projeto_arquivo.estado_da_janela(self)
        self._assinatura_salva = projeto_arquivo.assinatura(self)
        self._timer_titulo = QTimer(self)
        self._timer_titulo.setSingleShot(True)
        self._timer_titulo.setInterval(400)
        self._timer_titulo.timeout.connect(self._atualizar_titulo)
        self.canvas.pilha_desfazer.indexChanged.connect(lambda _i: self._timer_titulo.start())
        self.canvas.pilha_desfazer.indexChanged.connect(lambda _i: self.painel_propriedades_mockup.rebasear_foto())
        self._atualizar_titulo()
        # Cópia de recuperação: de tempos em tempos, se tem alteração não salva.
        self._timer_recuperacao = QTimer(self)
        self._timer_recuperacao.setInterval(projeto_arquivo.INTERVALO_RECUPERACAO_MS)
        self._timer_recuperacao.timeout.connect(self.salvar_recuperacao)
        self._timer_recuperacao.start()

    def menuBar(self) -> QMenuBar:  # noqa: N802
        """Os menus moram na barra de título do redesign (`BarraTitulo`), não
        na faixa de menu padrão do Qt — mesmos menus, mesmos atalhos."""
        return self._barra_menus

    # ── Montagem da UI ──────────────────────────────────────────────
    def _montar_ui(self) -> None:
        # Pilha do centro: a área de trabalho (abas) e a tela de Início.
        self.pilha_central = QStackedWidget()
        self.setCentralWidget(self.pilha_central)
        central = QWidget()
        self.pilha_central.addWidget(central)
        self._area_trabalho = central
        # Página escondida não dita a largura mínima da janela (a do Início
        # somada ao inspetor do Layout passava de uma tela de 1366).
        self.pilha_central.currentChanged.connect(lambda _i: self._so_pagina_atual_conta(self.pilha_central))
        layout_raiz = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout_raiz.addWidget(splitter)

        # Com rolagem: com muitas tintas na legenda, numa tela baixa (notebook)
        # o painel não empurra a janela pra fora da tela.
        conteudo_esquerdo = self._montar_painel_esquerdo()
        self.painel_esquerdo = QScrollArea()
        self.painel_esquerdo.setObjectName("rolagemPainelEsquerdo")
        self.painel_esquerdo.setWidget(conteudo_esquerdo)
        self.painel_esquerdo.setWidgetResizable(True)
        self.painel_esquerdo.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.painel_esquerdo.setFrameShape(QFrame.Shape.NoFrame)
        self.painel_esquerdo.setMaximumWidth(conteudo_esquerdo.maximumWidth() + 12)
        self.painel_esquerdo.setMinimumWidth(min(conteudo_esquerdo.sizeHint().width() + 12, conteudo_esquerdo.maximumWidth() + 12))
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
        for tipo in ORDEM_TIPOS_CAIXA:
            self.combo_tipo.addItem(NOME_EXIBICAO_TIPO_CAIXA[tipo], tipo)
            self.combo_tipo.setItemData(self.combo_tipo.count() - 1, DESCRICAO_TIPO_CAIXA[tipo], Qt.ItemDataRole.ToolTipRole)
        self.combo_tipo.setCurrentIndex(self.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
        # A lista aberta mostra o nome inteiro, mesmo com a caixa estreita.
        self.combo_tipo.view().setMinimumWidth(self.combo_tipo.view().sizeHintForColumn(0) + 24)
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
        self._grid_cores = QGridLayout(grupo_cores)
        self._grid_cores.setHorizontalSpacing(8)
        self._grid_cores.setVerticalSpacing(8)
        self._montar_chips_cores()
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

        # Aba 3D troca só esta área (canvas 2D ↔ caixa montada); as medidas
        # à esquerda e os trechos embaixo continuam editáveis e o 3D
        # acompanha ao vivo (ver `_recalcular`).
        self.visualizacao_3d = Visualizacao3D()
        self.visualizacao_3d.angulo_alterado.connect(self._ao_mudar_angulo_3d)
        self.visualizacao_3d.face_base_escolhida.connect(self._ao_escolher_base_3d)
        self.pilha_visualizacao = QStackedWidget()
        self.pilha_visualizacao.addWidget(legenda_e_canvas)
        self.pilha_visualizacao.addWidget(self.visualizacao_3d)
        # O 3D escondido não pode alargar a janela já ao abrir o app.
        self._so_pagina_atual_conta(self.pilha_visualizacao)
        vbox.addWidget(self.pilha_visualizacao, 1)

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

    def _montar_chips_cores(self) -> None:
        """Os chips da legenda (todas as tintas, 3 por linha) e o "+ Nova cor".
        Refazer mantém as marcadas."""
        marcadas = {nome for nome, (chip, _rgb) in self._chips_cor.items() if chip.isChecked()}
        grid = self._grid_cores
        while grid.count():
            item = grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self._chips_cor = {}
        colunas = 2  # nomes compostos ("Azul Escuro", "Verde Limão") cortavam com 3
        cores = _cores_disponiveis()
        personalizadas = {n for n, _rgb in configuracoes.cores_personalizadas()}
        for i, (nome, rgb) in enumerate(cores):
            chip = self._montar_chip_cor(nome, rgb)
            chip.setChecked(nome in marcadas)
            chip.toggled.connect(self._ao_alternar_cor)
            if nome in personalizadas:
                chip.setToolTip(f"{nome} (sua) — botão direito pra tirar")
                chip.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                chip.customContextMenuRequested.connect(lambda _p, n=nome: self._remover_cor_personalizada(n))
            self._chips_cor[nome] = (chip, rgb)
            grid.addWidget(chip, i // colunas, i % colunas)
        botao_nova = QPushButton("+ Nova cor")
        botao_nova.setProperty("chipCor", True)
        botao_nova.setCursor(Qt.CursorShape.PointingHandCursor)
        botao_nova.setToolTip("Criar uma tinta (nome e tom) — fica guardada pras próximas vezes")
        botao_nova.clicked.connect(self._nova_cor_personalizada)
        grid.addWidget(botao_nova, len(cores) // colunas, len(cores) % colunas)
        if hasattr(self, "_paleta_cores"):
            self._paleta_cores.definir_cores(cores)

    def _ao_alternar_cor(self, _marcado: bool = False) -> None:
        if hasattr(self, "canvas") and hasattr(self, "linha_riscador"):  # já montada
            self._recalcular()

    def _nova_cor_personalizada(self, nome: str | None = None, rgb: tuple[int, int, int] | None = None) -> bool:
        """Tinta nova: escolhe o tom e o nome (ex.: "Pantone 286"). Fica nas
        Configurações e aparece na legenda e na paleta da direita."""
        from PySide6.QtWidgets import QColorDialog

        if rgb is None:
            cor = QColorDialog.getColor(QColor(0, 0, 0), self, "Tom da nova tinta")
            if not cor.isValid():
                return False
            rgb = (cor.red(), cor.green(), cor.blue())
        if nome is None:
            nome, ok = QInputDialog.getText(self, "Nova tinta", "Nome da tinta (ex.: Pantone 286, Azul Cliente):")
            if not ok:
                return False
        nome = nome.strip()
        if not nome:
            return False
        existentes = {n.lower() for n, _rgb in _cores_disponiveis()}
        if nome.lower() in existentes:
            self.statusBar().showMessage(f"Já existe uma tinta chamada “{nome}”.", 6000)
            return False
        configuracoes.definir_cores_personalizadas(configuracoes.cores_personalizadas() + [(nome, rgb)])
        self._montar_chips_cores()
        self._chips_cor[nome][0].setChecked(True)  # criou pra usar: já marca
        return True

    def _remover_cor_personalizada(self, nome: str, confirmar=None) -> bool:
        if confirmar is None:
            confirmar = lambda: QMessageBox.question(self, "Tirar tinta", f"Tirar “{nome}” da lista de tintas?") == QMessageBox.StandardButton.Yes  # noqa: E731
        if not confirmar():
            return False
        configuracoes.definir_cores_personalizadas([(n, rgb) for n, rgb in configuracoes.cores_personalizadas() if n != nome])
        self._montar_chips_cores()
        self._recalcular()
        return True

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
            # Desmarcado: borda na cor da tinta e o nome na mesma cor, clareada
            # ou escurecida o mínimo pra ler sobre o fundo (azul/magenta/preto
            # sumiam no tema escuro).
            # Texto pequeno sobre o cartão: 4,5:1 (Verde Escuro, Vinho, Marrom
            # ficavam quase ilegíveis no tema escuro com 3:1 sobre a janela).
            tr, tg, tb = cor_legivel_sobre(r, g, b, fundo=Cor.CARTAO, minimo=4.5)
            chip.setStyleSheet(
                f"background: transparent; color: rgb({tr},{tg},{tb}); "
                f"border: 1px solid rgb({tr},{tg},{tb});"
            )

    # ── Lógica ──────────────────────────────────────────────────────
    def _ao_trocar_tipo(self) -> None:
        tipo = self.combo_tipo.currentData()
        self.combo_tipo.setToolTip(DESCRICAO_TIPO_CAIXA.get(tipo, ""))
        self.linha_impressora.definir_visiveis(5)
        if tipo in TIPOS_MEIA_CAIXA:
            self.linha_impressora.definir_rotulos(_ROTULOS_IMPRESSORA_MEIA)
            self.linha_impressora.definir_visiveis(3)
            self.linha_riscador.definir_rotulos(_ROTULOS_RISCADOR_MALETA)
            self.linha_riscador.definir_visiveis(3)
        elif tipo == TipoCaixa.ENVOLTORIO_CAPA:
            self.linha_impressora.definir_rotulos(_ROTULOS_IMPRESSORA_CAPA)
            self.linha_impressora.definir_visiveis(3)
            self.linha_riscador.definir_rotulos(_ROTULOS_RISCADOR_CAPA)
            self.linha_riscador.definir_visiveis(3)
        elif tipo in _TIPOS_MALETA:
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
        """Zoom e "Ajustar à tela" (vão pra barra de status, ver
        `_montar_painel_status`). Os botões de exportar que ficavam numa
        barra aqui foram pro diálogo único Exportar (`abrir_exportar`)."""
        self.label_zoom = QLabel("100%")
        self.label_zoom.setObjectName("rotuloTecnico")
        self.label_zoom.setStyleSheet(f"color: {Cor.TEXTO_SECUNDARIO};")
        self.botao_ajustar_tela = QPushButton("Ajustar à tela")
        self.botao_ajustar_tela.setObjectName("botaoStatus")
        self.botao_ajustar_tela.setFlat(True)
        self.botao_ajustar_tela.clicked.connect(self._ajustar_a_tela)
        self.canvas.zoom_alterado.connect(lambda z: self.label_zoom.setText(f"{z * 100:.0f}%"))

    def _montar_moldura(self) -> None:
        """Barra de título do redesign (REDESIGN.md 2.1): símbolo, menus,
        projeto, seletor Dieline | Layout | 3D, desfazer/refazer e Exportar."""
        self.barra_titulo = BarraTitulo(self._barra_menus, self.abas_tela)
        self.setMenuWidget(self.barra_titulo)
        pilha = self.canvas.pilha_desfazer
        self.barra_titulo.botao_desfazer.setIcon(construir_icone("desfazer"))
        self.barra_titulo.botao_refazer.setIcon(construir_icone("refazer"))
        self.barra_titulo.botao_desfazer.clicked.connect(pilha.undo)
        self.barra_titulo.botao_refazer.clicked.connect(pilha.redo)
        self.barra_titulo.botao_desfazer.setEnabled(pilha.canUndo())
        self.barra_titulo.botao_refazer.setEnabled(pilha.canRedo())
        pilha.canUndoChanged.connect(self.barra_titulo.botao_desfazer.setEnabled)
        pilha.canRedoChanged.connect(self.barra_titulo.botao_refazer.setEnabled)
        self.barra_titulo.botao_exportar.clicked.connect(lambda: self.abrir_exportar())

    # ── Tela de Início (REDESIGN.md 2.2) ────────────────────────────
    def _montar_inicio(self) -> None:
        from .projeto_arquivo import ler_miniatura

        cartoes = [
            Cartao("Maleta normal", "inteira ou meia caixa", "caixa_maleta", tipo=TipoCaixa.MALETA_NORMAL,
                   variantes=(("Caixa", ("Inteira", "Meia caixa")),),
                   tipos={("Inteira",): TipoCaixa.MALETA_NORMAL, ("Meia caixa",): TipoCaixa.MALETA_NORMAL_MEIA}),
            Cartao("Maleta transpassada", "inteira ou meia caixa", "caixa_transpassada",
                   tipo=TipoCaixa.MALETA_TRANSPASSADA,
                   variantes=(("Caixa", ("Inteira", "Meia caixa")),),
                   tipos={("Inteira",): TipoCaixa.MALETA_TRANSPASSADA,
                          ("Meia caixa",): TipoCaixa.MALETA_TRANSPASSADA_MEIA}),
            Cartao("Envoltório", "normal ou fecha no meio", "caixa_envoltorio",
                   tipo=TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE,
                   variantes=(("Fechamento", ("Normal", "No meio")), ("Corte", ("Com corte", "Sem corte"))),
                   tipos={("Normal", "Com corte"): TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE,
                          ("Normal", "Sem corte"): TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_SEM_CORTE,
                          ("No meio", "Com corte"): TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_COM_CORTE,
                          ("No meio", "Sem corte"): TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_SEM_CORTE}),
            Cartao("Envoltório capa", "bandeja", "caixa_capa", tipo=TipoCaixa.ENVOLTORIO_CAPA),
            Cartao("FEFCO 0201", "catálogo de estilos", sigla="0201", acao=lambda: self._inicio_estilo("FEFCO 0201")),
            Cartao("FEFCO 0427", "catálogo de estilos", sigla="0427", acao=lambda: self._inicio_estilo("FEFCO 0427")),
            Cartao("Faca em branco", "desenho livre", "mais", acao=lambda: self._inicio_e(self._nova_faca_em_branco)),
            Cartao("Construtor de dieline", "monte por trechos", "linha_medida",
                   acao=lambda: self._inicio_e(self._abrir_construtor_dieline)),
        ]
        self.tela_inicio = TelaInicio(cartoes)
        self.tela_inicio.criar = self._criar_pelo_inicio
        self.tela_inicio.abrir_projeto = self.abrir_projeto
        self.tela_inicio.ver_todos = self.abrir_galeria_recentes
        self.tela_inicio.abrir_configuracoes = self._abrir_configuracoes
        self.tela_inicio.obter_recentes = configuracoes.projetos_recentes
        self.tela_inicio.ler_miniatura = ler_miniatura
        self.pilha_central.addWidget(self.tela_inicio)
        self._so_pagina_atual_conta(self.pilha_central)
        self.barra_titulo.simbolo.ao_clicar = self.mostrar_inicio
        self.barra_titulo.simbolo.setToolTip("Início")
        # Clicar numa tela do seletor (mesmo a que já estava) sai do Início.
        self.abas_tela.tabBarClicked.connect(lambda _i: self.mostrar_trabalho())

    @staticmethod
    def _so_pagina_atual_conta(pilha: QStackedWidget) -> None:
        for i in range(pilha.count()):
            atual = i == pilha.currentIndex()
            politica = QSizePolicy.Policy.Preferred if atual else QSizePolicy.Policy.Ignored
            pilha.widget(i).setSizePolicy(politica, QSizePolicy.Policy.Preferred)

    @property
    def no_inicio(self) -> bool:
        return self.pilha_central.currentWidget() is self.tela_inicio

    def mostrar_inicio(self) -> None:
        if self.no_inicio:
            return
        if self.abas_tela.currentIndex() == 1:  # lembra a página aberta do inspetor
            self._guardar_inspetor_layout()
            self._estava_no_layout = False
        for barra in self.findChildren(QToolBar):
            barra.hide()
        self.dock_inspetor.hide()
        self.tela_inicio.recarregar_recentes()
        self.pilha_central.setCurrentWidget(self.tela_inicio)

    def mostrar_trabalho(self) -> None:
        if not self.no_inicio:
            return
        self.pilha_central.setCurrentWidget(self._area_trabalho)
        self._trocar_tela(self.abas_tela.currentIndex())  # devolve as barras da tela atual

    def _criar_pelo_inicio(self, tipo: TipoCaixa, comprimento: float, largura: float, altura: float) -> None:
        """"Criar faca": projeto novo com o tipo e as medidas escolhidos."""
        if not self.novo_projeto():
            return
        self.combo_tipo.setCurrentIndex(self.combo_tipo.findData(tipo))
        self.spin_comprimento.setValue(comprimento)
        self.spin_largura.setValue(largura)
        self.spin_altura.setValue(altura)
        self.abas_tela.setCurrentIndex(0)
        self.mostrar_trabalho()

    def _inicio_e(self, acao) -> None:
        """Projeto novo, volta pro trabalho (Dieline) e faz `acao`."""
        if not self.novo_projeto():
            return
        self.abas_tela.setCurrentIndex(0)
        self.mostrar_trabalho()
        acao()

    def _inicio_estilo(self, codigo: str) -> None:
        nome = next((e.nome_exibicao for e in carregar_estilos(pasta_estilos_usuario()) if e.nome_exibicao.startswith(codigo)), None)
        self._inicio_e(lambda: self._abrir_catalogo_estilos(nome))

    def _destinos_exportar(self) -> list[Destino]:
        """Os destinos do diálogo Exportar — cada um chama a MESMA função de
        antes (mesmo arquivo, mesmas perguntas)."""
        return [
            Destino("pdf", "Arquivo de produção", "PDF", "PDF vetorial",
                    "Layout técnico completo (faca + arte + legenda de cores), vetorial, preto sobre branco — "
                    "para a gráfica e o clichê.", "Exportar PDF", self._exportar_pdf, True),
            Destino("svg", "Arquivo de produção", "SVG", "SVG vetorial",
                    "O mesmo layout técnico em SVG vetorial, preto sobre branco.", "Exportar SVG", self._exportar_svg, True),
            Destino("jpg", "Arquivo de produção", "JPG", "Imagem JPG",
                    "Imagem quadrada do layout, com o layout centralizado, na resolução das Configurações.",
                    "Exportar JPG", self._exportar_jpg, True),
            Destino("aprovacao", "Para o cliente", "✓", "Folha de aprovação",
                    "Abre o diálogo da folha de aprovação (PDF pro cliente), sem mudança.",
                    "Abrir folha de aprovação", self.gerar_folha_aprovacao),
            Destino("imagem_3d", "Para o cliente", "3D", "Imagem do 3D",
                    "A caixa em 3D na vista atual, em JPG ou PNG.", "Salvar imagem do 3D", self._exportar_imagem_3d),
            Destino("tudo", "Tudo de uma vez", "▤", "Salvar tudo",
                    "Projeto .autoline + imagem do layout + imagem do 3D, cada um na sua pasta, com o nome do projeto.",
                    "Salvar tudo", self.salvar_e_exportar_tudo),
            Destino("corel", "", "→", "Enviar para o CorelDRAW",
                    "Manda a faca e a arte direto pro CorelDRAW aberto (conecta se precisar).",
                    "Enviar para o CorelDRAW", self._exportar_corel),
        ]

    def abrir_exportar(self, inicial: str = "pdf", executar: bool = True) -> DialogoExportar:
        """Diálogo único Exportar. `executar=False` (testes) devolve sem abrir."""

        def previa():
            if self.canvas.layout_efetivo is None:
                return None
            try:
                return exportacao.imagem_do_layout(self.canvas.cena, self.canvas.layout_efetivo, dpi=40)
            except Exception:  # noqa: BLE001 — sem prévia não impede exportar
                return None

        dialogo = DialogoExportar(self._destinos_exportar(), previa, self, inicial=inicial)
        if executar and dialogo.exec() == QDialog.DialogCode.Accepted and dialogo.escolhido is not None:
            dialogo.escolhido.acao()
        return dialogo

    def _ajustar_a_tela(self) -> None:
        if self.abas_tela.currentIndex() == 2:
            self.visualizacao_3d.enquadrar()
        else:
            self.canvas.ajustar_a_tela()

    def _montar_menu(self) -> None:
        menu_arquivo = self.menuBar().addMenu("&Arquivo")
        menu_arquivo.addAction("Início", self.mostrar_inicio)
        menu_arquivo.addSeparator()
        acao = menu_arquivo.addAction("Novo projeto", self.novo_projeto)
        acao.setShortcut(QKeySequence("Ctrl+N"))
        acao = menu_arquivo.addAction("Abrir projeto...", self.abrir_projeto)
        acao.setShortcut(QKeySequence("Ctrl+O"))
        self._menu_recentes = menu_arquivo.addMenu("Abrir recente")
        self._menu_recentes.aboutToShow.connect(self._montar_menu_recentes)
        acao = menu_arquivo.addAction("Salvar projeto", self.salvar_projeto)
        acao.setShortcut(QKeySequence("Ctrl+S"))
        acao = menu_arquivo.addAction("Salvar projeto como...", self.salvar_projeto_como)
        acao.setShortcut(QKeySequence("Ctrl+Shift+S"))
        acao = menu_arquivo.addAction("Folha de aprovação (PDF)...", self.gerar_folha_aprovacao)
        acao.setShortcut(QKeySequence("Ctrl+Shift+P"))
        acao = menu_arquivo.addAction("Salvar e exportar tudo", self.salvar_e_exportar_tudo)
        acao.setShortcut(QKeySequence("Ctrl+Shift+E"))
        acao.setToolTip("Salva o projeto, a imagem do layout e a do 3D, cada um na sua pasta, com o nome do projeto")
        menu_arquivo.addSeparator()
        menu_arquivo.addAction("Nova faca em branco (desenho livre)", self._nova_faca_em_branco)
        acao_catalogo = menu_arquivo.addAction("Nova faca a partir de estilo (catálogo)...", self._abrir_catalogo_estilos)
        acao_catalogo.setShortcut(QKeySequence("Ctrl+Shift+N"))
        acao_construtor = menu_arquivo.addAction("Construtor de dieline...", self._abrir_construtor_dieline)
        acao_construtor.setShortcut(QKeySequence("Ctrl+Shift+D"))
        menu_arquivo.addAction("Salvar faca como estilo...", self._salvar_faca_como_estilo)
        menu_arquivo.addSeparator()
        menu_arquivo.addAction("Conectar ao CorelDRAW", self._conectar_corel)
        menu_arquivo.addSeparator()

        menu_exportar = menu_arquivo.addMenu("Exportar layout")
        menu_exportar.addAction("Exportar como SVG...", self._exportar_svg)
        menu_exportar.addAction("Exportar como PDF...", self._exportar_pdf)
        menu_exportar.addAction("Exportar como JPG...", self._exportar_jpg)
        menu_exportar.addAction("Imagem do 3D (JPG/PNG)...", self._exportar_imagem_3d)
        menu_exportar.addSeparator()
        menu_exportar.addAction("Enviar para o CorelDRAW", self._exportar_corel)

        menu_arquivo.addSeparator()
        menu_arquivo.addAction("Configurações...", self._abrir_configuracoes)
        menu_arquivo.addSeparator()
        acao_sair = menu_arquivo.addAction("Sair")
        acao_sair.setShortcut("Alt+F4")
        acao_sair.triggered.connect(self.close)

        menu_objeto = self.menuBar().addMenu("&Objeto")
        # Sempre ativo: fora da tela de Layout, escolher um item leva pra lá
        # (desativado em cinza parecia que o menu "não abria").
        menu_objeto.addAction("Converter em curvas\tCtrl+Q", self._no_layout(lambda: self.canvas.converter_selecionados_em_curvas()))
        menu_objeto.addAction("Combinar\tCtrl+L", self._no_layout(lambda: self.canvas.combinar_selecionados()))
        menu_objeto.addAction("Separar\tCtrl+K", self._no_layout(lambda: self.canvas.separar_selecionados()))
        menu_objeto.addAction("Salvar no banco de simbologias…", self._no_layout(self.salvar_no_banco_de_simbologias))
        menu_modelar = menu_objeto.addMenu("Modelar")
        for operacao, nome in OPERACOES.items():
            menu_modelar.addAction(
                construir_icone(f"modelar_{operacao}"), nome, self._no_layout(lambda op=operacao: self.canvas.modelar_selecionados(op))
            )
        self._menu_objeto = menu_objeto

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
        self._acao_snap = acao_snap
        menu_exibir.addMenu(self._menu_ajustar_a)
        acao_dinamicas = menu_exibir.addAction("Guias dinâmicas\tAlt+Shift+D")
        acao_dinamicas.setCheckable(True)
        acao_dinamicas.setChecked(self.canvas.guias_dinamicas)
        acao_dinamicas.setToolTip("Ao desenhar, alinha o cursor com os nós da faca, dos objetos e da chapa")
        acao_dinamicas.toggled.connect(self.canvas.definir_guias_dinamicas)
        self.canvas.guias_dinamicas_alteradas.connect(
            lambda ativas: (acao_dinamicas.setChecked(ativas), self.statusBar().showMessage(
                f"Guias dinâmicas {'ligadas' if ativas else 'desligadas'}", 4000))
        )
        self._acao_guias_dinamicas = acao_dinamicas
        menu_dockers = menu_exibir.addMenu("Janelas de encaixe (Layout)")
        for chave, dock in self._docks.items():
            menu_dockers.addAction(dock.windowTitle(), self._no_layout(lambda c=chave: self.abrir_docker(c)))
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
        self.abas_tela = QTabBar()
        self.abas_tela.addTab("Dieline")
        self.abas_tela.addTab("Layout")
        self.abas_tela.addTab("3D")
        self.abas_tela.setToolTip(
            "Dieline: medidas, cores e a faca de corte. Layout: texto/formas/logotipo sobre a caixa. "
            "3D: a caixa montada, com animação de planificar e montar."
        )
        self.abas_tela.currentChanged.connect(self._trocar_tela)

    def _trocar_tela(self, indice: int) -> None:
        # Se uma tela já alargou a janela (o 3D numa tela pequena), a volta
        # mira a largura de ANTES dela, não a alargada.
        largura_antes = self._largura_antes_de_alargar or self.width()
        modo_layout = indice == 1
        modo_3d = indice == 2
        self.pilha_visualizacao.setCurrentIndex(1 if modo_3d else 0)
        # A barra de controles do 3D é larga: escondida, não pode ditar a
        # largura mínima da janela (no Layout ainda tem o inspetor ao lado).
        self._so_pagina_atual_conta(self.pilha_visualizacao)
        self.label_zoom.setVisible(not modo_3d)
        self.painel_esquerdo.setVisible(not modo_layout)
        self._grupo_medidas.setVisible(not modo_layout)
        self.barra_mockup.setVisible(modo_layout)
        if hasattr(self, "painel_status"):
            self.painel_status.definir_controles_de_cor(modo_layout)
            self._atualizar_tintas_status()
        self.barra_faca.setVisible(indice == 0)
        self.barra_ferramentas_faca.setVisible(indice == 0)
        self._atalho_editar_faca.setEnabled(indice == 0)  # no Layout, F10 é a Forma de curvas
        if indice != 0:
            self._acoes_faca["navegar"].setChecked(True)
            self.canvas.definir_edicao_faca(False)
        self.barra_organizar.setVisible(modo_layout)
        self.barra_paleta.setVisible(modo_layout)
        # Dockers só na tela de Layout: ao sair, lembra quais estavam
        # abertos pra reabrir na volta.
        if not modo_layout:
            if self._estava_no_layout:
                self._guardar_inspetor_layout()
            self.dock_inspetor.hide()
        self._estava_no_layout = modo_layout
        self.barra_propriedades_mockup.setVisible(modo_layout)
        self.canvas.definir_modo_mockup(modo_layout)
        if not modo_layout:
            self.painel_propriedades_mockup.definir_elemento(None)
        if modo_layout:
            self._abrir_inspetor_layout()
        # Durante a troca o Qt soma as barras e o dock com o mínimo ANTIGO do
        # centro e alarga a janela (numa tela de 1366 ela passava da borda e
        # o Exportar e a paleta sumiam); assentado, o mínimo cabe de novo —
        # então a janela volta pra largura em que estava.
        # O alargamento pode vir só depois (quando o layout assenta), então
        # a volta é conferida sempre, não só se já alargou aqui.
        if self.isVisible() and not (self.isMaximized() or self.isFullScreen()):
            self._largura_antes_de_alargar = largura_antes
            QTimer.singleShot(0, lambda: self._voltar_largura(largura_antes))
        # Mostrar/esconder os painéis ao redor muda o tamanho disponível
        # do canvas — sem reencaixar aqui, a visão que estava centralizada
        # antes da troca fica deslocada (às vezes "presa" perto do canto
        # superior esquerdo) porque o zoom/posição antigos não fazem mais
        # sentido pro novo tamanho de viewport.
        # Na aba 3D o canvas fica escondido (tamanho zero): ajustar ali
        # levava o zoom a ~0% e o desenho "sumia" na volta. Ajusta só nas
        # telas do canvas, e depois que o layout assentar o tamanho novo.
        if not modo_3d:
            # Duas vezes: logo depois e quando barras/painéis que aparecem ou
            # somem nesta troca já tiverem reorganizado a janela.
            QTimer.singleShot(0, self.canvas.ajustar_a_tela)
            QTimer.singleShot(150, self.canvas.ajustar_a_tela)
        if modo_3d:
            self._atualizar_modelo_3d()  # a faca pode ter sido editada na Dieline
            self._atualizar_arte_3d()
            self.visualizacao_3d.enquadrar()

    def _voltar_largura(self, largura: int, tentativas: int = 20) -> None:
        if self._largura_antes_de_alargar != largura:
            return  # outra troca de tela já assumiu
        if self.width() > largura and self.minimumSizeHint().width() <= largura:
            self.resize(largura, self.height())
        if tentativas > 0:  # os layouts podem ainda não ter assentado: confere logo depois
            QTimer.singleShot(30, lambda: self._voltar_largura(largura, tentativas - 1))
        elif self.width() <= largura:
            # Voltou. Se não (o 3D não cabe), a próxima troca ainda mira aqui.
            self._largura_antes_de_alargar = None

    def _ao_mudar_angulo_3d(self, linha: int, angulo: float) -> None:
        self._angulos_dobra[linha] = angulo
        self._atualizar_modelo_3d()

    def _ao_escolher_base_3d(self, painel_id: str) -> None:
        self._face_base_3d = int(painel_id.split("_")[1])
        self._atualizar_modelo_3d()

    def _nova_faca_em_branco(self) -> None:
        """Começa uma faca do zero (desenho livre, como no ArtiosCAD): a faca
        calculada sai, as medidas travam e a ferramenta de corte já fica
        ativa. Ctrl+Z volta; "Descartar edições" volta pra faca calculada."""
        self.abas_tela.setCurrentIndex(0)
        self._faca_do_zero = True  # não herda o fechamento do tipo de caixa
        self._dobras_estilo, self._base_estilo, self._estilo_atual = None, None, None
        self.canvas._aplicar_faca("Nova faca em branco", [])
        self._acoes_faca["corte"].trigger()
        self.statusBar().showMessage(
            "Faca em branco: desenhe os cortes e vincos (barra Faca). A aba 3D dobra o que você desenhar.", 8000
        )

    # ── Estilos paramétricos (catálogo, como o do ArtiosCAD) ─────────────
    def _abrir_catalogo_estilos(self, estilo_inicial: str | None = None) -> None:
        atual = getattr(self, "_estilo_atual", None)
        if not isinstance(estilo_inicial, str):  # ligado a clique: chega um bool
            estilo_inicial = atual[0] if atual else None
        dialogo = DialogoEstilos(
            self, estilo_inicial=estilo_inicial, valores_iniciais=atual[1] if atual else None
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted or dialogo.faca is None:
            return
        self.aplicar_estilo(dialogo.estilo_escolhido, dialogo.valores, dialogo.faca)

    def _abrir_construtor_dieline(self) -> None:
        dialogo = DialogoConstrutorDieline(self)
        if dialogo.exec() != QDialog.DialogCode.Accepted or dialogo.faca is None:
            return
        self.aplicar_estilo(dialogo.estilo, dialogo.valores, dialogo.faca)

    def aplicar_estilo(self, estilo, valores: dict, faca) -> None:
        """Troca a faca pela do estilo (Ctrl+Z volta). A chapa fica do
        tamanho da faca e o 3D dobra com os ângulos e a ordem do estilo.
        Abrir o catálogo de novo traz o mesmo estilo e as mesmas medidas
        pra refazer com outros valores."""
        self.abas_tela.setCurrentIndex(0)
        self._faca_do_zero = True
        self.canvas.definir_pagina_pela_faca(True)
        self.canvas._aplicar_faca(f"Estilo {estilo.nome_exibicao}", faca.linhas)
        # Depois de aplicar: a faca editada liga aqui (e zera o anterior).
        self._estilo_atual = (estilo.nome_exibicao, dict(valores))
        self._dobras_estilo = list(faca.dobras)
        self._base_estilo = faca.ponto_base
        self._assinatura_faca_3d = None
        if "E" in faca.valores:
            # O 3D mostra o papelão que o estilo usou nas contas.
            self.visualizacao_3d.definir_espessura(faca.valores["E"])
        self.canvas.ajustar_a_tela()
        self._atualizar_modelo_3d()
        self.statusBar().showMessage(
            f"{estilo.nome_exibicao}: faca de {faca.largura:.1f} × {faca.altura:.1f} mm. "
            "Arquivo > Nova faca a partir de estilo refaz com outras medidas.",
            8000,
        )

    def _salvar_faca_como_estilo(self) -> None:
        linhas = list(self.canvas.linhas_faca())
        if not linhas:
            QMessageBox.information(self, "Salvar faca como estilo", "Não há faca pra salvar.")
            return
        nome, ok = QInputDialog.getText(self, "Salvar faca como estilo", "Nome do estilo:")
        if not ok or not nome.strip():
            return
        destino = salvar_estilo(estilo_da_faca(linhas, nome.strip()), pasta_estilos_usuario())
        self.statusBar().showMessage(f"Estilo salvo em {destino} — aparece no catálogo (Ctrl+Shift+N).", 10000)

    def _atualizar_modelo_3d(self) -> None:
        """Modelo 3D da faca atual. Faca calculada: o modelo próprio do tipo
        de caixa (com sequência de montagem e abas por baixo). Faca editada à
        mão: a dobra genérica, que acha as faces e os vincos sozinha, como o
        "Converter em 3D" do ArtiosCAD (ver dobra_generica.py)."""
        layout = self.canvas.layout_atual
        if layout is None:
            return
        medidas = self._obter_medidas()
        texto = f"{medidas.comprimento:g} × {medidas.largura:g} × {medidas.altura:g} mm"
        if self.canvas.faca_editada:
            linhas = list(self.canvas.linhas_faca())
            assinatura = tuple((l.x1, l.y1, l.x2, l.y2, l.tipo, l.bojo) for l in linhas)
            if assinatura != self._assinatura_faca_3d:
                # A faca mudou: índices de linha e de face não valem mais.
                self._assinatura_faca_3d = assinatura
                self._angulos_dobra = {}
                self._face_base_3d = None
            # Faca vinda do tipo de caixa: herda o fechamento dele (mexer no
            # corte de uma aba não muda como a caixa fecha).
            referencia = None
            if not getattr(self, "_faca_do_zero", False):
                referencia = montar_modelo(medidas.tipo, layout.segmentos_impressora, layout.segmentos_riscador)
            modelo = montar_modelo_generico(
                linhas,
                angulos=self._angulos_dobra,
                base=self._face_base_3d,
                descricao=self._estilo_atual[0] if getattr(self, "_estilo_atual", None) else "Faca editada",
                referencia=referencia,
                dobras_estilo=getattr(self, "_dobras_estilo", None),
                ponto_base=getattr(self, "_base_estilo", None),
            )
            texto = ""
        else:
            modelo = montar_modelo(medidas.tipo, layout.segmentos_impressora, layout.segmentos_riscador)
        self.visualizacao_3d.definir_modelo(modelo, texto)

    def _atualizar_arte_3d(self) -> None:
        """Liga o 3D à arte do Layout. O 3D pede a arte face a face, na
        resolução que precisar (ver `renderizar_arte_regioes`); aqui só
        entrega a fonte — e chamar de novo descarta as texturas antigas,
        então basta chamar ao entrar na aba 3D e ao recalcular com ela aberta."""
        if self.canvas.layout_atual is None or not self.canvas.elementos_mockup:
            self.visualizacao_3d.definir_fonte_arte(None)
            return
        cena, elementos = self.canvas.cena, list(self.canvas.elementos_mockup)
        self.visualizacao_3d.definir_fonte_arte(lambda pedidos: renderizar_arte_regioes(cena, elementos, pedidos))

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
        self.painel_propriedades_mockup.agrupar_solicitado = lambda: self.canvas.agrupar_selecionados()
        self.painel_propriedades_mockup.desagrupar_solicitado = lambda: self.canvas.desagrupar_selecionados()
        self.painel_propriedades_mockup.desagrupar_tudo_solicitado = lambda: self.canvas.desagrupar_tudo()
        self.painel_propriedades_mockup.propriedades_alteradas = lambda el, antes, depois: (
            self.canvas.registrar_propriedades({el: antes}, {el: depois}, "Propriedade", juntar=True)
        )
        self.painel_propriedades_mockup.alinhar_multiplos_solicitado = self.canvas.alinhar_selecionados
        self.painel_propriedades_mockup.obter_tamanho_pagina = self._tamanho_pagina
        self.painel_propriedades_mockup.modelar_solicitado = self.canvas.modelar_selecionados

        # Quebra de linha de propósito, mesmo motivo de `_montar_barra_mockup`:
        # sem isso o Qt tenta encaixar essa barra na mesma linha da barra
        # de criar elemento, em vez de ficar embaixo dela (a leitura de
        # cima pra baixo — criar elemento, depois editar propriedade dele
        # — fica confusa se as duas disputam a mesma linha).
        barra = QToolBar("Propriedades")
        barra.setObjectName("barraPropriedadesMockup")
        barra.setMovable(False)
        self.addToolBar(barra)
        self.painel_propriedades_mockup.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        barra.addWidget(self.painel_propriedades_mockup)
        self.barra_propriedades_mockup = barra
        barra.setFixedHeight(ALTURA_CONTEXTO)
        # Sem a margem padrão da QToolBar: com ela o painel (da mesma altura
        # da barra) descia 10 px e a linha ficava torta, cortada embaixo.
        barra.layout().setContentsMargins(0, 0, 0, 0)
        # Organizar à direita das propriedades, na mesma linha de contexto.
        self.removeToolBar(self.barra_organizar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.barra_organizar)
        # Inspetor: a aba Propriedades (Geometria, Alinhar ao painel, Tinta...).
        rolagem = QScrollArea()
        rolagem.setObjectName("rolagemInspetor")
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rolagem.setWidget(self.painel_propriedades_mockup.inspetor)
        self.abas_inspetor.insertTab(0, rolagem, "Propriedades")
        self.abas_inspetor.setCurrentIndex(0)
        self._docks["propriedades"] = _PaginaInspetor(self, rolagem, "Propriedades", False)
        self.painel_propriedades_mockup.nova_tinta_solicitada = self._nova_tinta_inspetor
        # 3D: sem linha de contexto (os controles ficam na própria vista).
        self.barra_propriedades_mockup.hide()  # só aparece na tela de Layout (ver _trocar_tela)

    def _nova_tinta_inspetor(self) -> None:
        """"+ Nova tinta" do inspetor: as tintas moram na legenda da
        Dieline — vai pra lá, onde se marca/adiciona a cor."""
        self.abas_tela.setCurrentIndex(0)
        self.statusBar().showMessage("Marque ou adicione a tinta na legenda de cores, acima do desenho.", 6000)

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
        barra.setObjectName("colunaFerramentas")
        barra.setMovable(False)
        barra.setFixedWidth(LARGURA_COLUNA_FERRAMENTAS)
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
            ferramenta(
                "cota_angular",
                "Cota angular — clique no vértice, depois num ponto de cada braço (Esc cancela)",
                FerramentaMockup.COTA_ANGULAR,
            ),
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
            acao_simples(
                "ferramenta_simbolo",
                "Banco de simbologias (Ctrl+Shift+Y) — símbolos prontos e os seus, dois cliques põe no layout",
                lambda: self.abrir_docker("simbologias"),
            ),
        )
        self._acoes_ferramenta[FerramentaMockup.SELECIONAR].setChecked(True)

        self.canvas.ferramenta_alterada.connect(self._ao_ferramenta_alterada)
        self.canvas.retangulo_desenhado.connect(self._criar_retangulo_por_arrasto)
        self.canvas.linha_desenhada.connect(self._criar_linha_por_arrasto)
        self.canvas.cota_desenhada.connect(self._criar_cota_por_arrasto)
        self.canvas.curva_desenhada.connect(self._criar_curva)
        self.canvas.cota_angular_desenhada.connect(self._criar_cota_angular)
        self.canvas.mensagem_status.connect(lambda texto: self.statusBar().showMessage(texto, 6000))
        self.canvas.texto_solicitado.connect(self._criar_texto_por_clique)
        self.canvas.cor_amostrada.connect(self._ao_cor_amostrada)
        self.canvas.tinta_amostrada.connect(self._ao_tinta_amostrada)
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
        # Barra de contexto (opções da ferramenta) em cima; as ferramentas
        # numa coluna vertical à esquerda (REDESIGN.md 2.1).
        barra = QToolBar("Faca")
        barra.setObjectName("barraContexto")
        barra.setMovable(False)
        barra.setFixedHeight(ALTURA_CONTEXTO)
        barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, barra)
        self.barra_faca = barra
        coluna = QToolBar("Ferramentas da faca")
        coluna.setObjectName("colunaFerramentas")
        coluna.setMovable(False)
        coluna.setFixedWidth(LARGURA_COLUNA_FERRAMENTAS)
        coluna.setOrientation(Qt.Orientation.Vertical)
        coluna.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, coluna)
        self.barra_ferramentas_faca = coluna

        grupo = QActionGroup(self)
        grupo.setExclusive(True)
        self._acoes_faca: dict[str, QAction] = {}

        def modo(chave: str, icone: str, dica: str) -> None:
            acao = QAction(construir_icone(icone), dica, self)
            acao.setCheckable(True)
            acao.triggered.connect(lambda: self._definir_modo_faca(chave))
            grupo.addAction(acao)
            coluna.addAction(acao)
            self._acoes_faca[chave] = acao

        modo("navegar", "navegar", "Navegar — arrastar move a visão (a faca não muda)")
        modo(
            "forma",
            "editar_faca",
            "Editar faca (F10) — clique numa linha; arraste a linha ou uma ponta (as linhas ligadas acompanham; "
            "Alt solta a ponta, Shift trava na horizontal/vertical). Delete remove a linha",
        )
        coluna.addSeparator()
        modo("corte", "linha_corte", "Nova linha de corte — arraste de um ponto a outro (Ctrl = 15°)")
        modo("vinco", "linha_vinco", "Nova linha de vinco — arraste de um ponto a outro (Ctrl = 15°)")
        modo("retangulo", "ferramenta_retangulo", "Retângulo — arraste de um canto ao oposto: 4 linhas do tipo novo")
        modo(
            "medida",
            "linha_medida",
            "Linha por medida (ArtiosCAD) — clique o ponto inicial e digite comprimento e ângulo "
            "(0° = direita, 90° = cima), Enter. A próxima começa onde esta acabou; Esc para",
        )
        modo(
            "arco",
            "faca_arco",
            "Arco — arraste de uma ponta à outra, solte, mova o mouse para curvar e clique para confirmar (Ctrl = 15°)",
        )
        coluna.addSeparator()
        modo("aparar", "faca_aparar", "Aparar — clique no trecho da linha que passa do cruzamento para cortá-lo fora")
        modo("estender", "faca_estender", "Estender — clique perto da ponta: a linha cresce até a próxima linha no caminho")
        modo("arredondar", "faca_arredondar", "Arredondar canto — clique no canto onde duas retas se encontram (raio ao lado)")
        self._acoes_faca["navegar"].setChecked(True)

        barra.addWidget(QLabel(" Linha selecionada: "))
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
        self.combo_tipo_linha.setMaximumWidth(140)
        self.combo_tipo_linha.activated.connect(
            lambda _i: self.canvas.definir_tipo_linha_selecionada(self.combo_tipo_linha.currentData())
        )
        barra.addWidget(self.combo_tipo_linha)
        self._acao_paralela = self._acao_icone(
            coluna, "faca_paralela", "Paralela — cópia da linha selecionada a uma distância (negativo = outro lado)", self._criar_paralela
        )
        self._acao_paralela.setEnabled(False)
        self._acao_remover_linha = self._acao_icone(
            coluna, "remover", "Remover a linha selecionada (Delete)", lambda: self.canvas.remover_linha_faca_selecionada()
        )
        self._acao_remover_linha.setEnabled(False)
        barra.addSeparator()

        barra.addWidget(QLabel(" Linha nova: "))
        self.combo_tipo_novo = QComboBox()
        self.combo_tipo_novo.setToolTip("Tipo das linhas que o retângulo, a medida e o arco criam")
        for i in range(self.combo_tipo_linha.count()):
            self.combo_tipo_novo.addItem(self.combo_tipo_linha.itemText(i), self.combo_tipo_linha.itemData(i))
        self.combo_tipo_novo.activated.connect(
            lambda _i: self.canvas.definir_tipo_linha_nova(self.combo_tipo_novo.currentData())
        )
        self.combo_tipo_novo.setMaximumWidth(140)
        barra.addWidget(self.combo_tipo_novo)
        barra.addWidget(QLabel(" Raio: "))
        self.spin_raio_faca = QDoubleSpinBox()
        self.spin_raio_faca.setRange(0.1, 1000.0)
        self.spin_raio_faca.setDecimals(2)
        self.spin_raio_faca.setSuffix(" mm")
        self.spin_raio_faca.setValue(5.0)
        self.spin_raio_faca.setToolTip("Raio do Arredondar canto")
        self.spin_raio_faca.setMaximumWidth(110)
        self.spin_raio_faca.valueChanged.connect(self.canvas.definir_raio_arredondar)
        barra.addWidget(self.spin_raio_faca)
        espacador = QWidget()
        espacador.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        barra.addWidget(espacador)
        for icone, texto, dica, callback in (
            ("catalogo", "Catálogo de estilos", "Catálogo de estilos (Ctrl+Shift+N) — FEFCO 0201, 0427 e os seus, em qualquer medida",
             self._abrir_catalogo_estilos),
            ("medida", "Construtor de dieline",
             "Construtor de dieline (Ctrl+Shift+D) — monte uma faca nova por trechos: vincos, cortes, fendas e dobras",
             self._abrir_construtor_dieline),
        ):
            botao = QToolButton()
            botao.setObjectName("botaoContexto")
            botao.setIcon(construir_icone(icone))
            botao.setText(texto)
            botao.setToolTip(dica)
            botao.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            botao.clicked.connect(callback)
            barra.addWidget(botao)
        self._distancia_paralela = 3.0

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
        if chave in ("corte", "vinco"):
            indice = self.combo_tipo_novo.findData(TipoLinha.VINCO if chave == "vinco" else TipoLinha.CORTE)
            self.combo_tipo_novo.setCurrentIndex(indice)
        else:
            self.canvas.definir_tipo_linha_nova(self.combo_tipo_novo.currentData())

    def _criar_paralela(self) -> None:
        distancia, ok = QInputDialog.getDouble(
            self, "Paralela", "Distância (mm) — negativo cria do outro lado:", self._distancia_paralela, -10000.0, 10000.0, 2
        )
        if ok and distancia != 0:
            self._distancia_paralela = distancia
            self.canvas.criar_paralela_selecionada(distancia)

    def _ao_selecionar_linha_faca(self, tipo) -> None:
        self.combo_tipo_linha.setEnabled(tipo is not None)
        self._acao_remover_linha.setEnabled(tipo is not None)
        self._acao_paralela.setEnabled(tipo is not None)
        if tipo is not None:
            indice = self.combo_tipo_linha.findData(tipo)
            if indice >= 0:
                self.combo_tipo_linha.setCurrentIndex(indice)

    def _ao_faca_editada(self, editada: bool) -> None:
        """Faca editada à mão: trava tipo e medidas (mudar qualquer uma
        recalcularia a faca e jogaria a edição fora sem aviso)."""
        self.aviso_faca_editada.setVisible(editada)
        if not editada:
            self._faca_do_zero = False
            self._dobras_estilo, self._base_estilo, self._estilo_atual = None, None, None
        for widget in (self._grupo_tipo, self._grupo_medidas_cla, self._grupo_medidas):
            widget.setEnabled(not editada)
        if editada:
            self.statusBar().showMessage("Faca editada à mão — medidas travadas até descartar as edições.", 6000)

    def _montar_barra_organizar(self) -> None:
        """Desfazer/refazer, agrupar e ordem — no topo, como a barra
        padrão do CorelDRAW (não na caixa de ferramentas)."""
        barra = QToolBar("Organizar")
        barra.setObjectName("barraOrganizar")
        barra.setMovable(False)
        barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, barra)
        self.barra_organizar = barra

        self._montar_menu_ajustar_a()  # o botão fica na barra de status (Encaixe)
        barra.setFixedHeight(ALTURA_CONTEXTO)
        # Compacto (o Qt não usa o padding da QSS como margem de QToolBar).
        barra.setIconSize(QSize(20, 20))
        barra.layout().setContentsMargins(6, 0, 6, 0)
        barra.layout().setSpacing(1)
        self._acao_icone(barra, "agrupar", "Agrupar (Ctrl+G)", lambda: self.canvas.agrupar_selecionados())
        self._acao_icone(barra, "desagrupar", "Desagrupar (Ctrl+U)", lambda: self.canvas.desagrupar_selecionados())
        barra.addSeparator()
        self._acao_icone(barra, "converter_curvas", "Converter em curvas (Ctrl+Q)", lambda: self.canvas.converter_selecionados_em_curvas())
        self._acao_icone(barra, "combinar", "Combinar (Ctrl+L)", lambda: self.canvas.combinar_selecionados())
        self._acao_icone(barra, "separar", "Separar (Ctrl+K)", lambda: self.canvas.separar_selecionados())
        barra.addSeparator()
        self._acao_icone(barra, "trazer_frente", "Para a frente da página (Shift+PgUp)", lambda: self.canvas.trazer_para_frente())
        self._acao_icone(barra, "enviar_tras", "Para trás da página (Shift+PgDn)", lambda: self.canvas.enviar_para_tras())
        barra.addSeparator()
        self._acao_icone(
            barra, "alinhar_centro_h", "Alinhar e distribuir (Ctrl+Shift+A)", self._no_layout(lambda: self.abrir_docker("alinhar"))
        )
        barra.hide()

    def _montar_dockers(self) -> None:
        """Inspetor da direita (prancheta Layout do REDESIGN.md): UM dock,
        entre o desenho e a paleta, com as abas Propriedades | Objetos |
        Alinhar | ··· (Transformações, Simbologias). Os dockers do
        CorelDRAW (ver `dockers_corel.py`) viram páginas dele; `_docks`
        continua respondendo por cada um (ver `_PaginaInspetor`). Só existe
        na tela de Layout."""
        self.docker_objetos = DockerObjetos(self.canvas)
        self.docker_alinhar = DockerAlinhar(self.canvas)
        self.docker_transformacoes = DockerTransformacoes(self.canvas)
        self.docker_simbologias = DockerSimbologias()
        self.docker_simbologias.inserir_simbolo.connect(self.inserir_simbolo)
        self.dock_inspetor = QDockWidget("Inspetor", self)
        self.dock_inspetor.setObjectName("dockInspetor")
        self.dock_inspetor.setTitleBarWidget(QWidget())  # sem título: as abas já dizem o que é
        self.dock_inspetor.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.dock_inspetor.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.abas_inspetor = QTabWidget()
        self.abas_inspetor.setObjectName("abasInspetor")
        self.abas_inspetor.setDocumentMode(True)
        self.abas_inspetor.setMinimumWidth(300)
        self.dock_inspetor.setWidget(self.abas_inspetor)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_inspetor)
        self.resizeDocks([self.dock_inspetor], [320], Qt.Orientation.Horizontal)
        self.dock_inspetor.hide()
        mais = QToolButton()
        mais.setObjectName("botaoMaisInspetor")
        mais.setText("···")
        mais.setToolTip("Mais painéis")
        mais.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        mais.setMenu(QMenu(mais))
        self.abas_inspetor.setCornerWidget(mais, Qt.Corner.TopRightCorner)
        self._docks: dict[str, _PaginaInspetor] = {}
        for chave, titulo, rotulo_aba, conteudo, no_menu in (
            ("objetos", "Objetos", "Objetos", self.docker_objetos, False),
            ("alinhar", "Alinhar e distribuir", "Alinhar", self.docker_alinhar, False),
            ("transformacoes", "Transformações", "Transformações", self.docker_transformacoes, True),
            ("simbologias", "Simbologias", "Simbologias", self.docker_simbologias, True),
        ):
            self.abas_inspetor.addTab(conteudo, rotulo_aba)
            pagina = _PaginaInspetor(self, conteudo, titulo, no_menu)
            if no_menu:  # no "···": a aba só aparece quando é escolhida
                self.abas_inspetor.setTabVisible(self.abas_inspetor.indexOf(conteudo), False)
                mais.menu().addAction(titulo, lambda p=pagina: p.show())
            self._docks[chave] = pagina
        self._docks_abertos_layout: set[str] = {"propriedades"}
        self._estava_no_layout = False

        # Atalhos do CorelDRAW pra abrir cada docker (só na tela de Layout).
        self._acoes_docker: list[QAction] = []

        def atalho(texto: str, tecla: str, callback) -> None:
            acao = QAction(texto, self)
            acao.setShortcut(QKeySequence(tecla))
            acao.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            acao.triggered.connect(self._no_layout(callback))
            self.addAction(acao)
            self._acoes_docker.append(acao)

        atalho("Alinhar e distribuir", "Ctrl+Shift+A", lambda: self.abrir_docker("alinhar"))
        atalho("Simbologias", "Ctrl+Shift+Y", lambda: self.abrir_docker("simbologias"))
        for tecla, aba in (("Alt+F7", "posicao"), ("Alt+F8", "rotacao"), ("Alt+F9", "escala"), ("Alt+F10", "tamanho")):
            atalho(f"Transformações ({aba})", tecla, lambda _c=False, a=aba: self.abrir_docker("transformacoes", a))

    def _no_layout(self, funcao):
        """Ação que só vale na tela de Layout: de outra tela, vai pra lá antes."""

        def rodar(*_args) -> None:
            if self.abas_tela.currentIndex() != 1:
                self.abas_tela.setCurrentIndex(1)
                QApplication.processEvents()
            funcao()

        return rodar

    def _abrir_inspetor_layout(self) -> None:
        """Volta ao Layout: o inspetor reabre na página em que estava."""
        abertos = self._docks_abertos_layout
        if not abertos:
            return
        self.dock_inspetor.show()
        for chave in abertos:
            if chave in self._docks:
                self._docks[chave].show()

    def _guardar_inspetor_layout(self) -> None:
        if not self.dock_inspetor.isVisible():
            self._docks_abertos_layout = set()
            return
        atual = next((c for c, d in self._docks.items() if d.isVisible()), "propriedades")
        self._docks_abertos_layout = {atual}

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
        paleta = PaletaCores(_cores_disponiveis())
        self._paleta_cores = paleta
        paleta.preenchimento_escolhido.connect(lambda cor: self._aplicar_cor_paleta(cor, contorno=False))
        paleta.contorno_escolhido.connect(lambda cor: self._aplicar_cor_paleta(cor, contorno=True))
        barra.addWidget(paleta)
        self.barra_paleta = barra
        barra.hide()

    def _aplicar_cor_paleta(self, cor, contorno: bool) -> None:
        selecionados = [it for it in self.canvas.cena.selectedItems() if isinstance(it, ElementoMockup)]
        self.canvas.com_undo_propriedades(
            selecionados, "Cor", lambda: self._aplicar_cor_paleta_sem_desfazer(cor, contorno)
        )

    def _aplicar_cor_paleta_sem_desfazer(self, cor, contorno: bool) -> None:
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
                elif isinstance(el, ElementoLogoVetorial):
                    el.pintar_numa_tinta(None)  # X no logotipo/símbolo: volta às cores do arquivo
        else:
            nome, rgb = cor
            chip = self._chips_cor.get(nome, (None,))[0]
            if chip is not None and not chip.isChecked():
                chip.setChecked(True)
            tinta = CorImpressao(nome=nome.upper(), r=rgb[0], g=rgb[1], b=rgb[2])
            for el in selecionados:
                if isinstance(el, ElementoLogoVetorial):
                    el.pintar_numa_tinta(tinta)
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
        self.statusBar().setFixedHeight(ALTURA_STATUS)
        self.statusBar().addPermanentWidget(self.painel_status)
        self.statusBar().addPermanentWidget(divisoria_status())
        # Encaixe: liga/desliga (o mesmo do menu Exibir) + a setinha abre o "Ajustar a".
        self.botao_encaixe = QToolButton()
        self.botao_encaixe.setObjectName("botaoStatus")
        self.botao_encaixe.setCheckable(True)
        self.botao_encaixe.setToolTip("Encaixe (snap) ao arrastar — a setinha escolhe onde gruda (Ajustar a)")
        self.botao_encaixe.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.botao_encaixe.setMenu(self._menu_ajustar_a)
        self.botao_encaixe.toggled.connect(
            lambda ligado: self.botao_encaixe.setText(f"Encaixe: {'ligado' if ligado else 'desligado'}")
        )
        self.botao_encaixe.setChecked(self._acao_snap.isChecked())
        self.botao_encaixe.setText(f"Encaixe: {'ligado' if self._acao_snap.isChecked() else 'desligado'}")
        self.botao_encaixe.toggled.connect(self._acao_snap.setChecked)
        self._acao_snap.toggled.connect(self.botao_encaixe.setChecked)
        self.statusBar().addPermanentWidget(self.botao_encaixe)
        self.botao_guias = QToolButton()
        self.botao_guias.setObjectName("botaoStatus")
        self.botao_guias.setCheckable(True)
        self.botao_guias.setToolTip("Guias dinâmicas (Alt+Shift+D)")
        self.botao_guias.toggled.connect(
            lambda ligadas: self.botao_guias.setText(f"Guias dinâmicas: {'ligadas' if ligadas else 'desligadas'}")
        )
        self.botao_guias.setChecked(self._acao_guias_dinamicas.isChecked())
        self.botao_guias.setText(
            f"Guias dinâmicas: {'ligadas' if self._acao_guias_dinamicas.isChecked() else 'desligadas'}"
        )
        self.botao_guias.toggled.connect(self._acao_guias_dinamicas.setChecked)
        self._acao_guias_dinamicas.toggled.connect(self.botao_guias.setChecked)
        self.statusBar().addPermanentWidget(self.botao_guias)
        # Layout: quantas tintas o trabalho tem (a legenda/checklist de cores).
        self.rotulo_tintas_status = QLabel()
        self.rotulo_tintas_status.setObjectName("legendaMuted")
        self.rotulo_tintas_status.hide()
        self.statusBar().addPermanentWidget(self.rotulo_tintas_status)
        self.statusBar().addPermanentWidget(divisoria_status())
        self.ponte_corel = PonteCorel()
        self.statusBar().addPermanentWidget(self.ponte_corel)
        self.statusBar().addPermanentWidget(divisoria_status())
        self.statusBar().addPermanentWidget(self.botao_ajustar_tela)
        self.statusBar().addPermanentWidget(self.label_zoom)
        self.canvas.cursor_movido.connect(self.painel_status.definir_posicao)
        self.painel_status.conteudo_mudou.connect(self.statusBar().update)
        self.painel_status.definir_objeto("", None, None, False)
        # Cor do objeto embaixo, como no CorelDRAW: clicar na amostra abre as
        # tintas; o conta-gotas pega a cor de outro objeto.
        self.painel_status.botao_conta_gotas.setIcon(construir_icone("conta_gotas"))
        self.painel_status.botao_conta_gotas.clicked.connect(
            lambda: self.canvas.definir_ferramenta(FerramentaMockup.CONTA_GOTAS)
        )
        self.painel_status.amostra_preenchimento.clicada.connect(lambda: self._menu_cor_status(contorno=False))
        self.painel_status.amostra_contorno.clicada.connect(lambda: self._menu_cor_status(contorno=True))
        self.painel_status.definir_controles_de_cor(False)

    def _atualizar_tintas_status(self) -> None:
        rotulo = getattr(self, "rotulo_tintas_status", None)
        if rotulo is None:
            return
        n = len(self._cores_impressao_ativas())
        # Curto: numa tela de 1366 a descrição da caixa, à esquerda, sumia.
        rotulo.setText(f"{n} {'tinta' if n == 1 else 'tintas'}")
        rotulo.setToolTip("Checklist de cores: tintas marcadas na legenda")
        rotulo.setVisible(self.abas_tela.currentIndex() == 1)

    def _menu_cor_status(self, contorno: bool, executar: bool = True) -> QMenu:
        """Lista de tintas (com amostra) pra aplicar no selecionado — o mesmo
        que clicar na paleta: esquerdo = preenchimento, aqui escolhido pela
        amostra clicada."""
        from PySide6.QtGui import QIcon, QPixmap

        menu = QMenu(self)
        nenhum = menu.addAction("Nenhum" if not contorno else "Nenhum (só preenchimento)")
        nenhum.triggered.connect(lambda: self._aplicar_cor_paleta(None, contorno=contorno))
        menu.addSeparator()
        for nome, rgb in _cores_disponiveis():
            amostra = QPixmap(14, 14)
            amostra.fill(QColor(*rgb))
            acao = menu.addAction(QIcon(amostra), nome)
            acao.triggered.connect(lambda _c=False, n=nome, c=rgb: self._aplicar_cor_paleta((n, c), contorno=contorno))
        menu.addSeparator()
        menu.addAction("Nova cor…", self._nova_cor_personalizada)
        if executar:
            alvo = self.painel_status.amostra_contorno if contorno else self.painel_status.amostra_preenchimento
            menu.exec(alvo.mapToGlobal(alvo.rect().topLeft()) - QPoint(0, menu.sizeHint().height()))
        return menu

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
        self._ajustar_ao_zoom(elemento)  # nasce do mesmo tamanho na tela em qualquer zoom
        # Cada elemento novo nasce um pouco deslocado do anterior (efeito
        # "cascata", igual colar em qualquer editor vetorial) — sem isso,
        # criar vários elementos seguidos empilha tudo exatamente no
        # centro, um em cima do outro, impossível de distinguir/clicar.
        passo = 8.0 * self._fator_zoom() * (len(self.canvas.elementos_mockup) % 6)
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

    def _criar_cota_angular(self, vertice: QPointF, ponto_a: QPointF, ponto_b: QPointF) -> None:
        cota = ElementoCotaAngular(vertice, ponto_a, ponto_b, cor_tinta=self._cor_tinta_padrao())
        self.canvas.adicionar_elemento_mockup(cota, cota.posicao_inicial_cena)
        self.canvas.cena.clearSelection()
        cota.setSelected(True)
        # Continua na ferramenta, como as outras cotas.

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

    def _fator_zoom(self) -> float:
        """Quanto os elementos novos crescem/encolhem com o zoom: no zoom de
        ~1,25 px/mm (uma caixa grande inteira na tela) vale 1; numa caixa
        desenhada em escala reduzida, com mais zoom, eles nascem menores —
        sempre do mesmo tamanho na TELA, como no CorelDRAW."""
        return max(0.01, min(20.0, self.canvas.mm_por_px() / 0.8))

    def _ajustar_ao_zoom(self, elemento: ElementoMockup) -> None:
        f = self._fator_zoom()
        if isinstance(elemento, ElementoChecklistCores):
            # O checklist se mede pela letra: ela é que acompanha o zoom.
            elemento.definir_tamanho_pt(elemento.tamanho_pt * f)
            return
        elemento.definir_tamanho(elemento.largura * f, elemento.altura * f)

    def _criar_texto_por_clique(self, pos: QPointF) -> None:
        """Ferramenta Texto, como no CorelDRAW: o clique é o começo da linha
        de base, o cursor já pisca ali e é só digitar. A letra nasce com
        ~24 px de altura na tela, em qualquer zoom."""
        elemento = ElementoTexto(
            texto="", fonte_familia=configuracoes.fonte_padrao_texto(), cor_tinta=self._cor_tinta_padrao()
        )
        # Padrão da máquina (Configurações): Arial Black, 2 mm, meio esticada.
        elemento.aplicar_letra(configuracoes.altura_letra_padrao_mm(), configuracoes.largura_letra_padrao())
        self.canvas.iniciar_texto_novo(elemento, QPointF(pos.x(), pos.y() - elemento.altura))

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
        self._ajustar_ao_zoom(elemento)
        self.canvas.adicionar_elemento_mockup(elemento, pos)
        self._selecionar_e_voltar_ao_ponteiro(elemento)
        elemento.iniciar_edicao_inline()

    def _criar_tabela_por_clique(self, pos: QPointF) -> None:
        elemento = ElementoTabela(
            cor_tinta=self._cor_tinta_padrao(),
            fonte_familia=configuracoes.fonte_padrao_texto(),
            altura_letra_mm=configuracoes.altura_letra_padrao_mm(),
            largura_letra=configuracoes.largura_letra_padrao(),
        )
        self._ajustar_ao_zoom(elemento)
        self.canvas.adicionar_elemento_mockup(elemento, pos)
        self._selecionar_e_voltar_ao_ponteiro(elemento)

    def _criar_simbolo_por_clique(self, pos: QPointF) -> None:
        elemento = ElementoSimbolo(cor_tinta=self._cor_tinta_padrao())
        self._ajustar_ao_zoom(elemento)
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
        """Conta-gotas num pixel (imagem, fundo): a tinta da lista mais
        PRÓXIMA da cor — a caixa só imprime em tintas reais, nunca num RGB
        solto."""

        def distancia(item) -> int:
            _nome, (r, g, b) = item
            return (r - cor.red()) ** 2 + (g - cor.green()) ** 2 + (b - cor.blue()) ** 2

        nome, (r, g, b) = min(_cores_disponiveis(), key=distancia)
        self._ao_tinta_amostrada(CorImpressao(nome=nome.upper(), r=r, g=g, b=b))

    def _ao_tinta_amostrada(self, tinta: CorImpressao) -> None:
        selecionados = _folhas_coloriveis(self.canvas.cena.selectedItems())
        if not selecionados:
            # Como no CorelDRAW: pega a cor primeiro e clica depois em quem recebe.
            self.canvas.tinta_carregada = tinta
            self.statusBar().showMessage(f"Cor pega: {tinta.nome} — agora clique no objeto que vai recebê-la.", 10000)
            return
        self.canvas.com_undo_propriedades(selecionados, "Conta-gotas", lambda: self._aplicar_tinta_amostrada(tinta))

    def _aplicar_tinta_amostrada(self, tinta: CorImpressao) -> None:
        """Conta-gotas: a tinta pega vai pro(s) objeto(s) selecionado(s) e
        fica marcada na legenda (se ainda não estava)."""
        selecionados = _folhas_coloriveis(self.canvas.cena.selectedItems())  # grupo: todos os de dentro
        if not selecionados:
            return
        for elemento in selecionados:
            if isinstance(elemento, ElementoLogoVetorial):
                elemento.pintar_numa_tinta(tinta)
            else:
                elemento.definir_cor_tinta(tinta)
        chip = next((c for n, (c, _rgb) in self._chips_cor.items() if n.upper() == tinta.nome.upper()), None)
        if chip is None:
            # Tinta que não está na lista (projeto de outro computador): entra como sua.
            configuracoes.definir_cores_personalizadas(
                configuracoes.cores_personalizadas() + [(tinta.nome.title(), (tinta.r, tinta.g, tinta.b))]
            )
            self._montar_chips_cores()
            chip = next((c for n, (c, _rgb) in self._chips_cor.items() if n.upper() == tinta.nome.upper()), None)
        if chip is not None and not chip.isChecked():
            chip.setChecked(True)
        self._ao_selecao_mockup_mudar()
        self.statusBar().showMessage(f"Cor aplicada: {tinta.nome}", 6000)
        self.canvas.definir_ferramenta(FerramentaMockup.SELECIONAR)

    def _adicionar_checklist(self) -> None:
        # No padrão da máquina, como o texto (não acompanha o zoom: a letra
        # tem a altura certa de impressão).
        elemento = ElementoChecklistCores(
            variantes=["Cor 1", "Cor 2"],
            cor_tinta=self._cor_tinta_padrao(),
            fonte_familia=configuracoes.fonte_padrao_texto(),
            largura_letra=configuracoes.largura_letra_padrao(),
        )
        elemento.definir_altura_letra_mm(configuracoes.altura_letra_padrao_mm())
        pos = self._posicao_central_canvas()
        self.canvas.adicionar_elemento_mockup(elemento, QPointF(pos.x() - elemento.largura / 2, pos.y() - elemento.altura / 2))
        for item in self.canvas.cena.selectedItems():
            item.setSelected(False)
        elemento.setSelected(True)

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

    def _adicionar_logo(self, caminho: str | None = None) -> None:
        # Aceita PNG/JPG além de SVG — pra quem só tem o logotipo em
        # imagem (o caso mais comum na prática, a maioria das empresas
        # não tem versão vetorial à mão), não faz sentido travar no
        # formato: quem pediu "logotipo" quer usar o arquivo que tem, a
        # separação de cor automática só se aplica quando é SVG mesmo.
        if not isinstance(caminho, str):  # ligado a clique: chega um bool
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
        # No tamanho em que foi desenhado (SVG: unidade do arquivo; PNG/JPG:
        # resolução gravada), como os símbolos do banco.
        real = elemento.tamanho_real_mm
        if real is None and isinstance(elemento, ElementoLogoVetorial):
            real = tamanho_mm(Path(caminho))
        self._inserir_no_tamanho_real(elemento, real)
        if real is not None:
            self.statusBar().showMessage(
                f"Logotipo no tamanho do arquivo: {real[0]:.1f} × {real[1]:.1f} mm".replace(".", ","), 6000
            )
        if isinstance(elemento, ElementoLogoVetorial) and elemento.cores_detectadas:
            self._remapear_cores_logo(elemento)

    def inserir_simbolo(self, caminho: str, nome: str = "") -> ElementoLogoVetorial | None:
        """Símbolo do banco de simbologias no centro da tela, no tamanho real
        em que foi desenhado (é um logotipo vetorial: dá pra trocar as cores)."""
        try:
            elemento = ElementoLogoVetorial(caminho)
        except ValueError as exc:
            QMessageBox.critical(self, "Erro ao abrir símbolo", str(exc))
            return None
        self._inserir_no_tamanho_real(elemento, elemento.tamanho_real_mm or tamanho_mm(Path(caminho)))
        self.statusBar().showMessage(f"Símbolo “{nome or Path(caminho).stem}” inserido", 4000)
        return elemento

    def _inserir_no_tamanho_real(self, elemento: ElementoMockup, real: tuple[float, float] | None) -> None:
        """No centro da tela, no tamanho real (mm) do arquivo; sem tamanho
        conhecido, no tamanho padrão de tela como os outros elementos."""
        if real is None:
            self._adicionar_elemento_mockup_e_selecionar(elemento)
            return
        elemento.definir_tamanho(*real)
        passo = 8.0 * self._fator_zoom() * (len(self.canvas.elementos_mockup) % 6)  # cascata, como os outros
        pos = self._posicao_central_canvas() + QPointF(passo, passo)
        self.canvas.adicionar_elemento_mockup(
            elemento, QPointF(pos.x() - elemento.largura / 2, pos.y() - elemento.altura / 2)
        )
        for item in self.canvas.cena.selectedItems():
            item.setSelected(False)
        elemento.setSelected(True)

    def salvar_no_banco_de_simbologias(self, nome: str | None = None) -> Path | None:
        """O logotipo selecionado no layout vira um símbolo do banco (em
        "Meus símbolos"), pra usar nos próximos trabalhos."""
        logos = [it for it in self.canvas.cena.selectedItems() if isinstance(it, ElementoLogoVetorial)]
        if len(logos) != 1:
            QMessageBox.information(
                self, "Salvar no banco de simbologias",
                "Selecione um logotipo/símbolo vetorial (SVG) do layout pra guardar no banco.",
            )
            return None
        logo = logos[0]
        if not isinstance(nome, str):
            nome, ok = QInputDialog.getText(
                self, "Salvar no banco de simbologias", "Nome do símbolo:",
                text=getattr(logo, "nome_original", None) and Path(logo.nome_original).stem or Path(logo.caminho_arquivo).stem,
            )
            if not ok or not nome.strip():
                return None
        # O arquivo como veio (com o tamanho de verdade); sem ele, o desenho carregado.
        arquivo = Path(logo.caminho_arquivo)
        try:
            conteudo = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            conteudo = logo._conteudo_original
        destino = self.docker_simbologias.adicionar_conteudo(conteudo, nome)
        self.abrir_docker("simbologias")
        self.statusBar().showMessage(f"“{destino.stem}” guardado no banco de simbologias", 6000)
        return destino

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
            self.visualizacao_3d.vista.update()  # cor do papelão
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

    def _perguntar_arquivo_preso(self, caminho: str) -> str:
        """"tentar" | "outro" | "cancelar" — separado pra os testes responderem."""
        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Icon.Warning)
        caixa.setWindowTitle("Arquivo aberto em outro programa")
        caixa.setText(
            "O arquivo está aberto em outro programa (ex.: o leitor de PDF), que não deixa gravar por cima:"
            f"\n\n{caminho}\n\nFeche o arquivo nesse programa e clique em Tentar de novo."
        )
        tentar = caixa.addButton("Tentar de novo", QMessageBox.ButtonRole.AcceptRole)
        outro = caixa.addButton(f"Salvar como “{proximo_nome_livre(caminho).name}”", QMessageBox.ButtonRole.ActionRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(tentar)
        caixa.exec()
        if caixa.clickedButton() is tentar:
            return "tentar"
        if caixa.clickedButton() is outro:
            return "outro"
        return "cancelar"

    def _destino_livre(self, caminho: str) -> str | None:
        """O caminho pra gravar: o mesmo, se o arquivo não estiver aberto em
        outro programa; senão pergunta (tentar de novo / outro nome)."""
        while esta_preso(caminho):
            resposta = self._perguntar_arquivo_preso(caminho)
            if resposta == "outro":
                return str(proximo_nome_livre(caminho))
            if resposta != "tentar":
                return None
        return caminho

    def _exportar_svg(self) -> None:
        if not self._layout_pronto_para_exportar():
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar como SVG", self._sugestao_exportar("layout.svg", ".svg"), "SVG (*.svg)"
        )
        if caminho:
            configuracoes.definir_pasta_ultima("exportar", str(Path(caminho).parent))
        if not caminho:
            return
        caminho = self._destino_livre(caminho)
        if not caminho:
            return
        try:
            with self._cursor_espera():
                exportacao.exportar_svg(self.canvas.cena, self.canvas.layout_efetivo, caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
        else:
            self.statusBar().showMessage(f"Exportado: {caminho}", 6000)

    def _exportar_pdf(self) -> None:
        if not self._layout_pronto_para_exportar():
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar como PDF", self._sugestao_exportar("layout.pdf", ".pdf"), "PDF (*.pdf)"
        )
        if caminho:
            configuracoes.definir_pasta_ultima("exportar", str(Path(caminho).parent))
        if not caminho:
            return
        caminho = self._destino_livre(caminho)
        if not caminho:
            return
        try:
            with self._cursor_espera():
                exportacao.exportar_pdf(self.canvas.cena, self.canvas.layout_efetivo, caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
        else:
            self.statusBar().showMessage(f"Exportado: {caminho}", 6000)

    def _exportar_jpg(self) -> None:
        if not self._layout_pronto_para_exportar():
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar como JPG", self._sugestao_exportar("layout.jpg", ".jpg"), "JPEG (*.jpg)"
        )
        if caminho:
            configuracoes.definir_pasta_ultima("exportar", str(Path(caminho).parent))
        if not caminho:
            return
        caminho = self._destino_livre(caminho)
        if not caminho:
            return
        try:
            with self._cursor_espera():
                exportacao.exportar_jpg(self.canvas.cena, self.canvas.layout_efetivo, caminho)
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

    # ── Projeto (.autoline) ──────────────────────────────────────────
    @property
    def caminho_projeto(self) -> str | None:
        return self._caminho_projeto

    def _nome_projeto(self) -> str:
        return Path(self._caminho_projeto).stem if self._caminho_projeto else "Sem título"

    def projeto_modificado(self) -> bool:
        return projeto_arquivo.assinatura(self) != self._assinatura_salva

    def _atualizar_titulo(self) -> None:
        modificado = self.projeto_modificado()
        marca = "• " if modificado else ""
        self.setWindowTitle(f"{marca}{self._nome_projeto()} — Autoline")
        if hasattr(self, "barra_titulo"):
            self.barra_titulo.definir_projeto(self._nome_projeto(), modificado)
        self.visualizacao_3d.vista.nome_sugerido = self._nome_projeto() if self._caminho_projeto else "caixa"

    # Os testes desligam (não há quem responda a pergunta).
    perguntar_antes_de_descartar = True

    def _pode_descartar(self) -> bool:
        """Pergunta se salva antes de trocar/fechar o projeto. False = cancelou."""
        if not self.perguntar_antes_de_descartar or not self.projeto_modificado():
            return True
        resposta = QMessageBox.question(
            self,
            "Projeto alterado",
            f"Salvar as alterações em “{self._nome_projeto()}”?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if resposta == QMessageBox.StandardButton.Cancel:
            return False
        if resposta == QMessageBox.StandardButton.Save:
            return self.salvar_projeto()
        return True

    def salvar_projeto(self) -> bool:
        if not self._caminho_projeto:
            return self.salvar_projeto_como()
        return self._gravar_projeto(self._caminho_projeto)

    def salvar_projeto_como(self) -> bool:
        pasta = configuracoes.pasta_ultima("projetos")
        nome = f"{self._nome_projeto()}{projeto_arquivo.EXTENSAO}" if self._caminho_projeto else "caixa.autoline"
        sugestao = str(Path(pasta) / nome) if pasta else nome
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", sugestao, projeto_arquivo.FILTRO)
        if not caminho:
            return False
        return self._gravar_projeto(caminho)

    def _gravar_projeto(self, caminho: str) -> bool:
        try:
            with self._cursor_espera():
                destino = projeto_arquivo.salvar(self, caminho)
        except OSError as exc:
            QMessageBox.critical(self, "Salvar projeto", f"Não consegui salvar:\n{exc}")
            return False
        self._caminho_projeto = str(destino)
        self._assinatura_salva = projeto_arquivo.assinatura(self)
        configuracoes.definir_pasta_ultima("projetos", str(destino.parent))
        configuracoes.adicionar_projeto_recente(str(destino))
        self._atualizar_titulo()
        self.statusBar().showMessage(f"Projeto salvo: {destino}", 6000)
        return True

    def abrir_projeto(self, caminho: str | None = None) -> bool:
        if not self._pode_descartar():
            return False
        if caminho is None:
            caminho, _ = QFileDialog.getOpenFileName(
                self, "Abrir projeto", configuracoes.pasta_ultima("projetos"), projeto_arquivo.FILTRO
            )
            if not caminho:
                return False
        try:
            dados = projeto_arquivo.ler(caminho)
            with self._cursor_espera():
                avisos = projeto_arquivo.aplicar_na_janela(self, dados)
        except projeto_arquivo.ErroProjeto as exc:
            QMessageBox.warning(self, "Abrir projeto", str(exc))
            return False
        self._caminho_projeto = str(Path(caminho))
        self._assinatura_salva = projeto_arquivo.assinatura(self)
        configuracoes.definir_pasta_ultima("projetos", str(Path(caminho).parent))
        configuracoes.adicionar_projeto_recente(self._caminho_projeto)
        self._atualizar_titulo()
        if self.abas_tela.currentIndex() == 2:
            self._atualizar_arte_3d()
        if avisos:
            QMessageBox.information(self, "Abrir projeto", "\n".join(avisos))
        self.statusBar().showMessage(f"Projeto aberto: {caminho}", 6000)
        self.mostrar_trabalho()
        return True

    def novo_projeto(self) -> bool:
        if not self._pode_descartar():
            return False
        projeto_arquivo.aplicar_na_janela(self, self._estado_novo)
        self._caminho_projeto = None
        self._assinatura_salva = projeto_arquivo.assinatura(self)
        self._atualizar_titulo()
        return True

    def _montar_menu_recentes(self) -> None:
        self._menu_recentes.clear()
        recentes = [c for c in configuracoes.projetos_recentes() if Path(c).is_file()]
        if not recentes:
            self._menu_recentes.addAction("(nenhum)").setEnabled(False)
            return
        from PySide6.QtGui import QIcon, QPixmap

        for caminho in recentes:
            acao = self._menu_recentes.addAction(
                f"{Path(caminho).stem}   —   {Path(caminho).parent}", lambda c=caminho: self.abrir_projeto(c)
            )
            miniatura = projeto_arquivo.ler_miniatura(caminho)
            if miniatura is not None:
                acao.setIcon(QIcon(QPixmap.fromImage(miniatura)))
        self._menu_recentes.setStyleSheet("QMenu { icon-size: 48px; }")
        self._menu_recentes.addSeparator()
        self._menu_recentes.addAction("Ver todos com prévia…", self.abrir_galeria_recentes)

    def abrir_galeria_recentes(self, executar: bool = True):
        """Os projetos recentes em miniatura; dois cliques abre."""
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtWidgets import QListView, QListWidget, QListWidgetItem

        dialogo = QDialog(self)
        dialogo.setWindowTitle("Projetos recentes")
        dialogo.resize(980, 640)
        lista = QListWidget(dialogo)
        lista.setViewMode(QListView.ViewMode.IconMode)
        lista.setIconSize(QSize(260, 180))
        lista.setGridSize(QSize(290, 230))
        lista.setResizeMode(QListView.ResizeMode.Adjust)
        lista.setMovement(QListView.Movement.Static)
        lista.setWordWrap(True)
        for caminho in [c for c in configuracoes.projetos_recentes() if Path(c).is_file()]:
            miniatura = projeto_arquivo.ler_miniatura(caminho)
            icone = QIcon(QPixmap.fromImage(miniatura)) if miniatura is not None else QIcon()
            item = QListWidgetItem(icone, Path(caminho).stem)
            item.setToolTip(caminho)
            item.setData(Qt.ItemDataRole.UserRole, caminho)
            lista.addItem(item)

        def abrir_item(item) -> None:
            dialogo.accept()
            self.abrir_projeto(item.data(Qt.ItemDataRole.UserRole))

        lista.itemActivated.connect(abrir_item)
        layout = QVBoxLayout(dialogo)
        layout.addWidget(QLabel("Dois cliques abre o projeto."))
        layout.addWidget(lista, 1)
        if executar:
            dialogo.exec()
        return dialogo, lista

    def closeEvent(self, evento) -> None:  # noqa: N802
        if self._pode_descartar():
            projeto_arquivo.apagar_recuperacao()  # fechou direito: nada pra recuperar
            evento.accept()
        else:
            evento.ignore()

    def salvar_recuperacao(self) -> bool:
        """Guarda a cópia de recuperação se o projeto tem alteração não salva
        (sem alteração, apaga a que existir). Erro de disco não atrapalha."""
        try:
            if self.projeto_modificado():
                projeto_arquivo.salvar_recuperacao(self, self._caminho_projeto)
                return True
            projeto_arquivo.apagar_recuperacao()
        except OSError:
            pass
        return False

    def verificar_recuperacao(self, perguntar=None) -> bool:
        """Na abertura: se o Autoline fechou sem querer (sobrou a cópia de
        recuperação), oferece abrir o trabalho de onde parou. `perguntar`
        (testes) recebe o texto e devolve True/False."""
        copia = projeto_arquivo.recuperacao_pendente()
        if copia is None:
            return False
        try:
            dados = projeto_arquivo.ler(copia)
        except projeto_arquivo.ErroProjeto:
            projeto_arquivo.apagar_recuperacao()
            return False
        original = (dados.get("recuperacao") or {}).get("caminho_original")
        nome = Path(original).stem if original else "Sem título"
        texto = (
            f"O Autoline fechou sem salvar “{nome}”.\n\n"
            "Quer recuperar o trabalho de onde parou? (a última cópia automática, de até 2 minutos antes)"
        )
        if perguntar is None:
            resposta = QMessageBox.question(self, "Recuperar trabalho", texto) == QMessageBox.StandardButton.Yes
        else:
            resposta = perguntar(texto)
        if not resposta:
            projeto_arquivo.apagar_recuperacao()
            return False
        projeto_arquivo.aplicar_na_janela(self, dados)
        self._caminho_projeto = original if original and Path(original).exists() else None
        self._assinatura_salva = None  # recuperado = ainda não salvo
        self._atualizar_titulo()
        self.statusBar().showMessage("Trabalho recuperado — salve (Ctrl+S) pra não perder.", 10000)
        return True

    def _sugestao_exportar(self, nome_padrao: str, extensao: str) -> str:
        """Nome do projeto + pasta das imagens do layout (Configurações) ou a última usada."""
        pasta = configuracoes.pasta_imagens_layout() or configuracoes.pasta_ultima("exportar")
        nome = f"{self._nome_projeto()}{extensao}" if self._caminho_projeto else nome_padrao
        return str(Path(pasta) / nome) if pasta else nome

    def gerar_folha_aprovacao(self, caminho: str | None = None, dialogo=None, abrir: bool = True) -> Path | None:
        """Folha de aprovação em PDF (ver `folha_aprovacao.py`). `dialogo`
        (testes) recebe a janela já montada e devolve True pra seguir."""
        import datetime as _dt

        from .dialogo_folha_aprovacao import DialogoFolhaAprovacao
        from .folha_aprovacao import gerar_pdf, nome_do_arquivo, texto_medidas

        if not self._layout_pronto_para_exportar():
            return None
        medidas = self._obter_medidas()
        dados_antes = self._aprovacao
        criado = dados_antes.get("criado_em")
        janela = DialogoFolhaAprovacao(
            self,
            cliente=dados_antes.get("cliente", ""),
            referencia=dados_antes.get("referencia", ""),
            codigo=dados_antes.get("codigo", ""),
            medidas=texto_medidas(medidas.comprimento, medidas.largura, medidas.altura),  # desenho em 1:10
            tipo=NOME_EXIBICAO_TIPO_CAIXA.get(medidas.tipo, "").upper(),
            cores=self._cores_impressao_ativas(),
            criado_em=_dt.date.fromisoformat(criado) if criado else None,
            desenvolvido_por=configuracoes.desenvolvido_por(),
            logo=configuracoes.logo_folha_aprovacao(),
        )
        aceitou = dialogo(janela) if dialogo is not None else janela.exec() == QDialog.DialogCode.Accepted
        if not aceitou:
            return None
        dados = janela.dados()
        configuracoes.definir_desenvolvido_por(dados.desenvolvido_por)
        configuracoes.definir_logo_folha_aprovacao(janela.logo)
        if caminho is None:
            pasta = configuracoes.pasta_folhas_aprovacao() or configuracoes.pasta_ultima("aprovacao")
            sugestao = str(Path(pasta) / nome_do_arquivo(dados)) if pasta else nome_do_arquivo(dados)
            caminho, _ = QFileDialog.getSaveFileName(self, "Salvar folha de aprovação", sugestao, "PDF (*.pdf)")
            if not caminho:
                return None
        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"
        caminho = self._destino_livre(caminho)  # PDF anterior aberto no leitor
        if not caminho:
            return None
        try:
            with self._cursor_espera():
                imagem_3d = self._imagem_3d_montada() if janela.check_3d.isChecked() else None
                destino = gerar_pdf(
                    self.canvas.cena, self.canvas.layout_efetivo, dados, caminho, janela.logo or None, imagem_3d
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Folha de aprovação", f"Não consegui gerar o PDF:\n{exc}")
            return None
        configuracoes.definir_pasta_ultima("aprovacao", str(Path(caminho).parent))
        self._aprovacao = {
            "cliente": dados.cliente,
            "referencia": dados.referencia,
            "codigo": dados.codigo,
            "criado_em": dados.criado_em.isoformat() if dados.criado_em else None,
            "modificado_em": dados.modificado_em.isoformat() if dados.modificado_em else None,
        }
        if self._caminho_projeto:
            self._gravar_projeto(self._caminho_projeto)  # as datas ficam guardadas no projeto
        else:
            self._atualizar_titulo()
        self.statusBar().showMessage(f"Folha de aprovação salva: {destino}", 10000)
        if abrir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(destino)))
        return destino

    def _imagem_3d_montada(self):
        """A caixa montada, na vista 3/4 de sempre, com a arte, fundo branco
        e em alta resolução — pra folha de aprovação. A vista do usuário
        (giro, zoom, montagem) volta como estava."""
        vista = self.visualizacao_3d.vista
        self._atualizar_modelo_3d()
        self._atualizar_arte_3d()
        guardado = (vista._progresso, vista._yaw_usuario, vista._pitch_usuario, vista._zoom, QPointF(vista._pan), vista._giro_auto)
        tamanho = vista.size()
        try:
            if not vista.isVisible() or vista.width() < 600:
                vista.resize(1200, 820)
            vista._progresso = 1.0
            vista.vista_inicial()
            # Um pouco mais longe: a sombra embaixo cabe na vista (o recorte
            # da foto é justo, então a caixa sai do mesmo tamanho na folha).
            vista._zoom *= 0.85
            # 4000 px no lado maior da caixa: nítida na folha impressa (A4,
            # ~180 mm → mais de 500 dpi), qualquer que seja o formato da caixa.
            return vista.renderizar_imagem(fundo=QColor(255, 255, 255), lado_caixa_px=4000)
        finally:
            (vista._progresso, vista._yaw_usuario, vista._pitch_usuario, vista._zoom, vista._pan, vista._giro_auto) = guardado
            if vista.size() != tamanho:
                vista.resize(tamanho)
            vista.update()

    def _pasta_para(self, chave_config: str, chave_ultima: str, titulo: str, perguntar_pasta) -> str | None:
        """A pasta configurada; sem ela, pergunta (e passa a usar a escolhida)."""
        pasta = getattr(configuracoes, chave_config)() or configuracoes.pasta_ultima(chave_ultima)
        if pasta and Path(pasta).is_dir():
            return pasta
        pasta = perguntar_pasta(titulo)
        if not pasta:
            return None
        getattr(configuracoes, "definir_" + chave_config)(pasta)
        return pasta

    def salvar_e_exportar_tudo(self, perguntar_pasta=None, confirmar_substituir=None) -> list[Path]:
        """Um clique depois de alterar: salva o .autoline (na pasta do cliente),
        a imagem do layout (pasta das imagens) e a do 3D (pasta do 3D), todos
        com o nome do projeto. Pasta não configurada é perguntada uma vez e
        fica guardada. `perguntar_pasta`/`confirmar_substituir` são pros testes."""
        if not self._layout_pronto_para_exportar() or not self.salvar_projeto():
            return []
        if perguntar_pasta is None:
            def perguntar_pasta(titulo: str) -> str:
                return QFileDialog.getExistingDirectory(self, titulo)
        if confirmar_substituir is None:
            def confirmar_substituir(existentes: list[Path]) -> bool:
                lista = "\n".join(str(p) for p in existentes)
                return QMessageBox.question(
                    self, "Salvar e exportar tudo", f"Substituir as imagens que já existem?\n\n{lista}"
                ) == QMessageBox.StandardButton.Yes

        pasta_layout = self._pasta_para(
            "pasta_imagens_layout", "exportar", "Pasta das imagens do layout", perguntar_pasta
        )
        if pasta_layout is None:
            return []
        pasta_3d = self._pasta_para("pasta_imagens_3d", "imagem_3d", "Pasta das imagens do 3D", perguntar_pasta)
        if pasta_3d is None:
            return []
        nome = self._nome_projeto()
        imagem_layout = Path(pasta_layout) / f"{nome}.jpg"
        imagem_3d = Path(pasta_3d) / f"{nome} 3D.jpg"
        existentes = [p for p in (imagem_layout, imagem_3d) if p.exists()]
        if existentes and not confirmar_substituir(existentes):
            return []
        livres = [self._destino_livre(str(p)) for p in (imagem_layout, imagem_3d)]  # imagem aberta num visualizador
        if not all(livres):
            return []
        imagem_layout, imagem_3d = (Path(c) for c in livres)
        tela_antes = self.abas_tela.currentIndex()
        try:
            with self._cursor_espera():
                exportacao.exportar_jpg(self.canvas.cena, self.canvas.layout_efetivo, str(imagem_layout))
                if self.abas_tela.currentIndex() != 2:
                    self.abas_tela.setCurrentIndex(2)  # a foto sai da vista 3D como ela está
                    QApplication.processEvents()
                salvo_3d = self.visualizacao_3d.salvar_imagem(str(imagem_3d))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Salvar e exportar tudo", f"Não consegui exportar:\n{exc}")
            return []
        finally:
            if self.abas_tela.currentIndex() != tela_antes:
                self.abas_tela.setCurrentIndex(tela_antes)
        feitos = [Path(self._caminho_projeto), imagem_layout] + ([Path(salvo_3d)] if salvo_3d else [])
        self.statusBar().showMessage("Salvo: " + "  ·  ".join(str(p) for p in feitos), 12000)
        return feitos

    def _exportar_imagem_3d(self) -> None:
        """Foto da caixa em 3D na vista atual (vai pra aba 3D se precisar)."""
        if self.abas_tela.currentIndex() != 2:
            self.abas_tela.setCurrentIndex(2)
            QApplication.processEvents()
        caminho = self.visualizacao_3d.salvar_imagem()
        if caminho:
            self.statusBar().showMessage(f"Imagem do 3D salva em {caminho}", 8000)

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
                layout = self.canvas.layout_efetivo
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
        self._atualizar_tintas_status()
        self._paineis_atuais = calcular_paineis(medidas.tipo, layout.segmentos_impressora, layout.segmentos_riscador)
        self.canvas.definir_paineis(self._paineis_atuais)
        self._atualizar_modelo_3d()
        if self.abas_tela.currentIndex() == 2:
            self._atualizar_arte_3d()
        if not self.canvas.cena.selectedItems():
            self.painel_propriedades_mockup.definir_elemento(None)  # tamanho da chapa no estado "nada selecionado"

        self.linha_impressora.atualizar_valores_efetivos(layout.segmentos_impressora)
        self.linha_impressora.definir_total(layout.largura_total)
        self.linha_riscador.atualizar_valores_efetivos(
            layout.segmentos_riscador + [0.0] * (5 - len(layout.segmentos_riscador))
        )
        self.linha_riscador.definir_total(layout.altura_total)

        self.statusBar().showMessage(layout.descricao)
        if hasattr(self, "_timer_titulo"):
            self._timer_titulo.start()  # medidas/cores não passam pelo desfazer


class _PaginaInspetor:
    """Uma página do inspetor com a cara de um QDockWidget (`isVisible`,
    `show`, `hide`, `raise_`, `windowTitle`) — quem abria/fechava os
    dockers continua funcionando igual."""

    def __init__(self, janela: "JanelaPrincipal", widget: QWidget, titulo: str, no_menu: bool) -> None:
        self._janela = janela
        self._widget = widget
        self._titulo = titulo
        self._no_menu = no_menu

    def _indice(self) -> int:
        return self._janela.abas_inspetor.indexOf(self._widget)

    def windowTitle(self) -> str:  # noqa: N802
        return self._titulo

    def widget(self) -> QWidget:
        return self._widget

    def isVisible(self) -> bool:  # noqa: N802
        abas = self._janela.abas_inspetor
        return self._janela.dock_inspetor.isVisible() and abas.currentIndex() == self._indice()

    def show(self) -> None:
        abas = self._janela.abas_inspetor
        if self._no_menu:  # só uma do "···" à mostra por vez
            for pagina in self._janela._docks.values():
                if pagina._no_menu and pagina is not self:
                    abas.setTabVisible(pagina._indice(), False)
            abas.setTabVisible(self._indice(), True)
        abas.setCurrentIndex(self._indice())
        self._janela.dock_inspetor.show()

    def raise_(self) -> None:
        self.show()

    def hide(self) -> None:
        if not self.isVisible():
            return
        abas = self._janela.abas_inspetor
        if self._no_menu:
            abas.setTabVisible(self._indice(), False)
        abas.setCurrentIndex(abas.indexOf(self._janela._docks["propriedades"].widget()))
