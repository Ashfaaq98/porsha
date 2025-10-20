# --- tools/extract_metadata.py ---
import logging
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def get_metadata(file_path):
    """
    Extracts metadata from a file using Hachoir.

    Args:
        file_path (str): The path to the file.

    Returns:
        dict: A dictionary containing extracted metadata key-value pairs.
              Returns an empty dictionary if metadata cannot be extracted or
              an error occurs. Keys are made more readable.
              Returns {'Error': error_message} if parsing fails.
    """
    metadata_dict = {}
    parser = None
    try:
        logger.info(f"Attempting to extract metadata from: {file_path}")
        parser = createParser(file_path)
        if not parser:
            logger.warning(f"Hachoir could not create a parser for: {file_path}")
            return {"Error": "Unable to create parser for this file type."}

        with parser:
            metadata = extractMetadata(parser)

        if not metadata:
            logger.warning(f"Hachoir could not extract metadata from: {file_path}")
            return {"Info": "No metadata could be extracted."}

        for item in sorted(metadata):
            if not item.values:
                continue

            # Simplify key and format value
            key = item.key.replace('-', ' ').replace('_', ' ').title()
            value = item.display_value

            # Special handling for date/time to ensure consistent format
            if isinstance(value, datetime):
                 # Ensure timezone awareness (assume naive is local, convert to UTC for display consistency)
                if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
                    try:
                        # Attempt to treat as local time and convert to UTC
                        value = value.astimezone(timezone.utc)
                    except Exception: # Handle potential errors if it's already timezone-aware in a weird way
                         pass # Keep original value
                value = value.strftime('%Y-%m-%d %H:%M:%S %Z') # ISO-like format

            metadata_dict[key] = str(value) # Ensure all values are strings for display

        logger.info(f"Successfully extracted metadata from: {file_path}")
        return metadata_dict

    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return {"Error": "File not found."}
    except Exception as e:
        logger.error(f"Error extracting metadata for {file_path}: {e}", exc_info=True)
        # Provide a more user-friendly error message
        err_msg = f"An error occurred: {type(e).__name__}"
        if parser and hasattr(parser, 'error_message') and parser.error_message:
             err_msg += f" - Parser detail: {parser.error_message}"
        return {"Error": err_msg}