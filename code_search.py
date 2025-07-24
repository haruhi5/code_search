import sys
import subprocess
import os
from PyQt5.QtWidgets import (
    QStyle, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QLabel, QStyledItemDelegate
)
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtCore import Qt, QModelIndex, QSettings

class HighlightDelegate(QStyledItemDelegate):
    def __init__(self, keyword, parent=None):
        super().__init__(parent)
        self.keyword = keyword

    def paint(self, painter: QPainter, option, index: QModelIndex):
        text = index.data() or ""
        keyword = self.keyword

        if not keyword or keyword not in text:
            super().paint(painter, option, index)
            return

        # Paint selection background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            text_color = option.palette.highlightedText().color()
        else:
            text_color = option.palette.text().color()

        painter.save()
        painter.setFont(option.font)

        # Text layout (for full clipping and eliding support)
        x = option.rect.x()
        y = option.rect.y() + option.fontMetrics.ascent() + (option.rect.height() - option.fontMetrics.height()) // 2

        segments = text.split(keyword)
        for i, segment in enumerate(segments):
            painter.setPen(text_color)
            painter.drawText(x, y, segment)
            x += option.fontMetrics.width(segment)

            if i < len(segments) - 1:
                painter.setPen(QColor("red"))
                painter.drawText(x, y, keyword)
                x += option.fontMetrics.width(keyword)

        painter.restore()

class RipgrepTreeViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ripgrep Code Viewer with Highlighting + Persistent Path")
        self.resize(900, 600)

        self.settings = QSettings("DoodleLabs", "RipgrepCodeViewer")

        main_layout = QVBoxLayout()
        path_layout = QHBoxLayout()
        search_layout = QHBoxLayout()

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Set source root (e.g., /home/user/sdk)")
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_path)
        path_layout.addWidget(QLabel("SDK Path:"))
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Enter function/variable name (e.g. ath9k_hw_eeprom_init)")
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.perform_search)
        search_layout.addWidget(self.query_input)
        search_layout.addWidget(self.search_button)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File", "Line Preview"])
        self.tree.itemActivated.connect(self.open_file_location)

        main_layout.addLayout(path_layout)
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.tree)
        self.setLayout(main_layout)

        self.delegate = None
        self.load_last_path()

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select SDK/Project Root")
        if path:
            self.path_input.setText(path)
            self.save_last_path(path)

    def save_last_path(self, path):
        self.settings.setValue("last_sdk_path", path)

    def load_last_path(self):
        last_path = self.settings.value("last_sdk_path", "")
        if last_path:
            self.path_input.setText(last_path)

    def perform_search(self):
        self.tree.clear()
        keyword = self.query_input.text().strip()
        root_path = self.path_input.text().strip()

        if not keyword or not root_path:
            print("[WARN] Missing keyword or SDK path")
            return

        self.save_last_path(root_path)

        cmd = [
            "rg", "--no-ignore", "--color=never", "--with-filename", "--line-number",
            "--glob", "**/*.c", "--glob", "**/*.h", keyword
        ]

        print(f"[INFO] Running: {' '.join(cmd)}")
        print(f"[INFO] In directory: {root_path}")

        try:
            results = subprocess.check_output(
                cmd, cwd=root_path, universal_newlines=True, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            print("[ERROR] ripgrep returned non-zero exit code")
            print(e.output)
            return
        except FileNotFoundError:
            print("[ERROR] ripgrep (rg) is not installed or not in PATH")
            return

        print("[INFO] ripgrep output:")
        print(results)

        files = {}
        for line in results.strip().split('\n'):
            if ':' not in line:
                continue
            parts = line.split(':', 2)
            if len(parts) < 3:
                continue
            filepath, lineno, code = parts
            fullpath = os.path.join(root_path, filepath)
            if fullpath not in files:
                files[fullpath] = []
            files[fullpath].append((int(lineno), code.strip()))
            print(f"[DEBUG] Match: {fullpath}:{lineno} -> {code.strip()}")

        for filepath, lines in files.items():
            file_item = QTreeWidgetItem([filepath])
            for lineno, code in lines:
                child = QTreeWidgetItem([f"{filepath}:{lineno}", code])
                file_item.addChild(child)
            self.tree.addTopLevelItem(file_item)

        self.delegate = HighlightDelegate(keyword)
        self.tree.setItemDelegateForColumn(1, self.delegate)

    def open_file_location(self, item):
        text = item.text(0)
        if ':' in text:
            filepath, lineno = text.split(':', 1)
            print(f"[INFO] Opening file: {filepath} at line {lineno}")
            os.system(f'code -g "{filepath}":{lineno}')
        else:
            os.system(f'code "{text}"')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = RipgrepTreeViewer()
    viewer.show()
    sys.exit(app.exec_())
