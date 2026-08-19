"""Painel de propriedades do elemento de mockup selecionado — aparece
como um dock lateral (ver `_montar_dock_mockup` em main_window.py) e
reconstrói seus campos conforme o tipo do elemento selecionado no
canvas (texto, forma, checklist...). Fica vazio quando não há seleção
ou há mais de um elemento selecionado — editar propriedade de vários de
uma vez não é um caso coberto ainda.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import CorImpressao
from .mockup_checklist import ElementoChecklistCores
from .mockup_formas import ElementoLinha, ElementoRetangulo
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_texto import ElementoTexto

_FONTES_DISPONIVEIS = ["Arial", "Arial Black", "Verdana", "Times New Roman", "Impact"]

_NOME_TIPO: dict[type, str] = {
    ElementoTexto: "Texto",
    ElementoRetangulo: "Retângulo",
    ElementoLinha: "Linha",
    ElementoImagem: "Imagem",
    ElementoLogoVetorial: "Logotipo vetorial",
    ElementoChecklistCores: "Checklist de cores",
    GrupoMockup: "Grupo",
}


class PainelPropriedadesMockup(QWidget):
    def __init__(self, obter_tintas_disponiveis: Callable[[], list[CorImpressao]], parent=None) -> None:
        super().__init__(parent)
        self._obter_tintas = obter_tintas_disponiveis
        self._elemento: ElementoMockup | None = None

        # Callbacks ligados de fora (main_window.py) — este painel não
        # sabe mexer na cena/canvas, só nas propriedades do próprio
        # elemento, então ações que afetam a cena (remover, reabrir o
        # diálogo de separação de cor) sobem por aqui.
        self.remover_solicitado: Callable[[], None] | None = None
        self.remapear_logo_solicitado: Callable[[ElementoLogoVetorial], None] | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(10, 10, 10, 10)

        self._titulo = QLabel("Nada selecionado")
        self._titulo.setStyleSheet("font-weight: 700; font-size: 14px;")
        raiz.addWidget(self._titulo)

        self._form = QFormLayout()
        self._form.setVerticalSpacing(8)
        raiz.addLayout(self._form)
        raiz.addStretch(1)

        self._botao_remover = QPushButton("Remover elemento")
        self._botao_remover.setVisible(False)
        self._botao_remover.clicked.connect(lambda: self.remover_solicitado and self.remover_solicitado())
        raiz.addWidget(self._botao_remover)

    # ── API pública ─────────────────────────────────────────────────
    def definir_elemento(self, elemento: ElementoMockup | None) -> None:
        self._elemento = elemento
        self._limpar_form()

        if elemento is None:
            self._titulo.setText("Nada selecionado")
            self._botao_remover.setVisible(False)
            return

        self._titulo.setText(_NOME_TIPO.get(type(elemento), "Elemento"))
        self._botao_remover.setVisible(True)

        if isinstance(elemento, ElementoTexto):
            self._montar_campos_texto(elemento)
        elif isinstance(elemento, ElementoChecklistCores):
            self._montar_campos_checklist(elemento)
        elif isinstance(elemento, ElementoRetangulo):
            self._montar_campos_retangulo(elemento)
        elif isinstance(elemento, ElementoLinha):
            self._montar_campos_linha(elemento)
        elif isinstance(elemento, ElementoLogoVetorial):
            self._montar_campos_logo(elemento)
        elif isinstance(elemento, ElementoImagem):
            self._form.addRow(QLabel(elemento.caminho_arquivo.rsplit("\\", 1)[-1]))

    # ── Construção dos campos por tipo ────────────────────────────────
    def _limpar_form(self) -> None:
        while self._form.rowCount():
            self._form.removeRow(0)

    def _combo_cor(self, cor_atual: CorImpressao, ao_mudar: Callable[[CorImpressao], None]) -> QComboBox:
        combo = QComboBox()
        indice_atual = 0
        for i, tinta in enumerate(self._obter_tintas()):
            combo.addItem(tinta.nome, tinta)
            if tinta.nome == cor_atual.nome:
                indice_atual = i
        combo.setCurrentIndex(indice_atual)
        combo.currentIndexChanged.connect(lambda _i: ao_mudar(combo.currentData()))
        return combo

    def _linha_cor_tinta(self, cor_atual: CorImpressao, ao_mudar: Callable[[CorImpressao], None]) -> None:
        if self._obter_tintas():
            self._form.addRow("Cor de tinta:", self._combo_cor(cor_atual, ao_mudar))
        else:
            aviso = QLabel("Marque uma cor na legenda pra poder escolher aqui.")
            aviso.setWordWrap(True)
            self._form.addRow(aviso)

    def _campo_espessura_traco(self, valor_atual: float, ao_mudar: Callable[[float], None]) -> None:
        spin = QDoubleSpinBox()
        spin.setRange(0.05, 20.0)
        spin.setDecimals(2)
        spin.setSuffix(" mm")
        spin.setValue(valor_atual)
        spin.valueChanged.connect(ao_mudar)
        self._form.addRow("Espessura do traço:", spin)

    def _montar_campos_texto(self, el: ElementoTexto) -> None:
        campo_texto = QLineEdit(el.texto)
        campo_texto.textChanged.connect(el.definir_texto)
        self._form.addRow("Texto:", campo_texto)

        combo_fonte = QComboBox()
        combo_fonte.addItems(_FONTES_DISPONIVEIS)
        if el.fonte_familia in _FONTES_DISPONIVEIS:
            combo_fonte.setCurrentText(el.fonte_familia)
        combo_fonte.currentTextChanged.connect(el.definir_fonte)
        self._form.addRow("Fonte:", combo_fonte)

        check_negrito = QCheckBox("Negrito")
        check_negrito.setChecked(el.negrito)
        check_negrito.toggled.connect(el.definir_negrito)
        self._form.addRow("", check_negrito)

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_retangulo(self, el: ElementoRetangulo) -> None:
        check_preenchido = QCheckBox("Preenchido")
        check_preenchido.setChecked(el.preenchido)
        check_preenchido.toggled.connect(el.definir_preenchido)
        self._form.addRow("", check_preenchido)

        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_linha(self, el: ElementoLinha) -> None:
        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_checklist(self, el: ElementoChecklistCores) -> None:
        lista = QListWidget()
        lista.addItems(el.variantes)
        lista.setMaximumHeight(110)
        self._form.addRow("Variantes:", lista)

        campo_novo = QLineEdit()
        campo_novo.setPlaceholderText("Nome da nova cor...")

        def adicionar() -> None:
            nome = campo_novo.text().strip()
            if nome:
                el.adicionar_variante(nome)
                lista.addItem(nome)
                campo_novo.clear()

        campo_novo.returnPressed.connect(adicionar)
        self._form.addRow("", campo_novo)

        botao_remover_linha = QPushButton("Remover variante selecionada")

        def remover() -> None:
            linha = lista.currentRow()
            if linha >= 0:
                el.remover_variante(linha)
                lista.takeItem(linha)

        botao_remover_linha.clicked.connect(remover)
        self._form.addRow("", botao_remover_linha)

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_logo(self, el: ElementoLogoVetorial) -> None:
        self._form.addRow(QLabel(f"{len(el.cores_detectadas)} cor(es) detectada(s) no arquivo"))
        botao = QPushButton("Remapear cores...")
        botao.clicked.connect(lambda: self.remapear_logo_solicitado and self.remapear_logo_solicitado(el))
        self._form.addRow(botao)
