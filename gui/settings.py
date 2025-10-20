# --- gui/settings.py ---
# Placeholder for future settings dialog or about box logic
# For now, just an About box

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QDialogButtonBox
from PyQt6.QtCore import Qt

class AboutDialog(QDialog):
    """Simple About dialog."""
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("About Porsha")
        layout = QVBoxLayout(self)

        title = QLabel("Porsha Digital Forensics Toolkit")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)

        version_label = QLabel("Version: 0.1.0 (Alpha)") # Get from setup.py later if needed
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc_label = QLabel(
            "A foundational digital forensics toolkit utilizing open-source libraries.\n"
            "Built with Python and PyQt6."
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)

        # Add more info like Author, License, Website link here
        # author_label = QLabel("Author: Your Name")
        # author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(version_label)
        layout.addSpacing(10)
        layout.addWidget(desc_label)
        # layout.addWidget(author_label)
        layout.addSpacing(10)

        # Standard OK button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self.setFixedSize(350, 200) # Adjust size as needed