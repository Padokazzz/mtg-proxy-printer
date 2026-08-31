import logging
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, QSize, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..cli import configure_mode, run_generate
from ..config import AppConfig
from ..deck import parse_deck

# Paleta Magic: fundo escuro, dourado e os cinco pips de mana.
CSS = """
QWidget {
    background-color: #12141a;
    color: #ece9e1;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}
QGroupBox {
    background-color: #1b1e26;
    border: 1px solid #323846;
    border-radius: 10px;
    margin-top: 12px;
    padding: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #e6c66b;
    font-weight: 600;
}
QLineEdit {
    background-color: #232733;
    border: 1px solid #323846;
    border-radius: 8px;
    padding: 8px 10px;
    color: #ece9e1;
}
QLineEdit:focus { border: 1px solid #c9a227; }
QPlainTextEdit {
    background-color: #0d0f14;
    border: 1px solid #323846;
    border-radius: 8px;
    padding: 8px;
    color: #b9c0cf;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}
QPushButton {
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
    color: #12141a;
}
QPushButton:disabled { background-color: #2a2e38; color: #5a6072; }
QPushButton:hover:!disabled { filter: brightness(1.1); }
QPushButton:pressed:!disabled { filter: brightness(0.9); }

QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e6c66b, stop:1 #c9a227);
}
QPushButton#secondary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a86d4, stop:1 #2b6fb8);
    color: #f2f6ff;
}
QPushButton#danger {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0584a, stop:1 #c43d2f);
    color: #fff;
}
QPushButton#ghost {
    background-color: #232733;
    color: #cdd3e0;
    border: 1px solid #323846;
}
QProgressBar {
    border: 1px solid #323846;
    border-radius: 8px;
    background-color: #0d0f14;
    text-align: center;
    height: 18px;
    color: #ece9e1;
}
QProgressBar::chunk {
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #c9a227, stop:1 #e6c66b);
}
QLabel#status { color: #b9c0cf; }
QLabel#title { color: #e6c66b; font-size: 22px; font-weight: 700; }
QLabel#subtitle { color: #98a0b3; font-size: 12px; }
QLabel#pip { border-radius: 9px; border: 1px solid #00000055; }
"""

_MANA_COLORS = {
    "W": "#efe9d6",
    "U": "#2b7fd6",
    "B": "#1c1d22",
    "R": "#d6452f",
    "G": "#2c9d57",
}


class QtLogHandler(logging.Handler):
    def __init__(self, signal: Signal):
        super().__init__()
        self._signal = signal

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:  # pragma: no cover
            msg = record.getMessage()
        self._signal.emit(msg)


