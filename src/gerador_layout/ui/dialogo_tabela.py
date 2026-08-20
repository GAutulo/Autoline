"""Diálogo de edição de tabela — preenche todas as células de uma vez
numa grade (`QTableWidget`), em vez de clique-a-clique no canvas. Linhas/
colunas são ajustáveis aqui mesmo, sem precisar fechar e reabrir."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .mockup_tabela import _LIMITE_COLUNAS, _LIMITE_LINHAS


class DialogoTabela(QDialog):
    def __init__(self, linhas: int, colunas: int, celulas: list[list[str]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar tabela")
        self.setMinimumSize(480, 340)

        vbox = QVBoxLayout(self)

        linha_dimensoes = QHBoxLayout()
        linha_dimensoes.addWidget(QLabel("Linhas:"))
        self._spin_linhas = QSpinBox()
        self._spin_linhas.setRange(1, _LIMITE_LINHAS)
        self._spin_linhas.setValue(linhas)
        linha_dimensoes.addWidget(self._spin_linhas)
        linha_dimensoes.addWidget(QLabel("Colunas:"))
        self._spin_colunas = QSpinBox()
        self._spin_colunas.setRange(1, _LIMITE_COLUNAS)
        self._spin_colunas.setValue(colunas)
        linha_dimensoes.addWidget(self._spin_colunas)
        botao_aplicar_dimensoes = QPushButton("Aplicar tamanho")
        botao_aplicar_dimensoes.clicked.connect(self._redimensionar_tabela)
        linha_dimensoes.addWidget(botao_aplicar_dimensoes)
        linha_dimensoes.addStretch(1)
        vbox.addLayout(linha_dimensoes)

        self._tabela = QTableWidget(linhas, colunas)
        self._preencher(celulas)
        vbox.addWidget(self._tabela, 1)

        aviso = QLabel("A primeira linha vira o cabeçalho (fica em negrito) — mesma convenção de qualquer tabela.")
        aviso.setWordWrap(True)
        vbox.addWidget(aviso)

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        vbox.addWidget(botoes)

    def _preencher(self, celulas: list[list[str]]) -> None:
        for l, linha in enumerate(celulas):
            for c, texto in enumerate(linha):
                self._tabela.setItem(l, c, QTableWidgetItem(texto))

    def _celulas_atuais(self) -> list[list[str]]:
        return [
            [
                (self._tabela.item(l, c).text() if self._tabela.item(l, c) else "")
                for c in range(self._tabela.columnCount())
            ]
            for l in range(self._tabela.rowCount())
        ]

    def _redimensionar_tabela(self) -> None:
        # Preserva o que já foi digitado — só muda o tamanho da grade,
        # não descarta o conteúdo (mesma regra de `ElementoTabela.definir_dimensoes`).
        celulas = self._celulas_atuais()
        novas_linhas, novas_colunas = self._spin_linhas.value(), self._spin_colunas.value()
        self._tabela.setRowCount(novas_linhas)
        self._tabela.setColumnCount(novas_colunas)
        self._preencher(celulas)

    def linhas(self) -> int:
        return self._tabela.rowCount()

    def colunas(self) -> int:
        return self._tabela.columnCount()

    def celulas(self) -> list[list[str]]:
        return self._celulas_atuais()
