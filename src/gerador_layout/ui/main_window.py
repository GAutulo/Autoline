"""Janela principal do Gerador de Layout de Caixas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..layout_service import ServicoLayoutCaixa
from ..models import CorImpressao, MedidasCaixa, NOME_EXIBICAO_TIPO_CAIXA, TipoCaixa
from .preview_canvas import PreviewCanvas

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


class JanelaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Gerador de Layout de Caixas")
        self.resize(1100, 760)

        self._servico = ServicoLayoutCaixa()
        self._checks_cor: dict[str, tuple[QCheckBox, tuple[int, int, int]]] = {}

        self._montar_ui()
        self._conectar_sinais()
        self._recalcular()

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
        splitter.setSizes([360, 740])

    def _montar_painel_esquerdo(self) -> QWidget:
        painel = QWidget()
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

        grupo_trechos = QGroupBox("Medidas geradas / ajustáveis")
        form_trechos = QFormLayout(grupo_trechos)
        self.spin_imp_aba = self._criar_spin(4, opcional=True)
        self.spin_imp_l1 = self._criar_spin(0, opcional=True)
        self.spin_imp_c1 = self._criar_spin(0, opcional=True)
        self.spin_imp_l2 = self._criar_spin(0, opcional=True)
        self.spin_imp_c2 = self._criar_spin(0, opcional=True)
        self.spin_ris_sup = self._criar_spin(0, opcional=True)
        self.spin_ris_centro = self._criar_spin(0, opcional=True)
        self.spin_ris_inf = self._criar_spin(0, opcional=True)
        form_trechos.addRow("Impressora — aba:", self.spin_imp_aba)
        form_trechos.addRow("Impressora — L1:", self.spin_imp_l1)
        form_trechos.addRow("Impressora — C1:", self.spin_imp_c1)
        form_trechos.addRow("Impressora — L2:", self.spin_imp_l2)
        form_trechos.addRow("Impressora — C2:", self.spin_imp_c2)
        form_trechos.addRow("Riscador — superior:", self.spin_ris_sup)
        form_trechos.addRow("Riscador — centro:", self.spin_ris_centro)
        form_trechos.addRow("Riscador — inferior:", self.spin_ris_inf)
        vbox.addWidget(grupo_trechos)

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

        self.canvas = PreviewCanvas()
        self.canvas.zoom_alterado.connect(
            lambda z: self.label_zoom.setText(f"{z * 100:.0f}%")
        )
        vbox.addWidget(self.canvas, 1)

        self.label_info = QLabel("Dimensões serão exibidas aqui...")
        vbox.addWidget(self.label_info)

        return painel

    def _conectar_sinais(self) -> None:
        """Conecta todos os sinais de UI depois que toda a janela já existe,
        evitando disparar _recalcular() com widgets ainda não criados."""
        self.combo_tipo.currentIndexChanged.connect(self._recalcular)
        for chk, _rgb in self._checks_cor.values():
            chk.stateChanged.connect(self._recalcular)
        for spin in (
            self.spin_comprimento,
            self.spin_largura,
            self.spin_altura,
            self.spin_imp_aba,
            self.spin_imp_l1,
            self.spin_imp_c1,
            self.spin_imp_l2,
            self.spin_imp_c2,
            self.spin_ris_sup,
            self.spin_ris_centro,
            self.spin_ris_inf,
        ):
            spin.valueChanged.connect(self._recalcular)

    def _criar_spin(self, valor_padrao: float, *, opcional: bool = False) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 100000)
        spin.setDecimals(1)
        spin.setSuffix(" mm")
        spin.setValue(valor_padrao)
        if opcional:
            spin.setSpecialValueText("(automático)")
        return spin

    # ── Lógica ──────────────────────────────────────────────────────
    def _obter_medidas(self) -> MedidasCaixa:
        cores = [
            CorImpressao(nome=nome.upper(), r=rgb[0], g=rgb[1], b=rgb[2])
            for nome, (chk, rgb) in self._checks_cor.items()
            if chk.isChecked()
        ]
        return MedidasCaixa(
            tipo=self.combo_tipo.currentData(),
            comprimento=self.spin_comprimento.value(),
            largura=self.spin_largura.value(),
            altura=self.spin_altura.value(),
            impressora_aba=self.spin_imp_aba.value(),
            impressora_largura_1=self.spin_imp_l1.value(),
            impressora_comprimento_1=self.spin_imp_c1.value(),
            impressora_largura_2=self.spin_imp_l2.value(),
            impressora_comprimento_2=self.spin_imp_c2.value(),
            riscador_superior=self.spin_ris_sup.value(),
            riscador_centro=self.spin_ris_centro.value(),
            riscador_inferior=self.spin_ris_inf.value(),
            cores_legenda=cores,
        )

    def _recalcular(self) -> None:
        medidas = self._obter_medidas()
        layout = self._servico.calcular(medidas)
        self.canvas.definir_layout(layout)
        self.label_info.setText(
            f"Gerado: {layout.largura_total:.1f} × {layout.altura_total:.1f} mm "
            f"({len(layout.linhas)} segmentos) — {layout.descricao}"
        )
