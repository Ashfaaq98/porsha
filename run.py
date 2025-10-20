__author__ = "Ashfaaq Farzaan"
__license__ = "Affero GPL"
__version__ = "0.1"
__maintainer__ = "Ashfaaq Farzaan"
__email__ = "ashfaaqf@proton.me"
__status__ = "Development"

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication

log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
log_level = logging.INFO 
log_file = "porsha_toolkit.log"

logging.basicConfig(level=log_level,
                    format=log_format,
                    handlers=[
                        logging.FileHandler(log_file, mode='w'), 
                        logging.StreamHandler(sys.stdout) 
                    ])

logging.getLogger("hachoir").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)

try:
    from gui.main_window import MainWindow
except ImportError as e:
     logging.critical(f"Failed to import GUI components: {e}", exc_info=True)
     try:
          app = QApplication([])
          from PyQt6.QtWidgets import QMessageBox
          QMessageBox.critical(None, "Import Error",
                              f"Failed to load application components.\n"
                              f"Error: {e}\n\nPlease check logs and ensure all dependencies are installed correctly.")
     except Exception:
          print(f"CRITICAL: Failed to import GUI components: {e}", file=sys.stderr)
          print("Ensure PyQt6 and other dependencies are installed.", file=sys.stderr)
     sys.exit(1)


def main():
    """Main function to start the Porsha application."""
    logger.info("Starting Porsha Digital Forensics Toolkit...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Log file: {os.path.abspath(log_file)}")

    app = QApplication(sys.argv)


    main_window = MainWindow()
    main_window.show()

    logger.info("Application event loop started.")
    exit_code = app.exec()
    logger.info(f"Application finished with exit code {exit_code}.")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()