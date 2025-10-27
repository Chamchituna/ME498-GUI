import os
import re
import csv
import datetime
import subprocess
import importlib
import importlib.util
import sys
import shutil
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QGroupBox,
    QFormLayout, QFileDialog, QComboBox,
    QSizePolicy, QTableWidget, QTableWidgetItem, QDialog
)
from PyQt5.QtCore import pyqtSignal

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

scatmech_bin = str(Path.home() / "Local/ME498/SCATMECH")
os.environ["PATH"] = scatmech_bin + os.pathsep + os.environ.get("PATH", "")


_TYPE_CHOICES = [
    ("Reflection into incident medium", "0"),
    ("Transmission into incident medium", "1"),
    ("Reflection into transmission medium", "2"),
    ("Transmission into transmission medium", "3"),
]


class RCWForm(QWidget):

    requestClearPlot = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.main_layout = QHBoxLayout(self)
        self.setLayout(self.main_layout)

        self.form_layout = QVBoxLayout()
        form_widget = QWidget()
        form_widget.setLayout(self.form_layout)

        self.figure = Figure(figsize=(6, 5), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        plot_layout = QVBoxLayout()
        plot_layout.addWidget(self.canvas, 1)
        plot_widget = QWidget()
        plot_widget.setLayout(plot_layout)

        self.main_layout.addWidget(form_widget, 1)
        self.main_layout.addWidget(plot_widget, 1)
        self.main_layout.setStretch(0, 1)
        self.main_layout.setStretch(1, 1)

        basic_group = QGroupBox("Simulation Parameters")
        basic_form = QFormLayout()

        self.order = QLineEdit("6")
        basic_form.addRow("Maximum Diffraction Order:", self.order)

        self.type_combo = QComboBox()
        for label, code in _TYPE_CHOICES:
            self.type_combo.addItem(label, code)
        basic_form.addRow("Configuration Type:", self.type_combo)

        self.wavelength_um = QLineEdit("0.532")
        basic_form.addRow("Wavelength (µm):", self.wavelength_um)

        self.theta_inc_deg = QLineEdit("0")
        basic_form.addRow("Incident Polar Angle θᵢ (deg):", self.theta_inc_deg)

        self.rotation_deg = QLineEdit("0")
        basic_form.addRow("Grating Rotation φ (deg):", self.rotation_deg)

        self.medium_i = QLineEdit("(1,0)")
        basic_form.addRow("Incident Medium (n,k):", self.medium_i)

        self.medium_t = QLineEdit("(1,0)")
        basic_form.addRow("Transmission Medium (n,k):", self.medium_t)

        basic_group.setLayout(basic_form)
        self.form_layout.addWidget(basic_group)

        grating_group = QGroupBox("Grating Definition")
        grating_form = QFormLayout()
        path_row = QHBoxLayout()
        self.grating_path = QLineEdit("grating.dat")
        self.browse_grating = QPushButton("Browse…")
        path_row.addWidget(self.grating_path)
        path_row.addWidget(self.browse_grating)
        grating_form.addRow("Grating File:", path_row)
        grating_group.setLayout(grating_form)
        self.form_layout.addWidget(grating_group)

        ctrl_row = QHBoxLayout()
        self.run_btn = QPushButton("Run RCWProg")
        self.clear_btn = QPushButton("Clear Plot")
        self.open_output_btn = QPushButton("Open Last Output")
        self.open_input_btn = QPushButton("Open Last Input")
        ctrl_row.addWidget(self.run_btn, 1)
        ctrl_row.addWidget(self.clear_btn, 1)
        ctrl_row.addWidget(self.open_input_btn, 1)
        ctrl_row.addWidget(self.open_output_btn, 1)
        ctrl_widget = QWidget()
        ctrl_widget.setLayout(ctrl_row)
        self.form_layout.addWidget(ctrl_widget)

        self.form_layout.addWidget(QLabel("Input Deck Preview:"))
        self.input_preview = QTextEdit()
        self.input_preview.setMinimumHeight(140)
        self.form_layout.addWidget(self.input_preview)

        self.form_layout.addWidget(QLabel("Log:"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.form_layout.addWidget(self.log)
        self.form_layout.addStretch(1)

        self.run_btn.clicked.connect(self.run_rcwprog)
        self.clear_btn.clicked.connect(self.clear_plot)
        self.open_output_btn.clicked.connect(self.open_last_output)
        self.open_input_btn.clicked.connect(self.open_last_input)
        self.browse_grating.clicked.connect(self._browse_for_grating)

        self._plot_clear_callback = None
        self.last_stdout_path = None
        self.last_input_path = None
        self.last_csv_path = None

        self.populate_input_preview()

    def connect_plot_clear(self, slot):
        self._plot_clear_callback = slot

    def clear_plot(self):
        sig = getattr(self, "requestClearPlot", None)
        if sig is not None:
            try:
                sig.emit()
            except Exception as exc:
                self.log.append(f"Clear-plot signal error: {exc}")
        if callable(getattr(self, "_plot_clear_callback", None)):
            try:
                self._plot_clear_callback()
            except Exception as exc:
                self.log.append(f"Clear-plot callback error: {exc}")
        if hasattr(self, "figure"):
            self.figure.clear()
        if hasattr(self, "canvas"):
            self.canvas.draw()
        self.log.append("Plot cleared.")

    def _browse_for_grating(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select grating file", "", "All Files (*)")
        if fname:
            self.grating_path.setText(fname)
            self.populate_input_preview()

    def populate_input_preview(self):
        payload = self._build_input_payload()
        self.input_preview.setPlainText(payload)
        self.log.append("Parameters updated.")

    def _build_input_payload(self):
        order = self.order.text().strip() or "6"
        type_code = self.type_combo.currentData() or "0"
        wavelength = self.wavelength_um.text().strip() or "0.532"
        theta = self.theta_inc_deg.text().strip() or "0"
        rotation = self.rotation_deg.text().strip() or "0"
        med_i = self.medium_i.text().strip() or "(1,0)"
        med_t = self.medium_t.text().strip() or "(1,0)"
        grating = self.grating_path.text().strip() or "grating.dat"

        lines = [
            order,
            type_code,
            wavelength,
            theta,
            rotation,
            med_i,
            med_t,
            grating,
        ]

        return "\n".join(lines) + "\n"

    def run_rcwprog(self):
        payload = self._build_input_payload()
        self.input_preview.setPlainText(payload)
        self.last_csv_path = None        

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        data_dir = os.path.join("..", "DATA")
        os.makedirs(data_dir, exist_ok=True)
        input_txt = os.path.join(data_dir, f"rcw_input_{timestamp}.txt")
        output_txt = os.path.join(data_dir, f"rcw_stdout_{timestamp}.log")
        csv_filename = os.path.join(data_dir, f"rcw_output_{timestamp}.csv")

        try:
            with open(input_txt, "w", encoding="utf-8") as f:
                f.write(payload + "\n")
            self.last_input_path = input_txt
            self.log.append(f"Saved input deck: {input_txt}")
        except Exception as exc:
            self.log.append(f"[Error] Could not write input deck: {exc}")
            return

        exe = shutil.which("rcwprog")
        if not exe:
            self.log.append(
                "[Error] 'rcwprog' not found. Ensure it is on PATH or next to the app.\n"
                f"Current PATH includes: {scatmech_bin}"
            )
            return

        self.log.append(f"Running RCWProg: {exe}")
        try:
            proc = subprocess.run(
                [exe],
                input=payload,
                capture_output=True,
                text=True,
                check=False,
                cwd=os.path.dirname(exe) if os.path.sep in exe else None,
            )
        except Exception as exc:
            self.log.append(f"[Error] Could not invoke rcwprog: {exc}")
            return

        try:
            with open(output_txt, "w", encoding="utf-8", errors="ignore") as f:
                f.write(proc.stdout or "")
                if proc.stderr:
                    f.write("\n--- STDERR ---\n")
                    f.write(proc.stderr)
            self.last_stdout_path = output_txt
            self.log.append(f"Saved stdout log: {output_txt}")
        except Exception as exc:
            self.log.append(f"[Warning] Failed to store stdout: {exc}")

        if proc.returncode != 0:
            self.log.append("rcwprog returned non-zero exit code. See output log for details.")
            return

        self.log.append("rcwprog completed. Parsing output table…")

        try:
            header, rows = self._extract_table(proc.stdout)
        except Exception as exc:
            self.log.append(f"[Error] Failed to parse rcwprog output: {exc}")
            return

        if not rows:
            self.log.append("No numeric rows detected in rcwprog output.")
            return

        try:
            with open(csv_filename, "w", newline="", encoding="utf-8") as fcsv:
                writer = csv.writer(fcsv)
                if header:
                    writer.writerow(header)
                writer.writerows(rows)
            self.log.append(f"Saved CSV: {csv_filename}")
            self.last_csv_path = csv_filename
        except Exception as exc:
            self.log.append(f"[Error] Could not write CSV: {exc}")
            return

        self.render_with_external(csv_filename)

    def _extract_table(self, stdout: str):
        if not stdout:
            return [], []
        lines = stdout.splitlines()
        header_idx = None
        header = []
        for i, line in enumerate(lines):
            tokens = re.split(r"\s+", line.strip())
            if not tokens:
                continue
            lowered = [t.lower() for t in tokens]
            if any(key in lowered for key in ("order", "theta", "phi", "rs", "rp", "diff")):
                header_idx = i
                header = tokens
                break
        data_rows = []
        start = header_idx + 1 if header_idx is not None else 0
        for line in lines[start:]:
            s = line.strip()
            if not s:
                if data_rows:
                    break
                continue
            parts = re.split(r"\s+", s)
            if not parts:
                continue
            numeric_prefix = 0
            for token in parts:
                try:
                    float(token)
                    numeric_prefix += 1
                except Exception:
                    break
            if numeric_prefix == 0:
                if data_rows:
                    break
                continue
            data_rows.append(parts[:numeric_prefix])
        if not header and data_rows:
            width = max(len(row) for row in data_rows)
            header = [f"col{i+1}" for i in range(width)]
        if header:
            width = min(len(header), max(len(row) for row in data_rows))
            header = header[:width]
        else:
            width = max(len(row) for row in data_rows)
        trimmed = [row[:width] for row in data_rows]
        return header, trimmed

    def render_with_external(self, csv_path: str):
        self.figure.clear()
        ax = self.figure.gca()

        here = os.path.dirname(os.path.abspath(__file__))
        cwd = os.getcwd()
        csv_dir = os.path.dirname(os.path.abspath(csv_path)) if csv_path else None

        tried = []

        def _try_normal(name):
            try:
                mod = importlib.import_module(name)
                return mod, f"import {name}"
            except Exception as exc:
                tried.append(f"import {name}: {exc}")
                return None, None

        def _try_file(path):
            try:
                if path and os.path.exists(path):
                    spec = importlib.util.spec_from_file_location("rcwplot", path)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules["rcwplot"] = mod
                        spec.loader.exec_module(mod)
                        return mod, f"load {path}"
            except Exception as exc:
                tried.append(f"load {path}: {exc}")
            return None, None

        if here not in sys.path:
            sys.path.insert(0, here)

        mod, how = _try_normal("rcwplot")
        if mod is None:
            mod, how = _try_file(os.path.join(here, "rcwplot.py"))
        if mod is None:
            mod, how = _try_file(os.path.join(cwd, "rcwplot.py"))
        if mod is None and csv_dir:
            mod, how = _try_file(os.path.join(csv_dir, "rcwplot.py"))

        if mod is None:
            self.log.append("Could not import rcwplot.py: " + " | ".join(tried))
            self.canvas.draw()
            return
        else:
            self.log.append(f"rcwplot resolved via: {how}")

        fn = getattr(mod, "plot_csv", None)
        if not callable(fn):
            self.log.append("rcwplot.py found, but it must define plot_csv(ax, csv_path).")
            self.canvas.draw()
            return

        try:
            fn(ax, csv_path)
            self.canvas.draw()
            self.log.append("Plot updated via rcwplot.plot_csv")
        except Exception as exc:
            self.log.append(f"rcwplot render error: {exc}")
            self.canvas.draw()

    def open_last_output(self):
        data_dir = os.path.join("..", "DATA")
        path = getattr(self, "last_csv_path", None)
        if not path or not os.path.exists(path):
            path = self._find_latest("rcw_output_", data_dir, suffix=".csv")
        if not path:
            self.log.append("No RCW CSV output found in ../DATA.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Output: {os.path.basename(path)}")
        layout = QVBoxLayout(dlg)

        txt = QTextEdit(dlg)
        txt.setReadOnly(True)
        txt.setMinimumHeight(120)
        layout.addWidget(txt)

        table = QTableWidget(dlg)
        table.setMinimumHeight(320)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close", dlg)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        close_btn.clicked.connect(dlg.accept)

        try:
            with open(path, newline="") as f:
                rows = list(csv.reader(f))
            if not rows:
                txt.setPlainText("(Empty CSV)")
            else:
                header, data = rows[0], rows[1:]
                table.setColumnCount(len(header))
                table.setRowCount(len(data))
                table.setHorizontalHeaderLabels(header)
                for r, row in enumerate(data):
                    for c, val in enumerate(row):
                        table.setItem(r, c, QTableWidgetItem(val))
                table.setSortingEnabled(True)
                table.resizeColumnsToContents()
                txt_path = getattr(self, "last_stdout_path", None)
                if txt_path and os.path.exists(txt_path):
                    txt.setPlainText(self._read_file(txt_path))
                    
                else:
                    txt.setPlainText("(Stdout log not available)")
        except Exception as exc:
            txt.setPlainText(f"(Failed to open CSV: {exc})")
                    
        dlg.resize(900, 700)
        dlg.exec_()

    def open_last_input(self):
        data_dir = os.path.join("..", "DATA")
        path = getattr(self, "last_input_path", None)
        if not path or not os.path.exists(path):
            path = self._find_latest("rcw_input_", data_dir)
        if not path:
            self.log.append("No RCW input deck found in ../DATA.")
            return
        content = self._read_file(path)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Input: {os.path.basename(path)}")
        layout = QVBoxLayout(dlg)
        view = QTextEdit(dlg)
        view.setReadOnly(True)
        view.setPlainText(content)
        layout.addWidget(view)
        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close", dlg)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        close_btn.clicked.connect(dlg.accept)
        dlg.resize(700, 500)
        dlg.exec_()

    def _find_latest(self, prefix: str, folder: str, suffix: str = ""):
        try:
            paths = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.startswith(prefix) and f.endswith(suffix)
            ] if suffix else [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.startswith(prefix)
            ]
            if not paths:
                return None
            return max(paths, key=lambda p: os.path.getmtime(p))
        except Exception:
            return None

    def _read_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as exc:
            return f"(Could not open file: {exc})"

    def to_params(self):
        return {
            "order": self.order.text().strip(),
            "type": self.type_combo.currentData(),
            "wavelength_um": self.wavelength_um.text().strip(),
            "theta_inc_deg": self.theta_inc_deg.text().strip(),
            "rotation_deg": self.rotation_deg.text().strip(),
            "medium_i": self.medium_i.text().strip(),
            "medium_t": self.medium_t.text().strip(),
            "grating": self.grating_path.text().strip(),
            "input_deck": self.input_preview.toPlainText(),
        }

    def from_params(self, params: dict):
        if not params:
            return
        self.order.setText(params.get("order", ""))
        type_code = params.get("type")
        if type_code is not None:
            idx = self.type_combo.findData(type_code)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        self.wavelength_um.setText(params.get("wavelength_um", ""))
        self.theta_inc_deg.setText(params.get("theta_inc_deg", ""))
        self.rotation_deg.setText(params.get("rotation_deg", ""))
        self.medium_i.setText(params.get("medium_i", ""))
        self.medium_t.setText(params.get("medium_t", ""))
        self.grating_path.setText(params.get("grating", ""))
        deck = params.get("input_deck")
        if deck:
            self.input_preview.setPlainText(deck)
        else:
            self.populate_input_preview()