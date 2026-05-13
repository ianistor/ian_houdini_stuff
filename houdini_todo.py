import hou
import os
import json
import shutil
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtGui import QPixmap, QIcon, QColor, QGuiApplication
from PySide6.QtWidgets import QColorDialog

css = """
QWidget { color: #ffffff; background-color: #323232; }
QListWidget { background-color: #242424; }
QLineEdit { background-color: #4d4d4d; border: 1px solid #1e1e1e; border-radius: 4px; }
QPushButton { color: white; background-color: #4e4e4e; border: 1px solid #1e1e1e; border-radius: 4px; padding: 4px 8px; }
QPushButton:hover { border: 1px solid #ffa02f; }
QPushButton:pressed { background-color: #2d2d2d; }
QTextEdit { background-color: #242424; }
"""


class TodoListApp(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('IAN To-Do')
        self.setGeometry(100, 100, 460, 320)
        self.center()

        self.todo_file = None
        self.todo_data = []
        self.comment_dialog = None

        self.loadTodoList()
        self.initUI()

        self._hip_callback = self.onHipFileLoad
        hou.hipFile.addEventCallback(self.onHipFileLoad)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)

    def center(self):
        screen = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        center_point = screen.center()
        self.move(center_point - self.rect().center())

    def initUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.todo_list = QtWidgets.QListWidget()
        self.populateTodoList()

        input_layout = QtWidgets.QHBoxLayout()
        self.input_field = QtWidgets.QLineEdit()

        add_button = QtWidgets.QPushButton('Add')
        add_button.clicked.connect(self.addTodo)

        clear_button = QtWidgets.QPushButton('Clear All')
        clear_button.clicked.connect(self.clearAll)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(add_button)
        input_layout.addWidget(clear_button)

        layout.addWidget(self.todo_list)
        layout.addLayout(input_layout)
        close_button = QtWidgets.QPushButton('Close')
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        self.todo_list.itemDoubleClicked.connect(self.showOrUpdateCommentDialog)
        self.todo_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.todo_list.customContextMenuRequested.connect(self.showContextMenu)

    def _html_escape(self, txt):
        return txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def _build_html_from_todo(self, todo):
        # Newer format
        content = todo.get('content')
        if isinstance(content, list):
            parts = []
            for block in content:
                btype = block.get('type')
                if btype == 'html':
                    parts.append(block.get('html', ''))
                elif btype == 'text':
                    t = self._html_escape(block.get('text', '')).replace('\n', '<br/>')
                    parts.append(f"<p>{t}</p>")
                elif btype == 'image':
                    p = block.get('path')
                    if p:
                        parts.append(f"<p><img src='{QtCore.QUrl.fromLocalFile(p).toString()}'/></p>")
            if parts:
                return '\n'.join(parts)

        # Legacy fields fallback
        html = todo.get('comment_html', '')
        if html:
            return html

        comment = todo.get('comment', '')
        parts = []
        if comment:
            parts.append(f"<p>{self._html_escape(comment).replace(chr(10), '<br/>')}</p>")

        screenshot = todo.get('screenshot')
        if screenshot:
            parts.append(f"<p><img src='{QtCore.QUrl.fromLocalFile(screenshot).toString()}'/></p>")

        return '\n'.join(parts)

    def showOrUpdateCommentDialog(self, item):
        index = self.todo_list.row(item)
        html = self._build_html_from_todo(self.todo_data[index])

        if self.comment_dialog and self.comment_dialog.isVisible():
            if index == self.comment_dialog.current_index:
                return
            self.comment_dialog.close()

        self.comment_dialog = CommentDialog(html, index)
        self.comment_dialog.move(self.geometry().right(), self.geometry().top())
        self.comment_dialog.show()

    def showContextMenu(self, pos):
        menu = QtWidgets.QMenu(self)
        notes_action = menu.addAction("Show Notes")
        rename_action = menu.addAction("Rename Task")
        delete_action = menu.addAction("Delete Task")

        action = menu.exec(self.todo_list.mapToGlobal(pos))
        selected_items = self.todo_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        index = self.todo_list.row(item)

        if action == notes_action:
            self.showOrUpdateCommentDialog(item)
        elif action == rename_action:
            new_task, ok = QtWidgets.QInputDialog.getText(self, 'Rename Task', 'Enter new task name:', text=self.todo_data[index]['task'])
            if ok and new_task.strip():
                self.todo_data[index]['task'] = new_task.strip()
                self.saveTodoList()
                self.populateTodoList()
        elif action == delete_action:
            del self.todo_data[index]
            self.saveTodoList()
            self.populateTodoList()

    def loadTodoList(self):
        hipfile = hou.hipFile.path()
        if not hipfile:
            self.todo_data = []
            self.todo_file = os.path.join(os.path.expanduser('~'), 'untitled_todo.json')
            return
        hipfile_name = os.path.basename(hipfile)
        todo_file_name = hipfile_name.rsplit('.', 1)[0] + '_todo.json'
        self.todo_file = os.path.join(os.path.dirname(hipfile), todo_file_name)

        if os.path.exists(self.todo_file):
            with open(self.todo_file, 'r') as f:
                self.todo_data = json.load(f)
        else:
            self.todo_data = []

    def saveTodoList(self):
        with open(self.todo_file, 'w') as f:
            json.dump(self.todo_data, f, indent=4)

    def populateTodoList(self):
        self.todo_list.blockSignals(True)
        self.todo_list.clear()

        for todo in self.todo_data:
            item = QtWidgets.QListWidgetItem(todo['task'])
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if todo.get('completed') else QtCore.Qt.Unchecked)
            screenshot = todo.get('screenshot')
            if screenshot and os.path.exists(screenshot):
                pix = QPixmap(screenshot).scaled(24, 24, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                item.setIcon(QIcon(pix))
            self.todo_list.addItem(item)

        self.todo_list.blockSignals(False)
        try:
            self.todo_list.itemChanged.disconnect(self.updateTodoStatus)
        except Exception:
            pass
        self.todo_list.itemChanged.connect(self.updateTodoStatus)

    def addTodo(self):
        todo_text = self.input_field.text().strip()
        if not todo_text:
            QtWidgets.QMessageBox.warning(self, 'Warning', 'Please enter a task!')
            return
        self.todo_data.append({'task': todo_text, 'completed': False, 'comment': ''})
        self.saveTodoList()
        self.populateTodoList()
        self.input_field.clear()

    def updateTodoStatus(self, item):
        index = self.todo_list.row(item)
        self.todo_data[index]['completed'] = item.checkState() == QtCore.Qt.Checked
        self.saveTodoList()

    def clearAll(self):
        self.todo_data = []
        self.saveTodoList()
        self.populateTodoList()

    def onHipFileLoad(self, event_type):
        self.loadTodoList()
        self.populateTodoList()

    def closeEvent(self, event):
        if self.comment_dialog and self.comment_dialog.isVisible():
            self.comment_dialog.close()
        try:
            hou.hipFile.removeEventCallback(self._hip_callback)
        except Exception:
            pass
        super().closeEvent(event)


class CommentDialog(QtWidgets.QDialog):
    def __init__(self, initial_html, index):
        super().__init__()
        self.setWindowTitle('Notes')
        self.setGeometry(200, 200, 640, 480)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)

        self.current_index = index
        layout = QtWidgets.QVBoxLayout(self)

        toolbar = QtWidgets.QHBoxLayout()
        attach_btn = QtWidgets.QPushButton('Attach Image')
        paste_btn = QtWidgets.QPushButton('Paste Image (Ctrl+V)')
        attach_btn.clicked.connect(self.attachFromFile)
        paste_btn.clicked.connect(self.pasteFromClipboard)
        toolbar.addWidget(attach_btn)
        toolbar.addWidget(paste_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.textedit = QtWidgets.QTextEdit()
        self.textedit.setAcceptRichText(True)
        self.textedit.setHtml(initial_html or '')
        self._register_images_from_html(initial_html or '')
        layout.addWidget(self.textedit)

        buttons = QtWidgets.QHBoxLayout()
        save_button = QtWidgets.QPushButton('Save')
        cancel_button = QtWidgets.QPushButton('Cancel')
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_V and (event.modifiers() & QtCore.Qt.ControlModifier):
                return self.pasteFromClipboard()
        return super().eventFilter(obj, event)

    def _ensure_screens_dir(self):
        if todo_app.todo_file:
            base = os.path.dirname(todo_app.todo_file)
        else:
            base = os.path.expanduser('~')
        dest_dir = os.path.join(base, '.todo_screens')
        os.makedirs(dest_dir, exist_ok=True)
        return dest_dir

    def _insert_image_from_path(self, path):
        img = QtGui.QImage(path)
        if img.isNull():
            raise RuntimeError(f'Invalid image file: {path}')
        doc = self.textedit.document()
        url = QtCore.QUrl.fromLocalFile(path)
        doc.addResource(QtGui.QTextDocument.ImageResource, url, img)

        fmt = QtGui.QTextImageFormat()
        fmt.setName(url.toString())
        avail_w = max(120, self.textedit.viewport().width() - 40)
        width = min(avail_w, img.width())
        scale = width / img.width() if img.width() else 1.0
        fmt.setWidth(width)
        fmt.setHeight(img.height() * scale)

        cursor = self.textedit.textCursor()
        cursor.insertImage(fmt)
        cursor.insertText('\n')
        self.textedit.setTextCursor(cursor)
        self.textedit.ensureCursorVisible()
        self.textedit.viewport().update()
        QtWidgets.QApplication.processEvents()

    def attachFromFile(self):
        start_dir = os.path.dirname(hou.hipFile.path()) if hou.hipFile.path() else os.path.expanduser('~')
        filePath, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Choose Image', start_dir, 'Images (*.png *.jpg *.jpeg *.bmp)')
        if not filePath:
            return
        try:
            dest_dir = self._ensure_screens_dir()
            _, ext = os.path.splitext(filePath)
            stamp = int(__import__('time').time() * 1000)
            dest = os.path.join(dest_dir, f"todo_{self.current_index}_{stamp}{ext.lower()}")
            shutil.copy2(filePath, dest)
            self._insert_image_from_path(dest)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Attach failed", str(exc))

    def pasteFromClipboard(self):
        cb = QtGui.QGuiApplication.clipboard()
        md = cb.mimeData()
        dest_dir = self._ensure_screens_dir()
        stamp = int(__import__('time').time())

        # Prefer local image file urls when available (often the highest-fidelity source).
        if md.hasUrls():
            for url in md.urls():
                if not url.isLocalFile():
                    continue
                src = url.toLocalFile()
                if not os.path.exists(src):
                    continue
                ext = os.path.splitext(src)[1].lower()
                if ext not in {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'}:
                    continue
                dest = os.path.join(dest_dir, f"todo_{self.current_index}_{stamp}{ext}")
                shutil.copy2(src, dest)
                self._insert_image_from_path(dest)
                return True

        # Fallback: paste raster image bytes from clipboard.
        if md.hasImage():
            pix = cb.pixmap()
            if pix.isNull():
                img = cb.image()
                if img.isNull():
                    return False
                pix = QPixmap.fromImage(img)
            if pix.isNull():
                return False
            dest = os.path.join(dest_dir, f"todo_{self.current_index}_{stamp}.png")
            if not pix.save(dest, "PNG"):
                return False
            self._insert_image_from_path(dest)
            return True

        return False

    def _register_images_from_html(self, html):
        import re
        doc = self.textedit.document()
        for match in re.finditer(r"<img[^>]+src=['\"]([^'\"]+)['\"]", html, re.IGNORECASE):
            src = match.group(1)
            url = QtCore.QUrl(src)
            if url.isLocalFile():
                path = url.toLocalFile()
            elif src.startswith("file:"):
                path = QtCore.QUrl(src).toLocalFile()
            else:
                path = src
            if path and os.path.exists(path):
                img = QtGui.QImage(path)
                if not img.isNull():
                    doc.addResource(QtGui.QTextDocument.ImageResource, QtCore.QUrl.fromLocalFile(path), img)

    def accept(self):
        html = self.textedit.toHtml()
        todo_app.todo_data[self.current_index]['comment_html'] = html
        todo_app.todo_data[self.current_index]['comment'] = self.textedit.toPlainText()
        todo_app.todo_data[self.current_index]['content'] = [{'type': 'html', 'html': html}]
        first_img = None
        doc = self.textedit.document()
        block = doc.begin()
        while block.isValid() and first_img is None:
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.charFormat().isImageFormat():
                    img_fmt = QtGui.QTextImageFormat(frag.charFormat())
                    p = QtCore.QUrl(img_fmt.name()).toLocalFile()
                    if p and os.path.exists(p):
                        first_img = p
                        break
                it += 1
            block = block.next()
        if first_img:
            todo_app.todo_data[self.current_index]['screenshot'] = first_img
        todo_app.saveTodoList()
        todo_app.populateTodoList()
        super().accept()


class AnnotatorCanvas(QtWidgets.QWidget):
    def __init__(self, imagePath):
        super().__init__()
        self.pixmap = QPixmap(imagePath)
        self.setFixedSize(self.pixmap.size())
        self.penColor = QColor('red')
        self.penWidth = 3
        self.lastPoint = None
        self.history = [self.pixmap.copy()]

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)


class ImageAnnotatorDialog(QtWidgets.QDialog):
    def __init__(self, imagePath, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Annotate Screenshot')
        self.imagePath = imagePath
        self.savedPath = imagePath
        self.setMinimumSize(400, 300)

        self.canvas = AnnotatorCanvas(imagePath)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)

        controls = QtWidgets.QHBoxLayout()
        color_btn = QtWidgets.QPushButton('Color')
        size_spin = QtWidgets.QSpinBox()
        size_spin.setRange(1, 50)
        size_spin.setValue(3)
        save_btn = QtWidgets.QPushButton('Save')
        cancel_button = QtWidgets.QPushButton('Cancel')

        color_btn.clicked.connect(self.chooseColor)
        size_spin.valueChanged.connect(self.canvas.setPenWidth)
        save_btn.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        controls.addWidget(color_btn)
        controls.addWidget(QtWidgets.QLabel('Size'))
        controls.addWidget(size_spin)
        controls.addStretch()
        controls.addWidget(save_btn)
        controls.addWidget(cancel_button)
        layout.addLayout(controls)

    def chooseColor(self):
        color = QColorDialog.getColor(self.canvas.penColor, self)
        if color.isValid():
            self.canvas.setPenColor(color)

    def accept(self):
        self.canvas.pixmap.save(self.imagePath)
        self.savedPath = self.imagePath
        super().accept()


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
app.setStyleSheet(css)
try:
    if 'todo_app' in globals() and todo_app is not None and todo_app.isVisible():
        todo_app.raise_()
        todo_app.activateWindow()
    else:
        todo_app = TodoListApp()
        todo_app.setWindowFlags(todo_app.windowFlags() | QtCore.Qt.Window)
        todo_app.show()
except Exception:
    todo_app = TodoListApp()
    todo_app.setWindowFlags(todo_app.windowFlags() | QtCore.Qt.Window)
    todo_app.show()
