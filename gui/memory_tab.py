# --- gui/memory_tab.py ---
import os
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QComboBox,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QLabel, QMessageBox, QProgressBar, QSizePolicy)
from PyQt6.QtCore import Qt, QThread

from .worker import MemoryAnalysisWorker # Relative import
from tools import memory_analysis # For plugin list

logger = logging.getLogger(__name__)

class MemoryTab(QWidget):
    """QWidget for Memory Image Analysis using Volatility 3."""

    def __init__(self, parent=None):
        """Initializes the MemoryTab."""
        super().__init__(parent)
        self.setObjectName("MemoryTab")
        self._memory_worker = None
        self._memory_thread = None
        self._image_path = None
        self._volatility_available = memory_analysis.HAS_VOLATILITY # Check on init

        self._setup_ui()
        if not self._volatility_available:
             self._show_volatility_warning()

    def _setup_ui(self):
        """Sets up the UI elements for the tab."""
        main_layout = QVBoxLayout(self)

        # --- Top Section: Image Selection and Plugin Choice ---
        top_group = QGroupBox("Memory Analysis Setup")
        top_layout = QVBoxLayout()

        # Image Selection
        img_layout = QHBoxLayout()
        img_layout.addWidget(QLabel("Memory Image:"))
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setPlaceholderText("Select memory image file...")
        self.image_path_edit.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_image)
        img_layout.addWidget(self.image_path_edit)
        img_layout.addWidget(self.browse_button)
        top_layout.addLayout(img_layout)

        # Plugin Selection
        plugin_layout = QHBoxLayout()
        plugin_layout.addWidget(QLabel("Volatility Plugin:"))
        self.plugin_combo = QComboBox()
        self._populate_plugin_list() # Fill combo box
        plugin_layout.addWidget(self.plugin_combo, 1) # Give combo box more stretch space
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.clicked.connect(self._start_memory_analysis)
        self.analyze_button.setEnabled(False) # Enable only when image and plugin selected
        plugin_layout.addWidget(self.analyze_button)
        top_layout.addLayout(plugin_layout)

        # Optional: Add fields for plugin arguments if needed (e.g., PID)
        # self.plugin_args_edit = QLineEdit()
        # self.plugin_args_edit.setPlaceholderText("Optional plugin arguments (e.g., pid=1234)...")
        # top_layout.addWidget(self.plugin_args_edit)

        top_group.setLayout(top_layout)
        main_layout.addWidget(top_group)


        # --- Results Section ---
        results_group = QGroupBox("Analysis Results")
        results_layout = QVBoxLayout()
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(0) # Columns set dynamically
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection) # Allow multi-select/copy
        self.results_table.setSortingEnabled(True)
        results_layout.addWidget(self.results_table)
        results_group.setLayout(results_layout)

        main_layout.addWidget(results_group, 1) # Give results more stretch space

        self.setLayout(main_layout)

        # Enable analyze button only if Volatility is found
        if not self._volatility_available:
             self.plugin_combo.setEnabled(False)
             self.analyze_button.setEnabled(False)
             self.browse_button.setEnabled(False) # Also disable browse if vol not found


    def _show_volatility_warning(self):
         """Displays a warning if Volatility 3 is not available."""
         QMessageBox.warning(self, "Volatility 3 Not Found",
                             "The Volatility 3 library was not found or could not be imported.\n"
                             "Memory analysis features will be disabled.\n\n"
                             "Please ensure 'volatility3' is installed correctly in your Python environment (`pip install volatility3`).")

    def _populate_plugin_list(self):
        """Populates the plugin dropdown."""
        self.plugin_combo.clear()
        if not self._volatility_available:
            self.plugin_combo.addItem("Volatility 3 Not Available")
            return

        self.plugin_combo.addItem("-- Select Plugin --", "") # Placeholder item
        # Add plugins from the predefined list in memory_analysis
        for display_name, full_name in memory_analysis.SUPPORTED_PLUGINS.items():
            self.plugin_combo.addItem(display_name, full_name) # Store full name as data

        self.plugin_combo.currentIndexChanged.connect(self._check_analyze_button_state)

    def _browse_image(self):
        """Opens a file dialog to select a memory image."""
        self.stop_analysis() # Stop previous analysis

        # Common memory file extensions
        extensions = "Memory Images (*.vmem *.raw *.mem *.dmp);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Memory Image", "", extensions)
        if file_path:
            self._image_path = file_path
            self.image_path_edit.setText(file_path)
            self.results_table.setRowCount(0)
            self.results_table.setColumnCount(0)
            self._check_analyze_button_state()
            logger.info(f"Memory image selected: {file_path}")
        else:
            self._image_path = None
            self.image_path_edit.clear()
            self._check_analyze_button_state()

    def _check_analyze_button_state(self):
        """Enables/disables the Analyze button based on selections."""
        if not self._volatility_available:
             self.analyze_button.setEnabled(False)
             return

        valid_image = bool(self._image_path and os.path.exists(self._image_path))
        valid_plugin = bool(self.plugin_combo.currentData()) # Check if data (full name) is set

        self.analyze_button.setEnabled(valid_image and valid_plugin)


    def _start_memory_analysis(self):
        """Starts the Volatility analysis in a background thread."""
        if not self._image_path:
            QMessageBox.warning(self, "No Image", "Please select a memory image file first.")
            return

        plugin_full_name = self.plugin_combo.currentData()
        if not plugin_full_name:
            QMessageBox.warning(self, "No Plugin", "Please select a Volatility plugin first.")
            return

        if self._memory_thread and self._memory_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Memory analysis is already in progress.")
            return

        # Clear previous results
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)

        self.analyze_button.setEnabled(False) # Disable buttons during run
        self.browse_button.setEnabled(False)
        self.plugin_combo.setEnabled(False)

        # TODO: Parse plugin arguments from self.plugin_args_edit if implemented
        plugin_options = {}

        self._memory_thread = QThread()
        self._memory_worker = MemoryAnalysisWorker(
            image_path=self._image_path,
            plugin_full_name=plugin_full_name,
            plugin_options=plugin_options
        )
        self._memory_worker.moveToThread(self._memory_thread)

        # Connect signals
        self._memory_worker.finished.connect(self._memory_thread.quit)
        self._memory_worker.finished.connect(self._memory_worker.deleteLater)
        self._memory_thread.finished.connect(self._memory_thread.deleteLater)
        self._memory_thread.finished.connect(self._on_memory_analysis_finished)

        self._memory_worker.error.connect(self._show_error)
        self._memory_worker.progress.connect(lambda msg: self.parent().window().statusBar().showMessage(msg, 10000)) # Show progress longer
        self._memory_worker.volatility_results.connect(self._display_results)


        self._memory_thread.started.connect(self._memory_worker.run)
        self._memory_thread.start()
        logger.info(f"Memory analysis thread started for plugin: {plugin_full_name}")
        plugin_display_name = self.plugin_combo.currentText()
        self.parent().window().statusBar().showMessage(f"Starting analysis: {plugin_display_name}...")


    def _on_memory_analysis_finished(self):
        """Actions when the memory analysis thread finishes."""
        logger.info("Memory analysis thread finished.")
        self.analyze_button.setEnabled(True) # Re-enable controls
        self.browse_button.setEnabled(True)
        self.plugin_combo.setEnabled(True)
        self._check_analyze_button_state() # Re-check state
        self.parent().window().statusBar().showMessage("Memory analysis complete.", 5000)
        self._memory_thread = None
        self._memory_worker = None


    def _display_results(self, headers, rows_data):
        """Populates the results table with data from Volatility."""
        self.results_table.setRowCount(0) # Clear existing
        self.results_table.setColumnCount(0)
        self.results_table.setSortingEnabled(False) # Disable sorting during population

        if not headers or not rows_data:
             logger.info("No results returned from Volatility plugin.")
             # Display a message in the table?
             self.results_table.setColumnCount(1)
             self.results_table.setHorizontalHeaderLabels(["Info"])
             self.results_table.setRowCount(1)
             self.results_table.setItem(0, 0, QTableWidgetItem("Plugin ran successfully, but returned no data."))
             self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
             return

        self.results_table.setColumnCount(len(headers))
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.setRowCount(len(rows_data))

        for row_idx, row_items in enumerate(rows_data):
            for col_idx, item_data in enumerate(row_items):
                 # Convert all data to string for QTableWidgetItem
                 # For numerical sorting, store original int/float if needed via setData
                 table_item = QTableWidgetItem(str(item_data))
                 if isinstance(item_data, int) or isinstance(item_data, float):
                      # Store numerical data for sorting if needed
                      table_item.setData(Qt.ItemDataRole.UserRole, item_data)
                 self.results_table.setItem(row_idx, col_idx, table_item)

        self.results_table.resizeColumnsToContents()
        # Optionally stretch the last column or a specific named column
        if headers:
            # Try stretching 'Command Line' or 'Process' or the last column as fallback
            stretch_col_name = None
            if 'Command Line' in headers: stretch_col_name = 'Command Line'
            elif 'Process' in headers: stretch_col_name = 'Process'
            elif 'Name' in headers: stretch_col_name = 'Name' # Common in pslist

            stretch_col_index = -1
            if stretch_col_name:
                 try: stretch_col_index = headers.index(stretch_col_name)
                 except ValueError: pass # Name not found
            
            if stretch_col_index != -1:
                 self.results_table.horizontalHeader().setSectionResizeMode(stretch_col_index, QHeaderView.ResizeMode.Stretch)
            else:
                 # Stretch last column if no specific one found
                 self.results_table.horizontalHeader().setSectionResizeMode(len(headers)-1, QHeaderView.ResizeMode.Stretch)


        self.results_table.setSortingEnabled(True)
        logger.info(f"Displayed {len(rows_data)} results for plugin {self.plugin_combo.currentText()}.")
        self.parent().window().statusBar().showMessage(f"Displayed {len(rows_data)} results.", 5000)


    def _show_error(self, message):
        """Displays an error message."""
        logger.error(f"Memory Tab Error: {message}")
        self.parent().window().statusBar().showMessage(f"Error: {message}", 15000) # Show longer
        QMessageBox.critical(self, "Memory Analysis Error", message)


    def stop_analysis(self):
        """Attempts to stop the running memory analysis thread."""
        if self._memory_thread and self._memory_thread.isRunning():
            logger.info("Requesting memory worker stop...")
            # Volatility plugins might not be easily interruptible mid-run.
            # Stopping the thread might be the only option, but can be unclean.
            if self._memory_worker: self._memory_worker.stop() # Ask worker to stop if possible
            self._memory_thread.quit() # Ask thread to quit nicely
            self._memory_thread.wait(3000) # Wait a bit longer for Volatility
            if self._memory_thread.isRunning():
                 logger.warning("Forcing memory analysis thread termination (may be unstable).")
                 self._memory_thread.terminate() # Force stop
                 self._memory_thread.wait()
            self._on_memory_analysis_finished() # Trigger cleanup


    def closeEvent(self, event):
        """Ensure threads are stopped on close."""
        self.stop_analysis()
        super().closeEvent(event)