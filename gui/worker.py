# --- gui/worker.py ---
# Create a separate file for worker classes to keep tabs cleaner
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import logging
import traceback
import os
# Import backend functions - use absolute imports relative to project root
from tools import calculate_hash, extract_metadata, disk_analysis, network_analysis

logger = logging.getLogger(__name__)

# --- Base Worker ---
class BaseWorker(QObject):
    """Base class for worker objects running in QThreads."""
    finished = pyqtSignal()
    error = pyqtSignal(str) # Signal to emit error messages
    progress = pyqtSignal(str) # Signal for status updates
    results_ready = pyqtSignal(object) # Signal to emit results (type depends on task)

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.args = args
        self.kwargs = kwargs
        self._is_running = True

    def stop(self):
        """Request the worker to stop."""
        self._is_running = False
        self.progress.emit("Stopping analysis...")
        logger.info(f"{self.__class__.__name__} stop requested.")

    def run(self):
        """The main work method to be implemented by subclasses."""
        raise NotImplementedError


# --- Hashing Worker ---
class HashWorker(BaseWorker):
    def run(self):
        """Calculates hashes in a background thread."""
        try:
            file_path = self.args[0]
            self.progress.emit(f"Calculating hashes for {os.path.basename(file_path)}...")
            md5_hash, sha256_hash = calculate_hash.calculate_hashes(file_path)
            if not self._is_running: return # Check if stopped
            if md5_hash is not None:
                self.results_ready.emit({'md5': md5_hash, 'sha256': sha256_hash})
            else:
                self.error.emit(f"Failed to calculate hashes for {os.path.basename(file_path)}.")
        except Exception as e:
            if not self._is_running: return # Avoid emitting error if stopping caused it
            error_message = f"Error during hashing: {e}\n{traceback.format_exc()}"
            logger.error(error_message)
            self.error.emit(f"Hashing error: {e}")
        finally:
            if self._is_running: # Only emit finished if not stopped externally
                 self.finished.emit()


# --- Metadata Worker ---
class MetadataWorker(BaseWorker):
    def run(self):
        """Extracts metadata in a background thread."""
        try:
            file_path = self.args[0]
            self.progress.emit(f"Extracting metadata for {os.path.basename(file_path)}...")
            metadata = extract_metadata.get_metadata(file_path)
            if not self._is_running: return
            self.results_ready.emit(metadata) # Emit the dict, could be {'Error': ...}
        except Exception as e:
            if not self._is_running: return
            error_message = f"Error during metadata extraction: {e}\n{traceback.format_exc()}"
            logger.error(error_message)
            self.error.emit(f"Metadata error: {e}")
        finally:
            if self._is_running:
                 self.finished.emit()


# --- Disk Analysis Worker ---
class DiskAnalysisWorker(BaseWorker):
    """Worker for various disk analysis tasks."""
    # Define specific result signals if needed, or use results_ready with identifiers
    volume_info_ready = pyqtSignal(list)
    directory_listing_ready = pyqtSignal(list)
    filesystem_opened = pyqtSignal(bool, str) # Success/Fail, Message (e.g., FS type)

    def run(self):
        """Executes the requested disk analysis task."""
        task = self.kwargs.get('task')
        image_path = self.kwargs.get('image_path')
        partition_index = self.kwargs.get('partition_index')
        offset_sectors = self.kwargs.get('offset_sectors')
        list_path = self.kwargs.get('list_path', "/") # Default to root
        inode = self.kwargs.get('inode')

        disk_handler = None
        try:
            self.progress.emit(f"Starting disk task: {task}...")
            disk_handler = disk_analysis.DiskImageHandler(image_path)

            if task == 'get_volumes':
                 self.progress.emit("Reading volume information...")
                 volumes = disk_handler.get_volume_info()
                 if not self._is_running: return
                 self.volume_info_ready.emit(volumes)
            elif task == 'open_fs':
                 self.progress.emit(f"Attempting to open filesystem (Partition: {partition_index}, Offset: {offset_sectors})...")
                 success = disk_handler.open_filesystem(partition_index=partition_index, offset_sectors=offset_sectors)
                 if not self._is_running: return
                 fs_type_msg = ""
                 if success and disk_handler.fs_info:
                      fs_type = disk_handler.fs_info.info.ftype
                      fs_type_msg = f"FS Type: {pytsk3.TSK_FS_TYPE_ENUM(fs_type).name}"
                 self.filesystem_opened.emit(success, fs_type_msg)
                 # Store handler in kwargs if needed for subsequent tasks (careful with state)
                 # self.kwargs['disk_handler'] = disk_handler # Potential issues if thread finishes prematurely
            elif task == 'list_dir':
                 # This assumes open_filesystem was called previously and handler is passed or recreated
                 # For simplicity, let's assume the handler is recreated/opened each time for now
                 # A more complex state management would be needed otherwise.
                 self.progress.emit(f"Opening filesystem to list directory: {list_path}...")
                 success = disk_handler.open_filesystem(partition_index=partition_index, offset_sectors=offset_sectors)
                 if not success:
                     if not self._is_running: return
                     self.error.emit(f"Failed to open filesystem before listing directory.")
                 else:
                     self.progress.emit(f"Listing directory: {list_path}...")
                     entries = disk_handler.list_directory(path=list_path, inode=inode)
                     if not self._is_running: return
                     self.directory_listing_ready.emit(entries)
            else:
                 raise ValueError(f"Unknown disk task: {task}")

        except Exception as e:
            if not self._is_running: return
            error_message = f"Error during disk analysis task '{task}': {e}\n{traceback.format_exc()}"
            logger.error(error_message)
            self.error.emit(f"Disk analysis error: {e}")
        finally:
             if disk_handler:
                 disk_handler.close() # Ensure Img_Info is released (though no explicit close method exists)
             if self._is_running:
                 self.finished.emit()


# --- Network Analysis Worker ---
class NetworkAnalysisWorker(BaseWorker):
    def run(self):
        """Analyzes PCAP file in the background."""
        try:
            pcap_path = self.args[0]
            self.progress.emit(f"Analyzing PCAP: {os.path.basename(pcap_path)}...")
            results = network_analysis.analyze_pcap(pcap_path)
            if not self._is_running: return

            # Check if the backend function reported an error
            if results.get('summary', {}).get('error'):
                 self.error.emit(f"PCAP analysis error: {results['summary']['error']}")
            else:
                 self.results_ready.emit(results) # Emit {'summary': {...}, 'conversations': [...]}

        except Exception as e:
            if not self._is_running: return
            error_message = f"Error during network analysis: {e}\n{traceback.format_exc()}"
            logger.error(error_message)
            self.error.emit(f"Network analysis error: {e}")
        finally:
            if self._is_running:
                 self.finished.emit()


