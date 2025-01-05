import json
import sys
import os
import psutil
import src.globals as g
from notifypy import Notify
from src.download import DownloadThread
from src.thread import CompressionThread
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QFileDialog,
    QLabel,
    QLineEdit,
    QCheckBox,
    QProgressBar
)
from PyQt6.QtGui import QIcon, QDragEnterEvent, QDropEvent
from PyQt6.QtCore import Qt
from src.styles import *


def load_settings():
    try:
        with open(os.path.join(g.res_dir, "settings.json"), "r") as f:
            return json.load(f)
    except:
        return g.DEFAULT_SETTINGS


def save_settings(settings):
    with open(os.path.join(g.res_dir, "settings.json"), "w") as f:
        json.dump(settings, f)


def kill_ffmpeg():
    for proc in psutil.process_iter():
        if "ffmpeg" in proc.name():
            proc.kill()


def delete_bin():
    print("@@@@@@@@@@@@@@@@@@@@@@ DELETING BIN @@@@@@@@@@@@@@@@@@@@@@@")
    for root, dirs, files in os.walk(g.bin_dir, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))


class Window(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.verify_directories()
        self.settings = load_settings()
        self.setFixedSize(WINDOW.w, WINDOW.h)
        self.setWindowTitle(g.TITLE)
        icon_path = os.path.join(g.res_dir, "icon.ico")
        self.setWindowIcon(QIcon(icon_path))

        # Select Button
        self.button_select = QPushButton("Select Videos", self)
        self.button_select.resize(SELECT_BUTTON.w, SELECT_BUTTON.h)
        self.button_select.move(SELECT_BUTTON.x, SELECT_BUTTON.y)
        self.button_select.clicked.connect(self.select_videos)
        self.button_select.setEnabled(False)

        # Compress Button
        self.button_compress = QPushButton("Compress", self)
        self.button_compress.resize(COMPRESS_BUTTON.w, COMPRESS_BUTTON.h)
        self.button_compress.move(COMPRESS_BUTTON.x, COMPRESS_BUTTON.y)
        self.button_compress.clicked.connect(self.compress_videos)
        self.button_compress.setEnabled(False)

        # Abort and Clear Button
        self.button_abort = QPushButton("Clear", self)
        self.button_abort.resize(ABORT_BUTTON.w, ABORT_BUTTON.h)
        self.button_abort.move(ABORT_BUTTON.x, ABORT_BUTTON.y)
        self.button_abort.clicked.connect(self.abort_or_clear)
        self.button_abort.setEnabled(False)

        # File Size Label
        self.label_size = QLabel("Size (MB)", self)
        self.label_size.resize(FILE_SIZE_LABEL.w, FILE_SIZE_LABEL.h)
        self.label_size.move(FILE_SIZE_LABEL.x, FILE_SIZE_LABEL.y)

        # File Size Entry
        self.edit_size = QLineEdit(str(self.settings["target_size"]), self)
        self.edit_size.resize(FILE_SIZE_ENTRY.w, FILE_SIZE_ENTRY.h)
        self.edit_size.move(FILE_SIZE_ENTRY.x, FILE_SIZE_ENTRY.y)
        self.edit_size.setEnabled(True)

        # GPU Label
        self.label_gpu = QLabel("Use GPU", self)
        self.label_gpu.resize(GPU_LABEL.w, GPU_LABEL.h)
        self.label_gpu.move(GPU_LABEL.x, GPU_LABEL.y)

        # GPU Checkbox
        self.checkbox_gpu = QCheckBox(self)
        self.checkbox_gpu.resize(GPU_CHECKBOX.w, GPU_CHECKBOX.h)
        self.checkbox_gpu.move(GPU_CHECKBOX.x, GPU_CHECKBOX.y)
        self.checkbox_gpu.setChecked(self.settings["use_gpu"])

        # Drag and Drop Area
        self.drag_drop_area = QLabel(g.READY_TEXT, self)
        self.drag_drop_area.setEnabled(True)
        self.drag_drop_area.resize(DRAG_AND_DROP_AREA.w, DRAG_AND_DROP_AREA.h)
        self.drag_drop_area.move(DRAG_AND_DROP_AREA.x, DRAG_AND_DROP_AREA.y)
        self.drag_drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drag_drop_area.setStyleSheet(LABEL_LOG_STYLE)
        self.drag_drop_area.setAcceptDrops(True)
        self.drag_drop_area.dragEnterEvent = self.drag_enter_event
        self.drag_drop_area.dropEvent = self.drop_event

        # Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.resize(PROGRESS_BAR.w, PROGRESS_BAR.h)
        self.progress_bar.move(PROGRESS_BAR.x, PROGRESS_BAR.y)
        self.progress_bar.setRange(0, 100)

        self.download_thread = None
        self.compress_thread = None

        self.button_select.setStyleSheet(BUTTON_DISABLED_STYLE)
        self.button_compress.setStyleSheet(BUTTON_DISABLED_STYLE)
        self.button_abort.setStyleSheet(BUTTON_DISABLED_STYLE)
        self.label_size.setStyleSheet(LABEL_STYLE)
        self.edit_size.setStyleSheet(LINEEDIT_STYLE)
        self.label_gpu.setStyleSheet(LABEL_STYLE)
        self.checkbox_gpu.setStyleSheet(CHECKBOX_STYLE)
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)

        self.verify_ffmpeg()

    def filter_dragged_files(self, mime_data):
        files = [url.toLocalFile() for url in mime_data.urls()]
        video_files = [file for file in files if file.lower().endswith(("mp4", "avi", "mkv", "mov", "wmv", "flv", "webm", "m4v"))]
        return video_files

    def drag_enter_event(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls() and len(self.filter_dragged_files(mime_data)) > 0:
            event.acceptProposedAction()

    def drop_event(self, event: QDropEvent):
        files = self.filter_dragged_files(event.mimeData())
        for file in files:
            g.queue.append(file)
        self.button_compress.setEnabled(True)
        self.button_compress.setStyleSheet(BUTTON_COMPRESS_STYLE)
        self.button_abort.setEnabled(True)
        self.button_abort.setStyleSheet(BUTTON_ABORT_STYLE)
        print(f"Selected: {g.queue}")
        self.update_log(f"{g.READY_TEXT}\nSelected {len(g.queue)} video(s).")

    def closeEvent(self, event):
        # Save settings when closing
        self.settings["target_size"] = float(self.edit_size.text())
        self.settings["use_gpu"] = self.checkbox_gpu.isChecked()
        save_settings(self.settings)
        kill_ffmpeg()

        if os.path.exists(os.path.join(g.root_dir, "TEMP")):
            os.remove(os.path.join(g.root_dir, "TEMP"))

        event.accept()

    def reset(self):
        g.compressing = False
        g.queue = []
        self.button_select.setEnabled(True)
        self.button_select.setStyleSheet(BUTTON_SELECT_STYLE)
        self.button_select.setFocus()
        self.button_compress.setEnabled(False)
        self.button_compress.setStyleSheet(BUTTON_DISABLED_STYLE)
        self.button_abort.setEnabled(False)
        self.button_abort.setText("Clear")
        self.button_abort.setStyleSheet(BUTTON_DISABLED_STYLE)
        self.edit_size.setEnabled(True)
        self.drag_drop_area.setAcceptDrops(True)
        self.update_log(g.READY_TEXT)
        self.update_progress(0)

    def verify_directories(self):
        print("Verifying directories...")
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            g.root_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            g.root_dir = os.path.dirname(os.path.abspath(__file__))

        print(f"Root: {g.root_dir}")
        g.bin_dir = os.path.join(g.root_dir, "bin")

        if not os.path.exists(g.bin_dir):
            os.mkdir(g.bin_dir)

        print(f"Bin: {g.bin_dir}")
        g.output_dir = os.path.join(g.root_dir, "output")

        if not os.path.exists(g.output_dir):
            os.mkdir(g.output_dir)

        print(f"Output: {g.output_dir}")
        g.res_dir = os.path.join(g.root_dir, "res")
        print(f"Res: {g.res_dir}")

    def verify_ffmpeg(self):
        print("Verifying FFmpeg...")
        FFMPEG_PATH = os.path.join(g.bin_dir, "ffmpeg.exe")
        print(f"FFmpeg: {FFMPEG_PATH}")
        FFPROBE_PATH = os.path.join(g.bin_dir, "ffprobe.exe")
        print(f"FFprobe: {FFPROBE_PATH}")

        if os.path.exists(FFMPEG_PATH) and os.path.exists(FFPROBE_PATH):
            g.ffmpeg_installed = True
            g.ffmpeg_path = FFMPEG_PATH
            g.ffprobe_path = FFPROBE_PATH
            self.reset()
        else:
            self.download_thread = DownloadThread()
            self.download_thread.installed.connect(self.installed)
            self.download_thread.update_log.connect(self.update_log)
            self.download_thread.update_progress.connect(self.update_progress)
            self.download_thread.start()

    def select_videos(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v);;All Files (*.*)",
        )

        if len(file_paths) > 0:
            for PATH in file_paths:
                if PATH in g.queue:
                    continue

                g.queue.append(PATH)

            self.button_compress.setEnabled(True)
            self.button_compress.setStyleSheet(BUTTON_COMPRESS_STYLE)
            self.button_abort.setEnabled(True)
            self.button_abort.setStyleSheet(BUTTON_ABORT_STYLE)
            print(f"Selected: {g.queue}")
            msg = f"{g.READY_TEXT}\nSelected {len(g.queue)} video(s)."
            self.update_log(msg)

    def compress_videos(self):
        g.compressing = True
        self.button_select.setStyleSheet(BUTTON_DISABLED_STYLE)
        self.button_compress.setStyleSheet(BUTTON_DISABLED_STYLE)
        self.button_abort.setEnabled(True)
        self.button_abort.setText("Abort")
        self.button_abort.setStyleSheet(BUTTON_ABORT_STYLE)
        self.button_select.setEnabled(False)
        self.button_compress.setEnabled(False)
        self.edit_size.setEnabled(False)
        self.drag_drop_area.setAcceptDrops(False)
        self.compress_thread = CompressionThread(
            float(self.edit_size.text()), self.checkbox_gpu.isChecked()
        )
        self.compress_thread.completed.connect(self.completed)
        self.compress_thread.update_log.connect(self.update_log)
        self.compress_thread.update_progress.connect(self.update_progress)
        self.compress_thread.start()

    def abort_or_clear(self):
        if g.compressing:
            kill_ffmpeg()
            self.completed(True)
        else:
            g.queue = []
            self.update_log(g.READY_TEXT)
            self.button_compress.setEnabled(False)
            self.button_compress.setStyleSheet(BUTTON_DISABLED_STYLE)
            self.button_abort.setEnabled(False)
            self.button_abort.setStyleSheet(BUTTON_DISABLED_STYLE)

    def update_log(self, text):
        self.drag_drop_area.setText(text)

    def update_progress(self, progress_percentage):
        self.progress_bar.setValue(progress_percentage)

    def installed(self):
        g.ffmpeg_installed = True
        g.ffmpeg_path = os.path.join(g.bin_dir, "ffmpeg.exe")
        g.ffprobe_path = os.path.join(g.bin_dir, "ffprobe.exe")
        self.reset()
        n = Notify()
        n.title = "FFmpeg installed!"
        n.message = "You can now compress your videos."
        n.icon = os.path.join(g.res_dir, "icon.ico")
        n.send()

    def completed(self, aborted=False):
        g.compressing = False
        self.compress_thread.terminate()
        self.reset()
        n = Notify()
        n.title = "Done!" if not aborted else "Aborted!"
        n.message = (
            "Your videos are ready." if not aborted else "Your videos are cooked!"
        )
        n.icon = os.path.join(g.res_dir, "icon.ico")
        n.send()

        if not aborted:
            os.startfile(g.output_dir)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
