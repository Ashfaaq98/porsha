# --- tools/disk_analysis.py ---
import pytsk3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DiskImageHandler:
    """Handles opening and interacting with a disk image using pytsk3."""

    def __init__(self, image_path):
        """
        Initializes the handler and attempts to open the image.

        Args:
            image_path (str): Path to the disk image file.

        Raises:
            IOError: If the image cannot be opened by pytsk3.
            AttributeError: If the image path is invalid.
        """
        self.image_path = image_path
        self.img_info = None
        self.volume_info = None
        self.fs_info = None
        self.partition_offset = None # Store offset for opening FS

        try:
            self.img_info = pytsk3.Img_Info(url=image_path)
            logger.info(f"Successfully opened disk image: {image_path}")
        except IOError as e:
            logger.error(f"Failed to open disk image {image_path}: {e}")
            raise
        except AttributeError as e:
             logger.error(f"Invalid image path or pytsk3 issue: {e}")
             raise


    def get_volume_info(self):
        """
        Retrieves volume/partition information from the image.

        Returns:
            list: A list of dictionaries, each representing a partition/volume.
                  Keys include 'slot', 'desc', 'start_sector', 'num_sectors', 'flags'.
                  Returns an empty list if no volume system is found or an error occurs.
        """
        volumes = []
        try:
            self.volume_info = pytsk3.Volume_Info(self.img_info)
            logger.info("Volume system detected.")
            for part in self.volume_info:
                volumes.append({
                    'slot': part.addr,
                    'desc': part.desc.decode('utf-8', errors='replace') if part.desc else 'N/A',
                    'start_sector': part.start,
                    'num_sectors': part.len,
                    'flags': str(part.flags) # e.g., pytsk3.TSK_VS_PART_FLAG_ALLOC
                })
            logger.info(f"Found {len(volumes)} volumes/partitions.")
        except IOError as e:
            # This error often means no volume system (like analyzing a single partition dump)
            logger.warning(f"Could not detect a volume system in {self.image_path}. May be a single partition/FS image. Error: {e}")
            # Treat the entire image as a single potential filesystem source
            volumes.append({
                 'slot': 0,
                 'desc': 'Potential Filesystem (No Partition Table)',
                 'start_sector': 0,
                 'num_sectors': self.img_info.get_size() // self.img_info.get_block_size(), # Approx sector count
                 'flags': 'N/A'
            })
        except Exception as e:
            logger.error(f"Error getting volume info from {self.image_path}: {e}", exc_info=True)
            return [] # Return empty list on other errors
        return volumes

    def open_filesystem(self, partition_index=None, offset_sectors=None):
        """
        Opens the filesystem within a specific partition or at a given offset.

        Args:
            partition_index (int, optional): The index (slot number) of the partition from get_volume_info().
            offset_sectors (int, optional): The starting sector offset of the filesystem.
                                            Use this if no partition table or for manual specification.
                                            Exactly one of partition_index or offset_sectors must be provided.

        Returns:
            bool: True if the filesystem was opened successfully, False otherwise.
        """
        self.fs_info = None
        self.partition_offset = None

        if partition_index is not None and offset_sectors is not None:
             logger.error("Provide either partition_index or offset_sectors, not both.")
             return False
        if partition_index is None and offset_sectors is None:
             logger.error("Must provide either partition_index or offset_sectors.")
             return False

        try:
            if partition_index is not None:
                if not self.volume_info:
                    logger.error("Volume info not available, cannot open by partition index.")
                    return False
                part = self.volume_info.get_part_by_addr(partition_index)
                if not part:
                    logger.error(f"Partition index {partition_index} not found.")
                    return False
                self.partition_offset = part.start * self.volume_info.block_size # Offset in bytes
                logger.info(f"Attempting to open filesystem in partition {partition_index} at offset {self.partition_offset} bytes.")

            elif offset_sectors is not None:
                 # Assume 512 byte sectors if not explicitly known from volume_info
                 sector_size = getattr(self.volume_info, 'block_size', 512) # Use default if no volume
                 self.partition_offset = offset_sectors * sector_size
                 logger.info(f"Attempting to open filesystem at manual offset {self.partition_offset} bytes.")

            # Open the filesystem
            self.fs_info = pytsk3.FS_Info(self.img_info, offset=self.partition_offset)
            fs_type = self.fs_info.info.ftype
            logger.info(f"Successfully opened filesystem. Type: {pytsk3.TSK_FS_TYPE_ENUM(fs_type).name}")
            return True

        except IOError as e:
            logger.error(f"Failed to open filesystem at offset {self.partition_offset}: {e}. May be unsupported FS type or corrupt.")
            self.fs_info = None
            self.partition_offset = None
            return False
        except Exception as e:
            logger.error(f"Unexpected error opening filesystem: {e}", exc_info=True)
            self.fs_info = None
            self.partition_offset = None
            return False

    def list_directory(self, path="/", inode=None):
        """
        Lists files and directories within the currently opened filesystem.

        Args:
            path (str): The directory path to list (e.g., "/users/"). Default is root "/".
            inode (int, optional): The inode number of the directory. If provided, path is ignored.

        Returns:
            list: A list of dictionaries, each representing a file/directory entry.
                  Keys: 'inode', 'name', 'type', 'mode', 'size', 'mtime', 'atime', 'ctime', 'crtime', 'is_deleted'
                  Returns an empty list if the filesystem is not open or the directory is not found/readable.
        """
        if not self.fs_info:
            logger.error("Filesystem not open. Call open_filesystem first.")
            return []

        entries = []
        try:
            if inode is not None:
                directory = self.fs_info.open_dir(inode=inode)
                logger.info(f"Listing directory by inode: {inode}")
            else:
                directory = self.fs_info.open_dir(path=path)
                logger.info(f"Listing directory by path: {path}")

            for f in directory:
                # Skip special '.' and '..' entries unless it's the root inode
                if f.info.name.name in (b".", b"..") and directory.info.fs_file.meta.addr != self.fs_info.info.root_inum:
                    continue
                # Skip virtual $MBR, $FAT etc. if desired (can be noisy)
                if f.info.name.name.startswith(b"$"):
                     continue

                name = f.info.name.name.decode('utf-8', errors='replace')
                file_type = f.info.meta.type
                mode = f.info.meta.mode
                is_deleted = f.info.name.flags & pytsk3.TSK_FS_NAME_FLAG_UNALLOC != 0

                entry = {
                    'inode': f.info.meta.addr,
                    'name': name,
                    'type': pytsk3.TSK_FS_META_TYPE_ENUM(file_type).name, # DIR, REG, LNK etc.
                    'mode': oct(mode) if mode else 'N/A', # Permissions
                    'size': f.info.meta.size,
                    'mtime': self._format_timestamp(f.info.meta.mtime),
                    'atime': self._format_timestamp(f.info.meta.atime),
                    'ctime': self._format_timestamp(f.info.meta.ctime),
                    'crtime': self._format_timestamp(f.info.meta.crtime),
                    'is_deleted': is_deleted
                }
                entries.append(entry)

            logger.info(f"Found {len(entries)} entries in directory.")
            # Sort entries: directories first, then by name
            entries.sort(key=lambda x: (x['type'] != 'TSK_FS_META_TYPE_DIR', x['name'].lower()))
            return entries

        except IOError as e:
            logger.error(f"Error listing directory (inode={inode}, path={path}): {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing directory: {e}", exc_info=True)
            return []

    def _format_timestamp(self, ts):
        """Formats a Unix timestamp into a readable string."""
        if not ts or ts == 0:
            return "N/A"
        try:
            # TSK timestamps are Unix epoch time
            return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OSError): # Handle potential invalid timestamps
             logger.warning(f"Invalid timestamp encountered: {ts}")
             return "Invalid Date"

    def close(self):
        """Closes the image info object if it's open."""
        # Note: pytsk3 FS_Info and Volume_Info don't have explicit close methods.
        # Closing the Img_Info is the primary cleanup action.
        if self.img_info:
            # There isn't an explicit close method in the documented API for Img_Info
            # Garbage collection should handle it, but setting to None helps.
            self.img_info = None
            self.volume_info = None
            self.fs_info = None
            logger.info(f"Closed image reference for: {self.image_path}")