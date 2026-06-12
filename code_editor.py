#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import base64
import re
import time
import traceback
import shutil
import tempfile
import atexit
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QLabel,
    QFileDialog, QMessageBox, QMenu, QStatusBar, QMenuBar,
    QStyleFactory, QTabWidget, QToolBar, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QDialog, QDialogButtonBox,
    QProgressDialog, QInputDialog, QScrollArea, QGraphicsView, QGraphicsScene,
    QLineEdit, QCompleter
)
from PyQt6.QtCore import Qt, QSize, QTimer, QFileSystemWatcher, pyqtSignal, QThread, QProcess, QStringListModel
from PyQt6.QtGui import QIcon, QFont, QColor, QSyntaxHighlighter, QTextDocument, QTextCursor, QTextCharFormat, QPainter, QKeySequence
from PyQt6.QtGui import QAction, QActionGroup, QFontDatabase, QPixmap, QShortcut
from PyQt6.QtCore import QDir, QFileInfo
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt6 import QtSvg
from PyQt6.QtSvg import QSvgRenderer

# WebEngine для встроенного браузера (Scratch IDE)
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtCore import QUrl
    HAVE_WEBENGINE = True
except ImportError:
    HAVE_WEBENGINE = False

# Alan AI
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'AlanTrain'))
from PyQt6.QtWidgets import QDockWidget
try:
    from alan_nn import AlanPanel
    HAVE_ALAN = True
except ImportError:
    HAVE_ALAN = False

try:
    from alan_nn import HAVE_TORCH
except ImportError:
    HAVE_TORCH = False

# QSerialPortInfo для COM портов (Arduino)
try:
    from PyQt6.QtSerialPort import QSerialPortInfo
    HAVE_SERIALPORT = True
except ImportError:
    HAVE_SERIALPORT = False

from pygments import highlight
from pygments.lexers import get_lexer_by_name, get_all_lexers, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from pygments.styles import get_all_styles
from pygments.token import Token
import mimetypes

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

VERSION = "1.0.0"
GITHUB_REPO = "anzerscript/alan-code-editor"  # замени на свой репозиторий
VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/version.json"

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.avif', '.ico', '.bmp'}

def _load_icon(path, size=16):
    """Load icon from SVG or PNG file → QIcon (size fixed)"""
    if not os.path.exists(path):
        return None
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    _, ext = os.path.splitext(path.lower())
    if ext == '.svg':
        renderer = QSvgRenderer(path)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
    else:
        src = QPixmap(path)
        if not src.isNull():
            pixmap = src.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return QIcon(pixmap) if not pixmap.isNull() else None

# backward compat
_load_svg_icon = _load_icon