class Worker(QThread):
    logMessage = Signal(str)
    progressValue = Signal(int)
    progressPhase = Signal(str)
    cardImage = Signal(str, str)
    finished = Signal(dict)
    cancelled = Signal()
    error = Signal(str)

    def __init__(self, deck_text: str, config: AppConfig, output_dir, mode: str, deck_name=None):
        super().__init__()
        self.deck_text = deck_text
        self.config = config
        self.output_dir = output_dir
        self.mode = mode
        self.deck_name = deck_name
        self.cancel_event = threading.Event()

    def run(self) -> None:
        handler = QtLogHandler(self.logMessage)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger = logging.getLogger("mtg_proxy")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            cfg = configure_mode(self.config, self.mode)

            def on_progress(done: int, total: int, phase: str) -> None:
                base = 0 if phase == "Resolvendo" else 50
                pct = base + int(done / max(total, 1) * 50)
                self.progressValue.emit(pct)
                self.progressPhase.emit(phase)

            def on_card(name: str, path: str) -> None:
                self.cardImage.emit(name, path)

            stats = run_generate(
                self.deck_text, cfg, self.output_dir,
                on_progress=on_progress, cancel=self.cancel_event, on_card=on_card,
                deck_name=self.deck_name,
            )
            self.progressValue.emit(100)
            if self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.finished.emit(stats)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:  # pragma: no cover - reporta na UI
            self.error.emit(str(exc))
        finally:
            logger.removeHandler(handler)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, deck_path: Optional[str] = None,
                 output_dir: Optional[str] = None):
        super().__init__()
        self.config = config
        self.deck_text: Optional[str] = None
        self.worker: Optional[Worker] = None

        self.setWindowTitle("MTG Proxy Printer")
        self.resize(760, 600)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(CSS)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        root.addWidget(self._build_header())

        deck_box = QGroupBox("Deck")
        deck_layout = QHBoxLayout(deck_box)
        self.deck_edit = QLineEdit()
        self.deck_edit.setPlaceholderText("Caminho do deck.txt")
        deck_btn = QPushButton("Selecionar...")
        deck_btn.setObjectName("ghost")
        deck_btn.clicked.connect(self._select_deck)
        deck_layout.addWidget(self.deck_edit, 1)
        deck_layout.addWidget(deck_btn)
        root.addWidget(deck_box)

        out_box = QGroupBox("Pasta de saída")
        out_layout = QHBoxLayout(out_box)
        self.out_edit = QLineEdit()
        self.out_edit.setText(output_dir or str(config.output.directory))
        out_btn = QPushButton("Selecionar...")
        out_btn.setObjectName("ghost")
        out_btn.clicked.connect(self._select_output)
        out_layout.addWidget(self.out_edit, 1)
        out_layout.addWidget(out_btn)
        root.addWidget(out_box)

        self.status_label = QLabel("Selecione um arquivo de deck para começar.")
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("%v%")
        root.addWidget(self.progress)
        self.phase_label = QLabel("")
        self.phase_label.setObjectName("status")
        root.addWidget(self.phase_label)

        preview_box = QGroupBox("Pré-visualização das cartas")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.thumb_container = QWidget()
        self.thumb_layout = QGridLayout(self.thumb_container)
        self.thumb_layout.setContentsMargins(4, 4, 4, 4)
        self.thumb_layout.setSpacing(6)
        self.thumb_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.thumb_count = 0
        scroll.setWidget(self.thumb_container)
        preview_layout.addWidget(scroll)
        preview_box.setMaximumHeight(190)
        root.addWidget(preview_box)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(self.log, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.both_btn = QPushButton("Gerar Frente e Verso")
        self.both_btn.setObjectName("primary")
        self.front_btn = QPushButton("Gerar Somente Frente")
        self.front_btn.setObjectName("secondary")
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("danger")
        self.open_btn = QPushButton("Abrir PDF")
        self.open_btn.setObjectName("ghost")
        self.folder_btn = QPushButton("Abrir Pasta")
        self.folder_btn.setObjectName("ghost")
        self.both_btn.clicked.connect(lambda: self._start("duplex"))
        self.front_btn.clicked.connect(lambda: self._start("front"))
        self.cancel_btn.clicked.connect(self._cancel)
        self.open_btn.clicked.connect(self._open_pdf)
        self.folder_btn.clicked.connect(self._open_folder)
        self.cancel_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.folder_btn.setEnabled(False)
        btn_row.addWidget(self.both_btn)
        btn_row.addWidget(self.front_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.folder_btn)
        root.addLayout(btn_row)

        if deck_path:
            self.deck_edit.setText(deck_path)
            self._read_deck_file(deck_path)

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        logo_path = _resource("logo.png")
        if logo_path:
            logo = QLabel()
            logo.setPixmap(
                QPixmap(logo_path).scaled(
                    40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            logo.setStyleSheet("background: transparent;")
            layout.addWidget(logo)

        title_col = QVBoxLayout()
        title = QLabel("MTG Proxy Printer")
        title.setObjectName("title")
        sub = QLabel("Proxies de Magic para impressão — Scryfall")
        sub.setObjectName("subtitle")
        title_col.addWidget(title)
        title_col.addWidget(sub)
        layout.addLayout(title_col)
        layout.addStretch(1)
        pips = QHBoxLayout()
        pips.setSpacing(6)
        for sym, color in _MANA_COLORS.items():
            pip = QLabel()
            pip.setObjectName("pip")
            pip.setFixedSize(QSize(18, 18))
            pip.setStyleSheet(f"background-color: {color}; border-radius: 9px;")
            pip.setToolTip(f"Mana {sym}")
            pips.addWidget(pip)
        layout.addLayout(pips)
        return header

    def _select_deck(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar deck", "", "Arquivos de texto (*.txt);;Todos (*.*)"
        )
        if path:
            self.deck_edit.setText(path)
            self._read_deck_file(path)

    def _read_deck_file(self, path: str) -> None:
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except OSError as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível ler o arquivo:\n{exc}")
            return
        self.deck_text = text
        requests, errors = parse_deck(text, default_language=self.config.cards.default_language)
        total = sum(r.quantity for r in requests)
        unique = len({r.name for r in requests})
        self.status_label.setText(
            f"Cartas detectadas: {total} (em {unique} nomes únicos)"
            + (f" | {len(errors)} linha(s) com problema" if errors else "")
        )

    def _select_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Pasta de saída")
        if path:
            self.out_edit.setText(path)

    def _set_running(self, running: bool) -> None:
        self.both_btn.setEnabled(not running)
        self.front_btn.setEnabled(not running)
        if running:
            self.cancel_btn.setEnabled(True)
            self.open_btn.setEnabled(False)
            self.folder_btn.setEnabled(False)
        else:
            self.cancel_btn.setEnabled(False)

    def _start(self, mode: str) -> None:
        self.current_mode = mode
        if not self.deck_text:
            QMessageBox.warning(self, "Atenção", "Selecione um arquivo de deck primeiro.")
            return
        self._set_running(True)
        self.progress.setValue(0)
        self.progress.setStyleSheet("")
        self.phase_label.setText("")
        self.phase_label.setStyleSheet("")
        self.log.appendPlainText(f">> Cache de cartas: {self.config.cache_dir}")
        self._clear_thumbnails()
        self.log.appendPlainText(f">> Gerando modo: {mode}")

        output_dir = self.out_edit.text() or str(self.config.output.directory)
        self.worker = Worker(
            self.deck_text, self.config, output_dir, mode, deck_name=self.deck_edit.text()
        )
        self.worker.logMessage.connect(self._on_log)
        self.worker.progressValue.connect(self.progress.setValue)
        self.worker.progressPhase.connect(self.phase_label.setText)
        self.worker.cardImage.connect(self._add_thumbnail)
        self.worker.finished.connect(self._on_finished)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _cancel(self) -> None:
        if self.worker:
            self.worker.cancel_event.set()
        self.cancel_btn.setEnabled(False)
        self.phase_label.setText("Cancelando...")
        self.log.appendPlainText(">> Cancelando...")

    def _on_log(self, msg: str) -> None:
        self.log.appendPlainText(msg)
        self.log.moveCursor(QTextCursor.End)

    def _set_status(self, text: str, color: str) -> None:
        self.phase_label.setText(text)
        self.phase_label.setStyleSheet(f"color: {color};")

    def _clear_thumbnails(self) -> None:
        while self.thumb_layout.count():
            item = self.thumb_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.thumb_count = 0

    def _add_thumbnail(self, name: str, path: str) -> None:
        pix = QPixmap(path)
        if pix.isNull():
            return
        thumb = pix.scaled(76, 106, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        label = QLabel()
        label.setPixmap(thumb)
        label.setToolTip(name)
        label.setStyleSheet("border: 1px solid #323846; border-radius: 4px;")
        col = self.thumb_count % 6
        row = self.thumb_count // 6
        self.thumb_layout.addWidget(label, row, col)
        self.thumb_count += 1

    def _on_finished(self, stats: dict) -> None:
        self._set_running(False)
        self.open_btn.setEnabled(True)
        self.folder_btn.setEnabled(True)
        self.progress.setValue(100)
        self.progress.setStyleSheet(
            "QProgressBar::chunk { background: qlineargradient("
            "x1:0, y1:0, x2:1, y2:0, stop:0 #2c9d57, stop:1 #37c46d); }"
        )
        self._set_status("Concluído ✓", "#2c9d57")
        nf = stats.get("not_found") or []
        self.log.appendPlainText(
            f">> Concluído: {stats['requested']} cartas, {stats['pages']} páginas "
            f"(duplex={stats['duplex']}). Não encontradas: {len(nf)}"
        )
        for name in nf:
            self.log.appendPlainText(f"   [ERRO] {name}")

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self._set_status("Cancelado", "#e0a44a")
        self.log.appendPlainText(">> Geração cancelada.")

    def _on_error(self, msg: str) -> None:
        self._set_running(False)
        self._set_status("Erro", "#e0584a")
        self.log.appendPlainText(f">> ERRO: {msg}")
        QMessageBox.critical(self, "Erro na geração", msg)

    def _base_name(self) -> str:
        path = self.deck_edit.text().strip()
        return Path(path).stem if path else "deck"

    def _output_pdf(self) -> Path:
        out = Path(self.out_edit.text() or str(self.config.output.directory))
        name = "impressao" if getattr(self, "current_mode", "duplex") == "duplex" else "frente"
        return out / f"{self._base_name()}-{name}.pdf"

    def _open_pdf(self) -> None:
        pdf = self._output_pdf()
        if pdf.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf)))
        else:
            QMessageBox.information(self, "PDF", "O PDF ainda não foi gerado.")

    def _open_folder(self) -> None:
        out = Path(self.out_edit.text() or str(self.config.output.directory))
        out.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))


def _resource(name: str) -> Optional[str]:
    """Localiza um arquivo de recurso (logo, config), inclusive congelado."""
    candidates = [Path(name)]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / name)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / name)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def run(config: AppConfig, deck_path: Optional[str] = None,
        output_dir: Optional[str] = None) -> int:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    logo = _resource("logo.png")
    if logo:
        icon = QIcon(logo)
        app.setWindowIcon(icon)
    window = MainWindow(config, deck_path=deck_path, output_dir=output_dir)
    if logo:
        window.setWindowIcon(QIcon(logo))
    window.show()
    return app.exec()
