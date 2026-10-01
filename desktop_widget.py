"""Compact, always-on-top desktop chat window for Kev AI."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import keyboard
from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from main_ollama import resolve_pending_edit, run_agent_turn


SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "Never use emojis in your replies. Use web search for current or recent events. "
        "Never use em dashes. Read the complete file before editing, use edit_file to "
        "propose a focused change, and wait for user approval before applying it. "
        "Never use write_file to modify an existing file."
    ),
}
HOTKEY = "ctrl+space"


class AgentWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, prompt: str | None, messages: list, pending_edit=None, approved=None):
        super().__init__()
        self.prompt = prompt
        self.messages = messages
        self.pending_edit = pending_edit
        self.approved = approved

    def run(self):
        try:
            if self.pending_edit is not None:
                result = resolve_pending_edit(self.pending_edit, self.approved, self.messages)
            else:
                result = run_agent_turn(self.prompt, self.messages)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(f"Couldn't reach the local agent: {exc}")


class EditReviewDialog(QDialog):
    def __init__(self, filename: str, diff: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review file edit")
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Review the proposed changes to {filename}:"))

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(diff)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.preview, 1)

        buttons = QDialogButtonBox()
        apply_button = buttons.addButton("Apply changes", QDialogButtonBox.ButtonRole.AcceptRole)
        reject_button = buttons.addButton("Reject", QDialogButtonBox.ButtonRole.RejectRole)
        apply_button.clicked.connect(self.accept)
        reject_button.clicked.connect(self.reject)
        layout.addWidget(buttons)


class KevWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("KevWidget")
        self.setWindowTitle("Kev AI")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        icon_path = Path(__file__).with_name("agent.ico")
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget { background: #17191f; color: #edf0f6; font: 10pt 'Segoe UI'; }"
            "QWidget#KevWidget { background: transparent; }"
            "QPushButton { background: #292d37; border: 0; border-radius: 8px; padding: 7px 10px; }"
            "QPushButton:hover { background: #383e4b; }"
            "QLineEdit, QPlainTextEdit { background: #20232b; border: 1px solid #343945; "
            "border-radius: 9px; padding: 9px; selection-background-color: #6378d3; }"
        )
        self.messages = [dict(SYSTEM_MESSAGE)]
        self._drag_offset: QPoint | None = None
        self._launcher_drag_offset: QPoint | None = None
        self._launcher_dragging = False
        self._thread: QThread | None = None
        self._worker: AgentWorker | None = None
        self._turn_result = None
        self.collapsed = True

        root = QVBoxLayout(self)
        root.setContentsMargins(3, 3, 3, 3)
        root.setSpacing(8)

        self.launcher_button = QToolButton()
        self.launcher_button.setToolTip("Open Kev AI")
        self.launcher_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launcher_button.setFixedSize(58, 58)
        self.launcher_button.setIcon(QIcon(str(icon_path)))
        self.launcher_button.setIconSize(QSize(46, 46))
        self.launcher_button.setStyleSheet(
            "QToolButton { background: transparent; border: 1px solid #343945; border-radius: 18px; padding: 5px; }"
            "QToolButton:hover { background: #292d37; border-color: #6378d3; }"
        )
        self.launcher_button.installEventFilter(self)
        self.launcher_button.clicked.connect(self.toggle_collapsed)
        root.addWidget(self.launcher_button)

        self.header = QWidget()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(2, 0, 2, 0)
        self.title_label = QLabel("●  Kev AI")
        self.title_label.setStyleSheet("font-weight: 600; color: #cbd4ff")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        self.collapse_button = QPushButton("−")
        self.collapse_button.setFixedWidth(34)
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        header_layout.addWidget(self.collapse_button)
        close_button = QPushButton("×")
        close_button.setFixedWidth(34)
        close_button.clicked.connect(self.hide)
        header_layout.addWidget(close_button)
        root.addWidget(self.header)

        self.body = QWidget()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        self.chat = QPlainTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setPlaceholderText("Your conversation with Kev will appear here.")
        body_layout.addWidget(self.chat, 1)
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Kev anything...")
        self.input.returnPressed.connect(self.submit)
        input_row.addWidget(self.input, 1)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.submit)
        input_row.addWidget(self.send_button)
        body_layout.addLayout(input_row)
        root.addWidget(self.body, 1)
        self.header.hide()
        self.body.hide()
        self.setFixedSize(64, 64)

        self.tray = QSystemTrayIcon(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self
        )
        tray_menu = QMenu()
        show_action = QAction("Show / hide Kev", self)
        show_action.triggered.connect(self.toggle_visible)
        tray_menu.addAction(show_action)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.setToolTip("Kev AI (Ctrl+Space)")
        self.tray.show()

        self._hotkey_thread = threading.Thread(target=self._register_hotkey, daemon=True)
        self._hotkey_thread.start()

    def _register_hotkey(self):
        try:
            keyboard.add_hotkey(HOTKEY, lambda: self.show_requested.emit())
            keyboard.wait()
        except Exception as exc:
            print(f"Global shortcut unavailable: {exc}", file=sys.stderr)

    show_requested = Signal()

    def toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self.input.setFocus()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visible()

    def toggle_collapsed(self):
        self.collapsed = not self.collapsed
        self.launcher_button.setVisible(self.collapsed)
        self.header.setVisible(not self.collapsed)
        self.body.setVisible(not self.collapsed)
        self.collapse_button.setText("+" if self.collapsed else "−")
        if self.collapsed:
            self.layout().setContentsMargins(3, 3, 3, 3)
            self.setMinimumSize(64, 64)
            self.setFixedSize(64, 64)
        else:
            self.setMinimumSize(340, 180)
            self.setMaximumSize(16777215, 16777215)
            self.resize(380, 480)
            self.layout().setContentsMargins(10, 10, 10, 10)
            self.input.setFocus()

    def submit(self):
        prompt = self.input.text().strip()
        if not prompt or self._thread is not None:
            return
        self.input.clear()
        self.chat.appendPlainText(f"You: {prompt}\n")
        self.send_button.setEnabled(False)
        self.input.setEnabled(False)
        self._start_worker(prompt=prompt)

    def _start_worker(self, prompt=None, pending_edit=None, approved=None):
        self.send_button.setEnabled(False)
        self.input.setEnabled(False)
        if not self.collapsed:
            self.title_label.setText("●  Kev AI · thinking…")
        self._turn_result = None
        self._thread = QThread(self)
        self._worker = AgentWorker(prompt, self.messages, pending_edit, approved)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_answer)
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._on_worker_stopped)
        self._thread.start()

    def _on_answer(self, result):
        self._turn_result = result

    def _on_error(self, message: str):
        self.chat.appendPlainText(f"Kev: {message}\n")

    def _on_worker_stopped(self):
        if self._worker:
            self._worker.deleteLater()
        if self._thread:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self.send_button.setEnabled(True)
        self.input.setEnabled(True)
        self.title_label.setText("●  Kev AI")
        if self._turn_result is not None:
            result = self._turn_result
            self._turn_result = None
            self._handle_turn_result(result)
        elif self.isVisible() and not self.collapsed:
            self.input.setFocus()

    def _handle_turn_result(self, result):
        if result.pending_edit:
            proposal = result.pending_edit["proposal"]
            dialog = EditReviewDialog(proposal["filename"], proposal["diff"], self)
            approved = dialog.exec() == QDialog.DialogCode.Accepted
            self._start_worker(pending_edit=result.pending_edit, approved=approved)
            return

        if result.answer:
            self.chat.appendPlainText(f"Kev: {result.answer}\n")
        if self.isVisible() and not self.collapsed:
            self.input.setFocus()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.header.geometry().contains(event.position().toPoint()):
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.launcher_button:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._launcher_drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                self._launcher_dragging = False
            elif (
                event.type() == QEvent.Type.MouseMove
                and self._launcher_drag_offset is not None
                and event.buttons() & Qt.MouseButton.LeftButton
            ):
                pointer = event.globalPosition().toPoint()
                if (
                    not self._launcher_dragging
                    and (pointer - (self._launcher_drag_offset + self.frameGeometry().topLeft())).manhattanLength()
                    >= QApplication.startDragDistance()
                ):
                    self._launcher_dragging = True
                    self.launcher_button.setDown(False)
                if self._launcher_dragging:
                    self.move(pointer - self._launcher_drag_offset)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                was_dragging = self._launcher_dragging
                self._launcher_drag_offset = None
                self._launcher_dragging = False
                if was_dragging:
                    return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        self.tray.hide()
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Kev AI")
    app.setQuitOnLastWindowClosed(False)
    widget = KevWidget()
    widget.show_requested.connect(widget.toggle_visible, Qt.ConnectionType.QueuedConnection)
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
