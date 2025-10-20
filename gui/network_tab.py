# --- gui/network_tab.py ---
import os
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QTableWidget,
                             QTableWidgetItem, QHeaderView, QLabel, QMessageBox,
                             QSplitter)
from PyQt6.QtCore import Qt, QThread

from .worker import NetworkAnalysisWorker # Relative import

logger = logging.getLogger(__name__)

class NetworkTab(QWidget):
    """QWidget for Network Packet Capture (PCAP) Analysis."""

    def __init__(self, parent=None):
        """Initializes the NetworkTab."""
        super().__init__(parent)
        self.setObjectName("NetworkTab")
        self._network_worker = None
        self._network_thread = None
        self._pcap_path = None

        self._setup_ui()

    def _setup_ui(self):
        """Sets up the UI elements for the tab."""
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # --- Top Section: File Selection and Summary ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0,0,0,0)

        # File Selection Group
        file_group = QGroupBox("PCAP File")
        file_layout = QHBoxLayout()
        self.pcap_path_edit = QLineEdit()
        self.pcap_path_edit.setPlaceholderText("Select PCAP file...")
        self.pcap_path_edit.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_pcap)
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.clicked.connect(self._start_network_analysis)
        self.analyze_button.setEnabled(False) # Enable after file selection

        file_layout.addWidget(self.pcap_path_edit)
        file_layout.addWidget(self.browse_button)
        file_layout.addWidget(self.analyze_button)
        file_group.setLayout(file_layout)
        top_layout.addWidget(file_group)

        # Summary Group
        summary_group = QGroupBox("Summary")
        summary_layout = QHBoxLayout() # Use QHBoxLayout for side-by-side labels
        self.packet_count_label = QLabel("Packets: N/A")
        self.start_time_label = QLabel("Start Time: N/A")
        self.end_time_label = QLabel("End Time: N/A")
        summary_layout.addWidget(self.packet_count_label)
        summary_layout.addStretch()
        summary_layout.addWidget(self.start_time_label)
        summary_layout.addStretch()
        summary_layout.addWidget(self.end_time_label)
        summary_group.setLayout(summary_layout)
        top_layout.addWidget(summary_group)

        splitter.addWidget(top_widget)


        # --- Bottom Section: Conversations ---
        conv_group = QGroupBox("Conversations (IP/TCP/UDP)")
        conv_layout = QVBoxLayout()
        self.conv_table = QTableWidget()
        self.conv_table.setColumnCount(6)
        self.conv_table.setHorizontalHeaderLabels([
            "Protocol", "Source IP", "Source Port", "Dest IP", "Dest Port", "Packet Count"
        ])
        self.conv_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.conv_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.conv_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Packet count
        self.conv_table.setAlternatingRowColors(True)
        self.conv_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.conv_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.conv_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.conv_table.setSortingEnabled(True)

        conv_layout.addWidget(self.conv_table)
        conv_group.setLayout(conv_layout)

        splitter.addWidget(conv_group)

        # Adjust splitter sizes
        splitter.setStretchFactor(0, 0) # Give top less space
        splitter.setStretchFactor(1, 1) # Give bottom more space

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def _browse_pcap(self):
        """Opens a file dialog to select a PCAP file."""
        self.stop_analysis() # Stop previous work

        extensions = "Packet Capture Files (*.pcap *.pcapng *.cap);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select PCAP File", "", extensions)
        if file_path:
            self._pcap_path = file_path
            self.pcap_path_edit.setText(file_path)
            self.analyze_button.setEnabled(True)
            # Clear previous results
            self.packet_count_label.setText("Packets: N/A")
            self.start_time_label.setText("Start Time: N/A")
            self.end_time_label.setText("End Time: N/A")
            self.conv_table.setRowCount(0)
            logger.info(f"PCAP file selected: {file_path}")
            # Optionally auto-analyze:
            # self._start_network_analysis()
        else:
            self._pcap_path = None
            self.pcap_path_edit.clear()
            self.analyze_button.setEnabled(False)

    def _start_network_analysis(self):
        """Starts the PCAP analysis in a background thread."""
        if not self._pcap_path:
            QMessageBox.warning(self, "No File", "Please select a PCAP file first.")
            return

        if self._network_thread and self._network_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Network analysis is already in progress.")
            return

        # Clear previous results
        self.packet_count_label.setText("Packets: Analyzing...")
        self.start_time_label.setText("Start Time: Analyzing...")
        self.end_time_label.setText("End Time: Analyzing...")
        self.conv_table.setRowCount(0)

        self.analyze_button.setEnabled(False)
        self.browse_button.setEnabled(False)

        self._network_thread = QThread()
        self._network_worker = NetworkAnalysisWorker(self._pcap_path)
        self._network_worker.moveToThread(self._network_thread)

        # Connect signals
        self._network_worker.finished.connect(self._network_thread.quit)
        self._network_worker.finished.connect(self._network_worker.deleteLater)
        self._network_thread.finished.connect(self._network_thread.deleteLater)
        self._network_thread.finished.connect(self._on_network_analysis_finished)

        self._network_worker.error.connect(self._show_error)
        self._network_worker.progress.connect(lambda msg: self.parent().window().statusBar().showMessage(msg, 5000))
        self._network_worker.results_ready.connect(self._display_results)


        self._network_thread.started.connect(self._network_worker.run)
        self._network_thread.start()
        logger.info(f"Network analysis thread started for: {os.path.basename(self._pcap_path)}")
        self.parent().window().statusBar().showMessage(f"Analyzing PCAP: {os.path.basename(self._pcap_path)}...")


    def _on_network_analysis_finished(self):
        """Actions when the network analysis thread finishes."""
        logger.info("Network analysis thread finished.")
        self.analyze_button.setEnabled(True) # Re-enable controls
        self.browse_button.setEnabled(True)
        self.parent().window().statusBar().showMessage("Network analysis complete.", 5000)
        self._network_thread = None
        self._network_worker = None


    def _display_results(self, results):
        """Populates the summary labels and conversations table."""
        summary = results.get('summary', {})
        conversations = results.get('conversations', [])

        # Display Summary
        self.packet_count_label.setText(f"Packets: {summary.get('packet_count', 'N/A')}")
        self.start_time_label.setText(f"Start Time: {summary.get('start_time', 'N/A')}")
        self.end_time_label.setText(f"End Time: {summary.get('end_time', 'N/A')}")

        # Display Conversations
        self.conv_table.setRowCount(0) # Clear existing
        self.conv_table.setSortingEnabled(False)

        if not conversations:
             logger.info("No conversations found or returned.")
             # Optionally display message in table
             return

        self.conv_table.setRowCount(len(conversations))
        for row, conv in enumerate(conversations):
            proto_item = QTableWidgetItem(str(conv.get('protocol', 'N/A')))
            src_ip_item = QTableWidgetItem(str(conv.get('src_ip', 'N/A')))
            src_port_item = QTableWidgetItem(str(conv.get('src_port', 'N/A')))
            dst_ip_item = QTableWidgetItem(str(conv.get('dst_ip', 'N/A')))
            dst_port_item = QTableWidgetItem(str(conv.get('dst_port', 'N/A')))
            count_item = QTableWidgetItem(str(conv.get('packet_count', 0)))
            # Store packet count as number for sorting
            count_item.setData(Qt.ItemDataRole.UserRole, conv.get('packet_count', 0))


            self.conv_table.setItem(row, 0, proto_item)
            self.conv_table.setItem(row, 1, src_ip_item)
            self.conv_table.setItem(row, 2, src_port_item)
            self.conv_table.setItem(row, 3, dst_ip_item)
            self.conv_table.setItem(row, 4, dst_port_item)
            self.conv_table.setItem(row, 5, count_item)


        self.conv_table.resizeColumnsToContents()
        self.conv_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Stretch src ip
        self.conv_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Stretch dst ip
        self.conv_table.setSortingEnabled(True)
        # Default sort by packet count descending
        self.conv_table.sortByColumn(5, Qt.SortOrder.DescendingOrder)

        logger.info(f"Displayed {len(conversations)} network conversations.")
        self.parent().window().statusBar().showMessage(f"Displayed {len(conversations)} conversations.", 5000)


    def _show_error(self, message):
        """Displays an error message."""
        logger.error(f"Network Tab Error: {message}")
        self.parent().window().statusBar().showMessage(f"Error: {message}", 10000)
        QMessageBox.critical(self, "Network Analysis Error", message)
        # Reset summary labels on error
        self.packet_count_label.setText("Packets: Error")
        self.start_time_label.setText("Start Time: Error")
        self.end_time_label.setText("End Time: Error")


    def stop_analysis(self):
        """Attempts to stop the running network analysis thread."""
        if self._network_thread and self._network_thread.isRunning():
            logger.info("Requesting network worker stop...")
            # Scapy analysis might be hard to interrupt cleanly.
            if self._network_worker: self._network_worker.stop()
            self._network_thread.quit()
            self._network_thread.wait(2000)
            if self._network_thread.isRunning():
                 logger.warning("Forcing network analysis thread termination.")
                 self._network_thread.terminate()
                 self._network_thread.wait()
            self._on_network_analysis_finished() # Trigger cleanup


    def closeEvent(self, event):
        """Ensure threads are stopped on close."""
        self.stop_analysis()
        super().closeEvent(event)