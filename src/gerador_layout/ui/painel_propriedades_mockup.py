"""Barra de propriedades do elemento de mockup selecionado — uma
"property bar" horizontal (ver `_montar_barra_propriedades_mockup` em
main_window.py), no mesmo espírito da barra de propriedades contextual
de qualquer CAD/vetorial de verdade (CorelDRAW, Illustrator): fica logo
abaixo da barra de criar elemento, muda de conteúdo conforme o tipo do
elemento selecionado, e cada controle é um ÍCONE (com tooltip), não um
rótulo de texto — pedido explícito do usuário ("esse painel de
propriedades deveria ficar em cima separado por ícones igual é em
outros CAD... texto = ícone de uma letra, alinhamento = ícone de um
objeto com uma linha no local que será alinhado"). Fica vazia quando
não há seleção ou há mais de um elemento selecionado — editar
propriedade de vários de uma vez não é um caso coberto ainda.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ..models import CorImpressao
from ..paineis import Painel
from .dialogo_tabela import DialogoTabela
from .estilo import Cor
from .mockup_acabamento import ElementoAcabamento, TipoAcabamento
from .mockup_callout import ElementoCallout
from .mockup_checklist import ElementoChecklistCores
from .mockup_formas import ElementoElipse, ElementoLinha, ElementoPoligono, ElementoRetangulo
from .mockup_icones import TAMANHO_ICONE, construir_icone
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_tabela import ElementoTabela
from .mockup_texto import ElementoTexto

_ROTULO_SEM_PAINEL = "Nenhum"

_FONTES_DISPONIVEIS = ["Arial", "Arial Black", "Verdana", "Times New Roman", "Impact"]

_NOME_TIPO: dict[type, str] = {
    ElementoTexto: "Texto",
    ElementoRetangulo: "Retângulo",
    ElementoElipse: "Elipse",
    ElementoPoligono: "Polígono",
    ElementoLinha: "Linha",
    ElementoCallout: "Callout",
    ElementoTabela: "Tabela",
    ElementoAcabamento: "Acabamento de produção",
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

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(2, 0, 2, 0)
        raiz.setSpacing(8)

        self._rotulo_vazio = QLabel("Nada selecionado")
        self._rotulo_vazio.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};")
        raiz.addWidget(self._rotulo_vazio)

        self._rotulo_tipo = QLabel()
        self._rotulo_tipo.setStyleSheet("font-weight: 700;")
        self._rotulo_tipo.setVisible(False)
        raiz.addWidget(self._rotulo_tipo)

        self._container_campos = QWidget()
        self._layout_campos = QHBoxLayout(self._container_campos)
        self._layout_campos.setContentsMargins(0, 0, 0, 0)
        self._layout_campos.setSpacing(5)
        self._container_campos.setVisible(False)
        raiz.addWidget(self._container_campos)

        raiz.addStretch(1)

        self._botao_remover = QToolButton()
        self._botao_remover.setObjectName("botaoIconePropriedade")
        self._botao_remover.setIcon(construir_icone("remover"))
        self._botao_remover.setToolTip("Remover elemento")
        self._botao_remover.setVisible(False)
        self._botao_remover.clicked.connect(lambda: self.remover_solicitado and self.remover_solicitado())
        raiz.addWidget(self._botao_remover)

    # ── Peça básica: ícone + widget lado a lado, sem rótulo de texto ──
    def _grupo(self, tipo_icone: str, widget: QWidget, tooltip: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        icone = QLabel()
        icone.setObjectName("iconeCampoPropriedade")
        icone.setPixmap(construir_icone(tipo_icone).pixmap(TAMANHO_ICONE, TAMANHO_ICONE))
        icone.setToolTip(tooltip)
        widget.setToolTip(tooltip)
        layout.addWidget(icone)
        layout.addWidget(widget)
        self._layout_campos.addWidget(container)
        return container

    def _botao_icone(self, tipo_icone: str, tooltip: str, checkable: bool = False) -> QToolButton:
        botao = QToolButton()
        botao.setObjectName("botaoIconePropriedade")
        botao.setIcon(construir_icone(tipo_icone))
        botao.setToolTip(tooltip)
        botao.setCheckable(checkable)
        self._layout_campos.addWidget(botao)
        return botao

    def _separador(self) -> QFrame:
        linha = QFrame()
        linha.setFrameShape(QFrame.Shape.VLine)
        linha.setFrameShadow(QFrame.Shadow.Sunken)
        self._layout_campos.addWidget(linha)
        return linha

    # ── API pública ─────────────────────────────────────────────────
    def definir_elemento(self, elemento: ElementoMockup | None) -> None:
        if self._elemento is not None:
            # Desliga a conexão do elemento ANTERIOR antes de trocar —
            # sem isso, quando esse elemento mudasse de novo (ex.: mover
            # ele por outro caminho, tipo desfazer), o sinal ainda ia
            # tentar atualizar spinboxes que já foram destruídos junto
            # com a barra (ver `_limpar_barra`), e isso derruba o app.
            try:
                self._elemento.geometria_alterada.disconnect(self._atualizar_campos_geometria)
            except (TypeError, RuntimeError):
                pass

        self._elemento = elemento
        self._spins_geometria = {}
        self._rotulo_posicao_painel = None
        self._limpar_barra()

        if elemento is None:
            self._rotulo_vazio.setVisible(True)
            self._rotulo_tipo.setVisible(False)
            self._container_campos.setVisible(False)
            self._botao_remover.setVisible(False)
            return

        self._rotulo_vazio.setVisible(False)
        self._rotulo_tipo.setText(_NOME_TIPO.get(type(elemento), "Elemento"))
        self._rotulo_tipo.setVisible(True)
        self._container_campos.setVisible(True)
        self._botao_remover.setVisible(True)

        self._montar_campos_geometria(elemento)
        self._separador()
        self._montar_campos_painel(elemento)
        self._separador()

        if isinstance(elemento, ElementoTexto):
            self._montar_campos_texto(elemento)
        elif isinstance(elemento, ElementoChecklistCores):
            self._montar_campos_checklist(elemento)
        elif isinstance(elemento, ElementoRetangulo):
            self._montar_campos_retangulo(elemento)
        elif isinstance(elemento, ElementoElipse):
            self._montar_campos_elipse(elemento)
        elif isinstance(elemento, ElementoPoligono):
            self._montar_campos_poligono(elemento)
        elif isinstance(elemento, ElementoLinha):
            self._montar_campos_linha(elemento)
        elif isinstance(elemento, ElementoCallout):
            self._montar_campos_callout(elemento)
        elif isinstance(elemento, ElementoTabela):
            self._montar_campos_tabela(elemento)
        elif isinstance(elemento, ElementoAcabamento):
            self._montar_campos_acabamento(elemento)
        elif isinstance(elemento, ElementoLogoVetorial):
            self._montar_campos_logo(elemento)
        elif isinstance(elemento, ElementoImagem):
            nome = QLabel(elemento.caminho_arquivo.rsplit("\\", 1)[-1])
            nome.setMaximumWidth(160)
            nome.setToolTip(elemento.caminho_arquivo)
            self._layout_campos.addWidget(nome)
        elif isinstance(elemento, GrupoMockup):
            aviso = QLabel("Sem aparência própria")
            aviso.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};")
            aviso.setToolTip("Grupo não tem aparência própria — edite os elementos individualmente.")
            self._layout_campos.addWidget(aviso)

        elemento.geometria_alterada.connect(self._atualizar_campos_geometria)

    # ── Posição/tamanho/rotação — comuns a todo elemento ──────────────
    def _montar_campos_geometria(self, elemento: ElementoMockup) -> None:
        campos = (
            ("x", "x", "Posição X", " mm", -100000.0, 100000.0),
            ("y", "y", "Posição Y", " mm", -100000.0, 100000.0),
            ("largura", "largura", "Largura", " mm", 0.1, 100000.0),
            ("altura", "altura", "Altura", " mm", 0.1, 100000.0),
            ("angulo", "angulo", "Ângulo de rotação", " °", -3600.0, 3600.0),
        )
        for chave, tipo_icone, tooltip, sufixo, minimo, maximo in campos:
            spin = QDoubleSpinBox()
            spin.setRange(minimo, maximo)
            spin.setDecimals(2)
            spin.setSuffix(sufixo)
            spin.setMaximumWidth(78)
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
            self._grupo(tipo_icone, spin, tooltip)

        botao_trava = self._botao_icone("trava", "Travar proporção largura/altura", checkable=True)
        botao_trava.setChecked(elemento.proporcao_travada)
        botao_trava.toggled.connect(elemento.definir_proporcao_travada)

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
        combo.setMaximumWidth(110)
        combo.addItem(_ROTULO_SEM_PAINEL, None)
        indice_atual = 0
        for i, painel in enumerate(paineis, start=1):
            combo.addItem(painel.nome, painel.id)
            if painel.id == elemento.painel_id:
                indice_atual = i
        combo.setCurrentIndex(indice_atual)
        self._grupo("face", combo, "Face da caixa a que este elemento pertence")

        disposicao = (
            ("alinhar_esquerda", "esquerda", "Alinhar à esquerda da face"),
            ("alinhar_centro_h", "centro_h", "Centralizar horizontalmente na face"),
            ("alinhar_direita", "direita", "Alinhar à direita da face"),
            ("alinhar_topo", "topo", "Alinhar ao topo da face"),
            ("alinhar_centro_v", "centro_v", "Centralizar verticalmente na face"),
            ("alinhar_base", "base", "Alinhar à base da face"),
        )
        botoes: list[QToolButton] = []
        for tipo_icone, alinhamento, tooltip in disposicao:
            botao = self._botao_icone(tipo_icone, tooltip)
            botao.clicked.connect(lambda _c=False, a=alinhamento: self._alinhar_ao_painel(a))
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

        # Leitura de onde o elemento está DENTRO da face escolhida — a
        # mesma pergunta que se faz olhando o desenho de perto ("está bem
        # no meio? quão perto da borda?"), só que em número. Barra
        # horizontal não tem espaço pra escrever isso sempre visível
        # (era um QLabel de texto no dock antigo) — vira ícone com
        # tooltip dinâmico, igual qualquer indicador de status de CAD.
        self._rotulo_posicao_painel = QLabel()
        self._rotulo_posicao_painel.setObjectName("iconeCampoPropriedade")
        self._rotulo_posicao_painel.setPixmap(construir_icone("medida").pixmap(TAMANHO_ICONE, TAMANHO_ICONE))
        self._layout_campos.addWidget(self._rotulo_posicao_painel)
        self._atualizar_rotulo_posicao_painel()

    _TOLERANCIA_CENTRALIZADO_MM = 0.5

    def _atualizar_rotulo_posicao_painel(self) -> None:
        """Distância das 4 bordas da face até o elemento, mais se está
        centralizado (dentro de uma tolerância pequena) em cada eixo —
        substitui ter que estimar isso olhando o desenho. Fica só no
        tooltip do ícone "medida" (ver `_montar_campos_painel`)."""
        rotulo = self._rotulo_posicao_painel
        if rotulo is None:
            return
        elemento = self._elemento
        painel = None
        if elemento is not None and elemento.painel_id is not None:
            painel = next((p for p in self._obter_paineis() if p.id == elemento.painel_id), None)
        if elemento is None or painel is None:
            rotulo.setToolTip("Posição na face: sem face escolhida.")
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
        rotulo.setToolTip("\n".join(partes))

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
    def _limpar_barra(self) -> None:
        while self._layout_campos.count():
            item = self._layout_campos.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # `takeAt` só desliga o item do LAYOUT — o widget continua
                # filho de `_container_campos` e visível na posição antiga
                # até o `deleteLater()` ser processado (evento adiado, não
                # imediato). Sem o `setParent(None)`, sobra widget "morto"
                # flutuando/sobrepondo o conteúdo novo por um instante toda
                # vez que troca de elemento — achado testando de verdade,
                # não só teórico (mostrava várias trava-de-proporção juntas
                # ao selecionar elementos em sequência rápida).
                widget.setParent(None)
                widget.deleteLater()

    def _combo_cor(self, cor_atual: CorImpressao, ao_mudar: Callable[[CorImpressao], None]) -> QComboBox:
        combo = QComboBox()
        indice_atual = 0
        for i, tinta in enumerate(self._obter_tintas()):
            combo.addItem(tinta.nome, tinta)
            if tinta.nome == cor_atual.nome:
                indice_atual = i
        combo.setObjectName("comboCorTinta")  # pra achar de forma confiável, não por posição
        combo.setMaximumWidth(100)
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
            self._grupo("tinta", self._combo_cor(cor_atual, ao_mudar), "Cor de tinta")
        else:
            aviso = QLabel("Marque uma cor na legenda pra poder escolher aqui.")
            aviso.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};")
            self._layout_campos.addWidget(aviso)

    def _campo_espessura_traco(self, valor_atual: float, ao_mudar: Callable[[float], None]) -> None:
        spin = QDoubleSpinBox()
        spin.setRange(0.05, 20.0)
        spin.setDecimals(2)
        spin.setSuffix(" mm")
        spin.setMaximumWidth(78)
        spin.setValue(valor_atual)
        spin.setKeyboardTracking(False)  # mesmo motivo do campo de geometria — ver comentário lá
        spin.valueChanged.connect(ao_mudar)
        self._grupo("espessura", spin, "Espessura do traço")

    def _montar_campos_texto(self, el: ElementoTexto) -> None:
        campo_texto = QLineEdit(el.texto)
        campo_texto.setMaximumWidth(130)
        campo_texto.textChanged.connect(el.definir_texto)
        self._grupo("letra_a", campo_texto, "Conteúdo do texto")

        combo_fonte = QComboBox()
        combo_fonte.setMaximumWidth(100)
        combo_fonte.addItems(_FONTES_DISPONIVEIS)
        if el.fonte_familia in _FONTES_DISPONIVEIS:
            combo_fonte.setCurrentText(el.fonte_familia)
        combo_fonte.currentTextChanged.connect(el.definir_fonte)
        self._grupo("fonte_aa", combo_fonte, "Fonte")

        botao_negrito = self._botao_icone("negrito", "Negrito", checkable=True)
        botao_negrito.setChecked(el.negrito)
        botao_negrito.toggled.connect(el.definir_negrito)

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_retangulo(self, el: ElementoRetangulo) -> None:
        botao_preenchido = self._botao_icone("preenchido", "Preenchido", checkable=True)
        botao_preenchido.setChecked(el.preenchido)
        botao_preenchido.toggled.connect(el.definir_preenchido)

        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_linha(self, el: ElementoLinha) -> None:
        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_elipse(self, el: ElementoElipse) -> None:
        botao_preenchido = self._botao_icone("preenchido", "Preenchido", checkable=True)
        botao_preenchido.setChecked(el.preenchido)
        botao_preenchido.toggled.connect(el.definir_preenchido)

        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_poligono(self, el: ElementoPoligono) -> None:
        spin_lados = QSpinBox()
        spin_lados.setRange(3, 20)
        spin_lados.setValue(el.lados)
        spin_lados.setMaximumWidth(56)
        spin_lados.setKeyboardTracking(False)  # mesmo motivo do campo de geometria — ver comentário lá
        spin_lados.valueChanged.connect(el.definir_lados)
        self._grupo("ferramenta_poligono", spin_lados, "Número de lados")

        botao_preenchido = self._botao_icone("preenchido", "Preenchido", checkable=True)
        botao_preenchido.setChecked(el.preenchido)
        botao_preenchido.toggled.connect(el.definir_preenchido)

        self._campo_espessura_traco(el.largura_traco, el.definir_largura_traco)
        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_callout(self, el: ElementoCallout) -> None:
        campo_texto = QLineEdit(el.texto)
        campo_texto.setMaximumWidth(160)
        campo_texto.textChanged.connect(el.definir_texto)
        self._grupo("letra_a", campo_texto, "Texto da anotação")

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_tabela(self, el: ElementoTabela) -> None:
        botao_editar = self._botao_icone("ferramenta_tabela", f"Editar tabela ({el.linhas}×{el.colunas})...")
        botao_editar.clicked.connect(lambda: self._abrir_dialogo_tabela(el, botao_editar))

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _abrir_dialogo_tabela(self, el: ElementoTabela, botao: QToolButton) -> None:
        dialogo = DialogoTabela(el.linhas, el.colunas, el.celulas, parent=self)
        if dialogo.exec() == DialogoTabela.DialogCode.Accepted:
            el.definir_dimensoes(dialogo.linhas(), dialogo.colunas())
            el.definir_celulas(dialogo.celulas())
            botao.setToolTip(f"Editar tabela ({el.linhas}×{el.colunas})...")

    def _montar_campos_acabamento(self, el: ElementoAcabamento) -> None:
        # Sem cor de tinta de propósito — acabamento de produção usa
        # sempre a mesma cor de marcação técnica (ver docstring do
        # módulo), não uma das tintas do trabalho.
        combo_tipo = QComboBox()
        combo_tipo.setMaximumWidth(150)
        for tipo in TipoAcabamento:
            combo_tipo.addItem(tipo.value, tipo)
        combo_tipo.setCurrentIndex(list(TipoAcabamento).index(el.tipo))
        combo_tipo.currentIndexChanged.connect(lambda _i: el.definir_tipo(combo_tipo.currentData()))
        self._grupo("ferramenta_transparencia", combo_tipo, "Tipo de acabamento")

    def _montar_campos_checklist(self, el: ElementoChecklistCores) -> None:
        # A lista de variantes não cabe numa barra horizontal (precisa de
        # altura, não largura) — vira um popup: botão de ícone "lista"
        # abre um menu com o editor completo dentro (mesmo padrão de
        # "abrir um mini-painel a partir de um botão de barra" que
        # qualquer CAD usa pra ferramentas com mais opções do que cabe
        # numa linha).
        botao_lista = self._botao_icone("lista", f"Variantes ({len(el.variantes)}) — clique pra editar")
        botao_lista.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QMenu(botao_lista)
        editor = QWidget()
        layout_editor = QVBoxLayout(editor)
        layout_editor.setContentsMargins(8, 8, 8, 8)

        lista = QListWidget()
        lista.addItems(el.variantes)
        lista.setMinimumWidth(160)
        lista.setMaximumHeight(120)
        # Clique duplo remove na hora — mais rápido pra corrigir um erro
        # de digitação do que selecionar e depois procurar o botão.
        lista.itemDoubleClicked.connect(lambda item: remover_item(lista.row(item)))
        layout_editor.addWidget(lista)

        def atualizar_habilitado() -> None:
            # Sempre precisa sobrar pelo menos 1 variante (ver
            # `ElementoChecklistCores.remover_variante`) — desabilita em
            # vez de deixar clicável sem fazer nada (era isso que
            # desincronizava a lista visual do modelo: o clique "sumia"
            # com o item na tela mesmo quando o modelo recusava remover).
            pode_remover = lista.count() > 1
            botao_remover_linha.setEnabled(pode_remover)
            lista.setToolTip("" if pode_remover else "Precisa sobrar pelo menos uma cor na lista.")
            botao_lista.setToolTip(f"Variantes ({lista.count()}) — clique pra editar")

        def remover_item(linha: int) -> None:
            if 0 <= linha < lista.count() and el.remover_variante(linha):
                lista.takeItem(linha)
            atualizar_habilitado()

        linha_nova = QWidget()
        layout_linha_nova = QHBoxLayout(linha_nova)
        layout_linha_nova.setContentsMargins(0, 0, 0, 0)
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
        layout_linha_nova.addWidget(campo_novo)

        botao_adicionar = QToolButton()
        botao_adicionar.setObjectName("botaoIconePropriedade")
        botao_adicionar.setIcon(construir_icone("mais"))
        botao_adicionar.setToolTip("Adicionar variante")
        botao_adicionar.clicked.connect(adicionar)
        layout_linha_nova.addWidget(botao_adicionar)

        botao_remover_linha = QToolButton()
        botao_remover_linha.setObjectName("botaoIconePropriedade")
        botao_remover_linha.setIcon(construir_icone("remover"))
        botao_remover_linha.setToolTip("Remover selecionada")

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
        layout_linha_nova.addWidget(botao_remover_linha)
        layout_editor.addWidget(linha_nova)
        atualizar_habilitado()

        acao_editor = QWidgetAction(menu)
        acao_editor.setDefaultWidget(editor)
        menu.addAction(acao_editor)
        botao_lista.setMenu(menu)

        self._linha_cor_tinta(el.cor_tinta, el.definir_cor_tinta)

    def _montar_campos_logo(self, el: ElementoLogoVetorial) -> None:
        botao = self._botao_icone("remapear", f"{len(el.cores_detectadas)} cor(es) detectada(s) — remapear")
        botao.clicked.connect(lambda: self.remapear_logo_solicitado and self.remapear_logo_solicitado(el))
