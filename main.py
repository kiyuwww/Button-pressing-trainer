# trainer.py (English version)
# Requires: PySide6, pynput
# pip install PySide6 pynput

import sys
import time
import threading
from queue import Queue, Empty

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QListWidget, QVBoxLayout,
    QHBoxLayout, QSlider, QSpinBox, QLineEdit, QMessageBox, QListWidgetItem,
    QInputDialog, QDialog, QFormLayout, QDialogButtonBox
)

from pynput import keyboard, mouse


def key_to_name(k):
    try:
        if hasattr(k, 'char') and k.char is not None:
            return k.char.upper()
        return str(k).replace("Key.", "").upper()
    except Exception:
        return str(k).upper()


def mouse_button_to_name(b):
    return {
        mouse.Button.left: "MOUSE_LEFT",
        mouse.Button.right: "MOUSE_RIGHT",
        mouse.Button.middle: "MOUSE_MIDDLE"
    }.get(b, str(b).upper())


class InputEvent:
    def __init__(self, kind, name):
        self.kind = kind
        self.name = name


class InputWatcher(QObject):
    received = Signal(object)

    def __init__(self):
        super().__init__()
        self._kb_listener = None
        self._ms_listener = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True

        def on_press(key):
            name = key_to_name(key)
            ev = InputEvent('key', name)
            self.received.emit(ev)

        def on_click(x, y, button, pressed):
            if not pressed:
                return
            name = mouse_button_to_name(button)
            ev = InputEvent('mouse', name)
            self.received.emit(ev)

        self._kb_listener = keyboard.Listener(on_press=on_press)
        self._ms_listener = mouse.Listener(on_click=on_click)
        self._kb_listener.start()
        self._ms_listener.start()

    def stop(self):
        self._running = False
        try:
            if self._kb_listener:
                self._kb_listener.stop()
        except: pass
        try:
            if self._ms_listener:
                self._ms_listener.stop()
        except: pass


class TrainerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KeyPress Trainer — 2025 Dark")
        self.setMinimumSize(800, 480)
        self._load_font()
        self._apply_dark_style()

        self.targets = []
        self.current_target = None
        self.running = False
        self.delay_ms = 750
        self.start_time = None
        self.hit_count = 0
        self.miss_count = 0
        self.times = []

        self.watcher = InputWatcher()
        self.watcher.received.connect(self.on_input_received)
        self.watcher.start()

        self._build_ui()

        self.switch_timer = QTimer(self)
        self.switch_timer.timeout.connect(self.show_next_target)

    def _load_font(self):
        try:
            font_id = QFontDatabase.addApplicationFont("Inter-Regular.ttf")
            fam = QFontDatabase.applicationFontFamilies(font_id)
            if fam:
                QApplication.setFont(QFont(fam[0], 12))
                return
        except:
            pass
        QApplication.setFont(QFont("Segoe UI", 11))

    def _apply_dark_style(self):
        self.setStyleSheet("""
            QWidget { background: #0b0b0c; color: #E6E6E6; }
            QLabel#title { font-size: 20pt; font-weight: 700; color: #FFFFFF; }
            QLabel#targetLabel { font-size: 48pt; font-weight: 900; color: #FFFFFF; }   /* WHITE BOLD */
            QPushButton { background: #121212; border: 1px solid #222; padding: 8px; border-radius: 10px; }
            QPushButton:hover { border: 1px solid #333; }
            QPushButton#start { background: #1a1a1a; padding: 12px; font-size: 14pt; }
            QListWidget { background: #070707; border: 1px solid #222; border-radius: 8px; padding: 6px; }
            QSpinBox, QLineEdit { background: #0b0b0c; border: 1px solid #222; padding: 6px; border-radius: 6px; }
            QSlider::groove:horizontal { height: 8px; background: #222; border-radius: 6px; }
            QSlider::handle:horizontal { background: #eee; width: 14px; margin: -3px; border-radius: 7px; }
        """)

    def _build_ui(self):
        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        title = QLabel("KeyPress Trainer")
        title.setObjectName("title")
        left.addWidget(title, alignment=Qt.AlignLeft)

        self.targetLabel = QLabel("-")
        self.targetLabel.setObjectName("targetLabel")
        self.targetLabel.setAlignment(Qt.AlignCenter)
        left.addStretch()
        left.addWidget(self.targetLabel, stretch=2)
        left.addStretch()

        controls = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("start")
        self.start_btn.clicked.connect(self.toggle_start)
        controls.addWidget(self.start_btn)

        self.next_btn = QPushButton("Skip")
        self.next_btn.clicked.connect(self.show_next_target)
        controls.addWidget(self.next_btn)

        left.addLayout(controls)

        stats = QHBoxLayout()
        self.hits_label = QLabel("Hits: 0")
        self.misses_label = QLabel("Misses: 0")
        self.avg_label = QLabel("Avg reaction: —")
        stats.addWidget(self.hits_label)
        stats.addWidget(self.misses_label)
        stats.addWidget(self.avg_label)
        left.addLayout(stats)

        layout.addLayout(left, 3)

        right = QVBoxLayout()
        right_title = QLabel("Settings & Keys")
        right_title.setStyleSheet("font-size: 14pt; font-weight:700;")
        right.addWidget(right_title)

        self.list_widget = QListWidget()
        right.addWidget(self.list_widget, stretch=2)

        btns = QHBoxLayout()
        add_btn = QPushButton("Add (typed)")
        add_btn.clicked.connect(self.add_by_text)
        btns.addWidget(add_btn)

        record_btn = QPushButton("Record key")
        record_btn.clicked.connect(self.record_next_press)
        btns.addWidget(record_btn)

        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self.remove_selected)
        btns.addWidget(remove_btn)

        right.addLayout(btns)

        form = QFormLayout()
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(50, 5000)
        self.delay_spin.setValue(self.delay_ms)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.valueChanged.connect(self.on_delay_changed)
        form.addRow("Delay:", self.delay_spin)

        self.delay_slider = QSlider(Qt.Horizontal)
        self.delay_slider.setRange(50, 2000)
        self.delay_slider.setValue(self.delay_ms)
        self.delay_slider.valueChanged.connect(self.on_delay_changed_slider)
        form.addRow("Adjust:", self.delay_slider)

        right.addLayout(form)

        info = QLabel("Supports keyboard and mouse buttons.\nSettings apply instantly.")
        info.setWordWrap(True)
        right.addWidget(info)

        foot = QHBoxLayout()
        reset_stats = QPushButton("Reset stats")
        reset_stats.clicked.connect(self.reset_stats)
        foot.addWidget(reset_stats)

        clear_targets = QPushButton("Clear keys")
        clear_targets.clicked.connect(self.clear_targets)
        foot.addWidget(clear_targets)
        right.addLayout(foot)

        layout.addLayout(right, 2)

    def add_target(self, name):
        if not name:
            return
        name = name.upper()
        if name in self.targets:
            return
        self.targets.append(name)
        self.list_widget.addItem(QListWidgetItem(name))

    def add_by_text(self):
        text, ok = QInputDialog.getText(self, "Add keys", "Enter keys separated by commas:")
        if not ok:
            return
        parts = [p.strip().upper() for p in text.split(",") if p.strip()]
        for p in parts:
            if p in ("LMB", "LEFT"): p = "MOUSE_LEFT"
            elif p in ("RMB", "RIGHT"): p = "MOUSE_RIGHT"
            elif p in ("MMB", "MIDDLE"): p = "MOUSE_MIDDLE"
            self.add_target(p)

    def record_next_press(self):
        dlg = RecordingDialog(self)
        if dlg.exec() == QDialog.Accepted:
            if dlg.result_name:
                self.add_target(dlg.result_name)

    def remove_selected(self):
        for item in self.list_widget.selectedItems():
            name = item.text()
            self.targets.remove(name)
            self.list_widget.takeItem(self.list_widget.row(item))
        if self.current_target and self.current_target not in self.targets:
            self.show_next_target()

    def clear_targets(self):
        self.targets.clear()
        self.list_widget.clear()
        self.current_target = None
        self.targetLabel.setText("-")

    def on_delay_changed(self, v):
        self.delay_ms = v
        self.delay_slider.setValue(v)
        if self.running:
            self.switch_timer.setInterval(self.delay_ms)

    def on_delay_changed_slider(self, v):
        self.delay_ms = v
        self.delay_spin.setValue(v)

    def toggle_start(self):
        if not self.running:
            if not self.targets:
                QMessageBox.warning(self, "No keys", "Add at least one key first.")
                return
            self.running = True
            self.start_btn.setText("Stop")
            self.switch_timer.start(self.delay_ms)
            self.show_next_target()
        else:
            self.running = False
            self.start_btn.setText("Start")
            self.switch_timer.stop()
            self.targetLabel.setText("-")
            self.current_target = None

    def show_next_target(self):
        if not self.targets:
            self.current_target = None
            self.targetLabel.setText("-")
            return
        import random
        self.current_target = random.choice(self.targets)
        self.targetLabel.setText(self.current_target)
        self.start_time = time.time()

    def on_input_received(self, ev):
        name = ev.name.upper()
        if not self.current_target:
            return
        if name == self.current_target:
            self.hit_count += 1
            reaction = (time.time() - self.start_time) * 1000.0
            self.times.append(reaction)
            self._update_stats()
            if self.running:
                self.switch_timer.start(self.delay_ms)
                self.show_next_target()
        else:
            self.miss_count += 1
            self._update_stats()

    def _update_stats(self):
        self.hits_label.setText(f"Hits: {self.hit_count}")
        self.misses_label.setText(f"Misses: {self.miss_count}")
        if self.times:
            avg = sum(self.times) / len(self.times)
            self.avg_label.setText(f"Avg reaction: {avg:.0f} ms")
        else:
            self.avg_label.setText("Avg reaction: —")

    def reset_stats(self):
        self.hit_count = 0
        self.miss_count = 0
        self.times = []
        self._update_stats()

    def closeEvent(self, event):
        self.watcher.stop()
        super().closeEvent(event)


class RecordingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record a key")
        self.setModal(True)
        self.setFixedSize(400, 180)
        self.result_name = None
        self._setup_ui()
        self._listener_kb = None
        self._listener_ms = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        lbl = QLabel("Press any keyboard or mouse button.\nPress ESC to cancel.")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        self.feedback = QLabel("Waiting for input...")
        self.feedback.setStyleSheet("font-weight:700; font-size:14px;")
        layout.addWidget(self.feedback)
        btns = QDialogButtonBox(QDialogButtonBox.Cancel)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        QTimer.singleShot(100, self._start_listening)

    def _start_listening(self):
        def on_press(key):
            if key == keyboard.Key.esc:
                self.reject()
                self._stop_listening()
                return
            name = key_to_name(key).upper()
            self.result_name = name
            self.feedback.setText(f"Captured: {self.result_name}")
            QTimer.singleShot(200, self._accept_and_stop)

        def on_click(x, y, button, pressed):
            if not pressed:
                return
            name = mouse_button_to_name(button).upper()
            self.result_name = name
            self.feedback.setText(f"Captured: {self.result_name}")
            QTimer.singleShot(200, self._accept_and_stop)

        self._listener_kb = keyboard.Listener(on_press=on_press)
        self._listener_ms = mouse.Listener(on_click=on_click)
        self._listener_kb.start()
        self._listener_ms.start()

    def _accept_and_stop(self):
        self._stop_listening()
        self.accept()

    def _stop_listening(self):
        try: self._listener_kb.stop()
        except: pass
        try: self._listener_ms.stop()
        except: pass

    def reject(self):
        self._stop_listening()
        super().reject()


def main():
    app = QApplication(sys.argv)
    w = TrainerWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
