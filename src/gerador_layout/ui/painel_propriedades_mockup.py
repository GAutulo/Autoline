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
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import CorImpressao
from ..paineis import Painel
from .mockup_checklist import ElementoChecklistCores
from .mockup_formas import ElementoLinha, ElementoRetangulo
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_texto import ElementoTexto

_ROTULO_SEM_PAINEL = "Nenhum"

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
    def __init__(
        self,
        obter_tintas_disponiveis: Callable[[], list[CorImpressao]],
        obter_paineis_disponiveis: Callable[[], list[Painel]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._obter_tintas = obter_tintas_disponiveis
        self._obter_paineis = obter_paineis_disponiveis
        self._elemento: ElementoMockup | None = None
        self._spins_geometria: dict[str, QDoubleSpinBox] = {}
        self._rotulo_posicao_painel: QLabel | None = None

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
        if self._elemento is not None:
            # Desliga a conexão do elemento ANTERIOR antes de trocar —
            # sem isso, quando esse elemento mudasse de novo (ex.: mover
            # ele por outro caminho, tipo desfazer), o sinal ainda ia
            # tentar atualizar spinboxes que já foram destruídos junto
            # com o formulário (ver `_limpar_form`), e isso derruba o app.
            try:
                self._elemento.geometria_alterada.disconnect(self._atualizar_campos_geometria)
            except (TypeError, RuntimeError):
                pass

        self._elemento = elemento
        self._spins_geometria = {}
        self._rotulo_posicao_painel = None
        self._limpar_form()

        if elemento is None:
            self._titulo.setText("Nada selecionado")
            self._botao_remover.setVisible(False)
            return

        self._titulo.setText(_NOME_TIPO.get(type(elemento), "Elemento"))
        self._botao_remover.setVisible(True)

        self._montar_campos_geometria(elemento)
        self._montar_campos_painel(elemento)

        if not isinstance(elemento, GrupoMockup):
            rotulo_secao = QLabel("APARÊNCIA")
            rotulo_secao.setStyleSheet("font-weight: 700; font-size: 10.5px; letter-spacing: .05em;")
            self._form.addRow(rotulo_secao)

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

        elemento.geometria_alterada.connect(self._atualizar_campos_geometria)

    # ── Posição/tamanho/rotação — comuns a todo elemento ──────────────
    def _montar_campos_geometria(self, elemento: ElementoMockup) -> None:
        rotulo_secao = QLabel("POSIÇÃO E TAMANHO")
        rotulo_secao.setStyleSheet("font-weight: 700; font-size: 10.5px; letter-spacing: .05em;")
        self._form.addRow(rotulo_secao)

        campos = (
            ("x", "X:", " mm", -100000.0, 100000.0),
            ("y", "Y:", " mm", -100000.0, 100000.0),
            ("largura", "Largura:", " mm", 0.1, 100000.0),
            ("altura", "Altura:", " mm", 0.1, 100000.0),
            ("angulo", "Ângulo:", " °", -3600.0, 3600.0),
        )
        for chave, rotulo, sufixo, minimo, maximo in campos:
            spin = QDoubleSpinBox()
            spin.setRange(minimo, maximo)
            spin.setDecimals(2)
            spin.setSuffix(sufixo)
            # Sem isso, `valueChanged` dispara a CADA TECLA digitada, não
            # só ao terminar — digitar "20" aplicava primeiro "2" (vira
            # "4" por causa do mínimo de 4mm), a tela atualizava o campo
            # PRA ESSE VALOR ERRADO no meio da digitação, e o "0" seguinte
            # continuava a partir do "4" em vez do "2" que a pessoa
            # realmente digitou — resultado "40" em vez de "20". Só
            # aplicar ao confirmar (Enter/Tab/perder o foco) resolve.
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda valor, c=chave: self._ao_editar_geometria(c, valor))
            self._spins_geometria[chave] = spin
            self._form.addRow(rotulo, spin)

        check_proporcao = QCheckBox("Travar proporção")
        check_proporcao.setChecked(elemento.proporcao_travada)
        check_proporcao.toggled.connect(elemento.definir_proporcao_travada)
        self._form.addRow("", check_proporcao)

        self._atualizar_campos_geometria()

    def _atualizar_campos_geometria(self) -> None:
        """Reflete a geometria atual do elemento nos campos — chamado na
        montagem E toda vez que `geometria_alterada` dispara (arrastar,
        redimensionar ou girar na tela, ver `mockup_itens.py`), pra não
        deixar os números desatualizados enquanto o usuário edita pelo
        canvas em vez de pelos campos."""
        elemento = self._elemento
        if elemento is None or not self._spins_geometria:
            return
        valores = {
            "x": elemento.pos().x(),
            "y": elemento.pos().y(),
            "largura": elemento.largura,
            "altura": elemento.altura,
            "angulo": elemento.rotation(),
        }
        for chave, valor in valores.items():
            spin = self._spins_geometria.get(chave)
            if spin is None:
                continue
            spin.blockSignals(True)  # senão setValue() aqui disparava _ao_editar_geometria de volta
            spin.setValue(valor)
            spin.blockSignals(False)
        self._atualizar_rotulo_posicao_painel()

    # ── Painel (face da caixa) + alinhamento ─────────────────────────
    def _montar_campos_painel(self, elemento: ElementoMockup) -> None:
        paineis = self._obter_paineis()
        combo = QComboBox()
        combo.setObjectName("comboPainel")  # pra achar de forma confiável (ex.: em teste), não por posição
        combo.addItem(_ROTULO_SEM_PAINEL, None)
        indice_atual = 0
        for i, painel in enumerate(paineis, start=1):
            combo.addItem(painel.nome, painel.id)
            if painel.id == elemento.painel_id:
                indice_atual = i
        combo.setCurrentIndex(indice_atual)
        self._form.addRow("Painel:", combo)

        # QGridLayout direto (não QVBoxLayout de 2 QHBoxLayout) e cada
        # botão com `setMinimumHeight` explícito — tentativas anteriores
        # com layouts aninhados dentro de um `addRow(rótulo, widget)`
        # colapsavam pra 1px de altura (bug real do Qt nesse tipo de
        # aninhamento, não só cosmético: os botões ficavam praticamente
        # inclicáveis). Achado revisando com a janela em tamanho
        # restaurado — na maximizada passava despercebido.
        botoes: list[QPushButton] = []
        container_botoes = QWidget()
        grade_botoes = QGridLayout(container_botoes)
        grade_botoes.setContentsMargins(0, 0, 0, 0)
        grade_botoes.setSpacing(4)
        disposicao = (
            ("Esq.", "esquerda", 0, 0),
            ("Centro H", "centro_h", 0, 1),
            ("Dir.", "direita", 0, 2),
            ("Topo", "topo", 1, 0),
            ("Centro V", "centro_v", 1, 1),
            ("Base", "base", 1, 2),
        )
        for texto, alinhamento, linha, coluna in disposicao:
            botao = QPushButton(texto)
            botao.setMinimumHeight(26)
            botao.clicked.connect(lambda _c=False, a=alinhamento: self._alinhar_ao_painel(a))
            grade_botoes.addWidget(botao, linha, coluna)
            botoes.append(botao)

        def atualizar_habilitado() -> None:
            ativo = combo.currentData() is not None
            for botao in botoes:
                botao.setEnabled(ativo)

        def ao_mudar(_indice: int) -> None:
            elemento.definir_painel(combo.currentData())
            atualizar_habilitado()
            self._atualizar_rotulo_posicao_painel()

        combo.currentIndexChanged.connect(ao_mudar)
        atualizar_habilitado()

        self._form.addRow("Alinhar:", container_botoes)

        # Leitura de onde o elemento está DENTRO da face escolhida — a
        # mesma pergunta que se faz olhando o desenho de perto ("está bem
        # no meio? quão perto da borda?"), só que em número, sem precisar
        # medir na régua/zoom.
        self._rotulo_posicao_painel = QLabel()
        self._rotulo_posicao_painel.setWordWrap(True)
        self._rotulo_posicao_painel.setStyleSheet("color: palette(mid); font-size: 11px;")
        self._form.addRow("Na face:", self._rotulo_posicao_painel)
        self._atualizar_rotulo_posicao_painel()

    _TOLERANCIA_CENTRALIZADO_MM = 0.5

    def _atualizar_rotulo_posicao_painel(self) -> None:
        """Distância das 4 bordas da face até o elemento, mais se está
        centralizado (dentro de uma tolerância pequena) em cada eixo —
        substitui ter que estimar isso olhando o desenho."""
        rotulo = self._rotulo_posicao_painel
        if rotulo is None:
            return
        elemento = self._elemento
        painel = None
        if elemento is not None and elemento.painel_id is not None:
            painel = next((p for p in self._obter_paineis() if p.id == elemento.painel_id), None)
        if elemento is None or painel is None:
            rotulo.setText("Sem face escolhida.")
            return

        x, y = elemento.pos().x(), elemento.pos().y()
        esq = x - painel.x1
        dir_ = painel.x2 - (x + elemento.largura)
        topo = y - painel.y1
        base = painel.y2 - (y + elemento.altura)
        centralizado_h = abs(esq - dir_) <= self._TOLERANCIA_CENTRALIZADO_MM
        centralizado_v = abs(topo - base) <= self._TOLERANCIA_CENTRALIZADO_MM

        partes = [
            f"Esq. {esq:.1f} / Dir. {dir_:.1f} mm" + (" (centralizado H)" if centralizado_h else ""),
            f"Topo {topo:.1f} / Base {base:.1f} mm" + (" (centralizado V)" if centralizado_v else ""),
        ]
        rotulo.setText("\n".join(partes))

    def _alinhar_ao_painel(self, alinhamento: str) -> None:
        elemento = self._elemento
        if elemento is None or elemento.painel_id is None:
            return
        painel = next((p for p in self._obter_paineis() if p.id == elemento.painel_id), None)
        if painel is None:
            return

        x, y = elemento.pos().x(), elemento.pos().y()
        if alinhamento == "esquerda":
            x = painel.x1
        elif alinhamento == "direita":
            x = painel.x2 - elemento.largura
        elif alinhamento == "centro_h":
            x = painel.x1 + (painel.largura - elemento.largura) / 2
        elif alinhamento == "topo":
            y = painel.y1
        elif alinhamento == "base":
            y = painel.y2 - elemento.altura
        elif alinhamento == "centro_v":
            y = painel.y1 + (painel.altura - elemento.altura) / 2
        elemento.setPos(x, y)

    def _ao_editar_geometria(self, chave: str, valor: float) -> None:
        elemento = self._elemento
        if elemento is None:
            return
        if chave == "x":
            elemento.setPos(valor, elemento.pos().y())
        elif chave == "y":
            elemento.setPos(elemento.pos().x(), valor)
        elif chave == "largura":
            elemento.definir_largura(valor)
        elif chave == "altura":
            elemento.definir_altura(valor)
        elif chave == "angulo":
            elemento.setRotation(valor)

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
        combo.setObjectName("comboCorTinta")  # pra achar de forma confiável, não por posição
        combo.setCurrentIndex(indice_atual)
        # `currentData()` pode vir None em situações que não deviam
        # acontecer no fluxo normal (ex.: índice inválido) — guarda aqui
        # em vez de deixar propagar um `cor_tinta=None` pro elemento, que
        # derruba a próxima repintura (`self._cor_tinta.r` em cima de
        # `None`). Achado testando, não só teórico.
        combo.currentIndexChanged.connect(
            lambda _i: combo.currentData() is not None and ao_mudar(combo.currentData())
        )
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
        spin.setKeyboardTracking(False)  # mesmo motivo do campo de geometria — ver comentário lá
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
        # Clique duplo remove na hora — mais rápido pra corrigir um erro
        # de digitação do que selecionar e depois procurar o botão.
        lista.itemDoubleClicked.connect(lambda item: remover_item(lista.row(item)))
        self._form.addRow("Variantes (2x clique remove):", lista)

        def atualizar_habilitado() -> None:
            # Sempre precisa sobrar pelo menos 1 variante (ver
            # `ElementoChecklistCores.remover_variante`) — desabilita em
            # vez de deixar clicável sem fazer nada (era isso que
            # desincronizava a lista visual do modelo: o clique "sumia"
            # com o item na tela mesmo quando o modelo recusava remover).
            pode_remover = lista.count() > 1
            botao_remover_linha.setEnabled(pode_remover)
            lista.setToolTip("" if pode_remover else "Precisa sobrar pelo menos uma cor na lista.")

        def remover_item(linha: int) -> None:
            if 0 <= linha < lista.count() and el.remover_variante(linha):
                lista.takeItem(linha)
            atualizar_habilitado()

        campo_novo = QLineEdit()
        campo_novo.setPlaceholderText("Nome da nova cor...")

        def adicionar() -> None:
            nome = campo_novo.text().strip()
            if nome:
                el.adicionar_variante(nome)
                lista.addItem(nome)
                lista.setCurrentRow(lista.count() - 1)  # já deixa selecionada — digitou errado, corrige na hora
                campo_novo.clear()
                atualizar_habilitado()

        campo_novo.returnPressed.connect(adicionar)
        self._form.addRow("", campo_novo)

        botao_remover_linha = QPushButton("Remover selecionada")

        def remover() -> None:
            linha = lista.currentRow()
            if linha < 0:
                # Nada selecionado (ex.: só digitou nomes sem nunca clicar
                # na lista) — antes isso não fazia nada, silenciosamente,
                # e parecia que o botão não funcionava. Remove a última
                # como padrão razoável em vez de exigir clicar primeiro.
                linha = lista.count() - 1
            remover_item(linha)

        botao_remover_linha.clicked.connect(remover)
        self._form.addRow("", botao_remover_linha)
        atualizar_habilitado()

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_logo(self, el: ElementoLogoVetorial) -> None:
        self._form.addRow(QLabel(f"{len(el.cores_detectadas)} cor(es) detectada(s) no arquivo"))
        botao = QPushButton("Remapear cores...")
        botao.clicked.connect(lambda: self.remapear_logo_solicitado and self.remapear_logo_solicitado(el))
        self._form.addRow(botao)
