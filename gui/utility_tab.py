# --- gui/utility_tab.py ---
import os
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QLabel,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QScrollArea, QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt, QThread

# Use relative import for worker within the gui package
from .worker import HashWorker, MetadataWorker

logger = logging.getLogger(__name__)

class UtilityTab(QWidget):
    """QWidget for Hashing and Metadata extraction utilities."""

    def __init__(self, parent=None):
        """Initializes the UtilityTab."""
        super().__init__(parent)
        self.setObjectName("UtilityTab") # For styling or identification
        self._hash_worker = None
        self._hash_thread = None
        self._metadata_worker = None
        self._metadata_thread = None
        self._selected_file = ""

        self._setup_ui()

    def _setup_ui(self):
        """Sets up the UI elements for the tab."""
        main_layout = QVBoxLayout(self)

        # --- File Selection ---
        file_group = QGroupBox("Select File")
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select a file to analyze...")
        self.file_path_edit.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.browse_button)
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        # --- Hashing Section ---
        hash_group = QGroupBox("Calculate Hashes (MD5, SHA-256)")
        hash_layout = QVBoxLayout()
        self.hash_button = QPushButton("Calculate Hashes")
        self.hash_button.clicked.connect(self._start_hash_calculation)
        self.hash_button.setEnabled(False) # Disabled until file selected

        self.md5_label = QLabel("MD5:")
        self.md5_result_edit = QLineEdit()
        self.md5_result_edit.setReadOnly(True)
        self.md5_result_edit.setPlaceholderText("MD5 hash will appear here")

        self.sha256_label = QLabel("SHA-256:")
        self.sha256_result_edit = QLineEdit()
        self.sha256_result_edit.setReadOnly(True)
        self.sha256_result_edit.setPlaceholderText("SHA-256 hash will appear here")

        hash_layout.addWidget(self.hash_button)
        hash_layout.addWidget(self.md5_label)
        hash_layout.addWidget(self.md5_result_edit)
        hash_layout.addWidget(self.sha256_label)
        hash_layout.addWidget(self.sha256_result_edit)
        hash_group.setLayout(hash_layout)
        main_layout.addWidget(hash_group)

        # --- Metadata Section ---
        metadata_group = QGroupBox("Extract Metadata")
        metadata_layout = QVBoxLayout()
        self.metadata_button = QPushButton("Extract Metadata")
        self.metadata_button.clicked.connect(self._start_metadata_extraction)
        self.metadata_button.setEnabled(False) # Disabled until file selected

        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.metadata_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.metadata_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.metadata_table.setAlternatingRowColors(True)
        self.metadata_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Read-only
        self.metadata_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # Make table scrollable if content overflows
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.metadata_table)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


        metadata_layout.addWidget(self.metadata_button)
        metadata_layout.addWidget(scroll_area) # Add scroll area instead of table directly
        metadata_group.setLayout(metadata_layout)
        main_layout.addWidget(metadata_group)

        main_layout.addStretch() # Push elements upwards


    def _browse_file(self):
        """Opens a file dialog to select a file for analysis."""
        # Stop any ongoing analysis before changing file
        self.stop_all_analyses()

        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "All Files (*)")
        if file_path:
            self._selected_file = file_path
            self.file_path_edit.setText(file_path)
            self.hash_button.setEnabled(True)
            self.metadata_button.setEnabled(True)
            # Clear previous results
            self.md5_result_edit.clear()
            self.sha256_result_edit.clear()
            self.metadata_table.setRowCount(0)
            logger.info(f"File selected for utility analysis: {file_path}")
            # Optionally trigger one of the analyses automatically
            # self._start_hash_calculation()
            # self._start_metadata_extraction()
        else:
            self._selected_file = ""
            self.file_path_edit.clear()
            self.hash_button.setEnabled(False)
            self.metadata_button.setEnabled(False)


    # --- Hashing ---
    def _start_hash_calculation(self):
        """Starts the hashing process in a background thread."""
        if not self._selected_file:
            QMessageBox.warning(self, "No File", "Please select a file first.")
            return

        if self._hash_thread and self._hash_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Hashing is already in progress.")
            return

        # Clear previous results
        self.md5_result_edit.clear()
        self.sha256_result_edit.clear()

        self.hash_button.setEnabled(False) # Disable button during calculation
        self.browse_button.setEnabled(False)

        self._hash_thread = QThread()
        self._hash_worker = HashWorker(self._selected_file)
        self._hash_worker.moveToThread(self._hash_thread)

        # Connect signals
        self._hash_worker.finished.connect(self._hash_thread.quit)
        self._hash_worker.finished.connect(self._hash_worker.deleteLater)
        self._hash_thread.finished.connect(self._hash_thread.deleteLater)
        self._hash_thread.finished.connect(self._on_hash_finished)
        self._hash_worker.results_ready.connect(self._display_hashes)
        self._hash_worker.error.connect(self._show_error)
        # self._hash_worker.progress.connect(self.parent().parent().parent().statusBar().showMessage) # Example: show progress in status bar
        self._hash_worker.progress.connect(lambda msg: self.parent().window().statusBar().showMessage(msg, 5000))


        self._hash_thread.started.connect(self._hash_worker.run)
        self._hash_thread.start()
        logger.info("Hashing thread started.")


    def _on_hash_finished(self):
        """Actions to perform when hashing thread finishes."""
        logger.info("Hashing thread finished.")
        self.hash_button.setEnabled(True) # Re-enable button
        self.browse_button.setEnabled(True)
        self.parent().window().statusBar().showMessage("Hashing complete.", 3000)
        self._hash_thread = None # Clean up reference
        self._hash_worker = None


    def _display_hashes(self, hash_results):
        """Displays the calculated hashes."""
        self.md5_result_edit.setText(hash_results.get('md5', 'Error'))
        self.sha256_result_edit.setText(hash_results.get('sha256', 'Error'))
        logger.info(f"Displayed hashes for {os.path.basename(self._selected_file)}")

    # --- Metadata ---
    def _start_metadata_extraction(self):
        """Starts the metadata extraction in a background thread."""
        if not self._selected_file:
            QMessageBox.warning(self, "No File", "Please select a file first.")
            return

        if self._metadata_thread and self._metadata_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Metadata extraction is already in progress.")
            return

        self.metadata_table.setRowCount(0) # Clear previous results
        self.metadata_button.setEnabled(False)
        self.browse_button.setEnabled(False)


        self._metadata_thread = QThread()
        self._metadata_worker = MetadataWorker(self._selected_file)
        self._metadata_worker.moveToThread(self._metadata_thread)

        # Connect signals
        self._metadata_worker.finished.connect(self._metadata_thread.quit)
        self._metadata_worker.finished.connect(self._metadata_worker.deleteLater)
        self._metadata_thread.finished.connect(self._metadata_thread.deleteLater)
        self._metadata_thread.finished.connect(self._on_metadata_finished)
        self._metadata_worker.results_ready.connect(self._display_metadata)
        self._metadata_worker.error.connect(self._show_error)
        # self._metadata_worker.progress.connect(self.parent().parent().parent().statusBar().showMessage)
        self._metadata_worker.progress.connect(lambda msg: self.parent().window().statusBar().showMessage(msg, 5000))


        self._metadata_thread.started.connect(self._metadata_worker.run)
        self._metadata_thread.start()
        logger.info("Metadata extraction thread started.")


    def _on_metadata_finished(self):
        """Actions when metadata thread finishes."""
        logger.info("Metadata extraction thread finished.")
        self.metadata_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.parent().window().statusBar().showMessage("Metadata extraction complete.", 3000)
        self._metadata_thread = None
        self._metadata_worker = None


    def _display_metadata(self, metadata_results):
        """Displays extracted metadata in the table."""
        self.metadata_table.setRowCount(0) # Clear again just in case

        if isinstance(metadata_results, dict):
            if "Error" in metadata_results:
                 self._show_error(f"Metadata Error: {metadata_results['Error']}")
                 return
            if "Info" in metadata_results:
                 # Display info message, maybe in status bar or a single table row
                 self.metadata_table.setRowCount(1)
                 self.metadata_table.setItem(0, 0, QTableWidgetItem("Info"))
                 self.metadata_table.setItem(0, 1, QTableWidgetItem(metadata_results['Info']))
                 self.parent().window().statusBar().showMessage(metadata_results['Info'], 5000)
                 return

            self.metadata_table.setRowCount(len(metadata_results))
            row = 0
            for key, value in metadata_results.items():
                self.metadata_table.setItem(row, 0, QTableWidgetItem(str(key)))
                self.metadata_table.setItem(row, 1, QTableWidgetItem(str(value)))
                row += 1
            self.metadata_table.resizeRowsToContents() # Adjust row height
            logger.info(f"Displayed metadata for {os.path.basename(self._selected_file)}")
        else:
             self._show_error("Received invalid data format for metadata.")

    # --- Common ---
    def _show_error(self, message):
        """Displays an error message to the user."""
        logger.error(f"Utility Tab Error: {message}")
        # Display in status bar and potentially a message box
        self.parent().window().statusBar().showMessage(f"Error: {message}", 10000) # Show longer
        # Decide if a pop-up is always necessary or just for critical errors
        # QMessageBox.critical(self, "Analysis Error", message)


    def stop_all_analyses(self):
        """Attempts to stop any running worker threads."""
        if self._hash_thread and self._hash_thread.isRunning():
            logger.info("Requesting hash worker stop...")
            if self._hash_worker: self._hash_worker.stop()
            self._hash_thread.quit()
            self._hash_thread.wait(2000) # Wait max 2 seconds
            if self._hash_thread.isRunning(): # Force quit if still running
                 logger.warning("Forcing hash thread termination.")
                 self._hash_thread.terminate()
                 self._hash_thread.wait()
            self._on_hash_finished() # Trigger cleanup manually if stopped

        if self._metadata_thread and self._metadata_thread.isRunning():
            logger.info("Requesting metadata worker stop...")
            if self._metadata_worker: self._metadata_worker.stop()
            self._metadata_thread.quit()
            self._metadata_thread.wait(2000)
            if self._metadata_thread.isRunning():
                 logger.warning("Forcing metadata thread termination.")
                 self._metadata_thread.terminate()
                 self._metadata_thread.wait()
            self._on_metadata_finished() # Trigger cleanup


    def closeEvent(self, event):
        """Ensure threads are stopped when the widget/window is closed."""
        self.stop_all_analyses()
        super().closeEvent(event)