"""Tela de Configurações — tema, DPI de exportação JPG, traço do vinco,
tamanho da legenda de cores, e os parâmetros de ferramenta do modo Layout
(encaixe, grade, mover fino pela seta, duplicar, fonte padrão de texto).
Tudo persistido via `configuracoes.py`.

Todo valor numérico/combo aqui é lido ao vivo no ponto de uso (ver
`exportacao.py`/`corel_bridge.py` pro traço/legenda, `preview_canvas.py`
pros parâmetros de ferramenta) — sem cache, então muda já na próxima vez
que a ferramenta for usada, sem precisar reiniciar. O tema é a única
exceção (ver `estilo.py`)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import configuracoes
from .painel_propriedades_mockup import _FONTES_DISPONIVEIS as _FONTES_TEXTO

_ROTULO_TEMA = {
    configuracoes.TEMA_CLARO: "Claro (atual)",
    configuracoes.TEMA_ESCURO: "Escuro",
}


class DialogoConfiguracoes(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(440)
        # Conteúdo cresceu bastante com a aba "Ferramentas" — mais alto
        # que os ~768px úteis de um notebook comum (mesma preocupação já
        # documentada em `main.py::main`) sem rolagem. Um tamanho inicial
        # que cabe de sobra em qualquer tela, com `QScrollArea` pra quem
        # tiver uma ainda menor — os botões (OK/Cancelar) ficam FORA da
        # área rolável, sempre visíveis.
        self.resize(460, 640)

        vbox = QVBoxLayout(self)
        area_rolavel = QScrollArea()
        area_rolavel.setWidgetResizable(True)
        area_rolavel.setFrameShape(QScrollArea.Shape.NoFrame)
        vbox.addWidget(area_rolavel, 1)

        conteudo = QWidget()
        area_rolavel.setWidget(conteudo)
        vbox_conteudo = QVBoxLayout(conteudo)

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
        vbox_conteudo.addWidget(grupo_aparencia)

        grupo_exportacao = QGroupBox("Exportação")
        form_exportacao = QFormLayout(grupo_exportacao)
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 1200)
        self.spin_dpi.setSuffix(" dpi")
        self.spin_dpi.setValue(configuracoes.dpi_exportacao_jpg())
        form_exportacao.addRow("Resolução do JPG:", self.spin_dpi)
        vbox_conteudo.addWidget(grupo_exportacao)

        grupo_vinco = QGroupBox("Traço do vinco")
        form_vinco = QFormLayout(grupo_vinco)
        traco_mm, espaco_mm = configuracoes.traco_vinco_mm()
        self.spin_traco = self._criar_spin_mm(traco_mm)
        self.spin_espaco = self._criar_spin_mm(espaco_mm)
        form_vinco.addRow("Comprimento do traço:", self.spin_traco)
        form_vinco.addRow("Comprimento do espaço:", self.spin_espaco)
        vbox_conteudo.addWidget(grupo_vinco)

        grupo_legenda = QGroupBox("Legenda de cores")
        form_legenda = QFormLayout(grupo_legenda)
        self.spin_altura_legenda = self._criar_spin_mm(configuracoes.altura_legenda_mm())
        form_legenda.addRow("Altura do texto/bolinha:", self.spin_altura_legenda)
        vbox_conteudo.addWidget(grupo_legenda)

        # Parâmetros de ferramenta do modo Layout — eram tudo constante
        # fixa no código até virarem preferência (ver `configuracoes.py`).
        # Lidos ao vivo no ponto de uso, então valem já na próxima vez que
        # a ferramenta for usada, sem precisar reiniciar (só o tema
        # precisa — ver aviso lá em cima).
        grupo_ferramentas = QGroupBox("Ferramentas (modo Layout)")
        form_ferramentas = QFormLayout(grupo_ferramentas)
        form_ferramentas.setVerticalSpacing(10)

        self.check_snap_padrao = QCheckBox("Encaixe (snap) já começa ligado")
        self.check_snap_padrao.setChecked(configuracoes.snap_ativo_padrao())
        form_ferramentas.addRow(self.check_snap_padrao)

        self.spin_limiar_snap = self._criar_spin_mm(configuracoes.limiar_snap_mm())
        form_ferramentas.addRow("Distância pra grudar no encaixe:", self.spin_limiar_snap)

        self.spin_passo_grade = self._criar_spin_mm(configuracoes.passo_grade_mm())
        form_ferramentas.addRow("Espaçamento da grade:", self.spin_passo_grade)

        passo_nudge, passo_nudge_shift = configuracoes.passo_nudge_mm()
        self.spin_passo_nudge = self._criar_spin_mm(passo_nudge)
        form_ferramentas.addRow("Mover fino pela seta do teclado:", self.spin_passo_nudge)
        self.spin_passo_nudge_shift = self._criar_spin_mm(passo_nudge_shift)
        form_ferramentas.addRow("Mover fino com Shift + seta:", self.spin_passo_nudge_shift)

        self.spin_passo_duplicar = self._criar_spin_mm(configuracoes.passo_duplicar_mm())
        form_ferramentas.addRow("Deslocamento ao duplicar (Ctrl+D):", self.spin_passo_duplicar)

        self.combo_fonte_texto = QComboBox()
        self.combo_fonte_texto.addItems(_FONTES_TEXTO)
        fonte_atual = configuracoes.fonte_padrao_texto()
        if fonte_atual in _FONTES_TEXTO:
            self.combo_fonte_texto.setCurrentText(fonte_atual)
        form_ferramentas.addRow("Fonte padrão de texto novo:", self.combo_fonte_texto)

        self.spin_altura_letra = self._criar_spin_mm(configuracoes.altura_letra_padrao_mm())
        self.spin_altura_letra.setToolTip("Altura da maiúscula de texto e checklist novos (padrão da máquina: 2 mm)")
        form_ferramentas.addRow("Altura da letra de texto novo:", self.spin_altura_letra)
        self.spin_largura_letra = QDoubleSpinBox()
        self.spin_largura_letra.setRange(20.0, 200.0)
        self.spin_largura_letra.setDecimals(1)
        self.spin_largura_letra.setSuffix(" %")
        self.spin_largura_letra.setValue(configuracoes.largura_letra_padrao() * 100)
        self.spin_largura_letra.setToolTip("Largura das letras em relação à normal da fonte (padrão da máquina: 66,7%, a Arial Black meio esticada)")
        form_ferramentas.addRow("Largura das letras de texto novo:", self.spin_largura_letra)

        vbox_conteudo.addWidget(grupo_ferramentas)

        grupo_pastas = QGroupBox("Arquivos")
        form_pastas = QFormLayout(grupo_pastas)
        form_pastas.setVerticalSpacing(10)
        self.campo_pasta_imagens = self._campo_pasta(configuracoes.pasta_imagens_layout())
        form_pastas.addRow("Pasta das imagens do layout:", self.campo_pasta_imagens)
        self.campo_pasta_3d = self._campo_pasta(configuracoes.pasta_imagens_3d())
        form_pastas.addRow("Pasta das imagens do 3D:", self.campo_pasta_3d)
        botao_associar = QPushButton("Abrir .autoline com dois cliques e mostrar a prévia no Explorer")
        botao_associar.setToolTip(
            "Faz o Windows abrir os arquivos .autoline no Autoline e mostrar a prévia do projeto no ícone "
            "(só pro seu usuário). Funciona no Autoline.exe. Projeto antigo ganha prévia ao salvar de novo."
        )
        botao_associar.clicked.connect(self._associar_arquivos)
        form_pastas.addRow(botao_associar)
        vbox_conteudo.addWidget(grupo_pastas)
        vbox_conteudo.addStretch(1)

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

    def _campo_pasta(self, valor: str) -> QWidget:
        linha = QWidget()
        lay = QHBoxLayout(linha)
        lay.setContentsMargins(0, 0, 0, 0)
        campo = QLineEdit(valor)
        campo.setPlaceholderText("a última usada")
        botao = QPushButton("…")
        botao.setFixedWidth(28)
        botao.setToolTip("Escolher a pasta")

        def escolher() -> None:
            pasta = QFileDialog.getExistingDirectory(self, "Escolher pasta", campo.text())
            if pasta:
                campo.setText(pasta.replace("/", "\\"))

        botao.clicked.connect(escolher)
        lay.addWidget(campo, 1)
        lay.addWidget(botao)
        linha.campo = campo
        return linha

    def _associar_arquivos(self) -> None:
        from . import associacao_arquivo

        try:
            associacao_arquivo.associar()
        except associacao_arquivo.ErroAssociacao as exc:
            QMessageBox.information(self, "Abrir com dois cliques", str(exc))
        else:
            QMessageBox.information(
                self, "Abrir com dois cliques",
                "Pronto: os .autoline abrem no Autoline com dois cliques e mostram a prévia no Explorer "
                "(projetos antigos ganham a prévia quando forem salvos de novo).",
            )

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
        self.check_snap_padrao.setChecked(configuracoes.snap_ativo_padrao())
        self.spin_limiar_snap.setValue(configuracoes.limiar_snap_mm())
        self.spin_passo_grade.setValue(configuracoes.passo_grade_mm())
        passo_nudge, passo_nudge_shift = configuracoes.passo_nudge_mm()
        self.spin_passo_nudge.setValue(passo_nudge)
        self.spin_passo_nudge_shift.setValue(passo_nudge_shift)
        self.spin_passo_duplicar.setValue(configuracoes.passo_duplicar_mm())
        self.combo_fonte_texto.setCurrentText(configuracoes.fonte_padrao_texto())
        self.spin_altura_letra.setValue(configuracoes.altura_letra_padrao_mm())
        self.spin_largura_letra.setValue(configuracoes.largura_letra_padrao() * 100)
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
        configuracoes.definir_snap_ativo_padrao(self.check_snap_padrao.isChecked())
        configuracoes.definir_limiar_snap_mm(self.spin_limiar_snap.value())
        configuracoes.definir_passo_grade_mm(self.spin_passo_grade.value())
        configuracoes.definir_passo_nudge_mm(self.spin_passo_nudge.value(), self.spin_passo_nudge_shift.value())
        configuracoes.definir_passo_duplicar_mm(self.spin_passo_duplicar.value())
        configuracoes.definir_fonte_padrao_texto(self.combo_fonte_texto.currentText())
        configuracoes.definir_pasta_imagens_layout(self.campo_pasta_imagens.campo.text().strip())
        configuracoes.definir_pasta_imagens_3d(self.campo_pasta_3d.campo.text().strip())
        configuracoes.definir_altura_letra_padrao_mm(self.spin_altura_letra.value())
        configuracoes.definir_largura_letra_padrao(self.spin_largura_letra.value() / 100)
        self.accept()
