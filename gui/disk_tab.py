# --- gui/disk_tab.py ---
import os
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QTreeView,
                             QSplitter, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLabel, QMessageBox, QAbstractItemView,
                             QMenu)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFileSystemModel, QAction
from PyQt6.QtCore import Qt, QThread, QModelIndex, QItemSelectionModel

from .worker import DiskAnalysisWorker # Relative import
from tools import disk_analysis # Needed for pytsk3 constants potentially

logger = logging.getLogger(__name__)

class DiskTab(QWidget):
    """QWidget for Disk Image Analysis."""

    def __init__(self, parent=None):
        """Initializes the DiskTab."""
        super().__init__(parent)
        self.setObjectName("DiskTab")
        self._disk_worker = None
        self._disk_thread = None
        self._image_path = None
        self._disk_handler = None # Potentially store handler if stateful ops needed
        self._selected_partition_index = None # Track selected partition for FS ops
        self._selected_offset = None          # Track selected offset if no partitions
        self._current_fs_open = False        # Flag if a filesystem is currently open

        self._setup_ui()

    def _setup_ui(self):
        """Sets up the UI elements for the tab."""
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # --- Top Section: Image Selection and Volume Info ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0,0,0,0) # Remove margins for splitter

        # Image Selection Group
        img_group = QGroupBox("Disk Image")
        img_layout = QHBoxLayout()
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setPlaceholderText("Select disk image (Raw/dd)...")
        self.image_path_edit.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_image)
        img_layout.addWidget(self.image_path_edit)
        img_layout.addWidget(self.browse_button)
        img_group.setLayout(img_layout)
        top_layout.addWidget(img_group)

        # Volume Info Group
        vol_group = QGroupBox("Volumes / Partitions")
        vol_layout = QVBoxLayout()
        self.volume_table = QTableWidget()
        self.volume_table.setColumnCount(5)
        self.volume_table.setHorizontalHeaderLabels(["Slot", "Description", "Start Sector", "Sector Count", "Flags"])
        self.volume_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Stretch description
        self.volume_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.volume_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.volume_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.volume_table.setAlternatingRowColors(True)
        self.volume_table.doubleClicked.connect(self._volume_selected) # Double click to open FS
        vol_layout.addWidget(self.volume_table)
        vol_group.setLayout(vol_layout)
        top_layout.addWidget(vol_group)

        splitter.addWidget(top_widget)

        # --- Bottom Section: Filesystem Browser ---
        fs_group = QGroupBox("Filesystem Browser")
        fs_layout = QVBoxLayout()
        self.fs_status_label = QLabel("Status: No filesystem selected/opened.")
        fs_layout.addWidget(self.fs_status_label)

        self.file_listing_table = QTableWidget()
        # Headers: inode, name, type, mode, size, mtime, atime, ctime, crtime, is_deleted
        self.file_listing_table.setColumnCount(10)
        self.file_listing_table.setHorizontalHeaderLabels([
            "Inode", "Name", "Type", "Mode", "Size", "Modified", "Accessed", "Changed", "Created", "Deleted?"
        ])
        self.file_listing_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Stretch name
        for i in [0, 2, 3, 4, 9]: # Resize some columns to contents
             self.file_listing_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.file_listing_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_listing_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.file_listing_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.file_listing_table.setAlternatingRowColors(True)
        self.file_listing_table.setSortingEnabled(True) # Allow column sorting
        self.file_listing_table.doubleClicked.connect(self._file_double_clicked) # Navigate into directories

        fs_layout.addWidget(self.file_listing_table)
        fs_group.setLayout(fs_layout)
        splitter.addWidget(fs_group)

        # Adjust splitter sizes (optional)
        splitter.setStretchFactor(0, 1) # Give top less space initially
        splitter.setStretchFactor(1, 3) # Give bottom more space

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def _browse_image(self):
        """Opens a file dialog to select a disk image."""
        self.stop_analysis() # Stop previous analysis if any

        file_path, _ = QFileDialog.getOpenFileName(self, "Select Disk Image", "", "Raw Disk Images (*.dd *.raw *.img);;All Files (*)")
        if file_path:
            self._image_path = file_path
            self.image_path_edit.setText(file_path)
            self.volume_table.setRowCount(0) # Clear previous volumes
            self.file_listing_table.setRowCount(0) # Clear file listing
            self._selected_partition_index = None
            self._selected_offset = None
            self._current_fs_open = False
            self.fs_status_label.setText("Status: Image selected. Double-click a volume to open.")
            logger.info(f"Disk image selected: {file_path}")
            self._start_disk_analysis(task='get_volumes')
        else:
            self._image_path = None
            self.image_path_edit.clear()


    def _start_disk_analysis(self, task, **kwargs):
        """Starts a disk analysis task in a background thread."""
        if not self._image_path:
            QMessageBox.warning(self, "No Image", "Please select a disk image first.")
            return

        if self._disk_thread and self._disk_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Disk analysis is already in progress.")
            return

        self.browse_button.setEnabled(False) # Disable browse during analysis

        kwargs['image_path'] = self._image_path # Ensure image path is in kwargs

        self._disk_thread = QThread()
        self._disk_worker = DiskAnalysisWorker(task=task, **kwargs)
        self._disk_worker.moveToThread(self._disk_thread)

        # Connect signals
        self._disk_worker.finished.connect(self._disk_thread.quit)
        self._disk_worker.finished.connect(self._disk_worker.deleteLater)
        self._disk_thread.finished.connect(self._disk_thread.deleteLater)
        self._disk_thread.finished.connect(self._on_disk_analysis_finished)

        self._disk_worker.error.connect(self._show_error)
        self._disk_worker.progress.connect(lambda msg: self.parent().window().statusBar().showMessage(msg, 5000))

        # Connect task-specific result signals
        if task == 'get_volumes':
            self._disk_worker.volume_info_ready.connect(self._display_volumes)
        elif task == 'open_fs':
             self._disk_worker.filesystem_opened.connect(self._on_filesystem_opened)
        elif task == 'list_dir':
            self._disk_worker.directory_listing_ready.connect(self._display_directory_listing)
            # We also need the filesystem_opened signal if the worker opens it internally
            # Reconnecting is fine, Qt handles duplicate connections.
            self._disk_worker.filesystem_opened.connect(self._on_filesystem_opened)


        self._disk_thread.started.connect(self._disk_worker.run)
        self._disk_thread.start()
        logger.info(f"Disk analysis thread started for task: {task}")


    def _on_disk_analysis_finished(self):
        """Actions when the disk analysis thread finishes."""
        logger.info("Disk analysis thread finished.")
        self.browse_button.setEnabled(True) # Re-enable browse
        self.parent().window().statusBar().showMessage("Disk analysis task complete.", 3000)
        self._disk_thread = None
        self._disk_worker = None


    def _display_volumes(self, volumes):
        """Populates the volume table."""
        self.volume_table.setRowCount(0) # Clear existing entries
        self.volume_table.setSortingEnabled(False) # Disable sorting during population

        if not volumes:
            self.fs_status_label.setText("Status: No volumes/partitions found. May be single FS image.")
            # Optionally, try to open FS at offset 0 automatically? Or provide button.
            # For now, just inform user. They can try manually if needed (feature not added yet)
            return

        self.volume_table.setRowCount(len(volumes))
        for row, vol in enumerate(volumes):
            self.volume_table.setItem(row, 0, QTableWidgetItem(str(vol['slot'])))
            self.volume_table.setItem(row, 1, QTableWidgetItem(vol['desc']))
            self.volume_table.setItem(row, 2, QTableWidgetItem(str(vol['start_sector'])))
            self.volume_table.setItem(row, 3, QTableWidgetItem(str(vol['num_sectors'])))
            self.volume_table.setItem(row, 4, QTableWidgetItem(vol['flags']))
            # Store the index/offset in the item data for retrieval on selection
            self.volume_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, (vol['slot'], vol['start_sector']))


        self.volume_table.resizeColumnsToContents()
        self.volume_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.volume_table.setSortingEnabled(True)
        logger.info(f"Displayed {len(volumes)} volumes.")
        self.fs_status_label.setText("Status: Volumes loaded. Double-click a volume to open its filesystem.")


    def _volume_selected(self, index: QModelIndex):
        """Handles double-clicking a volume in the table."""
        if not index.isValid():
            return

        # Retrieve stored data (slot, start_sector) from the first column (index 0) of the clicked row
        item_data = self.volume_table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
        if not item_data:
             logger.warning("No data found for selected volume item.")
             return

        slot, start_sector = item_data
        desc = self.volume_table.item(index.row(), 1).text()
        logger.info(f"Volume double-clicked: Slot={slot}, Start={start_sector}, Desc={desc}")

        self.file_listing_table.setRowCount(0) # Clear previous listing
        self._selected_partition_index = slot
        # Use offset primarily, as slot might be ambiguous if no partition table
        self._selected_offset = start_sector
        self._current_fs_open = False # Reset flag

        # If the description indicates it's just a potential FS, use offset=0
        if "Potential Filesystem" in desc:
             self._selected_partition_index = None # No partition index
             self._selected_offset = 0
             logger.info("Treating as single filesystem image at offset 0.")
             self._start_disk_analysis(task='list_dir', offset_sectors=self._selected_offset, list_path="/")
        else:
             # Start the task to open the FS, which will then trigger listing the root
             # Pass the partition index to the worker
             self._start_disk_analysis(task='list_dir', partition_index=self._selected_partition_index, list_path="/")


    def _on_filesystem_opened(self, success: bool, message: str):
        """Callback when the filesystem open attempt finishes."""
        self._current_fs_open = success
        if success:
            self.fs_status_label.setText(f"Status: Filesystem Opened ({message}). Listing root...")
            # The worker should proceed to list the directory after opening
            logger.info(f"Filesystem opened successfully. {message}")
        else:
            self.fs_status_label.setText(f"Status: Failed to open filesystem. {message}")
            self._show_error(f"Could not open filesystem for partition/offset {self._selected_partition_index}/{self._selected_offset}. Check FS type/corruption.")


    def _display_directory_listing(self, entries):
        """Populates the file listing table."""
        self.file_listing_table.setRowCount(0) # Clear existing
        self.file_listing_table.setSortingEnabled(False) # Disable sorting during population

        if not self._current_fs_open: # Check if FS failed to open before listing started
             logger.warning("Filesystem is not open, cannot display directory listing.")
             # Status label should already indicate failure from _on_filesystem_opened
             return

        if not entries and self._current_fs_open:
             # Handle case where FS is open but directory is empty or couldn't be read
             self.fs_status_label.setText(f"Status: Filesystem opened. Directory is empty or unreadable.")
             logger.info("Directory listing is empty.")
             # Don't show error, just empty table
             return


        self.file_listing_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            # Create items and set data
            inode_item = QTableWidgetItem(str(entry['inode']))
            name_item = QTableWidgetItem(entry['name'])
            type_item = QTableWidgetItem(entry['type'].replace('TSK_FS_META_TYPE_', '')) # Shorten type name
            mode_item = QTableWidgetItem(entry['mode'])
            size_item = QTableWidgetItem(str(entry['size']))
            mtime_item = QTableWidgetItem(entry['mtime'])
            atime_item = QTableWidgetItem(entry['atime'])
            ctime_item = QTableWidgetItem(entry['ctime'])
            crtime_item = QTableWidgetItem(entry['crtime'])
            deleted_item = QTableWidgetItem("Yes" if entry['is_deleted'] else "No")

            # Store full type and inode for navigation
            name_item.setData(Qt.ItemDataRole.UserRole, (entry['type'], entry['inode'], entry['name']))

            # Add items to table
            self.file_listing_table.setItem(row, 0, inode_item)
            self.file_listing_table.setItem(row, 1, name_item)
            self.file_listing_table.setItem(row, 2, type_item)
            self.file_listing_table.setItem(row, 3, mode_item)
            self.file_listing_table.setItem(row, 4, size_item)
            self.file_listing_table.setItem(row, 5, mtime_item)
            self.file_listing_table.setItem(row, 6, atime_item)
            self.file_listing_table.setItem(row, 7, ctime_item)
            self.file_listing_table.setItem(row, 8, crtime_item)
            self.file_listing_table.setItem(row, 9, deleted_item)

            # Visual cue for directories or deleted files (optional)
            if entry['type'] == 'TSK_FS_META_TYPE_DIR':
                 name_item.setForeground(Qt.GlobalColor.blue)
            if entry['is_deleted']:
                 for col in range(self.file_listing_table.columnCount()):
                      item = self.file_listing_table.item(row, col)
                      if item: item.setForeground(Qt.GlobalColor.gray)


        self.file_listing_table.resizeColumnsToContents()
        # Ensure name column still stretches
        self.file_listing_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.file_listing_table.setSortingEnabled(True)
        logger.info(f"Displayed {len(entries)} file entries.")
        # Update status - path needs to be tracked if implementing navigation
        # self.fs_status_label.setText(f"Status: Displaying directory: [Current Path]") # TODO: Track path


    def _file_double_clicked(self, index: QModelIndex):
        """Handles double-clicking a file/directory in the listing."""
        if not index.isValid() or not self._current_fs_open:
            return

        name_item = self.file_listing_table.item(index.row(), 1) # Name column
        item_data = name_item.data(Qt.ItemDataRole.UserRole) if name_item else None

        if not item_data:
            logger.warning("No data associated with double-clicked file item.")
            return

        file_type, inode, name = item_data

        if file_type == 'TSK_FS_META_TYPE_DIR':
             # Navigate into the directory
             # Need to handle '.' and '..' navigation correctly
             # This requires tracking the current path or inode stack

             # Basic implementation: list directory by inode
             logger.info(f"Navigating into directory: {name} (inode: {inode})")
             self.fs_status_label.setText(f"Status: Loading directory: {name}...")
             # Use the same partition/offset as before
             kwargs = {'list_path': None, 'inode': inode} # Prioritize inode
             if self._selected_partition_index is not None:
                  kwargs['partition_index'] = self._selected_partition_index
             elif self._selected_offset is not None:
                  kwargs['offset_sectors'] = self._selected_offset
             else:
                  self._show_error("Cannot navigate: No valid partition or offset selected.")
                  return

             self._start_disk_analysis(task='list_dir', **kwargs)
        else:
            # Action for regular files (e.g., view hex, extract, metadata) - Future enhancement
            logger.info(f"File double-clicked: {name} (inode: {inode}). Action TBD.")
            QMessageBox.information(self, "File Clicked", f"You clicked on file: {name}\nInode: {inode}\n\n(Further actions like viewing or extracting are not yet implemented).")


    def _show_error(self, message):
        """Displays an error message."""
        logger.error(f"Disk Tab Error: {message}")
        self.parent().window().statusBar().showMessage(f"Error: {message}", 10000)
        # Only show critical errors as popups?
        if "Failed to open" in message or "Requirement Error" in message:
            QMessageBox.critical(self, "Disk Analysis Error", message)


    def stop_analysis(self):
        """Attempts to stop the running disk analysis thread."""
        if self._disk_thread and self._disk_thread.isRunning():
            logger.info("Requesting disk worker stop...")
            if self._disk_worker: self._disk_worker.stop()
            self._disk_thread.quit()
            self._disk_thread.wait(2000)
            if self._disk_thread.isRunning():
                 logger.warning("Forcing disk thread termination.")
                 self._disk_thread.terminate()
                 self._disk_thread.wait()
            self._on_disk_analysis_finished() # Trigger cleanup


    def closeEvent(self, event):
        """Ensure threads are stopped on close."""
        self.stop_analysis()
        super().closeEvent(event)