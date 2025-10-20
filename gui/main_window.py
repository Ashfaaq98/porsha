# --- gui/main_window.py ---
import sys
import logging
from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QStatusBar, QMessageBox,
                             QWidget, QVBoxLayout)
from PyQt6.QtGui import QAction, QIcon # For potential icons later
from PyQt6.QtCore import QSize

# Import Tab Widgets

from .disk_tab import DiskTab
from .network_tab import NetworkTab
from .utility_tab import UtilityTab
from .settings import AboutDialog # Import the About dialog

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        """Initializes the MainWindow."""
        super().__init__()
        self.setWindowTitle("Porsha Digital Forensics Toolkit v0.1")
        # Set a reasonable default size
        self.setGeometry(100, 100, 1000, 700) # x, y, width, height

        self._create_widgets()
        self._create_menu_bar()
        self._create_status_bar()

        logger.info("Main application window initialized.")

    def _create_widgets(self):
        """Creates the central tab widget and adds tabs."""
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(False) # Tabs are not closable

        # Create instances of tab widgets
  
        self.disk_tab = DiskTab(self)
        self.network_tab = NetworkTab(self)
        self.utility_tab = UtilityTab(self)
        # Add more tabs here if needed (e.g., EmailTab if implemented)

        # Add tabs to the QTabWidget

        self.tab_widget.addTab(self.disk_tab, "Disk Analysis")
        self.tab_widget.addTab(self.network_tab, "Network Analysis")
        self.tab_widget.addTab(self.utility_tab, "Utilities (Hash/Meta)")
        # self.tab_widget.addTab(EmailTab(self), "Email Analysis")

        self.setCentralWidget(self.tab_widget)

    def _create_menu_bar(self):
        """Creates the main menu bar and actions."""
        menu_bar = self.menuBar()

        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")

        # Example: Open Evidence Action (currently placeholder)
        # open_action = QAction("&Open Evidence...", self)
        # open_action.setStatusTip("Open an evidence file (image, pcap, etc.)")
        # open_action.triggered.connect(self.open_evidence) # Connect to a method
        # file_menu.addAction(open_action)
        # file_menu.addSeparator()

        exit_action = QAction("&Exit", self)
        exit_action.setStatusTip("Exit the application")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close) # Connect to QMainWindow's close method
        file_menu.addAction(exit_action)


        # --- Help Menu ---
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About Porsha", self)
        about_action.setStatusTip("Show information about this application")
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

        # Add placeholder for Volatility/Library info if needed
        # about_qt_action = QAction("About &Qt", self)
        # about_qt_action.triggered.connect(QMessageBox.aboutQt)
        # help_menu.addAction(about_qt_action)


    def _create_status_bar(self):
        """Creates the status bar at the bottom."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.", 3000) # Initial message, timeout 3s

    def open_evidence(self):
        """Placeholder method for a unified Open Evidence action."""
        # This could open a dialog asking for evidence type (memory, disk, pcap)
        # and then activate the corresponding tab and trigger its browse function.
        QMessageBox.information(self, "Open Evidence",
                                "This feature is not fully implemented yet.\n"
                                "Please use the 'Browse...' buttons within each specific analysis tab.")
        logger.warning("'Open Evidence' menu item clicked - feature not implemented.")


    def show_about_dialog(self):
        """Shows the About dialog."""
        about_dialog = AboutDialog(self)
        about_dialog.exec() # Show modally


    def closeEvent(self, event):
        """Handles the main window close event."""
        logger.info("Close event triggered. Asking user confirmation.")
        # Ask for confirmation before closing
        # reply = QMessageBox.question(self, 'Confirm Exit',
        #                              "Are you sure you want to exit Porsha?",
        #                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        #                              QMessageBox.StandardButton.No)

        # if reply == QMessageBox.StandardButton.Yes:
        logger.info("Attempting to stop all analysis threads before closing.")
        # Gracefully stop threads in each tab
        # Note: Tabs might need a public stop_analysis() method
        tabs = [ self.disk_tab, self.network_tab, self.utility_tab]
        for tab in tabs:
             if hasattr(tab, 'stop_analysis') and callable(tab.stop_analysis):
                  try:
                       tab.stop_analysis()
                  except Exception as e:
                       logger.error(f"Error stopping analysis in {tab.objectName()}: {e}")
             elif hasattr(tab, 'stop_all_analyses') and callable(tab.stop_all_analyses): # UtilityTab uses this name
                  try:
                       tab.stop_all_analyses()
                  except Exception as e:
                       logger.error(f"Error stopping analysis in {tab.objectName()}: {e}")

        logger.info("Accepting close event.")
        event.accept() # Close the window
        # else:
        #     logger.info("Close event cancelled by user.")
        #     event.ignore() # Don't close