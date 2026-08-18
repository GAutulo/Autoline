"""Janela principal do Gerador de Layout de Caixas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..layout_service import ServicoLayoutCaixa
from ..models import CorImpressao, MedidasCaixa, NOME_EXIBICAO_TIPO_CAIXA, TipoCaixa
from . import corel_bridge, exportacao
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
        self.setWindowTitle("Gerador de Layout de Caixas")
        self.resize(1200, 820)

        self._servico = ServicoLayoutCaixa()
        self._checks_cor: dict[str, tuple[QCheckBox, tuple[int, int, int]]] = {}
        self._corel_app = None

        self._montar_ui()
        self._montar_menu()
        self._conectar_sinais()
        self._ao_trocar_tipo()

    # ── Montagem da UI ──────────────────────────────────────────────
    def _montar_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout_raiz = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout_raiz.addWidget(splitter)

        splitter.addWidget(self._montar_painel_esquerdo())
        splitter.addWidget(self._montar_painel_direito())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        # Painel esquerdo só com tipo/medidas/cores agora — os trechos
        # (Impressora/Riscador) ficam embaixo da pré-visualização, à
        # direita, com bem mais espaço pra respirar.
        splitter.setSizes([260, 940])

    def _montar_painel_esquerdo(self) -> QWidget:
        painel = QWidget()
        painel.setMaximumWidth(300)
        vbox = QVBoxLayout(painel)

        grupo_tipo = QGroupBox("Tipo de caixa")
        form_tipo = QFormLayout(grupo_tipo)
        self.combo_tipo = QComboBox()
        for tipo in TipoCaixa:
            self.combo_tipo.addItem(NOME_EXIBICAO_TIPO_CAIXA[tipo], tipo)
        self.combo_tipo.setCurrentIndex(list(TipoCaixa).index(TipoCaixa.MALETA_NORMAL))
        form_tipo.addRow(self.combo_tipo)
        vbox.addWidget(grupo_tipo)

        grupo_medidas = QGroupBox("Medidas C × L × A (mm)")
        form_medidas = QFormLayout(grupo_medidas)
        self.spin_comprimento = self._criar_spin(300)
        self.spin_largura = self._criar_spin(200)
        self.spin_altura = self._criar_spin(150)
        form_medidas.addRow("Comprimento (C):", self.spin_comprimento)
        form_medidas.addRow("Largura (L):", self.spin_largura)
        form_medidas.addRow("Altura (A):", self.spin_altura)
        vbox.addWidget(grupo_medidas)

        grupo_cores = QGroupBox("Legenda de cores")
        grid_cores = QGridLayout(grupo_cores)
        for i, (nome, rgb) in enumerate(_CORES_DISPONIVEIS):
            chk = QCheckBox(nome)
            self._checks_cor[nome] = (chk, rgb)
            grid_cores.addWidget(chk, i // 2, i % 2)
        self._checks_cor["Preto"][0].setChecked(True)
        vbox.addWidget(grupo_cores)

        vbox.addStretch(1)
        return painel

    def _montar_painel_direito(self) -> QWidget:
        painel = QWidget()
        vbox = QVBoxLayout(painel)
        vbox.setContentsMargins(0, 0, 0, 0)

        barra = QHBoxLayout()
        barra.addWidget(QLabel("PRÉ-VISUALIZAÇÃO"))
        barra.addStretch(1)
        self.label_zoom = QLabel("100%")
        botao_ajustar = QPushButton("Ajustar à tela")
        botao_ajustar.clicked.connect(lambda: self.canvas.ajustar_a_tela())
        barra.addWidget(self.label_zoom)
        barra.addWidget(botao_ajustar)
        vbox.addLayout(barra)

        self.painel_legenda_cores = PainelLegendaCores()
        vbox.addWidget(self.painel_legenda_cores)

        self.canvas = PreviewCanvas()
        self.canvas.zoom_alterado.connect(
            lambda z: self.label_zoom.setText(f"{z * 100:.0f}%")
        )
        vbox.addWidget(self.canvas, 1)

        # Trechos (Impressora/Riscador) embaixo da pré-visualização — mais
        # largura disponível aqui do que na barra lateral esquerda.
        grupo_trechos = QGroupBox("Medidas geradas / ajustáveis")
        vbox_trechos = QVBoxLayout(grupo_trechos)
        self.linha_impressora = LinhaTrechos("Impressora", _ROTULOS_IMPRESSORA_MALETA)
        self.linha_riscador = LinhaTrechos("Riscador", _ROTULOS_RISCADOR_MALETA)
        vbox_trechos.addWidget(self.linha_impressora)
        vbox_trechos.addWidget(self.linha_riscador)
        vbox.addWidget(grupo_trechos)

        return painel

    def _conectar_sinais(self) -> None:
        """Conecta todos os sinais de UI depois que toda a janela já existe,
        evitando disparar _recalcular() com widgets ainda não criados."""
        self.combo_tipo.currentIndexChanged.connect(self._ao_trocar_tipo)
        for chk, _rgb in self._checks_cor.values():
            chk.stateChanged.connect(self._recalcular)
        for spin in (self.spin_comprimento, self.spin_largura, self.spin_altura):
            spin.valueChanged.connect(self._recalcular)
        self.linha_impressora.valor_alterado.connect(self._recalcular)
        self.linha_riscador.valor_alterado.connect(self._recalcular)

    def _criar_spin(self, valor_padrao: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 100000)
        spin.setDecimals(1)
        spin.setSuffix(" mm")
        spin.setValue(valor_padrao)
        return spin

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

    def _obter_medidas(self) -> MedidasCaixa:
        cores = [
            CorImpressao(nome=nome.upper(), r=rgb[0], g=rgb[1], b=rgb[2])
            for nome, (chk, rgb) in self._checks_cor.items()
            if chk.isChecked()
        ]
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
            exportacao.exportar_svg(self.canvas.cena, self.canvas.layout_atual.cores_legenda, caminho)
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
            exportacao.exportar_pdf(self.canvas.cena, self.canvas.layout_atual.cores_legenda, caminho)
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
            exportacao.exportar_jpg(self.canvas.cena, self.canvas.layout_atual.cores_legenda, caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
        else:
            self.statusBar().showMessage(f"Exportado: {caminho}", 6000)

    def _conectar_corel(self) -> None:
        try:
            self._corel_app = corel_bridge.conectar()
        except corel_bridge.CorelIndisponivel as exc:
            QMessageBox.critical(self, "Erro ao conectar", str(exc))
        else:
            self.statusBar().showMessage("Conectado ao CorelDRAW", 6000)

    def _exportar_corel(self) -> None:
        if not self._layout_pronto_para_exportar():
            return
        try:
            if self._corel_app is None:
                self._corel_app = corel_bridge.conectar()
            corel_bridge.desenhar_layout(self._corel_app, self.canvas.layout_atual)
        except corel_bridge.CorelIndisponivel as exc:
            self._corel_app = None
            QMessageBox.critical(self, "Erro ao conectar", str(exc))
        except Exception as exc:  # noqa: BLE001
            self._corel_app = None
            QMessageBox.critical(self, "Erro ao desenhar no CorelDRAW", str(exc))
        else:
            self.statusBar().showMessage("Layout enviado para o CorelDRAW", 6000)

    def _recalcular(self) -> None:
        medidas = self._obter_medidas()
        layout = self._servico.calcular(medidas)
        self.canvas.definir_layout(layout)
        self.painel_legenda_cores.definir_cores(layout.cores_legenda)

        self.linha_impressora.atualizar_valores_efetivos(layout.segmentos_impressora)
        self.linha_impressora.definir_total(layout.largura_total)
        self.linha_riscador.atualizar_valores_efetivos(
            layout.segmentos_riscador + [0.0] * (5 - len(layout.segmentos_riscador))
        )
        self.linha_riscador.definir_total(layout.altura_total)

        self.statusBar().showMessage(layout.descricao)