class PygmentsHighlighter(QSyntaxHighlighter):
    """Подсветка синтаксиса через Pygments (яркие цвета)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lexer = None
        self._formats = {}

    def set_lexer(self, lexer):
        self.lexer = lexer
        self._formats = {}
        self.rehighlight()

    def highlightBlock(self, text):
        if not self.lexer:
            return
        try:
            for index, token, value in self.lexer.get_tokens_unprocessed(text):
                fmt = self._get_format(token)
                if fmt:
                    self.setFormat(index, len(value), fmt)
        except Exception:
            pass

    def _get_format(self, token):
        if token in self._formats:
            return self._formats[token]

        fmt = QTextCharFormat()
        color = None

        if token in Token.Keyword.Constant:
            color = "#FF79C6"
        elif token in Token.Keyword:
            color = "#FF79C6"
        elif token in Token.Keyword.Type:
            color = "#8BE9FD"
        elif token in Token.Name.Function:
            color = "#50FA7B"
        elif token in Token.Name.Class:
            color = "#8BE9FD"
        elif token in Token.Name.Decorator:
            color = "#FFB86C"
        elif token in Token.Name.Builtin:
            color = "#50FA7B"
        elif token in Token.Name.Exception:
            color = "#FF79C6"
        elif token in Token.Name.Namespace:
            color = "#8BE9FD"
        elif token in Token.Name.Tag:
            color = "#FF79C6"
        elif token in Token.Name.Attribute:
            color = "#50FA7B"
        elif token in Token.Name.Entity:
            color = "#F1FA8C"
        elif token in Token.Name.Other:
            color = "#F8F8F2"
        elif token in Token.Literal.String:
            color = "#F1FA8C"
        elif token in Token.Literal.String.Doc:
            color = "#6272A4"
        elif token in Token.Literal.String.Interpol:
            color = "#FFB86C"
        elif token in Token.Literal.String.Escape:
            color = "#FFB86C"
        elif token in Token.Literal.Number:
            color = "#BD93F9"
        elif token in Token.Literal.Date:
            color = "#BD93F9"
        elif token in Token.Comment:
            color = "#6272A4"
        elif token in Token.Comment.Special:
            color = "#FFB86C"
        elif token in Token.Operator:
            color = "#FF79C6"
        elif token in Token.Operator.Word:
            color = "#FF79C6"
        elif token in Token.Punctuation:
            color = "#F8F8F2"
        elif token in Token.Generic.Deleted:
            color = "#FF5555"
        elif token in Token.Generic.Inserted:
            color = "#50FA7B"
        elif token in Token.Generic.Emph:
            color = "#F8F8F2"
        elif token in Token.Generic.Strong:
            color = "#F8F8F2"
        elif token in Token.Generic.Subheading:
            color = "#BD93F9"
        elif token in Token.Generic.Heading:
            color = "#BD93F9"
        elif token in Token.Generic.Traceback:
            color = "#FF5555"
        elif token in Token.Error:
            color = "#FF5555"
        else:
            self._formats[token] = None
            return None

        fmt.setForeground(QColor(color))

        if token in Token.Keyword.Constant:
            fmt.setFontWeight(QFont.Weight.Bold)
        if token in Token.Name.Class:
            fmt.setFontWeight(QFont.Weight.Bold)
        if token in Token.Name.Tag:
            fmt.setFontWeight(QFont.Weight.Bold)
        if token in Token.Generic.Strong:
            fmt.setFontWeight(QFont.Weight.Bold)
        if token in Token.Generic.Heading:
            fmt.setFontWeight(QFont.Weight.Bold)

        self._formats[token] = fmt
        return fmt


class FirebaseRulesHighlighter(QSyntaxHighlighter):
    """Regex-based highlighter for Firebase Security Rules v2 (.rules)
    
    Token taxonomy:
      keyword.control         — service, match, allow, function, rules_version
      support.function.action — read, write, get, list, create, update, delete
      variable.language       — request, resource, auth, firestore, database, root
      variable.other.prop     — uid, token, email, name, phone_number, data
      variable.parameter      — {variable}, {variable=**}, $(variable)
      constant.language       — true, false, null
      string.quoted           — "..." | '...'
      comment.line            — // ...
      constant.numeric        — 123, 3.14
      keyword.operator        — ==, ===, !=, !==, <, >, <=, >=, in, &&, ||, and, or, not
      punctuation.separator   — =, :
    """
    TOKEN_COLORS = {
        'keyword.control':         '#C586C0',   # purple (VS Code control keywords)
        'support.function.action': '#50FA7B',   # green  (actions)
        'variable.language':       '#9CDCFE',   # light blue (global objects)
        'variable.other.prop':     '#FFB86C',   # orange (properties)
        'variable.parameter':      '#FFD700',   # gold, bold (path vars)
        'constant.language':       '#F1FA8C',   # yellow (true/false/null)
        'string.quoted':           '#F1FA8C',   # yellow
        'comment.line':            '#6272A4',   # grey-blue, italic
        'constant.numeric':        '#BD93F9',   # purple
        'keyword.operator':        '#FF79C6',   # pink
        'punctuation.separator':   '#FF79C6',   # pink
    }
    TOKENS_BOLD  = {'variable.parameter'}
    TOKENS_ITALIC = {'comment.line'}

    STRING_COMMENT_PATTERNS = [
        (re.compile(r'//[^\n]*'), 'comment.line'),
        (re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), 'string.quoted'),
        (re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), 'string.quoted'),
    ]

    OTHER_PATTERNS = [
        # group 1: control keywords
        (re.compile(r'\b(service|match|allow|function|rules_version)\b'), 'keyword.control', True),
        # group 2: action methods
        (re.compile(r'\b(read|write|get|list|create|update|delete)\b'), 'support.function.action', True),
        # group 3: path interpolation — {variable} and {variable=**}
        (re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*|\*{2}=[a-zA-Z_][a-zA-Z0-9_]*)\}'), 'variable.parameter', False),
        # group 3b: $(variable) syntax
        (re.compile(r'\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)'), 'variable.parameter', False),
        # group 4: language built-in objects
        (re.compile(r'\b(request|resource|auth|firestore|database|root)\b'), 'variable.language', True),
        # group 5: well-known property names
        (re.compile(r'\b(uid|token|email|name|phone_number)\b'), 'variable.other.prop', True),
        (re.compile(r'\b(data)\b'), 'variable.other.prop', True),
        # group 6: constants
        (re.compile(r'\b(true|false|null)\b'), 'constant.language', True),
        # group 7: numbers
        (re.compile(r'\b\d+(\.\d+)?\b'), 'constant.numeric', True),
        # group 8: comparison operators
        (re.compile(r'(===?|!==?|[<>]=?|\bin\b)'), 'keyword.operator', False),
        # group 9: logical operators
        (re.compile(r'\b(and|or|not)\b'), 'keyword.operator', True),
        (re.compile(r'&&|\|\|'), 'keyword.operator', False),
        (re.compile(r'!'), 'keyword.operator', False),
        # group 10: assignment / colon
        (re.compile(r'[=:]'), 'punctuation.separator', False),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._formats = {}

    def _get_format(self, token_type):
        if token_type in self._formats:
            return self._formats[token_type]
        fmt = QTextCharFormat()
        color = self.TOKEN_COLORS.get(token_type, '#F8F8F2')
        fmt.setForeground(QColor(color))
        if token_type in self.TOKENS_BOLD:
            fmt.setFontWeight(QFont.Weight.Bold)
        if token_type in self.TOKENS_ITALIC:
            fmt.setFontItalic(True)
        self._formats[token_type] = fmt
        return fmt

    def highlightBlock(self, text):
        n = len(text)
        if n == 0:
            return

        consumed = [False] * n

        for pattern, token_type in self.STRING_COMMENT_PATTERNS:
            for m in pattern.finditer(text):
                start, end = m.start(), m.end()
                if any(consumed[start:end]):
                    continue
                fmt = self._get_format(token_type)
                self.setFormat(start, end - start, fmt)
                for i in range(start, end):
                    consumed[i] = True

        for pattern, token_type, check_boundary in self.OTHER_PATTERNS:
            for m in pattern.finditer(text):
                start, end = m.start(), m.end()
                if any(consumed[start:end]):
                    continue
                if check_boundary:
                    if (start > 0 and re.match(r'\w', text[start-1])) or \
                       (end < n and re.match(r'\w', text[end])):
                        continue
                fmt = self._get_format(token_type)
                self.setFormat(start, end - start, fmt)
                for i in range(start, end):
                    consumed[i] = True


class FileLoaderThread(QThread):
    """Поток для фоновой загрузки файлов"""
    loaded = pyqtSignal(str, str)
    error = pyqtSignal(str, str)
    progress = pyqtSignal(str)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            size = os.path.getsize(self.filepath)
            self.progress.emit(f"Загрузка: {os.path.basename(self.filepath)} ({self.format_size(size)})")
            with open(self.filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            self.loaded.emit(self.filepath, content)
        except Exception as e:
            self.error.emit(self.filepath, str(e))

    @staticmethod
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class LineNumberArea(QWidget):
    """Область нумерации строк"""
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, event):
        self.editor._paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """Расширенный текстовый редактор с нумерацией строк и автодополнением"""
    def __init__(self):
        super().__init__()
        
        font = QFont("Consolas" if sys.platform == "win32" else "Monaco" if sys.platform == "darwin" else "Monospace")
        font.setPointSize(11)
        self.setFont(font)
        
        self.setTabStopDistance(40)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        self.highlighter = PygmentsHighlighter(self.document())
        
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_width()
        
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                margin: 0px;
            }
        """)
        
        # Автодополнение (IntelliSense)
        self._completion_language = "Python"
        self._completer = QCompleter([], self)
        self._completer.setWidget(self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setMaxVisibleItems(12)
        self._completer.activated[str].connect(self._insert_completion)
        
        # Настройка всплывающего окна
        popup = self._completer.popup()
        popup.setStyleSheet("""
            QAbstractItemView {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #555;
                selection-background-color: #264f78;
                selection-color: #ffffff;
                font-family: Consolas, monospace;
                font-size: 12px;
                padding: 2px;
            }
        """)
        
        self._tag_pairs = []
        self.textChanged.connect(self._on_text_changed)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #2d2d2d; color: #d4d4d4; border: 1px solid #555; }
            QMenu::item:selected { background-color: #264f78; }
        """)
        menu.exec(event.globalPos())
    
    def _on_text_changed(self):
        """Авто-триггер дополнения при вводе >= 2 символов + обновление пар тегов."""
        self._find_tag_pairs()
        self.line_number_area.update()
        if not self._completer.popup().isVisible():
            cursor = self.textCursor()
            word = self._word_under_cursor(cursor)
            if len(word) >= 2:
                self._show_completions()
    
    _TAG_OPEN = re.compile(r'<(orion|obj|snd|dspl|sstm|db|font)>$')
    _TAG_CLOSE = re.compile(r'<-(orion|obj|snd|dspl|sstm|db|font)>$')
    
    def _find_tag_pairs(self):
        """Найти парные теги <tag> / <-tag> на разных строках."""
        pairs = []
        stack = []
        doc = self.document()
        for bn in range(doc.blockCount()):
            blk = doc.findBlockByNumber(bn)
            text = blk.text().strip()
            m_open = self._TAG_OPEN.match(text)
            m_close = self._TAG_CLOSE.match(text)
            if m_open:
                stack.append((bn, m_open.group(1)))
            elif m_close:
                if stack and stack[-1][1] == m_close.group(1):
                    open_bn, _ = stack.pop()
                    if open_bn != bn:
                        pairs.append((open_bn, bn))
        self._tag_pairs = pairs
    
    def _word_under_cursor(self, cursor=None):
        """Извлечь слово слева от курсора."""
        if cursor is None:
            cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfWord, QTextCursor.MoveMode.KeepAnchor)
        return cursor.selectedText().strip()
    
    def _show_completions(self):
        cursor = self.textCursor()
        prefix = self._word_under_cursor(cursor)
        if not prefix or len(prefix) < 2:
            self._completer.popup().hide()
            return
        model, ok = CompletionEngine.get_model(self._completion_language)
        if not ok:
            self._completer.popup().hide()
            return
        self._completer.setModel(model)
        self._completer.setCompletionPrefix(prefix)
        cr = self.cursorRect(cursor)
        cr.setWidth(self._completer.popup().sizeHintForColumn(0) + 30)
        self._completer.complete(cr)
    
    def _insert_completion(self, text):
        """Вставить выбранное дополнение."""
        cursor = self.textCursor()
        # Найти начало текущего слова
        cursor.movePosition(QTextCursor.MoveOperation.StartOfWord, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.setTextCursor(cursor)
    
    def set_completion_language(self, lang):
        """Установить язык для автодополнения."""
        self._completion_language = lang
    
    def _line_number_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 10 + 8 * digits

    def _update_line_number_width(self):
        self.setViewportMargins(self._line_number_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self._line_number_width(), cr.height())

    def _paint_line_numbers(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#252526"))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        line_ht = self.fontMetrics().height()
        lw = self.line_number_area.width()
        line_y = {}  # block_number -> center Y
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#858585"))
                painter.drawText(0, top, lw - 5, line_ht,
                                 Qt.AlignmentFlag.AlignRight, str(block_number + 1))
                line_y[block_number] = top + line_ht // 2
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1
        painter.end()
        # Отрисовка линий связи для парных тегов
        if not self._tag_pairs:
            return
        visible_min = self.firstVisibleBlock().blockNumber()
        visible_max = visible_min
        b = self.firstVisibleBlock()
        while b.isValid():
            visible_max = b.blockNumber()
            b = b.next()
        painter2 = QPainter(self.line_number_area)
        painter2.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#569cd6"), 2)
        pen.setStyle(Qt.PenStyle.DotLine)
        painter2.setPen(pen)
        x = lw - 6
        for op, cl in self._tag_pairs:
            if cl < visible_min or op > visible_max:
                continue
            y1 = line_y.get(op)
            y2 = line_y.get(cl)
            if y1 is not None and y2 is not None:
                painter2.drawLine(x, y1, x, y2)
                painter2.drawLine(x - 3, y1, x + 3, y1)
                painter2.drawLine(x - 3, y2, x + 3, y2)
        painter2.end()
    
    def keyPressEvent(self, event):
        """Обработка клавиш: Tab для сниппетов, Ctrl+Space для дополнения."""
        # Ctrl+Space — принудительное дополнение
        if event.key() == Qt.Key.Key_Space and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            cursor = self.textCursor()
            word = self._word_under_cursor(cursor)
            if not word or len(word) < 2:
                # Если нечего дополнять — вставляем из буфера обмена
                return
            self._show_completions()
            return
        
        # Tab — расширение сниппета или выбор дополнения
        if event.key() == Qt.Key.Key_Tab:
            # Если дополнение активно — принять его
            if self._completer.popup().isVisible():
                selected = self._completer.popup().currentIndex()
                if selected.isValid():
                    text = selected.data()
                    self._insert_completion(text)
                    return
                self._completer.popup().hide()
            
            # Расширение сниппета
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
            line_text = cursor.selectedText().strip()
            snippet = CompletionEngine.get_snippet(self._completion_language, line_text)
            if snippet:
                cursor.removeSelectedText()
                cursor.insertText(snippet)
                self.setTextCursor(cursor)
                return
            
            # Обычная табуляция
            self.insertPlainText("    ")
            return
        
        # Enter — принять дополнение при активном попапе
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._completer.popup().isVisible():
            selected = self._completer.popup().currentIndex()
            if selected.isValid():
                text = selected.data()
                self._insert_completion(text)
                return
        
        super().keyPressEvent(event)


# ================================================================
# CompletionEngine — мультиязычный движок (46 языков)
# ================================================================

class CompletionEngine:
    _LANG_MAP_BUILT = False

    @classmethod
    def _init_lang_list(cls, name, words):
        setattr(cls, name, words)

    @classmethod
    def _build_maps(cls):
        if cls._LANG_MAP_BUILT:
            return
        
        # ── Языки, определённые ниже как class-attributes ──
        # PYTHON_KEYWORDS, JS_KEYWORDS, ARDUINO_KEYWORDS, SQL_KEYWORDS,
        # RUBY_KEYWORDS — уже существуют
        
        # ── Системные / Строгие ──
        cls._init_lang_list("Rust", [
            "fn", "let", "mut", "const", "static", "impl", "trait", "pub", "use", "mod",
            "struct", "enum", "match", "if", "else", "loop", "while", "for", "in", "return",
            "true", "false", "Option", "Result", "Ok", "Err", "Some", "None", "self", "Self",
            "Box", "Rc", "Arc", "RefCell", "Cell", "move", "ref", "as", "where", "type",
            "dyn", "async", "await", "unsafe", "extern", "macro_rules", "cfg", "derive",
            "vec!", "println", "format", "unwrap", "expect", "clone", "copy", "iter", "map",
            "String", "Vec", "HashMap", "HashSet", "i32", "u32", "f64", "bool", "char",
        ])
        cls._init_lang_list("Go", [
            "func", "package", "import", "var", "const", "type", "struct", "interface",
            "map", "chan", "select", "go", "defer", "range", "if", "else", "switch", "case",
            "default", "for", "break", "continue", "return", "fallthrough", "nil", "true",
            "false", "error", "string", "int", "bool", "float64", "byte", "rune", "uint",
            "make", "new", "len", "cap", "append", "copy", "close", "delete", "panic",
            "recover", "go func", "fmt.Println", "fmt.Sprintf", "fmt.Errorf",
            "http.Get", "http.ListenAndServe", "json.Marshal", "json.Unmarshal",
            "goroutine", "WaitGroup", "Mutex", "RWMutex", "interface{}",
        ])
        cls._init_lang_list("CSharp", [
            "using", "namespace", "class", "struct", "interface", "enum", "record",
            "public", "private", "protected", "internal", "static", "readonly", "virtual",
            "override", "abstract", "sealed", "async", "await", "partial", "event", "delegate",
            "if", "else", "switch", "case", "default", "for", "foreach", "while", "do",
            "break", "continue", "return", "throw", "try", "catch", "finally", "using var",
            "var", "new", "typeof", "nameof", "sizeof", "is", "as", "in", "out", "ref",
            "string", "int", "bool", "float", "double", "decimal", "long", "short", "byte",
            "void", "object", "dynamic", "null", "true", "false", "this", "base",
            "List", "Dictionary", "IEnumerable", "IQueryable", "Task", "ActionResult",
            "async Task", "Console.WriteLine", "Console.Read", "LINQ",
            "get; set;", "value", "yield return", "yield break",
        ])
        cls._init_lang_list("Java", [
            "public", "private", "protected", "static", "final", "abstract", "interface",
            "class", "extends", "implements", "enum", "record", "sealed", "permits",
            "void", "return", "if", "else", "switch", "case", "default", "for", "while",
            "do", "break", "continue", "new", "this", "super", "instanceof", "throws",
            "throw", "try", "catch", "finally", "synchronized", "volatile", "transient",
            "import", "package", "var", "null", "true", "false",
            "String", "int", "long", "double", "float", "boolean", "char", "byte", "short",
            "List", "ArrayList", "Map", "HashMap", "Set", "HashSet", "Optional",
            "Integer", "Double", "Boolean", "Object", "Class", "System.out.println",
            "java.util.", "java.io.", "java.net.", "java.nio.", "java.sql.",
            "public static void main", "override", "default", "lambda", "stream",
            "map", "filter", "reduce", "collect", "forEach", "sorted",
            "var", "record", "yield", "sealed", "permits",
        ])
        cls._init_lang_list("Swift", [
            "var", "let", "func", "class", "struct", "enum", "protocol", "extension",
            "import", "return", "if", "else", "switch", "case", "default", "for", "in",
            "while", "repeat", "break", "continue", "guard", "defer", "throw", "throws",
            "rethrows", "try", "catch", "do", "where", "associatedtype", "typealias",
            "public", "private", "internal", "fileprivate", "open", "static", "final",
            "override", "mutating", "nonmutating", "lazy", "weak", "unowned",
            "true", "false", "nil", "self", "super", "init", "deinit",
            "String", "Int", "Double", "Bool", "Array", "Dictionary", "Set", "Optional",
            "map", "filter", "reduce", "compactMap", "flatMap", "forEach", "sorted",
            "guard let", "if let", "switch", "as!", "as?", "is",
            "UIView", "UIViewController", "UITableView", "UICollectionView",
            "Codable", "Encodable", "Decodable", "Hashable", "Equatable", "Comparable",
        ])
        cls._init_lang_list("Kotlin", [
            "fun", "val", "var", "class", "object", "data class", "enum class", "sealed class",
            "interface", "abstract", "open", "override", "final", "inner", "companion",
            "import", "package", "return", "if", "else", "when", "for", "while", "do",
            "break", "continue", "try", "catch", "finally", "throw", "is", "!is",
            "as", "as?", "in", "!in", "this", "super", "null", "true", "false",
            "public", "private", "internal", "protected", "lateinit", "lazy",
            "suspend", "inline", "noinline", "crossinline", "reified",
            "String", "Int", "Double", "Float", "Boolean", "Long", "Short", "Byte",
            "List", "MutableList", "Map", "MutableMap", "Set", "MutableSet",
            "ArrayList", "HashMap", "HashSet", "Array",
            "println", "print", "readLine", "require", "check", "error",
            "let", "apply", "run", "with", "also", "takeIf", "takeUnless",
            "filter", "map", "forEach", "reduce", "fold", "sorted", "groupBy",
            "coroutineScope", "launch", "async", "await", "withContext",
        ])
        cls._init_lang_list("TypeScript", [
            "let", "const", "var", "function", "class", "interface", "type", "enum",
            "abstract", "implements", "extends", "public", "private", "protected",
            "readonly", "static", "declare", "namespace", "module", "export", "import",
            "from", "as", "is", "keyof", "typeof", "infer", "never", "unknown",
            "any", "void", "null", "undefined", "true", "false",
            "string", "number", "boolean", "symbol", "bigint",
            "Array", "Record", "Pick", "Omit", "Partial", "Required", "Readonly",
            "Promise", "async", "await", "if", "else", "switch", "case", "default",
            "for", "while", "do", "break", "continue", "return", "throw", "try",
            "catch", "finally", "new", "this", "super", "instanceof", "in",
            "console.log", "console.error", "console.warn",
            "document.getElementById", "document.querySelector",
            "addEventListener", "fetch", "then", "catch", "finally",
            "=>", "=> {", "map", "filter", "reduce", "forEach",
            "JSON.stringify", "JSON.parse",
        ])
        
        # ── Функциональные / Нишевые ──
        cls._init_lang_list("Haskell", [
            "module", "where", "import", "qualified", "hiding", "data", "type", "class",
            "instance", "deriving", "newtype", "let", "in", "if", "then", "else",
            "case", "of", "do", "return", "pure", "fmap", "map", "filter", "foldl",
            "foldr", "zip", "concat", "maybe", "either", "fst", "snd", "head",
            "tail", "init", "last", "take", "drop", "splitAt", "length", "reverse",
            "null", "elem", "notElem", "lookup", "show", "read", "print", "putStrLn",
            "getLine", "getChar", "interact", "readFile", "writeFile", "appendFile",
            "undefined", "error", "seq", "$", ".", "::", "=>", "->", "<-",
            "Int", "Integer", "Float", "Double", "Bool", "Char", "String", "Maybe",
            "Either", "IO", "[]", "Ord", "Eq", "Show", "Read", "Enum", "Bounded",
            "Functor", "Applicative", "Monad", "Foldable", "Traversable",
            "mapM", "mapM_", "forM", "forM_", "sequence", "sequence_",
            "liftM", "liftM2", "liftM3", "when", "unless", "forever",
        ])
        cls._init_lang_list("Elixir", [
            "def", "defmodule", "defp", "defstruct", "defprotocol", "defimpl",
            "defmacro", "defmacrop", "defguard", "defguardp", "defexception",
            "import", "alias", "use", "require", "quote", "unquote", "super",
            "if", "else", "unless", "cond", "case", "receive", "send",
            "true", "false", "nil", "and", "or", "not", "in", "is",
            "fn", "end", "do", "with", "for", "try", "rescue", "catch",
            "after", "else", "raise", "throw", "exit", "throw",
            "Enum", "List", "Map", "Tuple", "Atom", "String", "Integer",
            "Float", "Keyword", "Range", "Stream", "Agent", "GenServer",
            "Supervisor", "Task", "Task.async", "Task.await",
            "|>", "->", "=", "when", "inspect", "IO.puts", "IO.inspect",
            "elem", "put_elem", "map_size", "tuple_size",
        ])
        cls._init_lang_list("Scala", [
            "def", "val", "var", "class", "object", "trait", "case class", "case object",
            "abstract", "sealed", "final", "implicit", "implicitly", "given", "using",
            "match", "case", "if", "else", "for", "yield", "while", "do", "return",
            "throw", "try", "catch", "finally", "new", "this", "super", "with",
            "extends", "mixin", "import", "package", "type", "lazy", "override",
            "private", "protected", "public", "package",
            "null", "true", "false", "Unit", "Nothing", "Any", "AnyVal", "AnyRef",
            "Int", "Double", "Float", "Long", "Short", "Byte", "Char", "Boolean",
            "String", "Array", "List", "Map", "Set", "Option", "Some", "None",
            "Either", "Left", "Right", "Try", "Success", "Failure", "Future",
            "map", "filter", "flatMap", "foreach", "reduce", "fold", "collect",
            "zip", "groupBy", "sorted", "sortBy", "mkString",
            "println", "print", "readLine", "toString",
        ])
        cls._init_lang_list("Clojure", [
            "def", "defn", "defmacro", "defmethod", "defmulti", "defrecord",
            "deftype", "defprotocol", "definterface", "ns", "in-ns", "require",
            "use", "import", "refer", "let", "letfn", "binding", "loop", "recur",
            "if", "if-not", "when", "when-not", "cond", "case", "do", "doto",
            "->", "->>", "as->", "some->", "some->>", "and", "or", "not",
            "fn", "partial", "comp", "complement", "juxt", "constantly",
            "nil?", "some?", "true?", "false?", "zero?", "empty?",
            "list", "vector", "map", "set", "hash-map", "array-map",
            "assoc", "dissoc", "get", "get-in", "update", "update-in",
            "conj", "cons", "into", "merge", "select-keys", "keys", "vals",
            "first", "rest", "next", "last", "butlast", "take", "drop",
            "map", "filter", "reduce", "remove", "keep", "distinct",
            "println", "prn", "str", "symbol", "keyword", "name",
            "atom", "swap!", "reset!", "deref", "ref", "alter", "commute",
            "agent", "send", "send-off", "future", "delay", "promise",
        ])
        cls._init_lang_list("Erlang", [
            "-module", "-export", "-import", "-record", "-define", "-type", "-spec",
            "-callback", "-behaviour", "-compile", "when", "receive", "after",
            "case", "of", "if", "end", "fun", "and", "or", "not", "div", "rem",
            "true", "false", "ok", "error", "undefined", "self",
            "spawn", "spawn_link", "spawn_monitor", "send", "register",
            "whereis", "unregister", "registered", "monitor", "demonitor",
            "link", "unlink", "exit", "throw", "catch", "try", "of", "after",
            "list_to_tuple", "tuple_to_list", "list_to_atom", "atom_to_list",
            "length", "hd", "tl", "lists:map", "lists:filter", "lists:foldl",
            "lists:reverse", "lists:sort", "lists:foreach", "lists:seq",
            "maps:new", "maps:get", "maps:put", "maps:remove", "maps:keys",
            "io:format", "io:fwrite", "io:read", "file:read_file",
            "gen_server:start_link", "gen_server:call", "gen_server:cast",
            "supervisor:start_link", "application:start",
        ])
        cls._init_lang_list("COBOL", [
            "IDENTIFICATION DIVISION.", "PROGRAM-ID.", "AUTHOR.", "DATE-WRITTEN.",
            "ENVIRONMENT DIVISION.", "CONFIGURATION SECTION.", "SOURCE-COMPUTER.",
            "OBJECT-COMPUTER.", "INPUT-OUTPUT SECTION.", "FILE-CONTROL.",
            "DATA DIVISION.", "WORKING-STORAGE SECTION.", "LINKAGE SECTION.",
            "FILE SECTION.", "SCREEN SECTION.",
            "PROCEDURE DIVISION.", "USING", "RETURNING",
            "MOVE", "TO", "ADD", "TO", "GIVING", "SUBTRACT", "MULTIPLY", "DIVIDE",
            "COMPUTE", "ACCEPT", "DISPLAY", "SPACE", "ZERO", "QUOTE",
            "IF", "ELSE", "END-IF", "PERFORM", "THRU", "TIMES", "UNTIL", "VARYING",
            "AFTER", "FROM", "BY", "WHEN", "CONTINUE", "EXIT", "GO TO",
            "CALL", "CANCEL", "STOP RUN", "CLOSE", "OPEN", "READ", "WRITE",
            "DELETE", "REWRITE", "START", "RETURN",
            "SELECT", "ASSIGN", "ORGANIZATION", "ACCESS", "LOCK MODE",
            "PIC", "PICTURE", "9", "X", "A", "S9", "VALUE", "OCCURS", "TIMES",
            "REDEFINES", "RENAMES", "CONDITION", "INVALID KEY", "NOT INVALID KEY",
            "AT END", "NOT AT END", "SIZE ERROR", "NOT SIZE ERROR",
            "PIC X(10)", "PIC 9(5)", "PIC S9(5)V99",
        ])
        cls._init_lang_list("Fortran", [
            "program", "end program", "subroutine", "end subroutine", "function",
            "end function", "module", "end module", "submodule",
            "implicit none", "integer", "real", "double precision", "complex",
            "character", "logical", "parameter", "dimension", "allocatable",
            "pointer", "target", "save", "intent(in)", "intent(out)", "intent(inout)",
            "if", "then", "else", "else if", "end if", "do", "end do", "while",
            "select case", "case", "end select", "where", "elsewhere", "end where",
            "forall", "end forall", "cycle", "exit", "return", "stop",
            "open", "close", "read", "write", "format", "rewind", "backspace",
            "call", "contains", "interface", "end interface", "public", "private",
            "use", "import", "only", "operator", "assignment",
            "write(*,*)", "read(*,*)", "print*", "format", "continue",
            "array", "shape", "size", "lbound", "ubound", "reshape",
            "matmul", "dot_product", "transpose", "maxval", "minval", "sum",
        ])
        cls._init_lang_list("Assembly", [
            "mov", "push", "pop", "call", "ret", "jmp", "je", "jne", "jg", "jl",
            "jge", "jle", "jz", "jnz", "jc", "jnc", "jo", "jno", "js", "jns",
            "cmp", "test", "add", "sub", "mul", "div", "imul", "idiv", "inc",
            "dec", "neg", "and", "or", "xor", "not", "shl", "shr", "sar", "ror",
            "rol", "lea", "nop", "hlt", "int", "iret",
            "db", "dw", "dd", "dq", "dt", "resb", "resw", "resd", "resq",
            "global", "extern", "section", "segment", "align", "org",
            "section .text", "section .data", "section .bss",
            "proc", "endp", "assume", "offset", "ptr", "byte", "word",
            "dword", "qword", "tbyte", "far", "near",
            "eax", "ebx", "ecx", "edx", "esi", "edi", "esp", "ebp", "eip",
            "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rsp", "rbp", "rip",
            "ax", "bx", "cx", "dx", "al", "ah", "bl", "bh", "cl", "ch", "dl", "dh",
            "st0", "st1", "st2", "st3", "st4", "st5", "st6", "st7",
            "mm0", "mm1", "xmm0", "xmm1", "xmm2", "xmm3",
        ])
        cls._init_lang_list("Bash", [
            "#!/bin/bash", "#!/usr/bin/env bash",
            "if", "then", "else", "elif", "fi", "for", "in", "do", "done",
            "while", "until", "select", "case", "esac", "continue", "break",
            "exit", "return", "source", ".", "function", "declare", "local",
            "export", "readonly", "unset", "shift", "exec", "trap", "wait",
            "echo", "printf", "read", "set", "getopts",
            "test", "[", "[[", "]]", "-eq", "-ne", "-gt", "-lt", "-ge", "-le",
            "-f", "-d", "-e", "-s", "-z", "-n", "-r", "-w", "-x",
            "$?", "$@", "$#", "$*", "$$", "$!", "$0", "$1", "${}",
            "|", ">", ">>", "<", "<<", "<<<", "2>&1", "&>", "&",
            "$(command)", "$((arithmetic))", "`command`",
            "var=", '${var}', "$(pwd)", "$(ls)", "basename", "dirname",
            "grep", "sed", "awk", "cut", "sort", "uniq", "wc", "find",
            "xargs", "tee", "cat", "head", "tail", "tr", "diff", "patch",
        ])
        cls._init_lang_list("PowerShell", [
            "Write-Host", "Write-Output", "Write-Error", "Write-Warning",
            "Write-Verbose", "Write-Debug", "Read-Host",
            "Get-ChildItem", "Set-Location", "Get-Location",
            "Get-Content", "Set-Content", "Add-Content",
            "Get-Item", "Set-Item", "Remove-Item", "New-Item", "Copy-Item",
            "Move-Item", "Rename-Item", "Test-Path", "Join-Path", "Split-Path",
            "Get-Process", "Stop-Process", "Get-Service", "Start-Service",
            "Where-Object", "Select-Object", "ForEach-Object", "Sort-Object",
            "Group-Object", "Measure-Object", "Compare-Object",
            "New-Object", "Add-Type", "Get-Member", "Get-Command",
            "Get-Help", "Get-Alias", "Set-Alias", "Get-Variable",
            "Set-Variable", "Clear-Variable", "Remove-Variable",
            "Import-Module", "Export-Module", "New-Module",
            "if", "else", "elseif", "switch", "for", "foreach", "while",
            "do", "until", "continue", "break", "return", "exit",
            "function", "filter", "param", "begin", "process", "end",
            "try", "catch", "finally", "throw", "trap",
            "$_", "$this", "$input", "$args", "$true", "$false", "$null",
            "[int]", "[string]", "[bool]", "[array]", "[hashtable]",
            "-eq", "-ne", "-gt", "-lt", "-ge", "-le", "-like", "-notlike",
            "-match", "-notmatch", "-contains", "-notcontains", "-in", "-notin",
            "-and", "-or", "-not", "-xor", "-is", "-isnot", "-as",
            "Export-Csv", "Import-Csv", "ConvertTo-Json", "ConvertFrom-Json",
            "Out-File", "Out-GridView", "Format-Table", "Format-List", "Format-Wide",
        ])
        cls._init_lang_list("PLSQL", [
            "DECLARE", "BEGIN", "END", "EXCEPTION", "WHEN", "OTHERS",
            "IF", "THEN", "ELSE", "ELSIF", "END IF", "LOOP", "END LOOP",
            "WHILE", "FOR", "IN", "REVERSE", "EXIT", "WHEN", "CONTINUE",
            "CASE", "WHEN", "ELSE", "END CASE",
            "GOTO", "NULL", "RETURN",
            "PROCEDURE", "FUNCTION", "PACKAGE", "PACKAGE BODY",
            "CREATE OR REPLACE", "IS", "AS", "LANGUAGE SQL",
            "CURSOR", "OPEN", "FETCH", "CLOSE", "BULK COLLECT",
            "INTO", "FROM", "WHERE", "SET", "VALUES",
            "SELECT", "INSERT", "UPDATE", "DELETE", "MERGE",
            "COMMIT", "ROLLBACK", "SAVEPOINT", "SET TRANSACTION",
            "PRAGMA", "AUTONOMOUS_TRANSACTION", "SERIALLY_REUSABLE",
            "TYPE", "TABLE", "RECORD", "VARRAY", "NESTED TABLE",
            "INDEX BY", "BINARY_INTEGER", "PLS_INTEGER", "SIMPLE_INTEGER",
            "BOOLEAN", "DATE", "TIMESTAMP", "INTERVAL", "NUMBER",
            "VARCHAR2", "CHAR", "CLOB", "BLOB", "BFILE",
            "EXECUTE IMMEDIATE", "DBMS_OUTPUT.PUT_LINE",
            "DBMS_SQL", "UTL_FILE", "UTL_HTTP", "UTL_SMTP",
            "SYS_REFCURSOR", "SQL%ROWCOUNT", "SQL%FOUND", "SQL%NOTFOUND",
            "RAISE", "RAISE_APPLICATION_ERROR", "SQLERRM", "SQLCODE",
        ])
        cls._init_lang_list("HTML5", [
            "html", "head", "body", "title", "meta", "link", "style", "script",
            "header", "nav", "main", "section", "article", "aside", "footer",
            "h1", "h2", "h3", "h4", "h5", "h6",
            "p", "br", "hr", "span", "div", "blockquote", "pre",
            "a", "href", "img", "src", "alt", "figure", "figcaption",
            "ul", "ol", "li", "dl", "dt", "dd",
            "table", "thead", "tbody", "tfoot", "tr", "th", "td", "colgroup", "col",
            "form", "input", "textarea", "select", "option", "optgroup", "label",
            "button", "fieldset", "legend", "datalist", "output",
            "audio", "video", "source", "track", "canvas", "svg",
            "iframe", "embed", "object", "param",
            "template", "slot", "details", "summary", "dialog",
            "data", "time", "mark", "meter", "progress", "output",
            "<!DOCTYPE html>", "charset", "viewport", "color", "content",
            "class", "id", "style", "onclick", "onsubmit", "onload",
            "data-", "aria-", "role", "type", "name", "value", "placeholder",
        ])
        cls._init_lang_list("CSS", [
            "color", "background", "background-color", "background-image",
            "font", "font-family", "font-size", "font-weight", "font-style",
            "text-align", "text-decoration", "text-transform", "text-shadow",
            "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
            "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
            "border", "border-style", "border-width", "border-color", "border-radius",
            "width", "height", "min-width", "max-width", "min-height", "max-height",
            "display", "position", "top", "right", "bottom", "left",
            "z-index", "overflow", "overflow-x", "overflow-y", "visibility",
            "opacity", "transform", "transition", "animation", "box-shadow",
            "flex", "flex-direction", "flex-wrap", "flex-flow", "justify-content",
            "align-items", "align-content", "align-self", "flex-grow", "flex-shrink",
            "grid", "grid-template", "grid-template-columns", "grid-template-rows",
            "grid-column", "grid-row", "grid-area", "gap", "column-gap", "row-gap",
            "box-sizing", "float", "clear", "list-style", "cursor", "outline",
            "filter", "backdrop-filter", "clip-path", "mask",
            "@media", "@keyframes", "@font-face", "@supports", "@import",
            "!important", "inherit", "initial", "unset", "revert",
            ":hover", ":focus", ":active", ":visited", ":first-child",
            ":last-child", ":nth-child", ":before", ":after", "::before", "::after",
        ])
        cls._init_lang_list("JSON", [
            '"$schema":', '"$id":', '"$ref":', '"definitions":', '"properties":',
            '"items":', '"type":', '"required":', '"additionalProperties":',
            '"minimum":', '"maximum":', '"minLength":', '"maxLength":',
            '"pattern":', '"enum":', '"const":', '"default":', '"examples":',
            '"description":', '"title":', '"format":', '"if":', '"then":', '"else":',
            '"allOf":', '"anyOf":', '"oneOf":', '"not":',
            '"object"', '"array"', '"string"', '"number"', '"integer"', '"boolean"', '"null"',
        ])
        cls._init_lang_list("XML", [
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "xmlns", "xml:lang", "xml:space", "xsi:schemaLocation",
            "xs:schema", "xs:element", "xs:attribute", "xs:complexType",
            "xs:sequence", "xs:choice", "xs:all", "xs:simpleType",
            "xs:restriction", "xs:enumeration", "xs:pattern", "xs:minInclusive",
            "xs:annotation", "xs:documentation", "xs:appinfo",
            "xsl:stylesheet", "xsl:template", "xsl:value-of", "xsl:for-each",
            "xsl:if", "xsl:choose", "xsl:when", "xsl:otherwise",
            "xsl:sort", "xsl:variable", "xsl:param", "xsl:call-template",
            "xpath", "/", "//", ".", "..", "@", "text()", "node()",
            "soap:Envelope", "soap:Header", "soap:Body", "soap:Fault",
            "html", "head", "body", "div", "span", "table", "tr", "td",
        ])
        cls._init_lang_list("YAML", [
            "---", "...", "true", "false", "yes", "no", "on", "off", "null", "~",
            "#", "|", ">", "&", "*", "!", "!!", "<<", ":",
        ])
        cls._init_lang_list("Markdown", [
            "#", "##", "###", "####", "#####", "######",
            "*", "**", "***", "_", "__", "~~", "`", "```",
            ">", ">>", ">>>", "-", "+", "1.", "1)",
            "[", "](", ")", "![", "]", "[][]", "[^", "]:",
            "---", "***", "___", "<!--", "-->",
            "|", ":-", "-:", ":-:",
            "{::", "::}", "{%", "%}", "{{", "}}",
            "`code`", "```language", "```",
        ])
        cls._init_lang_list("PHP", [
            "<?php", "?>", "echo", "print", "die", "exit",
            "if", "else", "elseif", "switch", "case", "default",
            "for", "foreach", "while", "do", "break", "continue",
            "function", "return", "use", "namespace", "class",
            "extends", "implements", "abstract", "final", "trait",
            "public", "private", "protected", "static", "const",
            "new", "clone", "instanceof", "self", "parent", "this",
            "try", "catch", "throw", "finally",
            "include", "include_once", "require", "require_once",
            "define", "defined", "isset", "unset", "empty", "eval",
            "array", "list", "each", "count", "sizeof", "in_array",
            "strlen", "strpos", "substr", "str_replace", "explode",
            "implode", "trim", "htmlspecialchars", "json_encode",
            "json_decode", "file_get_contents", "file_put_contents",
            "null", "true", "false", "mixed", "void", "?string",
            "int", "float", "bool", "string", "array", "object",
            "_GET", "_POST", "_SESSION", "_COOKIE", "_SERVER",
            "SESSION", "COOKIE", "header",
        ])
        cls._init_lang_list("R", [
            "function", "if", "else", "repeat", "while", "for", "in",
            "next", "break", "return", "switch",
            "TRUE", "FALSE", "NA", "NULL", "Inf", "NaN",
            "c", "list", "matrix", "array", "data.frame", "factor",
            "character", "numeric", "integer", "logical", "complex",
            "length", "dim", "nrow", "ncol", "rownames", "colnames",
            "names", "str", "summary", "head", "tail", "View",
            "mean", "median", "sd", "var", "cor", "cov", "quantile",
            "min", "max", "range", "sum", "prod", "diff", "scale",
            "order", "rank", "sort", "rev", "unique", "table",
            "sample", "set.seed", "rnorm", "runif", "rbinom", "rpois",
            "dnorm", "pnorm", "qnorm", "dbinom", "pbinom",
            "lm", "glm", "aov", "summary.lm", "predict",
            "plot", "hist", "boxplot", "barplot", "pie", "scatter.smooth",
            "library", "require", "install.packages", "source",
            "read.csv", "read.table", "write.csv", "save", "load",
            "t.test", "chisq.test", "cor.test", "wilcox.test",
            "library(ggplot2)", "library(dplyr)", "library(tidyr)",
            "mutate", "filter", "select", "arrange", "group_by",
            "summarise", "ggplot", "aes", "geom_point", "geom_line",
        ])
        cls._init_lang_list("Dart", [
            "import", "export", "library", "part", "part of",
            "class", "extends", "implements", "mixin", "with", "abstract",
            "enum", "extension", "typedef", "covariant",
            "void", "var", "final", "const", "new", "late",
            "if", "else", "switch", "case", "default",
            "for", "while", "do", "break", "continue",
            "return", "throw", "try", "catch", "finally", "rethrow",
            "assert", "async", "await", "yield", "sync*", "async*",
            "true", "false", "null",
            "int", "double", "num", "String", "bool", "dynamic",
            "List", "Map", "Set", "Record",
            "print", "toString", "runtimeType",
            "this", "super", "required", "factory", "static",
            "get", "set", "operator", "override", "noSuchMethod",
            "main", "runApp", "MaterialApp", "Scaffold", "Container",
            "Row", "Column", "Stack", "Center", "Padding", "EdgeInsets",
            "Text", "TextField", "ElevatedButton", "IconButton",
            "Icon", "Image", "NetworkImage", "AssetImage",
            "AppBar", "Drawer", "BottomNavigationBar", "TabBar",
            "StatefulWidget", "StatelessWidget", "State", "BuildContext",
            "widget", "setState", "initState", "dispose", "build",
            "Navigator.push", "Navigator.pop", "MaterialPageRoute",
        ])
        cls._init_lang_list("Lua", [
            "function", "end", "if", "then", "else", "elseif", "do",
            "while", "repeat", "until", "for", "in", "break", "return",
            "local", "global", "nil", "true", "false", "not", "and", "or",
            "type", "print", "pairs", "ipairs", "next", "select",
            "tonumber", "tostring", "string", "table", "math", "io",
            "string.sub", "string.find", "string.gsub", "string.match",
            "string.len", "string.lower", "string.upper", "string.rep",
            "string.format", "table.insert", "table.remove", "table.sort",
            "table.concat", "table.unpack", "table.pack", "table.maxn",
            "math.floor", "math.ceil", "math.abs", "math.sqrt",
            "math.sin", "math.cos", "math.random", "math.randomseed",
            "io.open", "io.read", "io.write", "io.close", "io.lines",
            "os.date", "os.time", "os.execute", "os.rename", "os.remove",
            "require", "dofile", "loadfile", "module", "package",
            "coroutine.create", "coroutine.resume", "coroutine.yield",
            "coroutine.running", "coroutine.status",
            "self", ":", "__index", "__newindex", "__call", "__tostring",
            "setmetatable", "getmetatable", "rawset", "rawget", "rawequal",
        ])
        cls._init_lang_list("Perl", [
            "use strict;", "use warnings;", "use feature 'say';",
            "my", "our", "local", "state", "sub", "return",
            "if", "else", "elsif", "unless", "given", "when", "default",
            "for", "foreach", "while", "until", "do", "continue",
            "last", "next", "redo", "goto", "die", "exit", "warn",
            "print", "say", "printf", "sprintf", "open", "close",
            "<", ">", ">>", "<:", ">:", ">>:", "|", "-|",
            "chomp", "chop", "split", "join", "grep", "map",
            "sort", "reverse", "keys", "values", "each", "exists",
            "defined", "undef", "shift", "unshift", "push", "pop",
            "length", "substr", "index", "rindex", "lc", "uc",
            "=~", "!~", "eq", "ne", "lt", "gt", "le", "ge", "cmp",
            "=>", "->", "..", "...", "File::Spec", "Cwd",
            "use lib", "require", "no", "package",
            "$_", "$!", "$?", "$0", "$$", "$@", "$\\", "$|",
            "@_", "@ARGV", "@INC", "%ENV",
            "while (<>)", "chdir", "glob", "mkdir", "rmdir",
            "-e", "-f", "-d", "-z", "-s", "-r", "-w", "-x", "-o",
        ])
        cls._init_lang_list("Julia", [
            "function", "end", "if", "else", "elseif", "for", "while", "do",
            "try", "catch", "finally", "throw", "error", "return", "break",
            "continue", "let", "begin", "quote", "struct", "mutable struct",
            "primitive type", "abstract type", "const", "global", "local",
            "module", "baremodule", "using", "import", "export", "public",
            "macro", "quote", "escape", "gensym",
            "true", "false", "nothing", "missing", "undef", "Inf", "NaN",
            "Integer", "Int", "Int8", "Int16", "Int32", "Int64", "Int128",
            "Float64", "Float32", "Float16", "Bool", "Char", "String",
            "Vector", "Matrix", "Array", "Tuple", "Dict", "Set", "Pair",
            "Any", "Union", "Type", "DataType",
            "println", "print", "show", "readline", "read",
            "push!", "pop!", "append!", "size", "length", "eltype",
            "map", "filter", "reduce", "foldl", "foldr",
            "findall", "findfirst", "findnext", "sort", "sort!",
            "rand", "randn", "zeros", "ones", "fill", "range",
            "sqrt", "exp", "log", "sin", "cos", "tan", "abs",
            "maximum", "minimum", "sum", "prod", "mean", "std",
            "plot", "scatter", "histogram", "hline", "vline",
            "using DataFrames", "using Plots", "using Statistics",
        ])
        cls._init_lang_list("Groovy", [
            "def", "class", "interface", "trait", "enum", "implements", "extends",
            "public", "private", "protected", "static", "final", "abstract",
            "void", "return", "if", "else", "switch", "case", "default",
            "for", "while", "do", "break", "continue", "for in",
            "try", "catch", "finally", "throw", "assert",
            "new", "this", "super", "it", "as", "in", "is", "!instanceof",
            "null", "true", "false",
            "String", "int", "long", "double", "float", "boolean", "char",
            "List", "Map", "Set", "Range", "ArrayList", "HashMap",
            "println", "printf", "print",
            "each", "eachWithIndex", "find", "findAll", "collect",
            "inject", "any", "every", "groupBy", "sort", "unique",
            "grep", "flatten", "intersect", "disjoint", "union",
            "with", "tap", "use", "withDefault",
            "?.", "*.", "?.@", "*.@",
            "~", "=~", "==~", "<=>",
            "assert", "shouldFail", "expect",
            "import", "package", "mixin", "category",
        ])
        cls._init_lang_list("FSharp", [
            "let", "let rec", "let inline", "let mutable",
            "module", "namespace", "open", "type", "member",
            "val", "static", "member val", "abstract", "default",
            "override", "inherit", "interface", "implement",
            "class", "struct", "record", "union", "enum",
            "if", "then", "else", "elif",
            "match", "with", "|", "function",
            "for", "to", "downto", "in", "while", "do", "done",
            "try", "with", "finally", "raise", "failwith",
            "use", "using", "async", "await", "yield", "return",
            "true", "false", "null", "unit", "not", "&&", "||",
            "int", "float", "double", "decimal", "string", "bool",
            "char", "byte", "sbyte", "int16", "uint16", "int32",
            "uint32", "int64", "uint64", "nativeint", "unativeint",
            "list", "array", "seq", "option", "Some", "None",
            "Result", "Ok", "Error", "Choice",
            "List.map", "List.filter", "List.fold", "List.iter",
            "Array.map", "Array.filter", "Seq.map", "Seq.filter",
            "printfn", "printf", "sprintf", "failwithf",
            "ignore", "fst", "snd", "id", "const",
            "|>", ">>", "<<", "<|", "^",
            "typeof", "nameof", "sizeof",
        ])
        cls._init_lang_list("ObjectiveC", [
            "@interface", "@end", "@implementation", "@protocol",
            "@property", "@synthesize", "@dynamic", "@class",
            "@selector", "@encode", "@synchronized", "@try",
            "@catch", "@finally", "@throw", "@autoreleasepool",
            "@public", "@package", "@protected", "@private",
            "IBOutlet", "IBAction", "IBOutletCollection",
            "nullable", "nonnull", "null_resettable", "null_unspecified",
            "NSObject", "NSString", "NSArray", "NSDictionary", "NSSet",
            "NSInteger", "NSUInteger", "CGFloat", "BOOL", "YES", "NO",
            "nil", "Nil", "NULL", "self", "super", "_cmd",
            "alloc", "init", "new", "copy", "mutableCopy",
            "retain", "release", "autorelease", "dealloc",
            "NSLog", "@\"", "stringWithFormat",
            "if", "else", "switch", "case", "default",
            "for", "for in", "while", "do", "break", "continue",
            "return", "typedef", "enum", "struct", "union",
            "static", "extern", "const", "inline",
            "#import", "#include", "#define", "#ifdef", "#ifndef",
            "#endif", "#if", "#else", "#pragma", "#warning",
            "dispatch_async", "dispatch_sync", "dispatch_once",
            "__block", "__weak", "__strong", "__unsafe_unretained",
            "NSIntegerMax", "CGRectMake", "CGPointMake", "CGSizeMake",
        ])
        cls._init_lang_list("Pascal", [
            "program", "unit", "interface", "implementation", "uses",
            "begin", "end", "var", "const", "type", "label",
            "procedure", "function", "constructor", "destructor",
            "public", "private", "protected", "published",
            "class", "object", "record", "set", "file", "packed",
            "array", "of", "string", "integer", "real", "boolean",
            "char", "byte", "word", "longint", "shortint",
            "if", "then", "else", "case", "of", "otherwise",
            "for", "to", "downto", "while", "do", "repeat", "until",
            "with", "goto", "break", "continue", "exit", "halt",
            "read", "readln", "write", "writeln", "readkey",
            "assign", "reset", "rewrite", "append", "close",
            "new", "dispose", "nil", "true", "false",
            "inc", "dec", "abs", "sqr", "sqrt", "sin", "cos",
            "ord", "chr", "pred", "succ", "odd", "round", "trunc",
            "div", "mod", "shl", "shr", "and", "or", "xor", "not",
            "inherited", "self", "as", "is", "^", "@",
            "property", "read", "write", "default", "stored",
            "overload", "override", "reintroduce", "virtual",
            "dynamic", "abstract", "static", "final",
            "on", "except", "raise", "finally",
            "TStringList", "TList", "TCollection", "TStream",
            "ShowMessage", "MessageDlg", "InputBox",
        ])
        cls._init_lang_list("VBNet", [
            "Imports", "Module", "End Module", "Class", "End Class",
            "Structure", "End Structure", "Interface", "End Interface",
            "Enum", "End Enum", "Namespace", "End Namespace",
            "Public", "Private", "Protected", "Friend", "Shared",
            "Overridable", "Overrides", "NotOverridable", "MustOverride",
            "Shadows", "ReadOnly", "WriteOnly", "Partial",
            "Sub", "End Sub", "Function", "End Function",
            "Property", "End Property", "Get", "Set", "Let",
            "Dim", "Set", "New", "As", "Of", "Is", "IsNot",
            "If", "Then", "Else", "ElseIf", "End If",
            "Select", "Case", "End Select",
            "For", "To", "Step", "Next", "For Each", "In",
            "While", "End While", "Do", "Loop", "Until",
            "Try", "Catch", "Finally", "End Try",
            "Throw", "Return", "Exit", "Continue", "Stop",
            "Integer", "Long", "Short", "Byte", "Boolean",
            "String", "Char", "Date", "Decimal", "Double",
            "Single", "Object", "SByte", "UInteger", "ULong",
            "UShort", "UInteger", "Nothing", "True", "False",
            "Console.WriteLine", "Console.Read", "Console.ReadLine",
            "My.", "Me", "MyBase", "MyClass",
            "Handles", "WithEvents", "Event", "RaiseEvent",
            "AddHandler", "RemoveHandler", "Custom",
            "Inherits", "Implements", "MustInherit", "NotInheritable",
            "Widening", "Narrowing", "Operator", "TypeOf",
            "Using", "End Using", "SyncLock", "End SyncLock",
        ])
        cls._init_lang_list("MATLAB", [
            "function", "end", "if", "else", "elseif", "switch", "case",
            "otherwise", "for", "while", "break", "continue", "return",
            "try", "catch", "parfor", "spmd", "global", "persistent",
            "classdef", "properties", "methods", "events", "enumeration",
            "true", "false", "inf", "NaN", "eps", "pi", "i", "j",
            "double", "single", "int8", "int16", "int32", "int64",
            "uint8", "uint16", "uint32", "uint64", "logical", "char",
            "cell", "struct", "table", "categorical", "datetime",
            "zeros", "ones", "rand", "randi", "randn", "eye", "linspace",
            "size", "length", "numel", "ndims", "reshape", "repmat",
            "sum", "prod", "mean", "median", "std", "var", "min",
            "max", "abs", "sqrt", "exp", "log", "sin", "cos", "tan",
            "plot", "plot3", "scatter", "scatter3", "surf", "mesh",
            "bar", "histogram", "pie", "stem", "stairs",
            "xlabel", "ylabel", "zlabel", "title", "legend",
            "grid", "hold on", "hold off", "figure", "subplot",
            "clf", "close", "axis", "xlim", "ylim", "zlim",
            "disp", "fprintf", "sprintf", "input",
            "load", "save", "csvread", "csvwrite", "dlmread",
            "fopen", "fclose", "fread", "fwrite", "fscanf",
            "strcmp", "strfind", "regexp", "regexprep",
            "arrayfun", "cellfun", "structfun",
            "feval", "eval", "evalc",
        ])

        cls.LANG_MAP = {
            "Python": cls.PYTHON_KEYWORDS,
            "JavaScript": cls.JS_KEYWORDS,
            "TypeScript": cls.TypeScript,
            "Java": cls.Java,
            "C++": cls.ARDUINO_KEYWORDS,
            "C": cls.ARDUINO_KEYWORDS,
            "C#": cls.CSharp,
            "PHP": cls.PHP,
            "Go": cls.Go,
            "Rust": cls.Rust,
            "Swift": cls.Swift,
            "Kotlin": cls.Kotlin,
            "Ruby": cls.RUBY_KEYWORDS,
            "SQL": cls.SQL_KEYWORDS,
            "PL/SQL": cls.PLSQL,
            "R": cls.R,
            "Dart": cls.Dart,
            "Lua": cls.Lua,
            "MATLAB": cls.MATLAB,
            "Scala": cls.Scala,
            "Perl": cls.Perl,
            "Objective-C": cls.ObjectiveC,
            "Haskell": cls.Haskell,
            "Clojure": cls.Clojure,
            "Elixir": cls.Elixir,
            "Erlang": cls.Erlang,
            "F#": cls.FSharp,
            "Groovy": cls.Groovy,
            "Julia": cls.Julia,
            "Delphi/Pascal": cls.Pascal,
            "Visual Basic .NET": cls.VBNet,
            "COBOL": cls.COBOL,
            "Fortran": cls.Fortran,
            "Assembly": cls.Assembly,
            "Bash/Shell": cls.Bash,
            "PowerShell": cls.PowerShell,
            "HTML5": cls.HTML5,
            "CSS": cls.CSS,
            "JSON": cls.JSON,
            "XML": cls.XML,
            "YAML": cls.YAML,
            "Markdown": cls.Markdown,
            "Arduino": cls.ARDUINO_KEYWORDS,
        }

        cls.SNIPPET_MAP = {
            "Arduino": cls.ARDUINO_SNIPPETS,
            "C++": cls.ARDUINO_SNIPPETS,
            "C": cls.ARDUINO_SNIPPETS,
            "Python": cls.PYTHON_SNIPPETS,
            "JavaScript": cls.JS_SNIPPETS,
            "TypeScript": cls.JS_SNIPPETS,
            "SQL": cls.SQL_SNIPPETS,
            "PL/SQL": cls.SQL_SNIPPETS,
            "Bash/Shell": cls.BASH_SNIPPETS,
            "PowerShell": cls.POWERSHELL_SNIPPETS,
            "HTML5": cls.HTML_SNIPPETS,
            "CSS": cls.CSS_SNIPPETS,
            "Java": cls.JAVA_SNIPPETS,
            "C#": cls.CSHARP_SNIPPETS,
            "Go": cls.GO_SNIPPETS,
            "Rust": cls.RUST_SNIPPETS,
            "PHP": cls.PHP_SNIPPETS,
        }

        cls._LANG_MAP_BUILT = True

    # ── Python ────────────────────────────────────
    PYTHON_KEYWORDS = [
        "False", "None", "True", "and", "as", "assert", "async",
        "await", "break", "class", "continue", "def", "del", "elif",
        "else", "except", "finally", "for", "from", "global", "if",
        "import", "in", "is", "lambda", "nonlocal", "not", "or",
        "pass", "raise", "return", "try", "while", "with", "yield",
        "print", "len", "range", "int", "str", "float", "list",
        "dict", "set", "tuple", "type", "isinstance", "enumerate",
        "zip", "map", "filter", "sorted", "reversed", "open",
        "self", "cls", "super", "property", "staticmethod", "classmethod",
        "__init__", "__str__", "__repr__", "__len__", "__iter__",
        "__next__", "__getitem__", "__setitem__", "__call__",
    ]

    PYTHON_SNIPPETS = {
        "if": "if ${1:condition}:\n    ${2:pass}",
        "elif": "elif ${1:condition}:\n    ${2:pass}",
        "else": "else:\n    ${1:pass}",
        "for": "for ${1:i} in ${2:iterable}:\n    ${3:pass}",
        "while": "while ${1:condition}:\n    ${2:pass}",
        "def": "def ${1:name}(${2:args}):\n    ${3:pass}",
        "class": "class ${1:Name}:\n    def __init__(self, ${2:args}):\n        ${3:pass}",
        "try": "try:\n    ${1:pass}\nexcept ${2:Exception} as e:\n    ${3:pass}",
        "with": "with ${1:expr} as ${2:var}:\n    ${3:pass}",
        "import": "import ${1:module}",
        "ifmain": "if __name__ == '__main__':\n    ${1:pass}",
        "async": "async def ${1:name}(${2:args}):\n    ${3:pass}",
        "await": "${1:result} = await ${2:coroutine}",
        "lambda": "${1:fn} = lambda ${2:x}: ${3:expr}",
        "print": "print(${1:value})",
        "bubble_sort": "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n - 1):\n        for j in range(n - i - 1):\n            if arr[j] > arr[j + 1]:\n                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n    return arr",
        "quick_sort": "def quick_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quick_sort(left) + middle + quick_sort(right)",
    }

    # ── JavaScript ────────────────────────────────
    JS_KEYWORDS = [
        "async", "await", "break", "case", "catch", "class", "const",
        "continue", "debugger", "default", "delete", "do", "else",
        "export", "extends", "finally", "for", "function", "if",
        "import", "in", "instanceof", "let", "new", "of", "return",
        "static", "super", "switch", "this", "throw", "try", "typeof",
        "var", "void", "while", "with", "yield",
        "console.log", "console.error", "console.warn",
        "document.getElementById", "document.querySelector",
        "Array", "Object", "String", "Number", "Boolean",
        "map", "filter", "reduce", "forEach", "then", "catch",
        "undefined", "null", "true", "false", "NaN", "Infinity",
    ]

    JS_SNIPPETS = {
        "function": "function ${1:name}(${2:args}) {\n    ${3}\n}",
        "arrow": "const ${1:name} = (${2:args}) => {\n    ${3}\n}",
        "async": "async function ${1:name}(${2:args}) {\n    ${3}\n}",
        "for": "for (let ${1:i} = 0; ${1:i} < ${2:n}; ${1:i}++) {\n    ${3}\n}",
        "if": "if (${1:condition}) {\n    ${2}\n}",
        "foreach": "${1:arr}.forEach((${2:item}) => {\n    ${3}\n});",
        "console.log": "console.log(${1:value});",
        "class": "class ${1:Name} {\n    constructor(${2:args}) {\n        ${3}\n    }\n}",
    }

    # ── Arduino C/C++ ────────────────────────────
    ARDUINO_KEYWORDS = [
        "pinMode", "digitalWrite", "digitalRead", "analogWrite", "analogRead",
        "delay", "delayMicroseconds", "millis", "micros",
        "Serial.begin", "Serial.print", "Serial.println", "Serial.read",
        "Serial.available", "Serial.parseInt", "Serial.parseFloat",
        "map", "constrain", "abs", "min", "max", "pow", "sqrt",
        "attachInterrupt", "detachInterrupt", "interrupts", "noInterrupts",
        "tone", "noTone", "pulseIn", "shiftOut", "shiftIn",
        "INPUT", "OUTPUT", "INPUT_PULLUP", "HIGH", "LOW",
        "A0", "A1", "A2", "A3", "A4", "A5",
        "LED_BUILTIN", "true", "false",
        "void setup", "void loop",
    ]

    ARDUINO_SNIPPETS = {
        "pinMode": "pinMode(${1:pin}, ${2:OUTPUT});",
        "digitalWrite": "digitalWrite(${1:pin}, ${2:HIGH});",
        "analogWrite": "analogWrite(${1:pin}, ${2:value});",
        "delay": "delay(${1:ms});",
        "Serial.begin": "Serial.begin(${1:9600});",
        "Serial.print": "Serial.print(${1:value});",
        "Serial.println": "Serial.println(${1:value});",
    }

    # ── SQL ──────────────────────────────────────
    SQL_KEYWORDS = [
        "SELECT", "FROM", "WHERE", "INSERT INTO", "VALUES",
        "UPDATE", "SET", "DELETE", "CREATE TABLE", "DROP TABLE",
        "ALTER TABLE", "JOIN", "LEFT JOIN", "RIGHT JOIN",
        "INNER JOIN", "ON", "AS", "AND", "OR", "NOT",
        "IN", "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL",
        "ORDER BY", "GROUP BY", "HAVING", "LIMIT", "OFFSET",
        "DISTINCT", "COUNT", "SUM", "AVG", "MIN", "MAX",
        "ASC", "DESC", "TRUE", "FALSE", "NULL",
        "users", "products", "orders", "categories",
        "id", "name", "age", "email", "city", "price", "quantity",
    ]

    SQL_SNIPPETS = {
        "select": "SELECT * FROM ${1:table} WHERE ${2:condition};",
        "select_all": "SELECT * FROM ${1:table};",
        "insert": "INSERT INTO ${1:table} (${2:columns}) VALUES (${3:values});",
        "update": "UPDATE ${1:table} SET ${2:column} = ${3:value} WHERE ${4:condition};",
        "delete": "DELETE FROM ${1:table} WHERE ${2:condition};",
        "create": "CREATE TABLE ${1:name} (\n  ${2:id} ${3:INTEGER PRIMARY KEY}\n);",
        "join": "SELECT * FROM ${1:t1} JOIN ${2:t2} ON ${3:condition};",
        "group": "SELECT ${1:col}, COUNT(*) FROM ${2:table} GROUP BY ${1:col};",
    }

    # ── Ruby ────────────────────────────────────
    RUBY_KEYWORDS = [
        "def", "class", "module", "include", "extend", "prepend", "require",
        "attr_reader", "attr_writer", "attr_accessor",
        "if", "else", "elsif", "unless", "then", "case", "when", "end",
        "for", "while", "until", "do", "break", "next", "redo", "retry",
        "return", "yield", "lambda", "proc", "block_given?",
        "begin", "rescue", "ensure", "raise", "throw", "catch",
        "nil", "true", "false", "self", "super",
        "public", "private", "protected", "module_function",
        "Integer", "Float", "String", "Symbol", "Array", "Hash",
        "true", "false", "nil",
        "puts", "print", "p", "gets", "chomp",
        "each", "map", "select", "reject", "reduce", "inject",
        "sort", "uniq", "flatten", "compact", "empty?",
        "new", "initialize", "to_s", "to_i", "to_f", "to_sym",
        "||=", "&.", "=>", "->", "=~",
        "Rails", "ActiveRecord", "ActionController",
        "has_many", "belongs_to", "validates", "before_action",
        "render", "redirect_to", "params", "session", "flash",
    ]

    # ── Bash snippets ────────────────────────────
    BASH_SNIPPETS = {
        "if": "if [ ${1:condition} ]; then\n    ${2}\nfi",
        "for": "for ${1:i} in ${2:list}; do\n    ${3}\ndone",
        "while": "while [ ${1:condition} ]; do\n    ${2}\ndone",
        "case": "case ${1:var} in\n    ${2:pattern})\n        ${3};;\nesac",
        "function": "function ${1:name} {\n    ${2}\n}",
        "read": "read -p \"${1:prompt}: \" ${2:var}",
        "heredoc": "cat << ${1:EOF}\n${2}\n${1:EOF}",
    }

    POWERSHELL_SNIPPETS = {
        "if": "if (${1:condition}) {\n    ${2}\n}",
        "for": "for (${1:i}=0; ${1:i} -lt ${2:n}; ${1:i}++) {\n    ${3}\n}",
        "foreach": "foreach (${1:item} in ${2:collection}) {\n    ${3}\n}",
        "function": "function ${1:Name} {\n    param(${2:args})\n    ${3}\n}",
        "try": "try {\n    ${1}\n} catch {\n    ${2}\n}",
        "class": "class ${1:Name} {\n    ${2}\n}",
    }

    HTML_SNIPPETS = {
        "html": "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>${1:Document}</title>\n</head>\n<body>\n    ${2}\n</body>\n</html>",
        "script": "<script>\n    ${1}\n</script>",
        "style": "<style>\n    ${1}\n</style>",
        "div": "<div class=\"${1:class}\">\n    ${2}\n</div>",
        "a": "<a href=\"${1:url}\">${2:text}</a>",
        "img": "<img src=\"${1:src}\" alt=\"${2:alt}\">",
        "form": "<form action=\"${1:url}\" method=\"${2:post}\">\n    ${3}\n</form>",
        "input": "<input type=\"${1:text}\" name=\"${2:name}\" placeholder=\"${3:placeholder}\">",
        "ul": "<ul>\n    <li>${1:item}</li>\n</ul>",
        "table": "<table>\n    <thead>\n        <tr>\n            <th>${1:header}</th>\n        </tr>\n    </thead>\n    <tbody>\n        <tr>\n            <td>${2:data}</td>\n        </tr>\n    </tbody>\n</table>",
    }

    CSS_SNIPPETS = {
        "flex": "display: flex;\njustify-content: ${1:center};\nalign-items: ${2:center};",
        "grid": "display: grid;\ngrid-template-columns: ${1:1fr};\ngap: ${2:10px};",
        "media": "@media (max-width: ${1:768px}) {\n    ${2}\n}",
        "keyframes": "@keyframes ${1:name} {\n    0% { ${2} }\n    100% { ${3} }\n}",
        "fontface": "@font-face {\n    font-family: '${1:name}';\n    src: url('${2:path}');\n}",
        "reset": "* {\n    margin: 0;\n    padding: 0;\n    box-sizing: border-box;\n}",
    }

    JAVA_SNIPPETS = {
        "class": "public class ${1:Name} {\n    ${2}\n}",
        "main": "public static void main(String[] args) {\n    ${1}\n}",
        "method": "public ${1:void} ${2:method}(${3:args}) {\n    ${4}\n}",
        "if": "if (${1:condition}) {\n    ${2}\n}",
        "for": "for (${1:int i = 0}; ${1:i < n}; ${1:i++}) {\n    ${2}\n}",
        "foreach": "for (${1:Type} ${2:item} : ${3:items}) {\n    ${4}\n}",
        "try": "try {\n    ${1}\n} catch (${2:Exception} e) {\n    ${3}\n}",
        "list": "List<${1:String}> list = new ArrayList<>();",
        "map": "Map<${1:String}, ${2:Integer}> map = new HashMap<>();",
    }

    CSHARP_SNIPPETS = {
        "class": "class ${1:Name} {\n    ${2}\n}",
        "main": "static void Main(string[] args) {\n    ${1}\n}",
        "prop": "public ${1:int} ${2:Property} { get; set; }",
        "propfull": "private ${1:int} _${2:field};\npublic ${1:int} ${3:Property} {\n    get => _${2:field};\n    set { _${2:field} = value; }\n}",
        "if": "if (${1:condition}) {\n    ${2}\n}",
        "for": "for (${1:int i = 0}; ${1:i < n}; ${1:i++}) {\n    ${2}\n}",
        "foreach": "foreach (${1:var} ${2:item} in ${3:collection}) {\n    ${4}\n}",
        "try": "try {\n    ${1}\n} catch (${2:Exception} e) {\n    ${3}\n}",
        "linq": "var result = from ${1:item} in ${2:source}\n            where ${3:condition}\n            select ${1:item};",
    }

    GO_SNIPPETS = {
        "func": "func ${1:name}(${2:args}) ${3:error} {\n    ${4}\n}",
        "if": "if ${1:condition} {\n    ${2}\n}",
        "for": "for ${1:i} := 0; ${1:i} < ${2:n}; ${1:i}++ {\n    ${3}\n}",
        "range": "for ${1:i}, ${2:v} := range ${3:slice} {\n    ${4}\n}",
        "switch": "switch ${1:val} {\ncase ${2}:\n    ${3}\n}",
        "struct": "type ${1:Name} struct {\n    ${2:field} ${3:string}\n}",
        "interface": "type ${1:Name} interface {\n    ${2:Method()} ${3:error}\n}",
        "goroutine": "go ${1:func}(${2:args})",
        "chan": "${1:ch} := make(chan ${2:int}, ${3:10})",
        "defer": "defer ${1:func}()",
    }

    RUST_SNIPPETS = {
        "fn": "fn ${1:name}(${2:args}) -> ${3:type} {\n    ${4}\n}",
        "if": "if ${1:condition} {\n    ${2}\n}",
        "for": "for ${1:i} in ${2:iterable} {\n    ${3}\n}",
        "match": "match ${1:value} {\n    ${2:pattern} => ${3},\n    _ => ${4},\n}",
        "struct": "struct ${1:Name} {\n    ${2:field}: ${3:type},\n}",
        "impl": "impl ${1:Name} {\n    fn ${2:method}(&self) -> ${3:type} {\n        ${4}\n    }\n}",
        "trait": "trait ${1:Name} {\n    fn ${2:method}(&self) -> ${3:type};\n}",
        "enum": "enum ${1:Name} {\n    ${2:Variant},\n}",
        "let": "let ${1:mut} ${2:var} = ${3:value};",
        "match_opt": "match ${1:option} {\n    Some(${2:val}) => ${3},\n    None => ${4},\n}",
        "macro": "macro_rules! ${1:name} {\n    (${2:pattern}) => {\n        ${3}\n    };\n}",
    }

    PHP_SNIPPETS = {
        "if": "if (${1:condition}) {\n    ${2}\n}",
        "for": "for (${1:i}=0; ${1:i}<${2:n}; ${1:i}++) {\n    ${3}\n}",
        "foreach": "foreach (${1:array} as ${2:item}) {\n    ${3}\n}",
        "function": "function ${1:name}(${2:args}) {\n    ${3}\n}",
        "class": "class ${1:Name} {\n    ${2}\n}",
        "try": "try {\n    ${1}\n} catch (${2:Exception} $e) {\n    ${3}\n}",
        "echo": "echo ${1:value};",
        "json": "echo json_encode(${1:data});",
    }

    _MODEL_CACHE = {}

    @classmethod
    def get_model(cls, lang_name):
        cls._build_maps()
        words = cls.LANG_MAP.get(lang_name)
        if words is None:
            from PyQt6.QtCore import QStringListModel
            return QStringListModel([]), False
        if lang_name in cls._MODEL_CACHE:
            return cls._MODEL_CACHE[lang_name], True
        from PyQt6.QtCore import QStringListModel
        m = QStringListModel(sorted(words))
        cls._MODEL_CACHE[lang_name] = m
        return m, True

    @classmethod
    def get_snippet(cls, lang, line_text):
        cls._build_maps()
        word = line_text.strip().split()[0] if line_text.strip() else ""
        snippets = cls.SNIPPET_MAP.get(lang, {})
        if word in snippets:
            return snippets[word]
        if line_text.strip() in snippets:
            return snippets[line_text.strip()]
        return None

class FileTreeWidget(QTreeWidget):
    """Проводник файлов с отображением размера"""
    file_selected = pyqtSignal(str)

    EXT_ICON_MAP = {
        '.py': 'python-original.svg', '.js': 'javascript-original.svg',
        '.java': 'java-original.svg', '.cpp': 'ISO_C++_Logo.svg.png',
        '.cc': 'ISO_C++_Logo.svg.png', '.cxx': 'ISO_C++_Logo.svg.png',
        '.cs': 'c-sharp-logo.png',
        '.ts': 'typescript-original.svg', '.tsx': 'typescript-original.svg',
        '.php': 'php-original.svg', '.go': 'go-original-wordmark.svg',
        '.rs': 'rust-original.svg', '.rules': 'firebase-original.svg', '.swift': 'swift-original.svg',
        '.kt': 'kotlin-original.svg', '.kts': 'kotlin-original.svg',
        '.rb': 'ruby-original.svg', '.sql': 'SQL-universal.svg',
        '.r': 'r-original.svg', '.c': 'c-original.svg',
        '.dart': 'dart-original.svg', '.lua': 'lua-original.svg',
        '.hs': 'haskell-original.svg', '.clj': 'clojure-original.svg',
        '.jl': 'julia-original.svg', '.scala': 'scala-original.svg',
        '.pl': 'perl-original.svg', '.pm': 'perl-original.svg',
        '.sh': 'bash-original.svg', '.bash': 'bash-original.svg',
        '.ps1': 'powershell-original.svg',
        '.html': 'html5-original-wordmark.svg', '.htm': 'html5-original-wordmark.svg',
        '.css': 'css3-original-wordmark.svg', '.less': 'less-plain-wordmark.svg',
        '.json': 'json-original.svg', '.xml': 'xml-original.svg',
        '.yaml': 'yaml-original.svg', '.yml': 'yaml-original.svg',
        '.md': 'markdown-original.svg',
        '.sol': 'solidity-original.svg',
        '.vue': 'vuejs-original.svg',
        '.svelte': 'svelte-original.svg',
        '.tf': 'terraform-original.svg',
        '.dockerfile': 'docker-original.svg',
        '.tex': 'latex.png', '.sty': 'latex.png',
        '.toml': 'Logo-toml.svg.png',
        '.cmake': 'cmake-original.svg', '.make': 'Makefile logo.png',
        '.os': 'OrionScriptLogo.png',
        '.dockerignore': 'docker-original.svg',
        '.ex': 'elixir-original.svg', '.exs': 'elixir-original.svg',
        '.erl': 'erlang-original.svg', '.hrl': 'erlang-original.svg',
        '.fs': 'fsharp-original.svg', '.fsx': 'fsharp-original.svg',
        '.groovy': 'groovy-original.svg',
        '.m': 'objectivec-plain.svg',
        '.pas': 'delphi-original.svg',
        '.vb': 'visualbasic-original.svg',
        '.cbl': 'cobol-original.svg', '.cob': 'cobol-original.svg',
        '.f90': 'fortran-original.svg', '.f95': 'fortran-original.svg',
        '.f': 'fortran-original.svg', '.for': 'fortran-original.svg',
        '.cls': 'apex-original.svg',
        '.graphql': 'graphql-plain.svg', '.gql': 'graphql-plain.svg',
    }

    def __init__(self):
        super().__init__()
        self.setColumnCount(2)
        self.setHeaderLabels(["Файл", "Размер"])
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.itemExpanded.connect(self.on_item_expanded)
        self.watcher = QFileSystemWatcher()
        self.current_root = None
        self._icon_cache = {}
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu()
        item_path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        is_dir = os.path.isdir(item_path) if item_path else False

        if item and is_dir:
            create_file = menu.addAction("📄 Создать файл")
            create_folder = menu.addAction("📁 Создать папку")
            menu.addSeparator()
            rename = menu.addAction("✏️ Переименовать")
            menu.addSeparator()
            delete = menu.addAction("🗑️ Удалить")
            delete.setData("delete")
            action = menu.exec(self.viewport().mapToGlobal(pos))
            if action == create_file:
                self._create_file(item_path)
            elif action == create_folder:
                self._create_folder(item_path)
            elif action == rename:
                self._rename_item(item, item_path)
            elif action == delete:
                self._delete_item(item, item_path)
        elif item and not is_dir:
            rename = menu.addAction("✏️ Переименовать")
            menu.addSeparator()
            delete = menu.addAction("🗑️ Удалить")
            action = menu.exec(self.viewport().mapToGlobal(pos))
            if action == rename:
                self._rename_item(item, item_path)
            elif action == delete:
                self._delete_item(item, item_path)

    def _create_file(self, parent_path):
        name, ok = QInputDialog.getText(self, "Создать файл", "Имя файла (с расширением):")
        if ok and name:
            full_path = os.path.join(parent_path, name)
            try:
                open(full_path, 'w').close()
                item = self._find_item_by_path(parent_path)
                if item:
                    child = QTreeWidgetItem(item)
                    child.setText(0, name)
                    child.setData(0, Qt.ItemDataRole.UserRole, full_path)
                    size = os.path.getsize(full_path)
                    child.setText(1, self.format_size(size))
                    child.setIcon(0, self._get_file_icon(full_path))
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать файл: {e}")

    def _create_folder(self, parent_path):
        name, ok = QInputDialog.getText(self, "Создать папку", "Имя папки:")
        if ok and name:
            full_path = os.path.join(parent_path, name)
            try:
                os.mkdir(full_path)
                item = self._find_item_by_path(parent_path)
                if item:
                    child = QTreeWidgetItem(item)
                    child.setText(0, name)
                    child.setData(0, Qt.ItemDataRole.UserRole, full_path)
                    child.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DirClosedIcon))
                    child.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать папку: {e}")

    def _rename_item(self, item, old_path):
        name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=name)
        if ok and new_name and new_name != name:
            parent = os.path.dirname(old_path)
            new_path = os.path.join(parent, new_name)
            try:
                os.rename(old_path, new_path)
                item.setText(0, new_name)
                item.setData(0, Qt.ItemDataRole.UserRole, new_path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать: {e}")

    def _delete_item(self, item, path):
        name = os.path.basename(path)
        reply = QMessageBox.question(self, "Подтверждение", f"Удалить '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                parent_item = item.parent()
                if parent_item:
                    parent_item.removeChild(item)
                else:
                    self.takeTopLevelItem(self.indexOfTopLevelItem(item))
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {e}")

    def _find_item_by_path(self, target_path, parent_item=None):
        target_path = os.path.normpath(target_path)
        for i in range(self.topLevelItemCount() if parent_item is None else parent_item.childCount()):
            item = self.topLevelItem(i) if parent_item is None else parent_item.child(i)
            item_path = os.path.normpath(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if item_path == target_path:
                return item
            if item.childCount() > 0:
                found = self._find_item_by_path(target_path, item)
                if found:
                    return found
        return None

    def _refresh_item(self, item, path):
        if item:
            item.takeChildren()
            self._load_items(path, item)
        else:
            self.load_directory(self.current_root or path)

    def load_directory(self, path):
        """Загрузить директорию в проводник"""
        self.clear()
        self.current_root = path
        self._load_items(path, None)
        self.resizeColumnToContents(0)
        
    EXT_COLORS = {
        '.asm': '#8B4513', '.s': '#8B4513', '.sas': '#003399',
        '.sb3': '#FF8C00', '.scratch': '#FF8C00',
        '.txt': '#808080', '.log': '#808080',
        '.cfg': '#808080', '.ini': '#808080', '.env': '#808080',
        '.rules': '#FFA000',
    }

    def _generate_placeholder_icon(self, ext):
        """Сгенерировать иконку-заглушку с буквами"""
        label = ext.lstrip('.').upper()[:3] or '?'
        color = self.EXT_COLORS.get(ext, '#555555')
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color))
        from PyQt6.QtGui import QPainter
        p = QPainter(pixmap)
        p.setPen(QColor('#FFFFFF'))
        font = QFont("Segoe UI", 7)
        p.setFont(font)
        p.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, label)
        p.end()
        return QIcon(pixmap)

    def _get_file_icon(self, filepath):
        """Получить иконку для файла по расширению"""
        _, ext = os.path.splitext(filepath.lower())
        icon_file = self.EXT_ICON_MAP.get(ext)
        if not icon_file and os.path.basename(filepath).lower() in self.EXT_ICON_MAP:
            icon_file = self.EXT_ICON_MAP[os.path.basename(filepath).lower()]
        if icon_file:
            if icon_file not in self._icon_cache:
                icon_path = os.path.join(ASSETS_DIR, icon_file)
                self._icon_cache[icon_file] = _load_icon(icon_path)
            cached = self._icon_cache.get(icon_file)
            if cached:
                return cached
        if ext in self.EXT_COLORS:
            icon = self._generate_placeholder_icon(ext)
            self._icon_cache[ext] = icon
            return icon
        return self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon)

    def _load_items(self, path, parent_item):
        """Загрузить элементы директории (без рекурсии в подпапки)"""
        try:
            for item in sorted(os.listdir(path)):
                if item.startswith('.'):
                    continue
                    
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path)
                
                if parent_item is None:
                    tree_item = QTreeWidgetItem(self)
                else:
                    tree_item = QTreeWidgetItem(parent_item)
                
                tree_item.setText(0, item)
                tree_item.setData(0, Qt.ItemDataRole.UserRole, full_path)
                
                if is_dir:
                    tree_item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DirClosedIcon))
                    tree_item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
                else:
                    try:
                        size = os.path.getsize(full_path)
                        size_text = self.format_size(size)
                        tree_item.setText(1, size_text)
                    except OSError:
                        tree_item.setText(1, "?")
                    tree_item.setIcon(0, self._get_file_icon(full_path))
        except PermissionError:
            pass
    
    def on_item_expanded(self, item):
        """Загрузить содержимое папки при раскрытии"""
        full_path = item.data(0, Qt.ItemDataRole.UserRole)
        if full_path and os.path.isdir(full_path):
            if item.childCount() == 0:
                self._load_items(full_path, item)
    
    @staticmethod
    def format_size(size):
        """Форматировать размер файла"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def on_item_double_clicked(self, item, column):
        """Обработка двойного клика на файл"""
        full_path = item.data(0, Qt.ItemDataRole.UserRole)
        if full_path and os.path.isfile(full_path):
            self.file_selected.emit(full_path)

class ImageViewer(QWidget):
    """Просмотр изображений с масштабированием"""
    ZOOM_PRESETS = ["Fit", "25%", "50%", "75%", "100%", "150%", "200%", "300%", "500%"]

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.dimensions = ""
        self._original_pixmap = None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        zoom_bar = QWidget()
        zoom_bar.setStyleSheet("background-color: #252526;")
        zl = QHBoxLayout()
        zl.setContentsMargins(8, 4, 8, 4)
        self._zoom_combo = QComboBox()
        self._zoom_combo.addItems(self.ZOOM_PRESETS)
        self._zoom_combo.setCurrentText("Fit")
        self._zoom_combo.setEditable(True)
        self._zoom_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._zoom_combo.currentTextChanged.connect(self._on_zoom_changed)
        zl.addWidget(QLabel("Масштаб:"))
        zl.addWidget(self._zoom_combo)
        zl.addStretch()
        zoom_bar.setLayout(zl)
        layout.addWidget(zoom_bar)

        self._scene = QGraphicsScene()
        self._view = QGraphicsView(self._scene)
        self._view.setStyleSheet("background-color: #1e1e1e; border: none;")
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self._view)

        self.setLayout(layout)
        self._load()

    def _load(self):
        ext = os.path.splitext(self.filepath)[1].lower()
        pixmap = None
        orig_w = orig_h = 0

        if ext == '.svg':
            renderer = QSvgRenderer(self.filepath)
            size = renderer.defaultSize()
            w = size.width() if size.isValid() else 800
            h = size.height() if size.isValid() else 600
            orig_w, orig_h = w, h
            pixmap = QPixmap(w, h)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
        else:
            pixmap = QPixmap(self.filepath)
            if not pixmap.isNull():
                orig_w, orig_h = pixmap.width(), pixmap.height()

        if pixmap and not pixmap.isNull():
            self._original_pixmap = pixmap
            self._scene.addPixmap(pixmap)
            self._scene.setSceneRect(0.0, 0.0, float(pixmap.width()), float(pixmap.height()))
            self.dimensions = f"{orig_w}x{orig_h}"
            self._fit_to_view()
        else:
            self._scene.addText("Не удалось загрузить изображение", QFont("Consolas", 14))

    def _fit_to_view(self):
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        t = self._view.transform()
        pct = int(round(t.m11() * 100))
        self._zoom_combo.blockSignals(True)
        self._zoom_combo.setCurrentText(f"{pct}%")
        self._zoom_combo.blockSignals(False)

    def _on_zoom_changed(self, text):
        if text == "Fit":
            self._fit_to_view()
            return
        if not self._original_pixmap:
            return
        try:
            pct = int(text.replace('%', '').strip())
        except ValueError:
            return
        pct = max(5, min(5000, pct))
        self._view.resetTransform()
        self._view.scale(pct / 100.0, pct / 100.0)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._zoom_combo.blockSignals(True)
        self._zoom_combo.setCurrentText(f"{pct}%")
        self._zoom_combo.blockSignals(False)

    def toPlainText(self):
        return ""
# ================================================================
# BackendAlgorithmTracer — Snapshot-трейсеры для StepPlayer
# ================================================================

class Node:
    """Узел связного списка."""
    __slots__ = ("id", "value", "next")
    _counter = 0
    def __init__(self, value):
        Node._counter += 1
        self.id = Node._counter
        self.value = value
        self.next = None

class TreeNode:
    """Узел бинарного дерева поиска (BST)."""
    __slots__ = ("id", "value", "left", "right")
    _counter = 0
    def __init__(self, value):
        TreeNode._counter += 1
        self.id = TreeNode._counter
        self.value = value
        self.left = None
        self.right = None

class BackendAlgorithmTracer:
    """Промышленный генератор Snapshot-пакетов для визуализации алгоритмов.
    
    Формат выхода — список dict, совместимый с JS StepPlayer:
      array:      {type, step, array, active, sorted, operation}
      linkedlist: {type, step, nodes:[{id,value,next}], active, operation}
      tree:       {type, step, nodes:[{id,value,left,right}], active, highlighted, operation}
      sql:        {type, step, columns, rows, activeRow, filterStatus, resultRows}
    """
    
    # ── Сериализация структур ──────────────────────────────────
    @staticmethod
    def _snapshot_array(a, active, sorted_, operation, step):
        return {"type":"array","step":step,"array":list(a),
                "active":list(active),"sorted":list(sorted_),
                "operation":operation}

    @staticmethod
    def _snapshot_list(head, active_ids, operation, step):
        nodes = []
        cur = head
        while cur:
            nodes.append({"id":cur.id,"value":cur.value,
                          "next":cur.next.id if cur.next else None})
            cur = cur.next
        return {"type":"linkedlist","step":step,"nodes":nodes,
                "active":list(active_ids),"operation":operation}

    @staticmethod
    def _snapshot_tree(roots, active_ids, highlighted_ids, operation, step):
        def _serialize(n):
            if n is None: return None
            return {"id":n.id,"value":n.value,
                    "left":n.left.id if n.left else None,
                    "right":n.right.id if n.right else None}
        nodes = []
        stack = list(roots)
        seen = set()
        while stack:
            n = stack.pop()
            if n is None or n.id in seen: continue
            seen.add(n.id)
            nodes.append(_serialize(n))
            stack.append(n.left)
            stack.append(n.right)
        return {"type":"tree","step":step,"nodes":nodes,
                "active":list(active_ids),
                "highlighted":list(highlighted_ids),
                "operation":operation}

    # ── Bubble Sort ────────────────────────────────────────────
    @staticmethod
    def bubble_sort(arr):
        a = list(arr)
        steps, step_num = [], 0
        n = len(a)
        for i in range(n - 1):
            sorted_part = list(range(n - i - 1, n))
            for j in range(n - i - 1):
                steps.append(BackendAlgorithmTracer._snapshot_array(
                    a, [j, j+1], sorted_part, "compare", step_num))
                step_num += 1
                if a[j] > a[j+1]:
                    a[j], a[j+1] = a[j+1], a[j]
                    steps.append(BackendAlgorithmTracer._snapshot_array(
                        a, [j, j+1], sorted_part, "swap", step_num))
                    step_num += 1
        steps.append(BackendAlgorithmTracer._snapshot_array(
            a, [], list(range(n)), "done", step_num))
        return steps

    # ── Quick Sort ─────────────────────────────────────────────
    @staticmethod
    def quick_sort(arr):
        a = list(arr)
        steps, step_counter = [], [0]
        def _qs(lo, hi):
            if lo >= hi: return
            pivot = a[(lo + hi) // 2]
            i, j = lo, hi
            while i <= j:
                while a[i] < pivot:
                    steps.append(BackendAlgorithmTracer._snapshot_array(
                        a, [i, (lo+hi)//2], [], "compare", step_counter[0]))
                    step_counter[0] += 1; i += 1
                while a[j] > pivot:
                    steps.append(BackendAlgorithmTracer._snapshot_array(
                        a, [j, (lo+hi)//2], [], "compare", step_counter[0]))
                    step_counter[0] += 1; j -= 1
                if i <= j:
                    a[i], a[j] = a[j], a[i]
                    steps.append(BackendAlgorithmTracer._snapshot_array(
                        a, [i, j], [], "swap", step_counter[0]))
                    step_counter[0] += 1; i += 1; j -= 1
            if lo < j: _qs(lo, j)
            if i < hi: _qs(i, hi)
        _qs(0, len(a)-1)
        steps.append(BackendAlgorithmTracer._snapshot_array(
            a, [], list(range(len(a))), "done", step_counter[0]))
        return steps

    # ── Insertion Sort ─────────────────────────────────────────
    @staticmethod
    def insertion_sort(arr):
        a = list(arr)
        steps, step_num = [], 0
        n = len(a)
        for i in range(1, n):
            key = a[i]
            j = i - 1
            steps.append(BackendAlgorithmTracer._snapshot_array(
                a, [i, j], list(range(i+1, n)), "compare", step_num))
            step_num += 1
            while j >= 0 and a[j] > key:
                a[j+1] = a[j]
                steps.append(BackendAlgorithmTracer._snapshot_array(
                    a, [j, j+1], list(range(i+1, n)), "swap", step_num))
                step_num += 1
                j -= 1
            a[j+1] = key
        steps.append(BackendAlgorithmTracer._snapshot_array(
            a, [], list(range(n)), "done", step_num))
        return steps

    # ── Merge Sort ─────────────────────────────────────────────
    @staticmethod
    def merge_sort(arr):
        a = list(arr)
        steps, step_counter = [], [0]
        def _ms(lo, hi):
            if hi - lo <= 1: return
            mid = (lo + hi) // 2
            _ms(lo, mid); _ms(mid, hi)
            left, right = a[lo:mid], a[mid:hi]
            i = j = 0; k = lo
            while i < len(left) and j < len(right):
                active = [lo+i] if left[i] <= right[j] else [mid+j]
                steps.append(BackendAlgorithmTracer._snapshot_array(
                    a, active, [], "compare", step_counter[0]))
                step_counter[0] += 1
                if left[i] <= right[j]:
                    a[k] = left[i]; i += 1
                else:
                    a[k] = right[j]; j += 1
                steps.append(BackendAlgorithmTracer._snapshot_array(
                    a, [k], list(range(k)), "swap", step_counter[0]))
                step_counter[0] += 1
                k += 1
            while i < len(left):
                a[k] = left[i]; i += 1; k += 1
                steps.append(BackendAlgorithmTracer._snapshot_array(
                    a, [k-1], list(range(k-1)), "swap", step_counter[0]))
                step_counter[0] += 1
            while j < len(right):
                a[k] = right[j]; j += 1; k += 1
                steps.append(BackendAlgorithmTracer._snapshot_array(
                    a, [k-1], list(range(k-1)), "swap", step_counter[0]))
                step_counter[0] += 1
        _ms(0, len(a))
        steps.append(BackendAlgorithmTracer._snapshot_array(
            a, [], list(range(len(a))), "done", step_counter[0]))
        return steps

    # ── Selection Sort ─────────────────────────────────────────
    @staticmethod
    def selection_sort(arr):
        a = list(arr)
        steps, step_num = [], 0
        n = len(a)
        for i in range(n):
            min_idx = i
            for j in range(i+1, n):
                steps.append(BackendAlgorithmTracer._snapshot_array(
                    a, [j, min_idx], list(range(i)), "compare", step_num))
                step_num += 1
                if a[j] < a[min_idx]:
                    min_idx = j
            if min_idx != i:
                a[i], a[min_idx] = a[min_idx], a[i]
                steps.append(BackendAlgorithmTracer._snapshot_array(
                    a, [i, min_idx], list(range(i+1)), "swap", step_num))
                step_num += 1
            steps.append(BackendAlgorithmTracer._snapshot_array(
                a, [i], list(range(i+1)), "sorted", step_num))
            step_num += 1
        steps.append(BackendAlgorithmTracer._snapshot_array(
            a, [], list(range(n)), "done", step_num))
        return steps

    # ── Linked List: построение ────────────────────────────────
    @staticmethod
    def linked_list(values):
        Node._counter = 0
        steps, head = [], None
        for i, v in enumerate(values):
            new_node = Node(v)
            if head is None:
                head = new_node
            else:
                cur = head
                while cur.next: cur = cur.next
                cur.next = new_node
            steps.append(BackendAlgorithmTracer._snapshot_list(
                head, [new_node.id], "append" if i > 0 else "create", i))
        return steps

    # ── Linked List: поиск ─────────────────────────────────────
    @staticmethod
    def linked_list_search(values, target):
        Node._counter = 0
        head = None
        for v in values:
            n = Node(v)
            if head is None: head = n
            else:
                c = head
                while c.next: c = c.next
                c.next = n
        steps, step_num = [], 0
        cur = head
        while cur:
            steps.append(BackendAlgorithmTracer._snapshot_list(
                head, [cur.id], "traverse", step_num))
            step_num += 1
            if cur.value == target:
                steps.append(BackendAlgorithmTracer._snapshot_list(
                    head, [cur.id], "found", step_num))
                step_num += 1
                return steps
            cur = cur.next
        steps.append(BackendAlgorithmTracer._snapshot_list(
            head, [], "not_found", step_num))
        return steps

    # ── Linked List: удаление по значению ──────────────────────
    @staticmethod
    def linked_list_delete(values, target):
        Node._counter = 0
        head = None
        for v in values:
            n = Node(v)
            if head is None: head = n
            else:
                c = head
                while c.next: c = c.next
                c.next = n
        steps, step_num = [], 0
        if head is None: return steps
        if head.value == target:
            steps.append(BackendAlgorithmTracer._snapshot_list(
                head, [head.id], "delete_head", step_num))
            head = head.next
            step_num += 1
            if head:
                steps.append(BackendAlgorithmTracer._snapshot_list(
                    head, [head.id], "new_head", step_num))
            return steps
        prev, cur = head, head.next
        while cur:
            steps.append(BackendAlgorithmTracer._snapshot_list(
                head, [cur.id], "traverse", step_num))
            step_num += 1
            if cur.value == target:
                prev.next = cur.next
                steps.append(BackendAlgorithmTracer._snapshot_list(
                    head, [prev.id], "delete", step_num))
                step_num += 1
                return steps
            prev, cur = cur, cur.next
        steps.append(BackendAlgorithmTracer._snapshot_list(
            head, [], "not_found", step_num))
        return steps

    # ── BST: вставка ───────────────────────────────────────────
    @staticmethod
    def binary_tree(values):
        TreeNode._counter = 0
        steps, roots = [], []
        for i, v in enumerate(values):
            new_node = TreeNode(v)
            if i == 0:
                roots.append(new_node)
                steps.append(BackendAlgorithmTracer._snapshot_tree(
                    roots, [new_node.id], [], "root", i))
                continue
            cur = roots[0]
            while True:
                if v < cur.value:
                    if cur.left is None:
                        cur.left = new_node; break
                    cur = cur.left
                else:
                    if cur.right is None:
                        cur.right = new_node; break
                    cur = cur.right
            roots.append(new_node)
            steps.append(BackendAlgorithmTracer._snapshot_tree(
                roots, [new_node.id],
                [n.id for n in roots[1:-1]] if len(roots)>2 else [],
                "insert", i))
        return steps

    # ── BST: поиск ─────────────────────────────────────────────
    @staticmethod
    def binary_tree_search(values, target):
        TreeNode._counter = 0
        roots = []
        for v in values:
            n = TreeNode(v)
            if not roots:
                roots.append(n); continue
            cur = roots[0]
            while True:
                if v < cur.value:
                    if cur.left is None: cur.left = n; break
                    cur = cur.left
                else:
                    if cur.right is None: cur.right = n; break
                    cur = cur.right
            roots.append(n)
        steps, step_num = [], 0
        cur = roots[0]
        while cur:
            steps.append(BackendAlgorithmTracer._snapshot_tree(
                roots, [cur.id],
                [n.id for n in roots if n.id != cur.id],
                "search", step_num))
            step_num += 1
            if target == cur.value:
                steps.append(BackendAlgorithmTracer._snapshot_tree(
                    roots, [cur.id],
                    [n.id for n in roots if n.id != cur.id],
                    "found", step_num))
                return steps
            cur = cur.left if target < cur.value else cur.right
        steps.append(BackendAlgorithmTracer._snapshot_tree(
            roots, [], [n.id for n in roots], "not_found", step_num))
        return steps

    # ── BST: удаление узла ────────────────────────────────────
    @staticmethod
    def binary_tree_delete(values, target):
        TreeNode._counter = 0
        roots = []
        for v in values:
            n = TreeNode(v)
            if not roots:
                roots.append(n); continue
            cur = roots[0]
            while True:
                if v < cur.value:
                    if cur.left is None: cur.left = n; break
                    cur = cur.left
                else:
                    if cur.right is None: cur.right = n; break
                    cur = cur.right
            roots.append(n)
        steps, step_num = [], 0
        root_node = roots[0]
        def _find_min(n):
            while n.left: n = n.left
            return n
        def _delete(node, val):
            nonlocal step_num
            if node is None: return None
            steps.append(BackendAlgorithmTracer._snapshot_tree(
                roots, [node.id], [n.id for n in roots if n.id!=node.id],
                "search", step_num)); step_num += 1
            if val < node.value:
                node.left = _delete(node.left, val)
            elif val > node.value:
                node.right = _delete(node.right, val)
            else:
                steps.append(BackendAlgorithmTracer._snapshot_tree(
                    roots, [node.id], [n.id for n in roots if n.id!=node.id],
                    "delete", step_num)); step_num += 1
                if node.left is None: return node.right
                if node.right is None: return node.left
                temp = _find_min(node.right)
                node.value = temp.value
                node.right = _delete(node.right, temp.value)
                steps.append(BackendAlgorithmTracer._snapshot_tree(
                    roots, [node.id], [n.id for n in roots if n.id!=node.id],
                    "replace", step_num)); step_num += 1
            return node
        _delete(root_node, target)
        steps.append(BackendAlgorithmTracer._snapshot_tree(
            roots, [], [n.id for n in roots], "done", step_num))
        return steps

    # ── Фабрика диспетчеризации ────────────────────────────────
    SORT_ALGORITHMS = {
        "bubble":    bubble_sort,
        "quick":     quick_sort,
        "insertion": insertion_sort,
        "merge":     merge_sort,
        "selection": selection_sort,
    }

    @classmethod
    def sort(cls, arr, algorithm="bubble"):
        fn = cls.SORT_ALGORITHMS.get(algorithm)
        if fn is None:
            raise ValueError(f"Неизвестный алгоритм: {algorithm}. "
                             f"Доступны: {', '.join(cls.SORT_ALGORITHMS)}")
        return fn(arr)


# ================================================================
# SQL WHERE Parser — парсер SELECT / WHERE с генерацией шагов
# ================================================================

class SQLWhereParser:
    """Парсер SQL-запросов с визуализацией пошаговой фильтрации.
    
    Поддерживаемые операторы WHERE:
      > < >= <= = != AND OR NOT LIKE IN BETWEEN IS NULL
    Поддерживаемые запросы:
      SELECT * FROM table WHERE condition
      SELECT col1, col2 FROM table WHERE condition
    """
    
    BUILTIN_TABLES = {
        "users": {
            "columns": ["id", "name", "age", "city", "salary"],
            "rows": [
                [1, "Alice",   25, "Moscow",       75000],
                [2, "Bob",     17, "Saint-Petersburg", 42000],
                [3, "Charlie", 30, "Kazan",        68000],
                [4, "Diana",   22, "Moscow",       55000],
                [5, "Eve",     19, "Novosibirsk",  31000],
                [6, "Frank",   35, "Moscow",       92000],
                [7, "Grace",   28, "Ekaterinburg", 61000],
                [8, "Henry",   16, "Saint-Petersburg", 20000],
                [9, "Ivan",    45, "Moscow",      120000],
                [10,"Julia",   33, "Kazan",        78000],
            ]
        },
        "products": {
            "columns": ["id", "name", "category", "price", "stock"],
            "rows": [
                [1, "Laptop",     "electronics", 1200, 15],
                [2, "Mouse",      "electronics",   25, 200],
                [3, "Desk",       "furniture",    450,  8],
                [4, "Chair",      "furniture",    220, 12],
                [5, "Monitor",    "electronics",  350, 30],
                [6, "Notebook",   "stationery",     5, 500],
                [7, "Pen",        "stationery",     1, 1000],
                [8, "Keyboard",   "electronics",   85, 45],
            ]
        },
    }

    @staticmethod
    def tokenize(sql):
        """Разбить SQL-запрос на токены с учётом строковых литералов."""
        import re
        tokens, i = [], 0
        while i < len(sql):
            if sql[i] in " \t\n\r": i += 1; continue
            if sql[i] in "(),*": tokens.append(sql[i]); i += 1; continue
            if sql[i] in ("'", '"'):
                quote = sql[i]; j = i + 1
                while j < len(sql) and sql[j] != quote: j += 1
                tokens.append(sql[i+1:j] if j < len(sql) else sql[i+1:])
                i = j + 1 if j < len(sql) else j
                continue
            if sql[i] in "><=!":
                if i+1 < len(sql) and sql[i:i+2] in (">=", "<=", "==", "!="):
                    tokens.append(sql[i:i+2]); i += 2; continue
                tokens.append(sql[i]); i += 1; continue
            j = i
            while j < len(sql) and (sql[j].isalnum() or sql[j] in "_."): j += 1
            if j > i: tokens.append(sql[i:j]); i = j; continue
            i += 1
        return tokens

    @staticmethod
    def _token_to_py(tokens, pos, row_var="row"):
        """Рекурсивно преобразовать токены условия в Python-выражение."""
        import re
        out, i = [], 0
        while i < len(tokens):
            t = tokens[i]
            # Бинарные операторы
            if t.upper() in ("AND", "OR"):
                left = " ".join(out)
                right = SQLWhereParser._token_to_py(tokens[i+1:], 0, row_var)
                op = "and" if t.upper() == "AND" else "or"
                return f"({left} {op} {right})"
            if t.upper() == "NOT" and i+1 < len(tokens):
                sub = SQLWhereParser._token_to_py(tokens[i+1:], 0, row_var)
                return f"(not {sub})"
            # LIKE
            if t.upper() == "LIKE" and i-1 >= 0 and i+1 < len(tokens):
                col = out.pop() if out else tokens[i-1]
                pattern = tokens[i+1]
                regex = "^" + re.escape(pattern).replace(r"\%", ".*").replace(r"\_", ".") + "$"
                return f"bool(re.match({regex!r}, str({row_var}.get({col!r}, ''))))"
            # IN
            if t.upper() == "IN" and i-1 >= 0 and i+2 < len(tokens) and tokens[i+1] == "(":
                col = out.pop() if out else tokens[i-1]
                j = i+2; values = []
                while j < len(tokens) and tokens[j] != ")":
                    if tokens[j] != ",": values.append(tokens[j])
                    j += 1
                return f"({row_var}.get({col!r}) in [{', '.join(values)}])"
            # BETWEEN
            if t.upper() == "BETWEEN" and i-1 >= 0 and i+3 < len(tokens):
                col = out.pop() if out else tokens[i-1]
                lo, hi = tokens[i+1], tokens[i+3]
                return f"({lo} <= {row_var}.get({col!r}) <= {hi})"
            # IS NULL / IS NOT NULL
            if t.upper() == "IS" and i+1 < len(tokens):
                col = out.pop() if out else tokens[i-1]
                if tokens[i+1].upper() == "NULL":
                    out.append(f"({row_var}.get({col!r}) is None)")
                    i += 2; continue
                if tokens[i+1].upper() == "NOT" and i+2 < len(tokens) and tokens[i+2].upper() == "NULL":
                    out.append(f"({row_var}.get({col!r}) is not None)")
                    i += 3; continue
            # Колонки (неключевые слова, не числа) → row['col']
            if t[0].isalpha() and t.upper() not in (
                "SELECT","FROM","WHERE","AS","ON","AND","OR","NOT","IN",
                "LIKE","BETWEEN","IS","NULL","TRUE","FALSE",
                "ORDER","BY","GROUP","HAVING","LIMIT","OFFSET",
                "DISTINCT","COUNT","SUM","AVG","MIN","MAX","ASC","DESC",
                "INSERT","INTO","VALUES","UPDATE","SET","DELETE","CREATE",
                "TABLE","DROP","ALTER","JOIN","LEFT","RIGHT","INNER",
            ):
                # Проверяем числовое значение
                try: float(t); out.append(t)
                except ValueError: out.append(f"{row_var}.get({t!r})")
            else:
                try: float(t); out.append(t)
                except ValueError: out.append(t.lower() if t.lower() in (
                    "and","or","not","in","is","null","true","false",
                    "none","none","none") else t)
            i += 1
        return " ".join(out)

    @staticmethod
    def _parse_select(tokens):
        """Извлечь имя таблицы из SELECT * FROM table ..."""
        try:
            idx_from = next(i for i, t in enumerate(tokens) if t.upper() == "FROM")
            if idx_from + 1 < len(tokens):
                return tokens[idx_from + 1].lower()
        except StopIteration:
            pass
        return "users"

    @staticmethod
    def _parse_where(tokens):
        """Извлечь условие WHERE и вернуть функцию-предикат."""
        import re
        idx = -1
        for i, t in enumerate(tokens):
            if t.upper() == "WHERE":
                idx = i; break
        if idx < 0:
            return lambda r: True
        where_tokens = tokens[idx + 1:]
        # Отсекаем всё после ORDER BY / GROUP BY / LIMIT
        for stop in ("ORDER", "GROUP", "LIMIT", "HAVING"):
            for j, t in enumerate(where_tokens):
                if t.upper() == stop:
                    where_tokens = where_tokens[:j]
                    break
        py_expr = SQLWhereParser._token_to_py(where_tokens, 0)
        try:
            code = compile(py_expr, "<sql_where>", "eval", flags=0)
        except SyntaxError:
            return lambda r: True
        return lambda r: bool(eval(code, {"__builtins__":{}, "re":re}, {"row":r}))

    @classmethod
    def generate_steps(cls, sql_query, custom_table=None):
        """Полный цикл: парсинг → пошаговая визуализация.
        
        Возвращает (steps, result_rows, table_name, total_rows, passed_count).
        """
        tokens = cls.tokenize(sql_query)
        table_name = cls._parse_select(tokens)
        table = custom_table if custom_table else cls.BUILTIN_TABLES.get(table_name, cls.BUILTIN_TABLES["users"])
        cols, rows = table["columns"], table["rows"]
        condition = cls._parse_where(tokens)
        steps, result_rows = [], []
        for i, row in enumerate(rows):
            row_dict = dict(zip(cols, row))
            passed = bool(condition(row_dict))
            steps.append({
                "type": "sql", "step": i,
                "columns": cols, "rows": rows,
                "activeRow": i,
                "filterStatus": "passed" if passed else "failed",
                "resultRows": [list(r) for r in result_rows] + ([list(row)] if passed else []),
            })
            if passed:
                result_rows.append(list(row))
        steps.append({
            "type": "sql", "step": len(rows),
            "columns": cols, "rows": rows,
            "activeRow": -1, "filterStatus": "done",
            "resultRows": [list(r) for r in result_rows],
        })
        return steps, result_rows, table_name, len(rows), len(result_rows)


class ScratchBridge(QObject):
    """Мост между Python и JavaScript через QWebChannel."""
    
    log_received = pyqtSignal(str, str)   # level, message
    json_received = pyqtSignal(str)       # snapshot JSON string
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._page = None
    
    def setPage(self, page):
        self._page = page
    
    def sendJsonToWeb(self, json_str, mode="algo"):
        """Отправить массив snapshot-шагов на фронтенд и переключить режим."""
        if self._page:
            import json as _json
            safe = _json.dumps(json_str)
            self._page.runJavaScript(
                f"window.receiveSnapshots({safe}, {_json.dumps(mode)})"
            )
    
    @pyqtSlot(str)
    def sendCodeToWeb(self, code):
        """Принять JS-код из Python и отправить в веб-интерфейс."""
        if self._page:
            import json
            self._page.runJavaScript(f"window.receiveFromPython({json.dumps(code)})")
    
    def sendSb3ToWeb(self, filepath):
        """Прочитать .sb3 (ZIP) в бинарном режиме, закодировать в Base64 и отправить."""
        if not self._page:
            return
        import base64 as _b64
        with open(filepath, 'rb') as f:
            raw = f.read()
        b64_str = _b64.b64encode(raw).decode('ascii')
        payload = f"BASE64:{b64_str}"
        import json as _json
        self._page.runJavaScript(f"window.receiveFromPython({_json.dumps(payload)})")
    
    @pyqtSlot(str, str)
    def logFromJs(self, level, message):
        """Принять лог из JavaScript и передать в Python."""
        self.log_received.emit(level, message)


# ─────────────────────────────────────────────────────────────
# Мультирежимный Интерактивный Терминал
# ─────────────────────────────────────────────────────────────

class OrionHighlighter(QSyntaxHighlighter):
    """VS Code Dark-тема подсветка синтаксиса для языка OrionScript (.os).

    Правила раскраски (Dracula / VS Code Dark):
      1. Теги структуры <orion> <obj> <snd> <dspl> <sstm> <db> и их закрытия
         — ярко-синий #569cd6, жирный
      2. Команды модулей (33 шт.): nav_*, tone, print, write, wait и т.д.
         — фиолетово-розовый #c586c0
      3. Строки в кавычках "…"
         — тёплый оранжевый #ce9178
      4. Инлайн-теги ВНУТРИ строк: <red> <-red> <curs> <fat> <line> <big=24> <small=10>
         — перекрывают цвет строки: бирюзовый #4ec9b0
      5. Числа целые и дробные
         — светло-зелёный #b5cea8
      6. Комментарии # …
         — тёмно-зелёный #6a9955, курсив
    """

    # ── Маска структурных тегов ─────────────────────────────────
    # <orion> <-orion> <obj> <-obj> <snd> <-snd> <dspl> <-dspl>
    # <sstm> <-sstm> <db> <-db> <font> <-font>
    TAG_PATTERN = re.compile(r'<-?('
        r'orion|obj|snd|dspl|sstm|db|font'
        r')>')

    # ── Маска команд (33 шт.) ───────────────────────────────────
    CMD_PATTERN = re.compile(r'\b('
        r'nav_move|nav_turn|nav_goto|nav_say|nav_think'
        r'|nav_pen|nav_color|nav_size|nav_clear'
        r'|nav_hide|nav_show|nav_home'
        r'|tone|play|mute'
        r'|print|clear|mode'
        r'|write|pwm|read|analog'
        r'|wait|log|select'
        r'|viz_array|viz_compare|viz_swap|viz_sorted'
        r')\b')

    # ── Беспрефиксные команды (ядро + модули) ───────────────────
    CMD_BAREPATTERN = re.compile(r'\b('
        r'move|turn|goto|say|pen|home|hide|show|glide|pensize|color|stamp|setx|sety|dir'
        r'|chart|table|tree|llist|highlight|reset'
        r'|repeat|end|if|else|focus'
        r'|notone|servo'
        r')\b')

    # ── Маска строк в кавычках ──────────────────────────────────
    STRING_PATTERN = re.compile(r'"[^"\\]*(\\.[^"\\]*)*"')

    # ── Маска инлайн-тегов форматирования (цвета + стили + размер) ──
    # Радужные цвета: red, orange, yellow, green, blue, purple, white
    # Стили: curs (курсив), fat (жирный), line (подчёркнутый)
    # Размер: big=NN, small=NN
    INLINE_TAG_PATTERN = re.compile(r'<-?('
        r'red|orange|yellow|green|blue|purple|white'
        r'|curs|fat|line'
        r'|big=\d+|small=\d+'
        r')>')

    # ── Маска чисел ─────────────────────────────────────────────
    NUMBER_PATTERN = re.compile(r'\b\d+(\.\d+)?\b')

    # ── Маска комментариев ──────────────────────────────────────
    COMMENT_PATTERN = re.compile(r'#[^\n]*')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        # 1. Теги структуры — синий жирный
        fmtTag = QTextCharFormat()
        fmtTag.setForeground(QColor('#569cd6'))
        fmtTag.setFontWeight(QFont.Weight.Bold)
        self.highlightingRules.append((self.TAG_PATTERN, fmtTag))

        # 2. Команды — фиолетово-розовый
        fmtCmd = QTextCharFormat()
        fmtCmd.setForeground(QColor('#c586c0'))
        self.highlightingRules.append((self.CMD_PATTERN, fmtCmd))
        self.highlightingRules.append((self.CMD_BAREPATTERN, fmtCmd))

        # 3. Строки — оранжевый
        fmtStr = QTextCharFormat()
        fmtStr.setForeground(QColor('#ce9178'))
        self.highlightingRules.append((self.STRING_PATTERN, fmtStr))

        # 4. Инлайн-теги ВНУТРИ строк — бирюзовый (перекрывает оранжевый)
        fmtInline = QTextCharFormat()
        fmtInline.setForeground(QColor('#4ec9b0'))
        self.highlightingRules.append((self.INLINE_TAG_PATTERN, fmtInline))

        # 5. Числа — зелёный
        fmtNum = QTextCharFormat()
        fmtNum.setForeground(QColor('#b5cea8'))
        self.highlightingRules.append((self.NUMBER_PATTERN, fmtNum))

        # 6. Комментарии — тёмно-зелёный курсив
        fmtCmt = QTextCharFormat()
        fmtCmt.setForeground(QColor('#6a9955'))
        fmtCmt.setFontItalic(True)
        self.highlightingRules.append((self.COMMENT_PATTERN, fmtCmt))

    def highlightBlock(self, text):
        """Применить все правила подсветки к блоку text."""
        for pattern, fmt in self.highlightingRules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class OrionCompiler:
    """Компилятор языка OrionScript (.os) в исполняемый JavaScript.

    Поддерживает:
      - Мульти-сценовые покадровые циклы (пустая строка = разделитель кадров)
      - Теги контейнеров: <orion> <obj> <snd> <dspl> <sstm> <db>
      - Команды без префиксов (контекст определяется тегом-контейнером)
      - Старые префиксные команды (nav_*, link_*, sys_*, viz_*) для совместимости
    """

    # ── Карта старых префиксных имён → новые (для обратной совместимости)
    OLD_TO_NEW = {
        'nav_move':'move','nav_turn':'turn','nav_goto':'goto','nav_say':'say',
        'nav_pen':'pen','nav_clear':'clear','nav_home':'home','nav_hide':'hide',
        'nav_show':'show','nav_glide':'glide','nav_pensize':'pensize',
        'nav_color':'color','nav_stamp':'stamp','nav_setx':'setx','nav_sety':'sety',
        'nav_dir':'dir',
        'link_write':'write','link_read':'read','link_pwm':'pwm',
        'link_tone':'tone','link_notone':'notone','link_servo':'servo',
        'sys_wait':'wait','sys_log':'log','sys_repeat':'repeat',
        'sys_end':'end','sys_if':'if','sys_else':'else','sys_focus':'focus',
        'viz_chart':'chart','viz_table':'table','viz_tree':'tree',
        'viz_llist':'llist','viz_highlight':'highlight','viz_reset':'reset',
    }

    # ── Контекстные карты команд ────────────────────────────────────
    # Каждая карта: имя_команды -> lambda(args) -> JS-строка

    # Ядро (внутри <obj> или вне модульных тегов)
    CORE = {
        'move': lambda a: f"await move({a[0]});",
        'turn': lambda a: f"await turn({a[0]});",
        'goto': lambda a: f"await goto({a[0]}, {a[1]});",
        'say': lambda a: f"await say({a[0]});",
        'pen': lambda a: f"await pen({a[0]});",
        'clear': lambda a: f"await clearCanvas();",
        'home': lambda a: f"await home();",
        'hide': lambda a: f"await hide();",
        'show': lambda a: f"await show();",
        'glide': lambda a: f"await glide({a[0]}, {a[1]}, {a[2]});",
        'pensize': lambda a: f"await penSize({a[0]});",
        'color': lambda a: f"await penColor({a[0]});",
        'stamp': lambda a: f"await stamp();",
        'setx': lambda a: f"await setX({a[0]});",
        'sety': lambda a: f"await setY({a[0]});",
        'dir': lambda a: f"await setDirection({a[0]});",
        # Визуализация
        'chart': lambda a: f"await vizChart({', '.join(a)});",
        'table': lambda a: f"await vizTable({', '.join(a)});",
        'tree': lambda a: f"await vizTree({', '.join(a)});",
        'llist': lambda a: f"await vizLinkedList({', '.join(a)});",
        'highlight': lambda a: f"await vizHighlight({', '.join(a)});",
        'reset': lambda a: f"await vizReset();",
        # Управляющие конструкции
        'repeat': lambda a: f"for(let __i=0;__i<{a[0]};__i++){{",
        'end': lambda a: f"}}",
        'if': lambda a: f"if({a[0]}){{",
        'else': lambda a: f"}}else{{",
    }

    # <sstm> — железо/система
    SSTM = {
        'wait': lambda a: f"await wait({a[0]});",
        'write': lambda a: f"await digitalWrite({a[0]}, {'\"HIGH\"' if a[1].strip('\"') == '1' else '\"LOW\"'});",
        'read': lambda a: f"const __val = await analogRead({a[0]});",
        'pwm': lambda a: f"await analogWrite({a[0]}, {a[1]});",
        'tone': lambda a: f"await tone({a[0]}, {a[1]});",
        'notone': lambda a: f"await noTone({a[0]});",
        'servo': lambda a: f"await servoWrite({a[0]}, {a[1]});",
        'log': lambda a: f"console.log({', '.join(a)});",
    }

    # <snd> — звук (3-аргументный tone с длительностью)
    SND = {
        'tone': lambda a: f"await tone({a[0]}, {a[1]}, {a[2]});",
        'notone': lambda a: f"await noTone({a[0]});",
    }

    # <dspl> — дисплей
    DSPL = {
        'print': lambda a: f"await displayPrint({a[0]});",
        'clear': lambda a: f"await displayClear();",
    }

    # Собираем всё в один словарь для быстрого доступа по контексту
    CONTEXT_MAPS = {
        'core': CORE,
        'sstm': SSTM,
        'snd': SND,
        'dspl': DSPL,
    }

    # Команды, обрабатываемые на Python
    SYSTEM_COMMANDS = frozenset(['focus'])

    HELP_TEXT = """\
<system>╔══════════════════════════════════════════════════════════════╗</system>
<system>║               OrionScript Language Reference                 ║</system>
<system>╠══════════════════════════════════════════════════════════════╣</system>
<system>║ МУЛЬТИ-СЦЕНОВЫЙ СИНТАКСИС:                                  ║</system>
<system>║   <orion>  <-orion>  — кадр анимации (разделяются пустой     ║</system>
<system>║                         строкой между блоками)                ║</system>
<system>║   <obj>  <-obj>      — контейнер спрайта                     ║</system>
<system>║   <snd>  <-snd>      — звуковой модуль (tone/notone)         ║</system>
<system>║   <dspl> <-dspl>     — дисплей (print/clear)                 ║</system>
<system>║   <sstm> <-sstm>     — железо (wait/write/read/pwm/...)      ║</system>
<system>║   <db>   <-db>       — SQL-запросы (dbQuery)                 ║</system>
<system>╠══════════════════════════════════════════════════════════════╣</system>
<system>║ ЯДРО (внутри <obj>):                                          ║</system>
<system>║   move <px> / turn <deg> / goto <x> <y>                     ║</system>
<system>║   say "<t>" / pen <0|1> / clear / home                      ║</system>
<system>║   hide / show / glide <x> <y> <t> / pensize <n>             ║</system>
<system>║   color "<c>" / stamp / setx <n> / sety <n> / dir <deg>    ║</system>
<system>║   chart / table / tree / llist / highlight / reset           ║</system>
<system>║   repeat <n> / end / if <cond> / else                        ║</system>
<system>║                                                              ║</system>
<system>║ <sstm> (железо):  wait / write / read / pwm / tone / servo   ║</system>
<system>║ <snd> (звук):     tone <pin> <freq> <ms>                      ║</system>
<system>║ <dspl> (дисплей): print "<t>" / clear                         ║</system>
<system>║ <db> (SQL):       любой SQL-запрос → dbQuery на Canvas       ║</system>
<system>║                                                              ║</system>
<system>║ ПРИМЕР (2 кадра):                                             ║</system>
<system>║   <orion>                                                    ║</system>
<system>║     <obj>                                                    ║</system>
<system>║       clear                                                  ║</system>
<system>║       home                                                   ║</system>
<system>║       say "Frame 1 — привет!"                               ║</system>
<system>║       move 100                                               ║</system>
<system>║     <-obj>                                                   ║</system>
<system>║   <-orion>                                                   ║</system>
<system>║                                                              ║</system>
<system>║   <orion>                                                    ║</system>
<system>║     <obj>                                                    ║</system>
<system>║       say "Frame 2 — ответ!"                                ║</system>
<system>║       turn 180                                               ║</system>
<system>║       move 100                                               ║</system>
<system>║     <-obj>                                                   ║</system>
<system>║     <sstm>                                                   ║</system>
<system>║       write 13 1    /* зажечь LED */                        ║</system>
<system>║       wait 0.5                                               ║</system>
<system>║       write 13 0    /* погасить */                          ║</system>
<system>║     <-sstm>                                                  ║</system>
<system>║   <-orion>                                                   ║</system>
<system>╚══════════════════════════════════════════════════════════════╝</system>"""

    # ── Теги модулей ───────────────────────────────────────────────
    MODULE_TAGS = frozenset(['snd', 'dspl', 'sstm', 'db'])

    @staticmethod
    def compile_line_in_context(line: str, context: str):
        """Компилирует одну строку в заданном контексте (core/snd/dspl/sstm/db).

        Возвращает:
            (js_code: str | None, is_system: bool)
        """
        raw = line.strip()
        if not raw or raw.startswith('#'):
            return None, False

        parts = OrionCompiler._split_args(raw)
        if not parts:
            return None, False

        cmd = parts[0].lower()
        args = parts[1:]

        # Контекст <db>: SQL передаётся как есть
        if context == 'db':
            escaped = raw.replace('\\', '\\\\').replace('"', '\\"')
            return f'await dbQuery("{escaped}");', False

        # Системная команда
        if cmd in OrionCompiler.SYSTEM_COMMANDS:
            return cmd, True

        # Пробуем контекстную карту
        cmd_map = OrionCompiler.CONTEXT_MAPS.get(context, OrionCompiler.CONTEXT_MAPS['core'])
        builder = cmd_map.get(cmd)
        if builder is not None:
            try:
                return builder(args), False
            except Exception:
                return None, False

        # Резерв: пробуем старый префикс как составное имя (nav_move, link_write и т.д.)
        new_cmd = OrionCompiler.OLD_TO_NEW.get(cmd)
        if new_cmd:
            # Системная команда через старый префикс (sys_focus → focus)
            if new_cmd in OrionCompiler.SYSTEM_COMMANDS:
                return new_cmd, True
            builder2 = cmd_map.get(new_cmd)
            if builder2 is not None:
                try:
                    return builder2(args), False
                except Exception:
                    return None, False

        return None, False

    @staticmethod
    def compile_line(line: str):
        """Компилирует одну строку OrionScript (режим terminal, контекст core).
        Сохраняет обратную совместимость со старыми префиксами.
        """
        return OrionCompiler.compile_line_in_context(line, 'core')

    @staticmethod
    def compile_to_js(code_text: str):
        """Мульти-сценовый компилятор OrionScript.

        - Пустые строки между <‑orion> и <orion> разделяют независимые кадры
        - Каждый кадр → async function frame_N()
        - В конце — координатор, вызывающий кадры последовательно

        Теги модулей внутри <obj>:
          <snd>   — звук (tone/notone)
          <dspl>  — дисплей (print/clear)
          <sstm>  — железо/система (wait/write/read/...)
          <db>    — SQL-запрос

        Возвращает:
            (js_code: str | None, system_commands: list[(cmd, raw_line)])
        """
        lines = code_text.split('\n')
        frames = []      # список (frame_lines, system_cmds)
        cur_lines = []
        cur_sys = []
        in_orion = False
        in_module = None   # core / snd / dspl / sstm / db
        prev_was_close = False  # пустая строка после <-orion> = разделитель

        for raw_line in lines:
            stripped = raw_line.strip()

            # ── Пустая строка ──────────────────────────────────
            if not stripped:
                if in_orion:
                    continue  # внутри кадра — игнорируем
                if prev_was_close and cur_lines:
                    frames.append((cur_lines, cur_sys))
                    cur_lines = []
                    cur_sys = []
                continue

            prev_was_close = False

            # ── Комментарий ────────────────────────────────────
            if stripped.startswith('#'):
                continue

            # ── Теги ───────────────────────────────────────────
            if stripped.startswith('<') and stripped.endswith('>'):
                tag = stripped[1:-1].strip().lower()

                # Открывающие теги
                if tag == 'orion':
                    in_orion = True
                    in_module = 'core'  # внутри <orion> по умолчанию core
                    continue
                if tag == 'obj' or tag.startswith('obj'):
                    in_module = 'core'
                    continue
                if tag in ('snd', 'dspl', 'sstm', 'db'):
                    in_module = tag
                    continue

                # Закрывающие теги
                if tag in ('-orion', '-obj', '-snd', '-dspl', '-sstm', '-db'):
                    if tag == '-orion':
                        prev_was_close = True
                        in_orion = False
                    in_module = None
                    continue

                continue  # неизвестный тег — пропускаем

            # ── Команда ────────────────────────────────────────
            ctx = in_module or 'core'
            result, is_system = OrionCompiler.compile_line_in_context(stripped, ctx)
            if result is None:
                continue
            if is_system:
                cur_sys.append((result, stripped))
            else:
                cur_lines.append(f"  {result}")

        # Последний кадр
        if cur_lines:
            frames.append((cur_lines, cur_sys))

        if not frames:
            return None, []

        # ── Сборка JS ──────────────────────────────────────────
        js_parts = []
        all_sys = []

        for i, (flines, scmds) in enumerate(frames, 1):
            js_parts.append(f"async function frame_{i}() {{")
            js_parts.extend(flines)
            js_parts.append("}")
            all_sys.extend(scmds)

        # Координатор
        coord_lines = ["(async () => {"]
        for i in range(1, len(frames) + 1):
            coord_lines.append(f"  await frame_{i}();")
        coord_lines.append("})();")

        js_parts.append("")
        js_parts.extend(coord_lines)

        return "\n".join(js_parts), all_sys

    @staticmethod
    def _split_args(line: str):
        """Разбивает строку по пробелам, сохраняя кавычки."""
        parts = []
        buf = []
        in_quote = False
        qchar = None
        for ch in line:
            if in_quote:
                buf.append(ch)
                if ch == qchar:
                    in_quote = False
            elif ch in ('"', "'"):
                if buf:
                    parts.append(''.join(buf))
                    buf = []
                buf.append(ch)
                in_quote = True
                qchar = ch
            elif ch == ' ':
                if buf:
                    parts.append(''.join(buf))
                    buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append(''.join(buf))
        return parts


class TerminalConsole(QPlainTextEdit):
    """Read-only консоль вывода с тремя цветовыми стилями."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0c0c0c;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #3e3e42;
            }
        """)
        self._cursor = self.textCursor()

    def append_styled(self, text, color="#d4d4d4"):
        self._cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFont(QFont("Consolas", 10))
        self._cursor.insertText(text, fmt)
        self.setTextCursor(self._cursor)
        self.ensureCursorVisible()

    def append_stdout(self, text):
        self.append_styled(text, "#d4d4d4")

    def append_stderr(self, text):
        self.append_styled(text, "#f85149")

    def append_system(self, text):
        self.append_styled(text, "#569cd6")


class TerminalProcessManager(QObject):
    """Управляет жизненным циклом QProcess в трёх режимах.

    Режимы:
      - system  — системный shell (PowerShell / Bash)
      - repl    — REPL интерпретатора (python -i / node)
      - ide     — встроенный IDE-парсер команд
    """

    output_ready = pyqtSignal(str)
    error_ready = pyqtSignal(str)
    process_started = pyqtSignal(str)
    process_stopped = pyqtSignal()
    custom_output = pyqtSignal(str)

    MODE_SYSTEM = "system"
    MODE_REPL   = "repl"
    MODE_IDE    = "ide"

    _ENCODINGS = ("utf-8", "cp866", "cp1251")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = self.MODE_IDE
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._on_stdout)
        self.process.readyReadStandardError.connect(self._on_stderr)
        self.process.finished.connect(self._on_finished)
        self._current_language = "Python"

    def set_language(self, lang):
        self._current_language = lang

    # ── Запуск ────────────────────────────────────────────────

    def start_system_shell(self):
        self.stop()
        self.mode = self.MODE_SYSTEM
        if sys.platform == "win32":
            self.process.start("powershell.exe", ["-NoLogo", "-NoExit", "-Command", "-"])
        else:
            self.process.start("bash", ["--noediting"])
        if self.process.waitForStarted(3000):
            self.process_started.emit("System Shell")
        else:
            self.custom_output.emit(
                f"<stderr>Ошибка запуска shell: {self.process.errorString()}</stderr>\n")

    def start_repl(self, language=None):
        self.stop()
        self.mode = self.MODE_REPL
        lang = language or self._current_language
        shell_map = {
            "Python": ("python", ["-i", "-q"]),
            "JavaScript": ("node", []),
            "TypeScript": ("node", []),
            "Ruby": ("irb", []),
            "SQL": ("sqlite3", []),
        }
        exe, args = shell_map.get(lang, ("python", ["-i", "-q"]))
        self.process.start(exe, args)
        if self.process.waitForStarted(3000):
            self.process_started.emit(f"REPL ({lang})")
        else:
            self.custom_output.emit(
                f"<stderr>Ошибка запуска {exe}: {self.process.errorString()}</stderr>\n")

    def start_ide(self):
        self.stop()
        self.mode = self.MODE_IDE
        self.process_started.emit("IDE Commands")

    def stop(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        self.process_stopped.emit()

    # ── Ввод ──────────────────────────────────────────────────

    def write(self, text):
        cmd = text.rstrip("\n")
        if self.mode == self.MODE_IDE:
            self._handle_ide_command(cmd)
        elif self.process.state() == QProcess.ProcessState.Running:
            for enc in self._ENCODINGS:
                try:
                    self.process.write((cmd + "\n").encode(enc))
                    return
                except (UnicodeEncodeError, LookupError):
                    continue
            self.process.write((cmd + "\n").encode("utf-8", errors="replace"))

    def _decode(self, data):
        raw = data.data()
        for enc in self._ENCODINGS:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace")

    # ── Асинхронное чтение ────────────────────────────────────

    def _on_stdout(self):
        text = self._decode(self.process.readAllStandardOutput())
        self.output_ready.emit(text)

    def _on_stderr(self):
        text = self._decode(self.process.readAllStandardError())
        self.error_ready.emit(text)

    def _on_finished(self, exit_code, exit_status):
        self.process_stopped.emit()
        self.custom_output.emit(
            f"\n<system>Процесс завершён (код {exit_code})</system>\n")

    # ── IDE Commands ──────────────────────────────────────────

    def _handle_ide_command(self, cmd):
        c = cmd.strip()
        if not c:
            return
        if c in ("clear", "cls"):
            self.custom_output.emit("__CLEAR__")
        elif c == "run":
            self.custom_output.emit("__RUN__")
        elif c == "stop":
            self.custom_output.emit("__STOP__")
        elif c == "scratch":
            self.custom_output.emit("__SCRATCH_OPEN__")
        elif c == "ports":
            self.custom_output.emit("__HARDWARE_SCAN__")
        elif c in ("help", "?"):
            self._show_help()
        else:
            # Пробуем скомпилировать как OrionScript
            js, system_cmds = OrionCompiler.compile_to_js(c)
            if js:
                self.custom_output.emit(f"__OSE_RUN__:{js}")
            elif system_cmds:
                for scmd, sline in system_cmds:
                    if scmd == "focus":
                        self.custom_output.emit(f"__FOCUS__:{sline}")
                    else:
                        self.custom_output.emit(
                            f"<stderr>Неизвестная системная команда: {sline}</stderr>\n")
            else:
                self.custom_output.emit(
                    f"<stderr>Неизвестная команда: {c}\n"
                    f"Введите «help» для списка команд.</stderr>\n")

    def _show_help(self):
        lines = [
            "\n<system>╔══════════════════════════════════════════════════╗</system>",
            "<system>║       IDE Commands — справка                     ║</system>",
            "<system>╠══════════════════════════════════════════════════╣</system>",
            "<system>║  clear / cls  — очистить терминал               ║</system>",
            "<system>║  run          — запустить текущий файл          ║</system>",
            "<system>║  stop         — остановить процесс              ║</system>",
            "<system>║  scratch      — открыть Scratch IDE             ║</system>",
            "<system>║  ports        — сканировать COM-порты           ║</system>",
            "<system>║  help / ?     — эта справка                     ║</system>",
            "<system>║  📜            — справка по OrionScript (.os)    ║</system>",
            "<system>║                                                ║</system>",
            "<system>║  Любая неизвестная команда автоматически        ║</system>",
            "<system>║  компилируется как OrionScript и отправляется   ║</system>",
            "<system>║  в Scratch IDE для выполнения на Canvas.        ║</system>",
            "<system>╚══════════════════════════════════════════════════╝</system>\n",
        ]
        for line in lines:
            self.custom_output.emit(line)


class TerminalWidget(QWidget):
    """Виджет мультирежимного терминала с шапкой OSE и интерактивным вводом.

    Сигналы:
      request_run          — выполнить текущий файл (IDE Commands: run)
      request_scratch_open — переключиться на Scratch IDE
      request_hardware_scan — вывести COM-порты
      request_ose_run      — выполнить скомпилированный OrionScript в Scratch IDE
      request_focus        — переключить фокус на указанную вкладку
    """

    request_run = pyqtSignal()
    request_scratch_open = pyqtSignal()
    request_hardware_scan = pyqtSignal()
    request_ose_run = pyqtSignal(str)
    request_focus = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = TerminalProcessManager(self)
        self.command_history = []
        self.history_index = -1
        self._build_ui()
        self._connect_signals()
        self.manager.start_ide()

    # ── UI сборка ─────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # Шапка терминала
        header = QHBoxLayout()
        header.setSpacing(6)

        title = QLabel("🌌 OrionScript Terminal")
        title.setStyleSheet("color: #569cd6; font-weight: bold; font-size: 12px; padding: 2px 4px;")
        header.addWidget(title)

        # Квадратный QComboBox "OSE"
        self.ose_combo = QComboBox()
        self.ose_combo.setEditable(False)
        self.ose_combo.addItem("OSE")
        self.ose_combo.setToolTip("OSE (OrionScript Engine)")
        self.ose_combo.setFixedWidth(42)
        self.ose_combo.setFixedHeight(24)
        self.ose_combo.setStyleSheet("""
            QComboBox {
                background-color: #0e639c;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border: none;
                padding: 0 2px;
            }
            QComboBox::drop-down { width: 0; border: none; }
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #cccccc;
                selection-background-color: #094771;
                outline: none;
            }
        """)
        header.addWidget(self.ose_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["System Shell", "REPL", "IDE Commands"])
        self.mode_combo.setMinimumWidth(130)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555;
                padding: 2px 6px;
                font-size: 11px;
            }
            QComboBox::drop-down { width: 18px; }
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #cccccc;
                selection-background-color: #094771;
                outline: none;
            }
        """)
        header.addWidget(self.mode_combo)

        header.addStretch()

        self.btn_stop = QPushButton("⏹ Стоп")
        self.btn_stop.setFixedHeight(24)
        self.btn_stop.setStyleSheet("""
            QPushButton { background-color: #c04040; color: white; border: none; padding: 2px 10px; font-size: 11px; }
            QPushButton:hover { background-color: #d05050; }
        """)
        header.addWidget(self.btn_stop)

        self.btn_clear = QPushButton("🗑 Очистить")
        self.btn_clear.setFixedHeight(24)
        self.btn_clear.setStyleSheet("""
            QPushButton { background-color: #555; color: white; border: none; padding: 2px 10px; font-size: 11px; }
            QPushButton:hover { background-color: #666; }
        """)
        header.addWidget(self.btn_clear)

        self.btn_ose_help = QPushButton("📜 Справка OSE")
        self.btn_ose_help.setFixedHeight(24)
        self.btn_ose_help.setStyleSheet("""
            QPushButton { background-color: #0e639c; color: white; border: none; padding: 2px 10px; font-size: 11px; }
            QPushButton:hover { background-color: #1177bb; }
        """)
        header.addWidget(self.btn_ose_help)

        header_w = QWidget()
        header_w.setLayout(header)
        layout.addWidget(header_w)

        # Зона вывода
        self.output = TerminalConsole()
        self.output.setMinimumHeight(80)
        layout.addWidget(self.output, 1)

        # Строка ввода
        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self.prompt_label = QLabel("ide $")
        self.prompt_label.setStyleSheet(
            "color: #569cd6; font-family: Consolas; font-size: 12px; padding: 2px 0;")
        self.prompt_label.setFixedWidth(80)
        input_row.addWidget(self.prompt_label)

        self.input_line = QLineEdit()
        self.input_line.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #3e3e42;
                padding: 3px 5px;
            }
        """)
        self.input_line.installEventFilter(self)
        input_row.addWidget(self.input_line)

        layout.addLayout(input_row)

    # ── Сигналы ───────────────────────────────────────────────

    def _connect_signals(self):
        self.input_line.returnPressed.connect(self._execute)
        self.btn_stop.clicked.connect(self._stop_clicked)
        self.btn_clear.clicked.connect(self.clear_output)
        self.btn_ose_help.clicked.connect(self._show_ose_help)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.manager.output_ready.connect(self._on_stdout)
        self.manager.error_ready.connect(self._on_stderr)
        self.manager.custom_output.connect(self._on_custom_output)
        self.manager.process_started.connect(self._on_process_started)
        self.manager.process_stopped.connect(self._on_process_stopped)

    # ── Event Filter (история ↑↓) ────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.input_line and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Up:
                self._history_prev()
                return True
            elif event.key() == Qt.Key.Key_Down:
                self._history_next()
                return True
        return super().eventFilter(obj, event)

    def _history_prev(self):
        if self.command_history and self.history_index > 0:
            self.history_index -= 1
            self.input_line.setText(self.command_history[self.history_index])

    def _history_next(self):
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.input_line.setText(self.command_history[self.history_index])
        else:
            self.history_index = len(self.command_history)
            self.input_line.clear()

    # ── Выполнение команды ────────────────────────────────────

    def _execute(self):
        cmd = self.input_line.text()
        if not cmd.strip():
            return
        self.command_history.append(cmd)
        self.history_index = len(self.command_history)

        prompt = self.prompt_label.text()
        self.output.append_stdout(f"{prompt} {cmd}\n")
        self.input_line.clear()

        self.manager.write(cmd)

    def _stop_clicked(self):
        self.output.append_system(
            "\n<system>⏹ Принудительная остановка процесса</system>\n")
        self.manager.stop()

    # ── Переключение режимов ──────────────────────────────────

    def _on_mode_changed(self, idx):
        if idx == 0:
            self.prompt_label.setText("powershell >")
            self.manager.start_system_shell()
        elif idx == 1:
            self.prompt_label.setText("repl >>>")
            self.manager.start_repl()
        else:
            self.prompt_label.setText("ide $")
            self.manager.start_ide()

    # ── Приём вывода ──────────────────────────────────────────

    def _on_stdout(self, text):
        self.output.append_stdout(text)

    def _on_stderr(self, text):
        self.output.append_stderr(text)

    def _on_custom_output(self, text):
        if text == "__CLEAR__":
            self.clear_output()
        elif text == "__RUN__":
            self.request_run.emit()
        elif text == "__STOP__":
            self.manager.stop()
        elif text == "__SCRATCH_OPEN__":
            self.request_scratch_open.emit()
        elif text == "__HARDWARE_SCAN__":
            self.request_hardware_scan.emit()
        elif text.startswith("__OSE_RUN__:"):
            js_code = text[len("__OSE_RUN__:"):]
            self.output.append_stdout(f"<system>▶ OSE → JS: {js_code[:80]}{'…' if len(js_code) > 80 else ''}</system>\n")
            self.request_ose_run.emit(js_code)
        elif text.startswith("__FOCUS__:"):
            self.request_focus.emit(text[len("__FOCUS__:"):])
        else:
            self.output.append_styled(text)

    def _show_ose_help(self):
        """Вывести справку по языку OrionScript в консоль терминала."""
        for line in OrionCompiler.HELP_TEXT.split('\n'):
            self.output.append_styled(line + '\n')

    def _on_process_started(self, name):
        self.output.append_system(f"\n<system>▶ Запущен: {name}</system>\n")

    def _on_process_stopped(self):
        self.output.append_system("<system>■ Остановлен</system>\n")

    def clear_output(self):
        self.output.clear()

    def write_stdout(self, text):
        self.output.append_stdout(text)


class DependenciesDialog(QDialog):
    """Диалог со списком зависимостей и авто-установкой"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Утилиты")
        self.setMinimumWidth(520)
        self.setModal(True)
        layout = QVBoxLayout(self)

        deps = [
            ("PyTorch (CPU)", "torch", "https://download.pytorch.org/whl/cpu",
             "Необходим для работы Alan AI"),
            ("NumPy", "numpy", "https://pypi.org/project/numpy/",
             "Требуется PyTorch для тензорных операций"),
            ("arduino-cli", "arduino-cli", "https://arduino.github.io/arduino-cli/",
             "Для компиляции и загрузки скетчей на Arduino (внешний бинарник)"),
        ]

        for name, pkg, url, desc in deps:
            gb = QGroupBox(name)
            gb.setStyleSheet("QGroupBox{font-weight:bold;color:#569cd6;}"
                             "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px 0 5px;}")
            fb = QFormLayout(gb)
            installed = False
            try:
                installed = self._check(pkg)
            except Exception:
                pass
            status_btn = QPushButton("✓ Установлен" if installed else "✗ Не установлен")
            status_btn.setEnabled(False)
            status_btn.setStyleSheet(
                f"background:{'#2d4d2d' if installed else '#4d2d2d'};"
                f"color:{'#6bdb6b' if installed else '#db6b6b'};"
                f"padding:4px;border-radius:3px;")
            fb.addRow("Статус:", status_btn)

            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color:#858585;font-size:11px;")
            fb.addRow(desc_lbl)

            link = QLabel(f'<a href="{url}" style="color:#569cd6;">{url}</a>')
            link.setOpenExternalLinks(True)
            fb.addRow("Ссылка:", link)

            if pkg.startswith("http"):
                pass
            else:
                install_btn = QPushButton("⬇ Установить")
                install_btn.setStyleSheet(
                    "QPushButton{background:#0e639c;color:white;padding:4px 12px;border-radius:3px;}"
                    "QPushButton:hover{background:#1177bb;}"
                    "QPushButton:disabled{background:#333;color:#666;}")
                install_btn.setEnabled(not installed)
                install_btn.clicked.connect(lambda _, b=install_btn, s=status_btn, p=pkg: self._install(p, b, s))
                fb.addRow("", install_btn)

            layout.addWidget(gb)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            "QPushButton{background:#3c3c3c;color:#ccc;padding:6px 20px;border-radius:3px;}"
            "QPushButton:hover{background:#4c4c4c;}")
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.log_out = QTextEdit()
        self.log_out.setReadOnly(True)
        self.log_out.setMaximumHeight(150)
        self.log_out.setStyleSheet("background:#1e1e1e;color:#d4d4d4;font:11px Consolas;border:1px solid #333;")
        layout.addWidget(self.log_out)

    @staticmethod
    def _check(pkg):
        if pkg == "torch":
            try:
                import torch; return True
            except Exception:
                return False
        elif pkg == "numpy":
            try:
                import numpy; return True
            except Exception:
                return False
        elif pkg == "arduino-cli":
            try:
                return shutil.which("arduino-cli") is not None
            except Exception:
                return False
        return False

    @staticmethod
    def _find_python():
        """Найти python.exe в системе (для frozen-режима)"""
        import sys
        if not getattr(sys, 'frozen', False):
            return sys.executable
        for name in ['python', 'python3', 'py']:
            exe = shutil.which(name)
            if exe:
                return exe
        return None

    def _install(self, pkg, btn, status_btn):
        python_exe = self._find_python()
        if not python_exe:
            QMessageBox.warning(self, "Ошибка",
                "Python не найден в PATH.\n"
                "Установите Python с python.org и повторите попытку.")
            return

        btn.setEnabled(False)
        btn.setText("⏳ Установка…")
        self.log_out.clear()
        self.log_out.append(f"$ {python_exe} -m pip install {pkg}" +
                            (" --index-url https://download.pytorch.org/whl/cpu" if pkg == "torch" else ""))

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(lambda: self.log_out.append(
            self._proc.readAllStandardOutput().data().decode('utf-8', errors='replace').rstrip()))
        self._proc.finished.connect(lambda ec, es: self._install_done(ec, btn, status_btn, pkg))

        args = ["-m", "pip", "install", pkg]
        if pkg == "torch":
            args += ["--index-url", "https://download.pytorch.org/whl/cpu"]
        self._proc.start(python_exe, args)

    def _install_done(self, exit_code, btn, status_btn, pkg):
        btn.setEnabled(True)
        if exit_code == 0:
            status_btn.setText("✓ Установлен")
            status_btn.setStyleSheet("background:#2d4d2d;color:#6bdb6b;padding:4px;border-radius:3px;")
            btn.setText("✓ Готово")
            self.log_out.append("✓ Установка завершена")
        else:
            btn.setText("⬇ Ошибка")
            self.log_out.append("✗ Установка не удалась")


class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str, str)
    error = pyqtSignal(str)
    up_to_date = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = VERSION

    def run(self):
        import urllib.request
        try:
            req = urllib.request.Request(VERSION_URL, headers={'User-Agent': 'CodeEditor'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            remote = data.get('version', '')
            if not remote:
                self.error.emit("Не удалось определить версию на сервере")
                return
            if self._compare_versions(remote, self.current_version) > 0:
                self.update_available.emit(remote, self.current_version, data.get('url', ''))
            else:
                self.up_to_date.emit()
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def _compare_versions(a, b):
        aparts = [int(x) for x in a.split('.')]
        bparts = [int(x) for x in b.split('.')]
        for i in range(max(len(aparts), len(bparts))):
            av = aparts[i] if i < len(aparts) else 0
            bv = bparts[i] if i < len(bparts) else 0
            if av > bv: return 1
            if av < bv: return -1
        return 0


class CodeEditorApp(QMainWindow):
    """Главное приложение редактора кода"""
    
    SUPPORTED_LANGUAGES = {
        'Python': 'python', 'JavaScript': 'javascript', 'Java': 'java',
        'C++': 'cpp', 'C#': 'csharp', 'TypeScript': 'typescript',
        'PHP': 'php', 'Go': 'go', 'Rust': 'rust', 'Swift': 'swift',
        'Kotlin': 'kotlin', 'Ruby': 'ruby', 'SQL': 'sql', 'R': 'r',
        'C': 'c', 'Dart': 'dart', 'Lua': 'lua', 'MATLAB': 'matlab',
        'Scala': 'scala', 'Perl': 'perl', 'Objective-C': 'objective-c',
        'Haskell': 'haskell', 'Clojure': 'clojure', 'Elixir': 'elixir',
        'Erlang': 'erlang',         'F#': 'fsharp', 'Firebase Rules': 'firebase-rules', 'Groovy': 'groovy', 'Julia': 'julia',
        'Delphi/Pascal': 'pascal', 'Visual Basic .NET': 'vbnet', 'COBOL': 'cobol',
        'Fortran': 'fortran', 'Assembly': 'asm', 'Bash/Shell': 'bash',
        'PowerShell': 'powershell', 'ABAP': 'abap', 'PL/SQL': 'plsql',
        'Apex': 'apex', 'SAS': 'sas', 'Scratch': 'scratch', 'OrionScript': 'text',
        'HTML5': 'html', 'CSS': 'css', 'JSON': 'json', 'XML': 'xml', 'YAML': 'yaml',
        'Markdown': 'markdown', 'Plain Text': 'text'
    }
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Code Editor")
        # размер под экран пользователя
        screen = QApplication.primaryScreen().geometry()
        w = min(1400, screen.width() - 60)
        h = min(800, screen.height() - 80)
        self.setGeometry(30, 30, w, h)
        self.setMinimumSize(800, 400)
        
        self.open_files = {}  # {filepath: editor_instance}
        self.current_file = None
        
        self.init_ui()
        self.load_styles()
        self._init_alan()
        QTimer.singleShot(3000, self._check_updates_silent)
        
    def init_ui(self):
        """Инициализировать интерфейс"""
        # Главный виджет
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        
        # Левая часть - проводник
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Файловая структура:"))
        self.file_tree = FileTreeWidget()
        self.file_tree.file_selected.connect(self.open_file)
        left_layout.addWidget(self.file_tree)
        
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMaximumWidth(300)
        
        # Правая часть - редактор
        right_layout = QVBoxLayout()
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        btn_open_dir = QPushButton("📁 Открыть папку")
        btn_open_dir.clicked.connect(self.open_directory)
        toolbar_layout.addWidget(btn_open_dir)
        
        btn_new_file = QPushButton("📄 Новый файл")
        btn_new_file.clicked.connect(self.new_file)
        toolbar_layout.addWidget(btn_new_file)
        
        btn_save = QPushButton("💾 Сохранить")
        btn_save.clicked.connect(self.save_current_file)
        toolbar_layout.addWidget(btn_save)
        
        btn_save_all = QPushButton("💾 Сохранить всё")
        btn_save_all.clicked.connect(self.save_all_files)
        toolbar_layout.addWidget(btn_save_all)
        
        toolbar_layout.addWidget(QLabel("Язык:"))
        self.language_combo = QComboBox()
        self.language_combo.setEditable(True)
        self.language_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.language_combo.setMaxVisibleItems(15)
        self.language_combo.setIconSize(QSize(14, 14))
        lang_list = sorted(self.SUPPORTED_LANGUAGES.keys())
        # OrionScript всегда первый
        if 'OrionScript' in lang_list:
            lang_list.remove('OrionScript')
            lang_list.insert(0, 'OrionScript')
        self.language_combo.addItems(lang_list)
        for i, lang in enumerate(lang_list):
            icon = self._get_language_icon(lang)
            if icon:
                self.language_combo.setItemIcon(i, icon)
        completer = self.language_combo.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.language_combo.currentTextChanged.connect(self.on_language_changed)
        toolbar_layout.addWidget(self.language_combo)
        
        toolbar_layout.addWidget(QLabel("Размер шрифта:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setValue(11)
        self.font_size_spin.setMinimum(8)
        self.font_size_spin.setMaximum(32)
        self.font_size_spin.valueChanged.connect(self.on_font_size_changed)
        toolbar_layout.addWidget(self.font_size_spin)
        
        self.btn_scratch = QPushButton(" Scratch IDE")
        self.btn_scratch.setToolTip("Открыть Scratch→JS транслятор в новой вкладке")
        self.btn_scratch.clicked.connect(self.open_scratch_ide)
        self.btn_scratch.setVisible(False)
        toolbar_layout.addWidget(self.btn_scratch)
        
        self.btn_send = QPushButton(" Запустить на Сцене")
        self.btn_send.setToolTip("Скомпилировать и отправить код в Scratch IDE")
        self.btn_send.clicked.connect(self.send_to_scratch)
        self.btn_send.setVisible(False)
        toolbar_layout.addWidget(self.btn_send)
        
        self.btn_ose = QPushButton(" OSE")
        self.btn_ose.setToolTip("Создать новый файл OrionScript (.os)")
        self.btn_ose.clicked.connect(self.open_ose_editor)
        ose_icon = _load_icon(os.path.join(ASSETS_DIR, "OrionScriptLogo.png"))
        if ose_icon:
            self.btn_ose.setIcon(ose_icon)
            self.btn_ose.setIconSize(QSize(16, 16))
        toolbar_layout.addWidget(self.btn_ose)
        
        # Arduino
        toolbar_layout.addWidget(QLabel("Порт:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(100)
        self.port_combo.setToolTip("COM-порт для прошивки Arduino")
        toolbar_layout.addWidget(self.port_combo)
        
        self.btn_refresh_ports = QPushButton("🔄")
        self.btn_refresh_ports.setToolTip("Обновить список портов")
        self.btn_refresh_ports.setMaximumWidth(32)
        self.btn_refresh_ports.clicked.connect(self.refresh_com_ports)
        toolbar_layout.addWidget(self.btn_refresh_ports)
        
        self.btn_compile = QPushButton("⚡ Компилировать .ino")
        self.btn_compile.setToolTip("Сгенерировать .ino скетч из Scratch JSON во вкладке")
        self.btn_compile.clicked.connect(self.compile_ino)
        toolbar_layout.addWidget(self.btn_compile)
        
        self.btn_upload = QPushButton("📡 Прошить")
        self.btn_upload.setToolTip("Скомпилировать и прошить в Arduino через arduino-cli")
        self.btn_upload.clicked.connect(self.compile_and_upload)
        toolbar_layout.addWidget(self.btn_upload)
        
        # Alan AI
        self.btn_alan = QPushButton("🤖 Alan AI")
        self.btn_alan.setToolTip("Открыть панель Alan AI")
        self.btn_alan.clicked.connect(self.toggle_alan)
        toolbar_layout.addWidget(self.btn_alan)

        # Визуализация алгоритмов и SQL
        toolbar_layout.addWidget(QLabel("  Визуализация:"))
        
        self.btn_viz_algo = QPushButton("📊 Алгоритм")
        self.btn_viz_algo.setToolTip("Запустить трассировку алгоритма (JSON-массив чисел)")
        self.btn_viz_algo.clicked.connect(self.run_algorithm_trace)
        toolbar_layout.addWidget(self.btn_viz_algo)
        
        self.btn_viz_sql = QPushButton("🗄 SQL SELECT")
        self.btn_viz_sql.setToolTip("Выполнить SQL SELECT с WHERE и показать визуализацию")
        self.btn_viz_sql.clicked.connect(self.run_sql_visualization)
        toolbar_layout.addWidget(self.btn_viz_sql)
        
        toolbar_layout.addStretch()
        
        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)
        right_layout.addWidget(toolbar_widget)
        
        # Вкладки с редакторами
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        right_layout.addWidget(self.tab_widget)
        
        # Правая панель (редактор + терминал)
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        
        # Терминал в нижней части
        self.terminal = TerminalWidget()
        self.terminal.setMinimumHeight(100)
        
        # Вертикальный сплиттер: сверху редактор, снизу терминал
        vert_splitter = QSplitter(Qt.Orientation.Vertical)
        vert_splitter.addWidget(right_widget)
        vert_splitter.addWidget(self.terminal)
        vert_splitter.setSizes([500, 150])
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")
        
        # Горизонтальный сплиттер: слева файлы, справа редактор+терминал
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(vert_splitter)
        splitter.setSizes([300, 1100])
        
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        
        # Меню
        self.create_menu()
        
        # Подключение сигналов терминала
        self.terminal.request_run.connect(self._terminal_run)
        self.terminal.request_scratch_open.connect(self.open_scratch_ide)
        self.terminal.request_hardware_scan.connect(self._terminal_hardware_scan)
        self.terminal.request_ose_run.connect(self._terminal_ose_run)
        self.terminal.request_focus.connect(self._terminal_focus)
        
    def create_menu(self):
        """Создать меню приложения"""
        menubar = self.menuBar()
        
        # File меню
        file_menu = menubar.addMenu("Файл")
        
        action_open_dir = QAction("Открыть папку", self)
        action_open_dir.triggered.connect(self.open_directory)
        file_menu.addAction(action_open_dir)
        
        action_open = QAction("Открыть файл", self)
        action_open.triggered.connect(self.open_file_dialog)
        file_menu.addAction(action_open)
        
        action_new = QAction("Новый файл", self)
        action_new.triggered.connect(self.new_file)
        file_menu.addAction(action_new)
        
        action_save = QAction("Сохранить", self)
        action_save.setShortcut(QKeySequence.StandardKey.Save)
        action_save.triggered.connect(self.save_current_file)
        file_menu.addAction(action_save)

        action_save_as = QAction("Сохранить как...", self)
        action_save_as.triggered.connect(self.save_file_as)
        file_menu.addAction(action_save_as)

        action_save_all = QAction("Сохранить всё", self)
        action_save_all.triggered.connect(self.save_all_files)
        file_menu.addAction(action_save_all)
        
        file_menu.addSeparator()
        
        action_exit = QAction("Выход", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)
        
        # Edit меню
        edit_menu = menubar.addMenu("Правка")
        
        action_undo = QAction("Отменить", self)
        action_undo.triggered.connect(lambda: self.current_editor().undo() if self.current_editor() else None)
        edit_menu.addAction(action_undo)
        
        action_redo = QAction("Повторить", self)
        action_redo.triggered.connect(lambda: self.current_editor().redo() if self.current_editor() else None)
        edit_menu.addAction(action_redo)
        
        edit_menu.addSeparator()
        
        action_select_all = QAction("Выбрать всё", self)
        action_select_all.triggered.connect(lambda: self.current_editor().selectAll() if self.current_editor() else None)
        edit_menu.addAction(action_select_all)
        
        # View меню
        view_menu = menubar.addMenu("Вид")
        
        action_increase_font = QAction("Увеличить шрифт", self)
        action_increase_font.triggered.connect(self.increase_font_size)
        view_menu.addAction(action_increase_font)
        
        action_decrease_font = QAction("Уменьшить шрифт", self)
        action_decrease_font.triggered.connect(self.decrease_font_size)
        view_menu.addAction(action_decrease_font)
        
        view_menu.addSeparator()
        
        action_scratch = QAction(" Scratch IDE", self)
        action_scratch.setToolTip("Открыть Scratch→JS транслятор")
        scratch_icon = _load_icon(os.path.join(ASSETS_DIR, "Scratch3-original.png"))
        if scratch_icon:
            action_scratch.setIcon(scratch_icon)
        action_scratch.triggered.connect(self.open_scratch_ide)
        view_menu.addAction(action_scratch)

        # Help меню
        help_menu = menubar.addMenu("Справка")
        action_deps = QAction("⚙ Утилиты", self)
        action_deps.setToolTip("Управление зависимостями (PyTorch, NumPy, arduino-cli)")
        action_deps.triggered.connect(self._open_deps_dialog)
        help_menu.addAction(action_deps)

        help_menu.addSeparator()

        action_check_upd = QAction("🔄 Проверить обновления", self)
        action_check_upd.triggered.connect(self.check_for_updates)
        help_menu.addAction(action_check_upd)

    def _open_deps_dialog(self):
        try:
            dlg = DependenciesDialog(self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог утилит:\n{e}")

    def check_for_updates(self):
        if hasattr(self, '_updater_active') and self._updater_active:
            return
        self._updater_active = True
        self.updater = UpdateChecker()
        self.updater.update_available.connect(self._on_update_available)
        self.updater.error.connect(self._on_update_error)
        self.updater.up_to_date.connect(self._on_up_to_date)
        self.updater.finished.connect(self.updater.deleteLater)
        self.updater.finished.connect(lambda: setattr(self, '_updater_active', False))
        self.updater.start()
        QMessageBox.information(self, "Проверка обновлений", "Проверка наличия обновлений…")

    def _check_updates_silent(self):
        if hasattr(self, '_updater_active') and self._updater_active:
            return
        self._updater_active = True
        self.updater = UpdateChecker()
        self.updater.update_available.connect(self._on_update_available)
        self.updater.error.connect(lambda err: setattr(self, '_updater_active', False))
        self.updater.up_to_date.connect(lambda: setattr(self, '_updater_active', False))
        self.updater.finished.connect(self.updater.deleteLater)
        self.updater.finished.connect(lambda: setattr(self, '_updater_active', False))
        self.updater.start()

    def _on_up_to_date(self):
        QMessageBox.information(self, "Обновлений нет",
            f"У вас установлена последняя версия ({VERSION}).")

    def _on_update_error(self, err):
        QMessageBox.warning(self, "Ошибка проверки",
            f"Не удалось проверить обновления:\n{err}\n\n"
            "Проверьте подключение к интернету или скачайте новую версию вручную:\n"
            f"https://github.com/{GITHUB_REPO}/releases")

    def _on_update_available(self, remote, current, url):
        import subprocess
        answer = QMessageBox.question(self, "Доступно обновление",
            f"Доступна новая версия: {remote}\n"
            f"Текущая версия: {current}\n\n"
            "Хотите скачать установщик?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes and url:
            import urllib.request
            save_path = os.path.join(tempfile.gettempdir(),
                f"CodeEditor_Setup_{remote}.exe")
            try:
                self.statusBar().showMessage(f"Скачиваю {remote}…")
                urllib.request.urlretrieve(url, save_path)
                self.statusBar().showMessage("Запуск установщика…")
                subprocess.Popen([save_path, '/SILENT', f'/D={BASE_DIR}'],
                    creationflags=0x08000000)
                QApplication.quit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка",
                    f"Не удалось скачать обновление:\n{e}\n\n"
                    f"Скачайте вручную: {url}")



    @staticmethod
    def _find_index_html():
        candidates = [
            os.path.join(BASE_DIR, "index.html"),
            os.path.join(os.getcwd(), "index.html"),
            os.path.join(os.path.dirname(__file__), "index.html"),
        ]
        if getattr(sys, 'frozen', False):
            candidates.append(os.path.join(os.path.dirname(sys.executable), "index.html"))
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def open_scratch_ide(self):
        """Открыть Scratch→JS IDE в новой вкладке редактора"""
        if not HAVE_WEBENGINE:
            QMessageBox.warning(
                self, "Ошибка",
                "PyQt6 WebEngine не установлен.\n"
                "Установите: pip install PyQt6-WebEngine"
            )
            return
        
        # Если уже открыта — переключиться
        for fp, w in self.open_files.items():
            if fp == "__scratch_ide__":
                idx = self.tab_widget.indexOf(w)
                self.tab_widget.setCurrentIndex(idx)
                return
        
        viewer = QWebEngineView()
        index_path = self._find_index_html()
        if not index_path:
            QMessageBox.warning(self, "Ошибка",
                "index.html не найден.\n"
                "Убедитесь, что файл index.html находится в папке редактора.")
            return
        
        # Мост QWebChannel
        self.scratch_bridge = ScratchBridge()
        self.scratch_bridge.setPage(viewer.page())
        self.scratch_bridge.log_received.connect(self._on_scratch_log)
        
        channel = QWebChannel()
        channel.registerObject("bridge", self.scratch_bridge)
        viewer.page().setWebChannel(channel)
        
        viewer.setUrl(QUrl.fromLocalFile(index_path))
        
        self.scratch_viewer = viewer
        self.open_files["__scratch_ide__"] = viewer
        tab_idx = self.tab_widget.addTab(viewer, " Scratch IDE")
        scratch_icon = _load_icon(os.path.join(ASSETS_DIR, "Scratch3-original.png"))
        if scratch_icon:
            self.tab_widget.setTabIcon(tab_idx, scratch_icon)
            self.btn_scratch.setIcon(scratch_icon)
            self.btn_scratch.setIconSize(QSize(16, 16))
            self.btn_send.setIcon(scratch_icon)
            self.btn_send.setIconSize(QSize(16, 16))
        self.tab_widget.setCurrentIndex(tab_idx)
        self.status_bar.showMessage("Scratch→JS IDE загружен")
    
    def open_ose_editor(self):
        """Создать новый файл OrionScript (.os), сохранить на диск (если открыта папка)
        и отобразить в проводнике."""
        # Определяем директорию для сохранения
        root = self.file_tree.current_root if hasattr(self, 'file_tree') else None
        if root and os.path.isdir(root):
            base_name = "new.os"
            full_path = os.path.join(root, base_name)
            counter = 1
            while os.path.exists(full_path):
                full_path = os.path.join(root, f"new_{counter}.os")
                counter += 1
            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write("# OrionScript (.os)\n")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать файл: {e}")
                return
            # Открываем созданный файл
            self.open_file(full_path)
            # Обновляем проводник
            parent_item = self.file_tree._find_item_by_path(root)
            if parent_item:
                self.file_tree._refresh_item(parent_item, root)
            self.status_bar.showMessage(f"Создан: {full_path}")
        else:
            # Нет открытой папки — просто открываем вкладку
            editor = CodeEditor()
            editor.setPlainText("# OrionScript (.os)\n")
            editor.set_completion_language("OrionScript")
            tab_idx = self.tab_widget.addTab(editor, " new.os")
            ose_icon = _load_icon(os.path.join(ASSETS_DIR, "OrionScriptLogo.png"))
            if ose_icon:
                self.tab_widget.setTabIcon(tab_idx, ose_icon)
            self.tab_widget.setCurrentIndex(tab_idx)
            self.current_file = None
            idx = self.language_combo.findText("OrionScript")
            if idx >= 0:
                self.language_combo.setCurrentIndex(idx)
            self.apply_syntax_highlighting(editor)
            self.status_bar.showMessage("Новый файл OrionScript создан (без сохранения)")

    def _on_scratch_log(self, level, message):
        """Показать лог из Scratch IDE в статус-баре."""
        tag = level.upper()
        self.status_bar.showMessage(f"[{tag}] {message}", 5000)
    
    def send_to_scratch(self):
        """Отправить содержимое редактора в Scratch IDE и запустить."""
        if not hasattr(self, 'scratch_viewer') or self.scratch_viewer is None:
            QMessageBox.warning(self, "Ошибка", "Scratch IDE не открыт.\nНажмите кнопку «Scratch IDE» сначала.")
            return
        
        editor = self.current_editor()
        if editor is None:
            QMessageBox.warning(self, "Ошибка", "Нет активного редактора кода.")
            return
        
        # Определяем путь к файлу текущего редактора
        filepath = None
        for fp, ed in self.open_files.items():
            if ed is editor:
                filepath = fp
                break
        
        # Если файл .sb3 — читаем бинарно и отправляем через Base64
        if filepath and filepath.lower().endswith('.sb3'):
            if hasattr(self, 'scratch_bridge') and self.scratch_bridge is not None:
                self.scratch_bridge.sendSb3ToWeb(filepath)
                self.status_bar.showMessage(f"✓ .sb3 отправлен в Scratch IDE: {os.path.basename(filepath)}")
            return
        
        text = editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Редактор пуст.")
            return
        
        # Просто отправляем raw текст в браузер — он сам разберётся:
        # JSON-блоки → loadJSON() (транспиляция в браузере)
        # Сырой JS → выполнить напрямую
        # Base64 .sb3 → распаковать через JSZip
        if hasattr(self, 'scratch_bridge'):
            self.scratch_bridge.sendCodeToWeb(text)
            self.status_bar.showMessage(f"Код отправлен в Scratch IDE ({len(text)} символов)")
    
    def refresh_com_ports(self):
        """Сканировать доступные COM-порты."""
        self.port_combo.clear()
        if not HAVE_SERIALPORT:
            self.port_combo.addItem("— QtSerialPort не найден —")
            return
        ports = QSerialPortInfo.availablePorts()
        if not ports:
            self.port_combo.addItem("— Порты не найдены —")
        for p in ports:
            desc = p.description().strip()
            label = f"{p.portName()} — {desc}" if desc else p.portName()
            self.port_combo.addItem(label, p.portName())
        self.status_bar.showMessage(f"COM-портов: {len(ports)}")
    
    def compile_ino(self):
        """Сгенерировать .ino скетч из Scratch JSON в активной вкладке."""
        editor = self.current_editor()
        if editor is None:
            QMessageBox.warning(self, "Ошибка", "Нет активного редактора кода.")
            return
        text = editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Редактор пуст.")
            return
        try:
            blocks = json.loads(text)
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Ошибка", "Неверный JSON в редакторе.")
            return
        try:
            from transpile import transpile_to_ino
            ino = transpile_to_ino(blocks)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка генерации", str(e))
            return
        
        # Открыть новую вкладку с .ino кодом
        viewer = QPlainTextEdit()
        viewer.setPlainText(ino)
        viewer.setReadOnly(True)
        viewer.setFont(QFont("Consolas", 10))
        viewer.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        self.open_files["__ino_output__"] = viewer
        idx = self.tab_widget.addTab(viewer, "⚙ sketch.ino")
        self.tab_widget.setCurrentIndex(idx)
        self.status_bar.showMessage(f".ino скетч сгенерирован ({len(ino)} символов)")
    
    def compile_and_upload(self):
        """Скомпилировать .ino и прошить в Arduino через arduino-cli."""
        editor = self.current_editor()
        if editor is None:
            QMessageBox.warning(self, "Ошибка", "Нет активного редактора кода.")
            return
        text = editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Редактор пуст.")
            return
        # Определяем, это JSON блоки или уже .ino код
        is_json = False
        try:
            json.loads(text)
            is_json = True
        except json.JSONDecodeError:
            pass
        
        port = self.port_combo.currentData()
        if not port or port.startswith("—"):
            QMessageBox.warning(self, "Ошибка", "Выберите COM-порт для прошивки.")
            return
        
        try:
            if is_json:
                from transpile import transpile_to_ino
                blocks = json.loads(text)
                ino_code = transpile_to_ino(blocks)
            else:
                ino_code = text
        except Exception as e:
            QMessageBox.critical(self, "Ошибка генерации", str(e))
            return
        
        self._run_arduino_cli(ino_code, port)
    
    def _run_arduino_cli(self, ino_code, port):
        """Запустить arduino-cli compile + upload через QProcess."""
        sketch_dir = tempfile.mkdtemp(prefix="ino_")
        sketch_file = os.path.join(sketch_dir, "sketch.ino")
        try:
            with open(sketch_file, "w", encoding="utf-8") as f:
                f.write(ino_code)
        except OSError as e:
            QMessageBox.critical(self, "Ошибка записи", str(e))
            return
        
        # Показать лог-вкладку
        log_viewer = QPlainTextEdit()
        log_viewer.setReadOnly(True)
        log_viewer.setFont(QFont("Consolas", 10))
        log_viewer.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        self.open_files["__compile_log__"] = log_viewer
        idx = self.tab_widget.addTab(log_viewer, "📟 Компиляция")
        self.tab_widget.setCurrentIndex(idx)
        log_viewer.appendPlainText(f"# Компиляция: {sketch_dir}\n")
        
        fqbn = "arduino:avr:uno"
        
        # Этап 1: compile
        self._run_process("arduino-cli", [
            "compile", "--fqbn", fqbn, sketch_dir
        ], log_viewer, lambda: self._run_upload(sketch_dir, port, fqbn, log_viewer))
    
    def _run_upload(self, sketch_dir, port, fqbn, log_viewer):
        """Этап 2: upload после успешной компиляции."""
        log_viewer.appendPlainText("\n# Загрузка на плату...\n")
        self._run_process("arduino-cli", [
            "upload", "-p", port, "--fqbn", fqbn, sketch_dir
        ], log_viewer, lambda: log_viewer.appendPlainText("\n✓ Прошивка завершена!"))
    
    def _run_process(self, program, args, log_viewer, on_success=None):
        """Запустить внешнюю программу через QProcess с построчным логом."""
        self.status_bar.showMessage(f"Запуск: {program} {' '.join(args)}...")
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        
        def on_ready_read():
            data = proc.readAll().data().decode("utf-8", errors="replace")
            for line in data.splitlines():
                log_viewer.appendPlainText(line)
        
        proc.readyReadStandardOutput.connect(on_ready_read)
        
        def on_finished(exit_code, exit_status):
            if exit_code == 0:
                log_viewer.appendPlainText("\n✓ Успешно")
                self.status_bar.showMessage("✓ Компиляция/прошивка выполнена")
                if on_success:
                    on_success()
            else:
                log_viewer.appendPlainText(f"\n✗ Код ошибки: {exit_code}")
                self.status_bar.showMessage(f"✗ Ошибка (код {exit_code})")
        
        proc.finished.connect(on_finished)
        proc.start(program, args)
        self._current_process = proc
    
    def run_algorithm_trace(self):
        """Сгенерировать шаги трассировки алгоритма из JSON в редакторе."""
        if not hasattr(self, 'scratch_viewer') or self.scratch_viewer is None:
            QMessageBox.warning(self, "Ошибка", "Scratch IDE не открыт.\nНажмите кнопку «Scratch IDE» сначала.")
            return
        editor = self.current_editor()
        if editor is None:
            QMessageBox.warning(self, "Ошибка", "Нет активного редактора кода.")
            return
        text = editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Редактор пуст.")
            return
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Ошибка", "Неверный JSON.\n\nФорматы:\n[1,5,3,8,2] — массив\n{\"array\":[1,5,3,8,2],\"algo\":\"quick\"}\n{\"type\":\"linked_list\",\"values\":[1,2,3],\"search\":2}\n{\"type\":\"bst\",\"values\":[10,5,15],\"search\":5}")
            return
        try:
            steps = None; label = ""
            if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
                steps = BackendAlgorithmTracer.bubble_sort(data)
                label = f"пузырьковая сортировка ({len(data)} эл., {len(steps)} шагов)"
            elif isinstance(data, dict):
                if "array" in data:
                    algo = data.get("algo", "bubble")
                    steps = BackendAlgorithmTracer.sort(data["array"], algo)
                    label = f"{algo} сортировка ({len(steps)} шагов)"
                elif data.get("type") == "linked_list":
                    vals = data.get("values", [])
                    if "search" in data:
                        steps = BackendAlgorithmTracer.linked_list_search(vals, data["search"])
                        label = f"поиск {data['search']} в списке ({len(steps)} шагов)"
                    elif "delete" in data:
                        steps = BackendAlgorithmTracer.linked_list_delete(vals, data["delete"])
                        label = f"удаление {data['delete']} из списка ({len(steps)} шагов)"
                    else:
                        steps = BackendAlgorithmTracer.linked_list(vals)
                        label = f"связный список ({len(steps)} узлов)"
                elif data.get("type") == "bst":
                    vals = data.get("values", [])
                    if "search" in data:
                        steps = BackendAlgorithmTracer.binary_tree_search(vals, data["search"])
                        label = f"поиск {data['search']} в BST ({len(steps)} шагов)"
                    elif "delete" in data:
                        steps = BackendAlgorithmTracer.binary_tree_delete(vals, data["delete"])
                        label = f"удаление {data['delete']} из BST ({len(steps)} шагов)"
                    else:
                        steps = BackendAlgorithmTracer.binary_tree(vals)
                        label = f"BST ({len(steps)} узлов)"
                elif "steps" in data and isinstance(data["steps"], list):
                    steps = data["steps"]
                    label = f"пользовательские шаги ({len(steps)})"
            elif isinstance(data, list) and all(isinstance(x, dict) for x in data):
                steps = data
                label = f"пользовательские шаги ({len(steps)})"
            if steps is None:
                QMessageBox.warning(self, "Ошибка", f"Неподдерживаемый формат: {type(data).__name__}")
                return
            self._switch_to_scratch_and_send(json.dumps(steps), "algo")
            self.status_bar.showMessage(f"✓ Алгоритм: {label}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка трассировки", str(e))
    
    def run_sql_visualization(self):
        """Распарсить SQL-запрос из редактора и показать визуализацию."""
        if not hasattr(self, 'scratch_viewer') or self.scratch_viewer is None:
            QMessageBox.warning(self, "Ошибка", "Scratch IDE не открыт.\nНажмите кнопку «Scratch IDE» сначала.")
            return
        editor = self.current_editor()
        if editor is None:
            QMessageBox.warning(self, "Ошибка", "Нет активного редактора кода.")
            return
        text = editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Редактор пуст.")
            return
        try:
            steps = None; label = ""
            raw = text.lstrip()
            if raw.upper().startswith("SELECT"):
                steps, results, tbl, total, passed = SQLWhereParser.generate_steps(text)
                label = f"SQL {tbl}: {total} строк, {passed} прошло ({len(steps)} шагов)"
            else:
                data = json.loads(text)
                if isinstance(data, list) and data and data[0].get("type") == "sql":
                    steps, results = data, []
                    label = f"SQL-шаги ({len(steps)})"
                elif isinstance(data, dict) and "columns" in data and "rows" in data:
                    where = data.get("where", "True")
                    fake_sql = f"SELECT * FROM t WHERE {where}"
                    steps, results, tbl, total, passed = SQLWhereParser.generate_steps(fake_sql, data)
                    label = f"SQL: {total} строк, {passed} прошло ({len(steps)} шагов)"
                elif isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
                    steps = BackendAlgorithmTracer.bubble_sort(data)
                    label = f"сортировка через SQL-кнопку ({len(steps)} шагов)"
            if steps is None:
                QMessageBox.warning(self, "Ошибка", "Неверный формат.\n\nИспользуйте:\nSELECT * FROM users WHERE age > 20\nили JSON с шагами SQL")
                return
            self._switch_to_scratch_and_send(json.dumps(steps), "sql")
            self.status_bar.showMessage(f"✓ {label}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка SQL", str(e))
    
    def _switch_to_scratch_and_send(self, json_str, mode):
        """Переключиться на Scratch IDE и отправить snapshot-шаги."""
        # Переключаемся на вкладку Scratch IDE
        for fp, w in self.open_files.items():
            if fp == "__scratch_ide__":
                idx = self.tab_widget.indexOf(w)
                self.tab_widget.setCurrentIndex(idx)
                break
        
        if hasattr(self, 'scratch_bridge') and self.scratch_bridge is not None:
            self.scratch_bridge.sendJsonToWeb(json_str, mode)
    
    # ── Terminal callback helpers ──────────────────────────────

    def _terminal_run(self):
        """Запустить текущий файл — сохранить и выполнить."""
        editor = self.current_editor()
        if editor is None:
            self.terminal.write_stdout("<stderr>Нет активного редактора.</stderr>\n")
            return
        filepath = None
        for fp, ed in self.open_files.items():
            if ed is editor:
                filepath = fp
                break
        if filepath:
            self.save_current_file()
            ext = os.path.splitext(filepath)[1].lower()
            runners = {
                '.py': ['python', filepath],
                '.js': ['node', filepath],
                '.ts': ['npx', 'ts-node', filepath],
                '.cpp': ['g++', filepath, '-o', filepath + '.exe', '&&', filepath + '.exe'],
                '.c': ['gcc', filepath, '-o', filepath + '.exe', '&&', filepath + '.exe'],
                '.rs': ['rustc', filepath, '-o', filepath + '.exe', '&&', filepath + '.exe'],
                '.go': ['go', 'run', filepath],
                '.rb': ['ruby', filepath],
                '.php': ['php', filepath],
                '.swift': ['swift', filepath],
                '.kt': ['kotlinc', '-script', filepath],
                '.sh': ['bash', filepath],
                '.ps1': ['powershell', '-File', filepath],
                '.lua': ['lua', filepath],
                '.pl': ['perl', filepath],
                '.r': ['Rscript', filepath],
                '.java': ['java', filepath],
                '.scala': ['scala', filepath],
            }
            # .os файлы компилируются в JS и запускаются в Scratch IDE
            if ext == '.os':
                self._terminal_run_os(editor, filepath)
                return
            cmd = runners.get(ext)
            if cmd:
                self.terminal.write_stdout(f"<system>▶ Запуск: {' '.join(cmd)}</system>\n")
                self._run_process_in_terminal(cmd)
            else:
                self.terminal.write_stdout(f"<stderr>Нет правила запуска для {ext}</stderr>\n")
        else:
            self.terminal.write_stdout("<stderr>Файл не сохранён на диск.</stderr>\n")

    def _terminal_hardware_scan(self):
        """Сканировать COM-порты и вывести в терминал."""
        if HAVE_SERIALPORT:
            ports = QSerialPortInfo.availablePorts()
            if not ports:
                self.terminal.write_stdout("<system>Порты не найдены.</system>\n")
                return
            lines = ["<system>Доступные COM-порты:</system>"]
            for p in ports:
                desc = p.description().strip()
                label = f"{p.portName()} — {desc}" if desc else p.portName()
                lines.append(f"  <system>{label}</system>")
            lines.append("")
            for line in lines:
                self.terminal.write_stdout(line + "\n")
        else:
            self.terminal.write_stdout("<stderr>QtSerialPort не установлен.</stderr>\n")

    def _terminal_run_os(self, editor, filepath):
        """Скомпилировать .os файл в JS и запустить в Scratch IDE."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code_text = f.read()
        except Exception as e:
            self.terminal.write_stdout(f"<stderr>Ошибка чтения .os файла: {e}</stderr>\n")
            return

        js, system_cmds = OrionCompiler.compile_to_js(code_text)
        if js:
            if hasattr(self, 'scratch_bridge') and self.scratch_bridge is not None:
                self.scratch_bridge.sendCodeToWeb(js)
                self.terminal.write_stdout(f"<system>✓ .os скомпилирован в JS и отправлен в Scratch IDE</system>\n")
            else:
                self.terminal.write_stdout(
                    "<stderr>Scratch IDE не открыт. Нажмите «Scratch IDE» на панели инструментов.</stderr>\n")
        else:
            self.terminal.write_stdout("<stderr>Не удалось скомпилировать .os — нет валидных команд.</stderr>\n")

        # Обработка системных команд
        for scmd, sline in system_cmds:
            if scmd == "focus":
                self._terminal_focus(sline)

    def _terminal_ose_run(self, js_code):
        """Отправить скомпилированный OrionScript в Scratch IDE для выполнения."""
        if hasattr(self, 'scratch_bridge') and self.scratch_bridge is not None:
            self.scratch_bridge.sendCodeToWeb(js_code)
            self.terminal.write_stdout("<system>✓ OSE код отправлен в Scratch IDE</system>\n")
        else:
            self.terminal.write_stdout("<stderr>Scratch IDE не открыт. Нажмите «Scratch IDE» на панели инструментов.</stderr>\n")

    def _terminal_focus(self, raw_line):
        """Обработать sys_focus — переключить вкладку."""
        import shlex
        try:
            parts = shlex.split(raw_line)
        except Exception:
            parts = raw_line.split()
        if len(parts) >= 2:
            target = parts[1].strip().lower()
            if "scratch" in target:
                self.open_scratch_ide()
                self.terminal.write_stdout(f"<system>✓ Фокус переключён на Scratch IDE</system>\n")
            elif "terminal" in target:
                self.terminal.write_stdout("<system>✓ Фокус на терминале (уже здесь)</system>\n")
            else:
                self.terminal.write_stdout(f"<stderr>sys_focus: вкладка «{target}» не найдена</stderr>\n")

    def _run_process_in_terminal(self, cmd_list):
        """Запустить внешний процесс и вывести stdout/stderr в терминал."""
        proc = QProcess(self)
        decode = self._decode_proc
        terminal = self.terminal
        proc.readyReadStandardOutput.connect(lambda p=proc: terminal.write_stdout(
            decode(p.readAllStandardOutput())))
        proc.readyReadStandardError.connect(lambda p=proc: terminal.write_stdout(
            "<stderr>" + decode(p.readAllStandardError()) + "</stderr>\n"))
        proc.finished.connect(lambda ec, es, p=proc: terminal.write_stdout(
            f"\n<system>■ Завершён (код {ec})</system>\n"))
        proc.start(cmd_list[0], cmd_list[1:])

    def _decode_proc(self, data):
        raw = data.data()
        for enc in ("utf-8", "cp866", "cp1251"):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace")
    
    def open_directory(self):
        """Открыть директорию"""
        try:
            path = QFileDialog.getExistingDirectory(self, "Выберите папку")
            if path:
                self.file_tree.load_directory(path)
                self.status_bar.showMessage(f"Папка загружена: {path}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть папку:\n{e}\n\n{tb}")
    
    def open_file(self, filepath=None):
        """Открыть файл"""
        if filepath is None:
            filepath, _ = QFileDialog.getOpenFileName(self, "Открыть файл")
        
        if not filepath or not os.path.exists(filepath):
            return
        
        if filepath in self.open_files:
            index = self.tab_widget.indexOf(self.open_files[filepath])
            self.tab_widget.setCurrentIndex(index)
            return
        
        _, ext = os.path.splitext(filepath.lower())
        if ext in IMAGE_EXTENSIONS:
            self._open_image(filepath)
            return
        
        if ext == '.sb3':
            self.open_scratch_ide()
            if hasattr(self, 'scratch_bridge') and self.scratch_bridge is not None:
                self.scratch_bridge.sendSb3ToWeb(filepath)
                self.status_bar.showMessage(f"✓ .sb3 загружен в Scratch IDE: {os.path.basename(filepath)}")
            return
        
        file_size = os.path.getsize(filepath)
        
        editor = CodeEditor()
        editor.setPlainText("Загрузка...")
        
        self.open_files[filepath] = editor
        tab_index = self.tab_widget.addTab(editor, os.path.basename(filepath))
        self.tab_widget.setCurrentIndex(tab_index)
        self.current_file = filepath
        
        if file_size > 5 * 1024 * 1024:
            self.status_bar.showMessage(f"Загрузка большого файла: {os.path.basename(filepath)} ({FileLoaderThread.format_size(file_size)})...")
            self._load_file_threaded(filepath, editor)
        else:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {e}")
                return
            
            self._finish_open_file(filepath, editor, content)
    
    def _open_image(self, filepath):
        """Открыть изображение"""
        if filepath in self.open_files:
            index = self.tab_widget.indexOf(self.open_files[filepath])
            self.tab_widget.setCurrentIndex(index)
            return
        viewer = ImageViewer(filepath)
        self.open_files[filepath] = viewer
        tab_index = self.tab_widget.addTab(viewer, os.path.basename(filepath))
        self.tab_widget.setCurrentIndex(tab_index)
        self.current_file = filepath
        size = os.path.getsize(filepath)
        self.status_bar.showMessage(f"Изображение: {os.path.basename(filepath)} "
                                    f"({FileLoaderThread.format_size(size)}) — {viewer.dimensions}")
    
    def _load_file_threaded(self, filepath, editor):
        """Загрузить большой файл в фоновом потоке"""
        self.loader = FileLoaderThread(filepath)
        self.loader.loaded.connect(lambda fp, content: self._finish_open_file(fp, editor, content))
        self.loader.error.connect(lambda fp, err: QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {err}"))
        self.loader.progress.connect(lambda msg: self.status_bar.showMessage(msg))
        self.loader.start()
    
    def _finish_open_file(self, filepath, editor, content):
        """Завершить открытие файла"""
        if editor not in self.open_files.values():
            return
        editor.setPlainText(content)
        editor.textChanged.connect(lambda: self.on_editor_modified(filepath))
        self.detect_language(filepath)
        self.apply_syntax_highlighting(editor)
        self.status_bar.showMessage(f"Открыт: {filepath}")
    
    def open_file_dialog(self):
        """Диалог открытия файла"""
        filepath, _ = QFileDialog.getOpenFileName(self, "Открыть файл")
        if filepath:
            self.open_file(filepath)
    
    def new_file(self):
        """Создать новый файл с выбором языка"""
        langs = sorted(self.SUPPORTED_LANGUAGES.keys())
        if 'OrionScript' in langs:
            langs.remove('OrionScript')
            langs.insert(0, 'OrionScript')
        lang, ok = QInputDialog.getItem(self, "Новый файл", "Выберите язык:", langs, 0, False)
        if not ok or not lang:
            return
        ext_map_rev = {v: k for k, v in self._ext_map().items()}
        lexer_name = self.SUPPORTED_LANGUAGES.get(lang, 'text')
        ext = ext_map_rev.get(lexer_name, '.txt')
        name, ok2 = QInputDialog.getText(self, "Новый файл", "Имя файла:", text=f"new{ext}")
        if not ok2 or not name:
            return
        editor = CodeEditor()
        tab_index = self.tab_widget.addTab(editor, name)
        self.tab_widget.setCurrentIndex(tab_index)
        self.current_file = None
        idx = self.language_combo.findText(lang)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)

    def _ext_map(self):
        return {
            '.py': 'python', '.js': 'javascript', '.java': 'java',
            '.cpp': 'cpp', '.cs': 'csharp', '.ts': 'typescript',
            '.php': 'php', '.go': 'go',         '.rs': 'rust', '.rules': 'firebase-rules', '.swift': 'swift',
            '.kt': 'kotlin', '.rb': 'ruby', '.sql': 'sql',
            '.r': 'r', '.c': 'c', '.dart': 'dart', '.lua': 'lua',
            '.m': 'objective-c', '.hs': 'haskell', '.clj': 'clojure',
            '.ex': 'elixir', '.erl': 'erlang', '.fs': 'fsharp',
            '.groovy': 'groovy', '.jl': 'julia', '.pas': 'pascal',
            '.vb': 'vbnet', '.cbl': 'cobol', '.f90': 'fortran',
            '.asm': 'asm', '.sh': 'bash', '.ps1': 'powershell',
            '.sas': 'sas', '.html': 'html', '.css': 'css',
            '.json': 'json', '.xml': 'xml', '.yaml': 'yaml',
            '.yml': 'yaml', '.md': 'markdown', '.txt': 'text', '.os': 'text',
        }
    
    def save_current_file(self):
        """Сохранить текущий файл"""
        editor = self.current_editor()
        if not editor:
            return
        
        if self.current_file is None:
            filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить файл")
            if not filepath:
                return
            self.current_file = filepath
        
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())
            
            # Обновить название вкладки
            current_index = self.tab_widget.currentIndex()
            self.tab_widget.setTabText(current_index, os.path.basename(self.current_file))
            
            self.status_bar.showMessage(f"Сохранено: {self.current_file}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {e}")
    
    def save_file_as(self):
        editor = self.current_editor()
        if not editor:
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить как")
        if not filepath:
            return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())
            self.current_file = filepath
            current_index = self.tab_widget.currentIndex()
            self.tab_widget.setTabText(current_index, os.path.basename(filepath))
            self.open_files[filepath] = editor
            self.status_bar.showMessage(f"Сохранено: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {e}")

    def save_all_files(self):
        """Сохранить все открытые файлы"""
        saved = 0
        for filepath, widget in list(self.open_files.items()):
            if isinstance(widget, ImageViewer) or not hasattr(widget, 'toPlainText'):
                continue
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(widget.toPlainText())
                idx = self.tab_widget.indexOf(widget)
                if idx >= 0:
                    name = os.path.basename(filepath)
                    self.tab_widget.setTabText(idx, name)
                saved += 1
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить {filepath}: {e}")
        if saved:
            self.status_bar.showMessage(f"Сохранено файлов: {saved}")

    def current_editor(self):
        """Получить текущий редактор (None для изображений)"""
        index = self.tab_widget.currentIndex()
        if index >= 0:
            widget = self.tab_widget.widget(index)
            if isinstance(widget, CodeEditor):
                return widget
        return None
    
    def close_tab(self, index):
        """Закрыть вкладку"""
        widget = self.tab_widget.widget(index)
        if widget:
            self.tab_widget.removeTab(index)
            for filepath, editor in list(self.open_files.items()):
                if editor == widget:
                    del self.open_files[filepath]
                    break
            # Очистить мост, если закрыли Scratch IDE
            if hasattr(self, 'scratch_viewer') and self.scratch_viewer is widget:
                self.scratch_viewer = None
                self.scratch_bridge = None

    def _init_alan(self):
        """Инициализация панели Alan AI"""
        if not hasattr(self, 'alan_panel'):
            from alan_nn import AlanPanel, HAVE_TORCH
            if not HAVE_TORCH:
                import torch
                import torch.nn
                import torch.nn.functional as F
        self.alan_dock = QDockWidget("🤖 Alan AI", self)
        self.alan_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea |
                                        Qt.DockWidgetArea.LeftDockWidgetArea)
        self.alan_panel = AlanPanel(main_app=self)
        self.alan_dock.setWidget(self.alan_panel)
        self.alan_dock.setMinimumWidth(350)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.alan_dock)

    def toggle_alan(self):
        """Показать/скрыть панель Alan AI"""
        if hasattr(self, 'alan_dock'):
            self.alan_dock.setVisible(not self.alan_dock.isVisible())
        else:
            self._init_alan()
            if hasattr(self, 'alan_dock'):
                self.alan_dock.setVisible(True)

    def _on_tab_changed(self, index):
        """Обновить язык и путь к файлу при переключении вкладок"""
        if index < 0:
            return
        widget = self.tab_widget.widget(index)
        self.current_file = None
        for fp, w in self.open_files.items():
            if w is widget:
                self.current_file = fp
                if isinstance(widget, CodeEditor):
                    self.detect_language(fp)
                break
        # Обновить язык автодополнения и подсветку
        if isinstance(widget, CodeEditor):
            lang = self.language_combo.currentText()
            widget.set_completion_language(lang)
            self.apply_syntax_highlighting(widget)
            if hasattr(self, 'terminal'):
                self.terminal.manager.set_language(lang)

    def _get_language_icon(self, lang_name):
        """Получить иконку для языка в комбобоксе"""
        lang_to_icon = {
            'Python': 'python-original.svg', 'JavaScript': 'javascript-original.svg',
            'Java': 'java-original.svg', 'C++': 'ISO_C++_Logo.svg.png',
            'C#': 'c-sharp-logo.png', 'TypeScript': 'typescript-original.svg',
            'PHP': 'php-original.svg', 'Go': 'go-original-wordmark.svg',
            'Rust': 'rust-original.svg', 'Swift': 'swift-original.svg',
            'Kotlin': 'kotlin-original.svg', 'Ruby': 'ruby-original.svg',
            'SQL': 'SQL-universal.svg', 'R': 'r-original.svg',
            'C': 'c-original.svg', 'Dart': 'dart-original.svg',
            'Lua': 'lua-original.svg', 'Scala': 'scala-original.svg',
            'Perl': 'perl-original.svg', 'Objective-C': 'objectivec-plain.svg',
            'MATLAB': 'matlab-original.svg',
            'Haskell': 'haskell-original.svg', 'Clojure': 'clojure-original.svg',
            'Elixir': 'elixir-original.svg',             'Erlang': 'erlang-original.svg',
            'F#': 'fsharp-original.svg',
            'Firebase Rules': 'firebase-original.svg', 'Groovy': 'groovy-original.svg',
            'Julia': 'julia-original.svg', 'Delphi/Pascal': 'delphi-original.svg',
            'Visual Basic .NET': 'visualbasic-original.svg',
            'COBOL': 'cobol-original.svg', 'Fortran': 'fortran-original.svg',
            'Assembly': '.asm', 'Bash/Shell': 'bash-original.svg',
            'PowerShell': 'powershell-original.svg',
            'ABAP': '.txt', 'PL/SQL': 'SQL-universal.svg',
            'Apex': 'apex-original.svg', 'SAS': '.sas',
            'Scratch': 'Scratch3-original.png', 'OrionScript': 'OrionScriptLogo.png',
            'HTML5': 'html5-original-wordmark.svg', 'CSS': 'css3-original-wordmark.svg',
            'JSON': 'json-original.svg', 'XML': 'xml-original.svg', 'YAML': 'yaml-original.svg',
            'Markdown': 'markdown-original.svg', 'Plain Text': '.txt',
        }
        icon_name = lang_to_icon.get(lang_name)
        if icon_name and icon_name.startswith('.'):
            return self.file_tree._get_file_icon(f"file{icon_name}") if hasattr(self, 'file_tree') else None
        if icon_name:
            icon_path = os.path.join(ASSETS_DIR, icon_name)
            icon = _load_svg_icon(icon_path)
            if icon:
                return icon
        return None

    def detect_language(self, filepath):
        """Определить язык по расширению файла"""
        _, ext = os.path.splitext(filepath)
        
        ext_map = {
            '.py': 'Python', '.js': 'JavaScript', '.java': 'Java',
            '.cpp': 'C++', '.cc': 'C++', '.cxx': 'C++', '.c++': 'C++',
            '.cs': 'C#', '.ts': 'TypeScript', '.php': 'PHP',
            '.go': 'Go',             '.rs': 'Rust', '.rules': 'Firebase Rules', '.swift': 'Swift',
            '.kt': 'Kotlin', '.rb': 'Ruby', '.sql': 'SQL',
            '.r': 'R', '.c': 'C', '.dart': 'Dart', '.lua': 'Lua',
            '.m': 'Objective-C', '.hs': 'Haskell', '.clj': 'Clojure',
            '.ex': 'Elixir', '.erl': 'Erlang', '.fs': 'F#',
            '.groovy': 'Groovy', '.jl': 'Julia', '.pas': 'Delphi/Pascal',
            '.vb': 'Visual Basic .NET', '.cbl': 'COBOL', '.f90': 'Fortran',
            '.asm': 'Assembly', '.s': 'Assembly', '.sh': 'Bash/Shell',
            '.ps1': 'PowerShell', '.sas': 'SAS', '.html': 'HTML5',
            '.css': 'CSS', '.json': 'JSON', '.xml': 'XML',
            '.yaml': 'YAML', '.yml': 'YAML', '.md': 'Markdown',
            '.os': 'OrionScript'
        }
        
        if ext.lower() in ext_map:
            lang = ext_map[ext.lower()]
            index = self.language_combo.findText(lang)
            if index >= 0:
                self.language_combo.setCurrentIndex(index)
    
    def on_language_changed(self):
        """Обработка изменения языка"""
        editor = self.current_editor()
        if editor:
            lang = self.language_combo.currentText()
            editor.set_completion_language(lang)
            self.apply_syntax_highlighting(editor)
            if hasattr(self, 'terminal'):
                self.terminal.manager.set_language(lang)
        # Показываем Scratch-кнопки только при выборе языка Scratch
        is_scratch = self.language_combo.currentText() == "Scratch"
        self.btn_scratch.setVisible(is_scratch)
        self.btn_send.setVisible(is_scratch)
    
    def apply_syntax_highlighting(self, editor):
        """Применить подсветку синтаксиса"""
        lang = self.language_combo.currentText()

        if lang == 'Firebase Rules':
            if not isinstance(editor.highlighter, FirebaseRulesHighlighter):
                old = editor.highlighter
                editor.highlighter = FirebaseRulesHighlighter(editor.document())
                old.setDocument(None)
            editor.highlighter.rehighlight()
            return

        if lang == 'OrionScript':
            if not isinstance(editor.highlighter, OrionHighlighter):
                old = editor.highlighter
                editor.highlighter = OrionHighlighter(editor.document())
                old.setDocument(None)
            editor.highlighter.rehighlight()
            return

        if isinstance(editor.highlighter, (FirebaseRulesHighlighter, OrionHighlighter)):
            old = editor.highlighter
            editor.highlighter = PygmentsHighlighter(editor.document())
            old.setDocument(None)

        lexer_name = self.SUPPORTED_LANGUAGES.get(lang, 'text')
        try:
            lexer = get_lexer_by_name(lexer_name, stripall=False)
        except Exception:
            lexer = None
        editor.highlighter.set_lexer(lexer)
    
    def on_editor_modified(self, filepath):
        """Обработка модификации редактора"""
        index = self.tab_widget.indexOf(self.open_files[filepath])
        current_text = self.tab_widget.tabText(index)
        if not current_text.endswith("*"):
            self.tab_widget.setTabText(index, current_text + "*")
    
    def on_font_size_changed(self):
        """Обработка изменения размера шрифта"""
        size = self.font_size_spin.value()
        for editor in self.open_files.values():
            font = editor.font()
            font.setPointSize(size)
            editor.setFont(font)
        
        editor = self.current_editor()
        if editor and editor not in self.open_files.values():
            font = editor.font()
            font.setPointSize(size)
            editor.setFont(font)
    
    def increase_font_size(self):
        """Увеличить размер шрифта"""
        current = self.font_size_spin.value()
        self.font_size_spin.setValue(min(current + 1, 32))
    
    def decrease_font_size(self):
        """Уменьшить размер шрифта"""
        current = self.font_size_spin.value()
        self.font_size_spin.setValue(max(current - 1, 8))
    
    def load_styles(self):
        """Загрузить стили приложения"""
        style = """
            QMainWindow {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
            QMenuBar {
                background-color: #252526;
                color: #cccccc;
                border-bottom: 1px solid #3e3e42;
            }
            QMenuBar::item:selected {
                background-color: #094771;
            }
            QMenu {
                background-color: #252526;
                color: #cccccc;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
            QTreeWidget {
                background-color: #252526;
                color: #cccccc;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: #2d2d30;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
            }
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #0d5a8f;
            }
            QComboBox, QSpinBox {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 3px;
            }
            QStatusBar {
                background-color: #007acc;
                color: white;
            }
            QTabBar::tab {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 5px 15px;
                border: 1px solid #3e3e42;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
            }
            QSplitter::handle {
                background-color: #3e3e42;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #3e3e42;
                padding: 2px 4px;
            }

        """
        self.setStyleSheet(style)

def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    
    app_icon_path = os.path.join(ASSETS_DIR, 'app.ico')
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))
    
    window = CodeEditorApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
