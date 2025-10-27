import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QStackedWidget, QScrollArea, QSizePolicy, QPushButton,
    QButtonGroup, QFrame
)
from PyQt5.QtCore import Qt

from brdf_form import BRDFForm
from mie_form import MieForm
from reflect_form import ReflectForm
from rcw_form import RCWForm  


AFFILIATION = "Woojun Lee · Purdue University · School of Mechanical Engineering"


class SCATMECHGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCATMECH GUI")

        # Vertical layout
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Top buttons
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        def make_btn(text):
            b = QPushButton(text, self)
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            return b

        self.btn_brdf    = make_btn("BRDF")
        self.btn_rcw     = make_btn("RCW")
        self.btn_reflect = make_btn("Reflect")
        self.btn_mie     = make_btn("Mie")

        buttons = [self.btn_brdf, self.btn_rcw, self.btn_reflect, self.btn_mie]
        for i, b in enumerate(buttons):
            self.btn_group.addButton(b, i)
            top.addWidget(b)
            top.setStretch(i, 1)

        root.addLayout(top)

        # Stacked forms
        self.stack = QStackedWidget(self)

        # Placeholder pages
        def placeholder(name):
            from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
            w = QWidget(self)
            v = QVBoxLayout(w)
            v.addStretch(1)
            lab = QLabel(f"{name} form not available yet.", w)
            lab.setStyleSheet("color:#888;")
            lab.setAlignment(Qt.AlignCenter)
            v.addWidget(lab)
            v.addStretch(1)
            return w

        # Forms 
        self.brdf_form    = BRDFForm()
        self.reflect_form = ReflectForm()
        self.mie_form     = MieForm()
        self.rcw_form = RCWForm()

        def wrap_in_scroll(w):
            sa = QScrollArea(self)
            sa.setWidgetResizable(True)
            sa.setWidget(w)
            sa.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            return sa

        # Pages
        self.stack.addWidget(wrap_in_scroll(self.brdf_form))     # index 0
        self.stack.addWidget(wrap_in_scroll(self.rcw_form))      # index 1
        self.stack.addWidget(wrap_in_scroll(self.reflect_form))  # index 2
        self.stack.addWidget(wrap_in_scroll(self.mie_form))      # index 3

        root.addWidget(self.stack, 1)

        # Affiliation footer
        footer = QFrame(self)
        footer.setObjectName("footer")
        footer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        footer.setMinimumHeight(24)
        footer.setStyleSheet(
            "#footer { border-top: 1px solid #e5e5e5; }"
            "#footer QLabel { color: #666; font-size: 11px; }"
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 2, 8, 6)
        footer_layout.setSpacing(0)

        self.affiliation_label = QLabel(AFFILIATION, footer)
        self.affiliation_label.setAlignment(Qt.AlignCenter)

        footer_layout.addStretch(1)
        footer_layout.addWidget(self.affiliation_label, 0, Qt.AlignCenter)
        footer_layout.addStretch(1)

        root.addWidget(footer, 0)

        # Wire buttons
        def set_page(idx):
            self.stack.setCurrentIndex(idx)
            btn = self.btn_group.button(idx)
            if btn and not btn.isChecked():
                btn.setChecked(True)

        self.btn_brdf.clicked.connect(lambda: set_page(0))
        self.btn_rcw.clicked.connect(lambda: set_page(1))
        self.btn_reflect.clicked.connect(lambda: set_page(2))
        self.btn_mie.clicked.connect(lambda: set_page(3))

        # Default selection
        set_page(0)
        self.btn_brdf.setChecked(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = SCATMECHGui()
    gui.show()
    sys.exit(app.exec_())
