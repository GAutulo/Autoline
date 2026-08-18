"""Tela de Configurações — tema, DPI de exportação JPG, traço do vinco e
tamanho da legenda de cores. Tudo persistido via `configuracoes.py`.

Os valores de traço/legenda são lidos ao vivo por `exportacao.py` e
`corel_bridge.py` (sem cache) — mudam já na próxima exportação, sem
precisar reiniciar. O tema é a única exceção (ver `estilo.py`)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from . import configuracoes

_ROTULO_TEMA = {
    configuracoes.TEMA_CLARO: "Claro (atual)",
    configuracoes.TEMA_ESCURO: "Escuro",
}


class DialogoConfiguracoes(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(380)

        vbox = QVBoxLayout(self)

        grupo_aparencia = QGroupBox("Aparência")
        form_aparencia = QFormLayout(grupo_aparencia)
        self.combo_tema = QComboBox()
        for valor, rotulo in _ROTULO_TEMA.items():
            self.combo_tema.addItem(rotulo, valor)
        indice_atual = self.combo_tema.findData(configuracoes.tema())
        self.combo_tema.setCurrentIndex(max(0, indice_atual))
        form_aparencia.addRow("Tema:", self.combo_tema)
        aviso_tema = QLabel("Trocar o tema exige reiniciar o app pra valer.")
        aviso_tema.setWordWrap(True)
        aviso_tema.setObjectName("legendaMuted")
        form_aparencia.addRow(aviso_tema)
        vbox.addWidget(grupo_aparencia)

        grupo_exportacao = QGroupBox("Exportação")
        form_exportacao = QFormLayout(grupo_exportacao)
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 1200)
        self.spin_dpi.setSuffix(" dpi")
        self.spin_dpi.setValue(configuracoes.dpi_exportacao_jpg())
        form_exportacao.addRow("Resolução do JPG:", self.spin_dpi)
        vbox.addWidget(grupo_exportacao)

        grupo_vinco = QGroupBox("Traço do vinco")
        form_vinco = QFormLayout(grupo_vinco)
        traco_mm, espaco_mm = configuracoes.traco_vinco_mm()
        self.spin_traco = self._criar_spin_mm(traco_mm)
        self.spin_espaco = self._criar_spin_mm(espaco_mm)
        form_vinco.addRow("Comprimento do traço:", self.spin_traco)
        form_vinco.addRow("Comprimento do espaço:", self.spin_espaco)
        vbox.addWidget(grupo_vinco)

        grupo_legenda = QGroupBox("Legenda de cores")
        form_legenda = QFormLayout(grupo_legenda)
        self.spin_altura_legenda = self._criar_spin_mm(configuracoes.altura_legenda_mm())
        form_legenda.addRow("Altura do texto/bolinha:", self.spin_altura_legenda)
        vbox.addWidget(grupo_legenda)

        # Qt não localiza os textos padrão pro português nesta instalação
        # (saem "OK"/"Cancel"/"Restore Defaults" em inglês) — define o
        # texto de cada botão explicitamente pra ficar consistente com o
        # resto do app.
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.RestoreDefaults
            | QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText("Restaurar padrões")
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._salvar_e_fechar)
        botoes.rejected.connect(self.reject)
        botoes.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restaurar_padroes)
        vbox.addWidget(botoes)

        self.tema_alterado = False

    @staticmethod
    def _criar_spin_mm(valor: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.1, 50.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.1)
        spin.setSuffix(" mm")
        spin.setValue(valor)
        return spin

    def _restaurar_padroes(self) -> None:
        configuracoes.restaurar_padroes()
        self.spin_dpi.setValue(configuracoes.dpi_exportacao_jpg())
        traco_mm, espaco_mm = configuracoes.traco_vinco_mm()
        self.spin_traco.setValue(traco_mm)
        self.spin_espaco.setValue(espaco_mm)
        self.spin_altura_legenda.setValue(configuracoes.altura_legenda_mm())
        # Tema não tem "padrão" salvo em restaurar_padroes (é intencional
        # que o usuário não perca o tema escolhido sem querer) — só reseta
        # os números.

    def _salvar_e_fechar(self) -> None:
        tema_escolhido = self.combo_tema.currentData()
        self.tema_alterado = tema_escolhido != configuracoes.tema()
        configuracoes.definir_tema(tema_escolhido)
        configuracoes.definir_dpi_exportacao_jpg(self.spin_dpi.value())
        configuracoes.definir_traco_vinco_mm(self.spin_traco.value(), self.spin_espaco.value())
        configuracoes.definir_altura_legenda_mm(self.spin_altura_legenda.value())
        self.accept()
