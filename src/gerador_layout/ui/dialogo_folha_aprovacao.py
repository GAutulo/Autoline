"""Janela da folha de aprovação: o que é digitado (cliente, referência,
código), o que vem do projeto (medidas, tipo, cores — dá pra corrigir) e as
datas (criado em fica; gerar de novo em outro dia vira modificação)."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import CorImpressao
from .folha_aprovacao import DadosFolha, data_br, datas_da_vez


class DialogoFolhaAprovacao(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        cliente: str = "",
        referencia: str = "",
        codigo: str = "",
        medidas: str = "",
        tipo: str = "",
        cores: list[CorImpressao] | None = None,
        criado_em: _dt.date | None = None,
        desenvolvido_por: str = "",
        logo: str = "",
        hoje: _dt.date | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Folha de aprovação")
        self.setMinimumWidth(520)
        self._cores = list(cores or [])
        self._criado_em = criado_em
        self._hoje = hoje or _dt.date.today()

        raiz = QVBoxLayout(self)
        form = QFormLayout()
        self.campo_cliente = QLineEdit(cliente)
        self.campo_referencia = QLineEdit(referencia)
        self.campo_referencia.setPlaceholderText("ex.: CAIXA 02 - 06 LONG NECK 355ML TRAD.")
        self.campo_codigo = QLineEdit(codigo)
        self.campo_medidas = QLineEdit(medidas)
        self.campo_tipo = QLineEdit(tipo)
        form.addRow("Cliente:", self.campo_cliente)
        form.addRow("Referência:", self.campo_referencia)
        form.addRow("Código:", self.campo_codigo)
        form.addRow("Medidas:", self.campo_medidas)
        form.addRow("Tipo de caixa:", self.campo_tipo)
        nomes = ", ".join(c.nome.upper() for c in self._cores) or "(nenhuma cor marcada na legenda)"
        rotulo_cores = QLabel(nomes)
        rotulo_cores.setToolTip("As cores marcadas na legenda de cores do projeto")
        form.addRow("Cores:", rotulo_cores)
        self.campo_desenvolvido = QLineEdit(desenvolvido_por)
        form.addRow("Desenvolvido por:", self.campo_desenvolvido)

        linha_logo = QWidget()
        lay = QHBoxLayout(linha_logo)
        lay.setContentsMargins(0, 0, 0, 0)
        self.campo_logo = QLineEdit(logo)
        self.campo_logo.setPlaceholderText("SVG ou PNG do logotipo da empresa")
        botao_logo = QPushButton("…")
        botao_logo.setFixedWidth(28)
        botao_logo.clicked.connect(self._escolher_logo)
        lay.addWidget(self.campo_logo, 1)
        lay.addWidget(botao_logo)
        form.addRow("Logotipo:", linha_logo)

        if criado_em is None:
            form.addRow("Criado em:", QLabel(f"{data_br(self._hoje)} (primeira vez)"))
            self.check_modificacao = None
        else:
            form.addRow("Criado em:", QLabel(data_br(criado_em)))
            self.check_modificacao = QCheckBox(f"É uma modificação — “Modificado em” {data_br(self._hoje)}")
            self.check_modificacao.setChecked(self._hoje != criado_em)
            form.addRow("", self.check_modificacao)
        raiz.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Gerar PDF…")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        raiz.addWidget(botoes)

    def _escolher_logo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Logotipo da folha de aprovação", str(Path(self.campo_logo.text()).parent), "Logotipo (*.svg *.png *.jpg)"
        )
        if caminho:
            self.campo_logo.setText(caminho)

    @property
    def logo(self) -> str:
        return self.campo_logo.text().strip()

    def dados(self) -> DadosFolha:
        modificacao = None if self.check_modificacao is None else self.check_modificacao.isChecked()
        criado, modificado = datas_da_vez(self._criado_em, self._hoje, modificacao)
        return DadosFolha(
            cliente=self.campo_cliente.text().strip(),
            referencia=self.campo_referencia.text().strip(),
            codigo=self.campo_codigo.text().strip(),
            medidas=self.campo_medidas.text().strip(),
            tipo=self.campo_tipo.text().strip(),
            cores=self._cores,
            criado_em=criado,
            modificado_em=modificado,
            desenvolvido_por=self.campo_desenvolvido.text().strip(),
        )
