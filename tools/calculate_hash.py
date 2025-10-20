# --- tools/calculate_hash.py ---
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

def calculate_hashes(file_path):
    """
    Calculates MD5 and SHA-256 hashes for a given file.

    Args:
        file_path (str): The path to the file.

    Returns:
        tuple: A tuple containing (md5_hash, sha256_hash) as strings.
               Returns (None, None) if the file cannot be read or doesn't exist.
    """
    if not os.path.isfile(file_path):
        logger.error(f"File not found or is not a regular file: {file_path}")
        return None, None

    md5_hasher = hashlib.md5()
    sha256_hasher = hashlib.sha256()
    buffer_size = 65536  # Read in 64k chunks

    try:
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                md5_hasher.update(data)
                sha256_hasher.update(data)
        md5_hex = md5_hasher.hexdigest()
        sha256_hex = sha256_hasher.hexdigest()
        logger.info(f"Calculated hashes for: {file_path}")
        return md5_hex, sha256_hex
    except IOError as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred during hashing {file_path}: {e}")
        return None, None