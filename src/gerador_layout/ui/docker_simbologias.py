"""Docker "Simbologias": o banco de símbolos (ver `simbologias.py`) com
miniaturas — duplo clique (ou "Inserir") põe o símbolo no layout, no
tamanho real em que foi desenhado.

Os símbolos do usuário ficam numa pasta própria (um .svg cada, nome do
arquivo = nome do símbolo): dá pra adicionar um SVG, importar uma folha
inteira (cada grupo vira um símbolo), arrastar SVGs do Explorer pra cá,
renomear e apagar; e substituir um símbolo de fábrica pelo seu arquivo
(botão direito), com volta ao original.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, QSize, QStandardPaths, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..simbologias import Simbolo, carregar_banco, nome_de_arquivo, salvar_simbolos, separar_folha_svg

_PAPEL_SIMBOLO = Qt.ItemDataRole.UserRole
_LADO_MINIATURA = 96


def pasta_simbolos_usuario() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "simbologias"


def miniatura(caminho: Path, lado: int = _LADO_MINIATURA) -> QIcon:
    pixmap = QPixmap(lado, lado)
    pixmap.fill(Qt.GlobalColor.white)
    renderer = QSvgRenderer(str(caminho))
    if renderer.isValid():
        caixa = renderer.viewBoxF()
        if caixa.isEmpty():
            caixa = QRectF(0, 0, renderer.defaultSize().width(), renderer.defaultSize().height())
        if not caixa.isEmpty():
            margem = 6
            escala = min((lado - 2 * margem) / caixa.width(), (lado - 2 * margem) / caixa.height())
            w, h = caixa.width() * escala, caixa.height() * escala
            p = QPainter(pixmap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(p, QRectF((lado - w) / 2, (lado - h) / 2, w, h))
            p.end()
    return QIcon(pixmap)


class DockerSimbologias(QWidget):
    inserir_simbolo = Signal(str, str)  # caminho do .svg, nome

    def __init__(self, pasta_usuario: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pasta_usuario = pasta_usuario or pasta_simbolos_usuario()

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar símbolo…")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(self._filtrar)

        self.lista = QListWidget()
        self.lista.setViewMode(QListView.ViewMode.IconMode)
        self.lista.setIconSize(QSize(_LADO_MINIATURA, _LADO_MINIATURA))
        self.lista.setGridSize(QSize(_LADO_MINIATURA + 24, _LADO_MINIATURA + 40))
        self.lista.setResizeMode(QListView.ResizeMode.Adjust)
        self.lista.setMovement(QListView.Movement.Static)
        self.lista.setWordWrap(True)
        self.lista.setUniformItemSizes(True)
        self.lista.itemDoubleClicked.connect(self._inserir_item)
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_contexto)
        self.lista.currentItemChanged.connect(lambda *_: self._atualizar_botoes())
        # Arrastar SVGs do Explorer pra lista = adicionar ao banco.
        self.lista.setAcceptDrops(True)
        self.lista.viewport().setAcceptDrops(True)
        self.lista.viewport().installEventFilter(self)
        self.setAcceptDrops(True)

        self.botao_inserir = QPushButton("Inserir")
        self.botao_inserir.setToolTip("Põe o símbolo no layout (ou dê dois cliques nele)")
        self.botao_inserir.clicked.connect(lambda: self._inserir_item(self.lista.currentItem()))
        botao_adicionar = QPushButton("Adicionar SVG…")
        botao_adicionar.setToolTip(
            "Guarda um ou mais arquivos SVG no banco, um símbolo por arquivo\n"
            "(ou arraste os arquivos do Explorer pra cá)"
        )
        botao_adicionar.clicked.connect(self.adicionar_svgs)
        botao_folha = QPushButton("Importar folha…")
        botao_folha.setToolTip("Um SVG com vários símbolos (exportado do CorelDRAW): cada grupo vira um símbolo")
        botao_folha.clicked.connect(self.importar_folha)

        botoes = QHBoxLayout()
        botoes.addWidget(botao_adicionar)
        botoes.addWidget(botao_folha)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.busca)
        layout.addWidget(self.lista, 1)
        layout.addWidget(self.botao_inserir)
        layout.addLayout(botoes)

        self.recarregar()

    # ── Lista ────────────────────────────────────────────────────────
    def recarregar(self, selecionar: Path | None = None) -> None:
        self.lista.clear()
        for simbolo in carregar_banco(self.pasta_usuario):
            item = QListWidgetItem(miniatura(simbolo.caminho), simbolo.nome)
            item.setData(_PAPEL_SIMBOLO, simbolo)
            item.setToolTip(f"{simbolo.nome}\n{simbolo.categoria}" if simbolo.categoria else simbolo.nome)
            self.lista.addItem(item)
            if selecionar is not None and simbolo.caminho == selecionar:
                self.lista.setCurrentItem(item)
        self._filtrar(self.busca.text())
        self._atualizar_botoes()

    def simbolos(self) -> list[Simbolo]:
        return [self.lista.item(i).data(_PAPEL_SIMBOLO) for i in range(self.lista.count())]

    def _filtrar(self, texto: str) -> None:
        texto = texto.strip().lower()
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            simbolo: Simbolo = item.data(_PAPEL_SIMBOLO)
            item.setHidden(bool(texto) and texto not in f"{simbolo.nome} {simbolo.categoria}".lower())

    def _atualizar_botoes(self) -> None:
        self.botao_inserir.setEnabled(self.lista.currentItem() is not None)

    def _inserir_item(self, item: QListWidgetItem | None) -> None:
        if item is not None:
            simbolo: Simbolo = item.data(_PAPEL_SIMBOLO)
            self.inserir_simbolo.emit(str(simbolo.caminho), simbolo.nome)

    # ── Arrastar e soltar ────────────────────────────────────────────
    @staticmethod
    def _svgs_arrastados(evento) -> list[str]:
        dados = evento.mimeData()
        if not dados.hasUrls():
            return []
        return [u.toLocalFile() for u in dados.urls() if u.toLocalFile().lower().endswith(".svg")]

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802
        tipo = evento.type()
        if tipo in (QEvent.Type.DragEnter, QEvent.Type.DragMove) and self._svgs_arrastados(evento):
            evento.acceptProposedAction()
            return True
        if tipo == QEvent.Type.Drop and self._svgs_arrastados(evento):
            evento.acceptProposedAction()
            self.adicionar_svgs(self._svgs_arrastados(evento), perguntar_nome=True)
            return True
        return super().eventFilter(objeto, evento)

    def dragEnterEvent(self, evento) -> None:  # noqa: N802
        if self._svgs_arrastados(evento):
            evento.acceptProposedAction()

    def dropEvent(self, evento) -> None:  # noqa: N802
        if self._svgs_arrastados(evento):
            evento.acceptProposedAction()
            self.adicionar_svgs(self._svgs_arrastados(evento), perguntar_nome=True)

    # ── Símbolos do usuário ──────────────────────────────────────────
    def adicionar_svgs(self, caminhos: list[str] | None = None, perguntar_nome: bool | None = None) -> list[Path]:
        if caminhos is None:
            caminhos, _ = QFileDialog.getOpenFileNames(self, "Adicionar símbolos", "", "SVG (*.svg)")
            perguntar_nome = True if perguntar_nome is None else perguntar_nome
        novos = []
        self.pasta_usuario.mkdir(parents=True, exist_ok=True)
        for origem in map(Path, caminhos):
            if QSvgRenderer(str(origem)).isValid():
                nome = origem.stem
                if perguntar_nome:
                    # O nome do arquivo raramente diz o que é ("simbologia.svg").
                    nome, ok = QInputDialog.getText(
                        self, "Adicionar ao banco", f"Nome do símbolo ({origem.name}):", text=origem.stem
                    )
                    if not ok:
                        continue
                    nome = nome_de_arquivo(nome) or origem.stem
                destino = self._nome_livre(nome)
                shutil.copyfile(origem, destino)
                novos.append(destino)
        if novos:
            self.recarregar(selecionar=novos[0])
        elif caminhos:
            QMessageBox.warning(self, "Adicionar símbolos", "Não consegui abrir esse SVG.")
        return novos

    def adicionar_conteudo(self, conteudo_svg: str, nome: str) -> Path:
        """Um símbolo a partir do conteúdo (ex.: logotipo que está no layout)."""
        self.pasta_usuario.mkdir(parents=True, exist_ok=True)
        destino = self._nome_livre(nome_de_arquivo(nome) or "Símbolo")
        destino.write_text(conteudo_svg, encoding="utf-8")
        self.recarregar(selecionar=destino)
        return destino

    def substituir(self, simbolo: Simbolo, origem: str | Path) -> Path | None:
        """Troca o desenho de um símbolo pelo arquivo `origem`, mantendo o
        nome. Um de fábrica ganha uma cópia sua com o mesmo nome, que fica no
        lugar dele (ver `carregar_banco`)."""
        origem = Path(origem)
        if not QSvgRenderer(str(origem)).isValid():
            QMessageBox.warning(self, "Substituir símbolo", "Não consegui abrir esse SVG.")
            return None
        self.pasta_usuario.mkdir(parents=True, exist_ok=True)
        destino = simbolo.caminho if simbolo.do_usuario else self.pasta_usuario / f"{nome_de_arquivo(simbolo.nome)}.svg"
        shutil.copyfile(origem, destino)
        self.recarregar(selecionar=destino)
        return destino

    def _substituir(self, simbolo: Simbolo) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, f"Substituir “{simbolo.nome}”", "", "SVG (*.svg)")
        if caminho:
            self.substituir(simbolo, caminho)

    def voltar_ao_original(self, simbolo: Simbolo) -> None:
        if simbolo.substitui_de_fabrica:
            simbolo.caminho.unlink(missing_ok=True)
            self.recarregar()

    def importar_folha(self, caminho: str | None = None) -> list[Path]:
        if caminho is None:
            caminho, _ = QFileDialog.getOpenFileName(self, "Importar folha de símbolos", "", "SVG (*.svg)")
            if not caminho:
                return []
        try:
            svgs = separar_folha_svg(Path(caminho).read_text(encoding="utf-8", errors="replace"))
        except (ValueError, OSError) as exc:  # ET.ParseError é ValueError
            QMessageBox.warning(self, "Importar folha", f"Não consegui ler a folha:\n{exc}")
            return []
        if not svgs:
            QMessageBox.information(self, "Importar folha", "Não achei nenhum símbolo nesse arquivo.")
            return []
        novos = salvar_simbolos(svgs, self.pasta_usuario, prefixo=Path(caminho).stem)
        self.recarregar(selecionar=novos[0])
        return novos

    def _nome_livre(self, nome: str) -> Path:
        # Nome de um símbolo de fábrica também conta como ocupado: com o mesmo
        # nome o arquivo SUBSTITUIRIA o de fábrica (isso é só pelo "Substituir").
        de_fabrica = {nome_de_arquivo(s.nome).lower() for s in carregar_banco(None)}
        destino = self.pasta_usuario / f"{nome}.svg"
        n = 2
        while destino.exists() or destino.stem.lower() in de_fabrica:
            destino = self.pasta_usuario / f"{nome} {n}.svg"
            n += 1
        return destino

    def _menu_contexto(self, pos) -> None:
        item = self.lista.itemAt(pos)
        if item is None:
            return
        simbolo: Simbolo = item.data(_PAPEL_SIMBOLO)
        menu = QMenu(self)
        menu.addAction("Inserir no layout", lambda: self._inserir_item(item))
        menu.addSeparator()
        menu.addAction("Substituir por outro SVG…", lambda: self._substituir(simbolo))
        if simbolo.substitui_de_fabrica:
            menu.addAction("Voltar ao original", lambda: self.voltar_ao_original(simbolo))
        elif simbolo.do_usuario:
            menu.addAction("Renomear…", lambda: self._renomear(simbolo))
            menu.addAction("Apagar do banco", lambda: self._apagar(simbolo))
        menu.exec(self.lista.viewport().mapToGlobal(pos))

    def renomear(self, simbolo: Simbolo, nome: str) -> Path | None:
        nome = nome.strip().replace("/", "-").replace("\\", "-")
        if not nome or nome == simbolo.nome:
            return None
        destino = self._nome_livre(nome)
        simbolo.caminho.rename(destino)
        self.recarregar(selecionar=destino)
        return destino

    def _renomear(self, simbolo: Simbolo) -> None:
        nome, ok = QInputDialog.getText(self, "Renomear símbolo", "Nome:", text=simbolo.nome)
        if ok:
            self.renomear(simbolo, nome)

    def _apagar(self, simbolo: Simbolo) -> None:
        resposta = QMessageBox.question(self, "Apagar símbolo", f"Tirar “{simbolo.nome}” do banco de simbologias?")
        if resposta == QMessageBox.StandardButton.Yes:
            simbolo.caminho.unlink(missing_ok=True)
            self.recarregar()
