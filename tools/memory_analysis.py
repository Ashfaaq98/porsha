# --- tools/memory_analysis.py ---
import logging
import os
import sys
from typing import List, Dict, Any, Optional, Tuple

# Setup Volatility 3 environment
# Make sure volatility3 library is installed and accessible
# This might involve ensuring the volatility3 directory (if installed from source)
# or the site-packages directory is in sys.path, but usually pip handles this.

# IMPORTANT: Volatility 3 dynamically loads plugins. Importing specific plugins
# directly might not always work as expected or might bypass necessary setup.
# It's generally better to rely on the framework finding them.

# Attempt to import necessary Volatility 3 components
try:
    from volatility3.framework import contexts, automagic, plugins, interfaces
    from volatility3.framework.configuration import requirements
    from volatility3.cli import PrintedProgress, MutedProgress # For progress feedback
    from volatility3.framework.renderers import format_hints
    HAS_VOLATILITY = True
except ImportError as e:
    logging.error(f"Failed to import volatility3 components: {e}. Is volatility3 installed correctly?", exc_info=True)
    HAS_VOLATILITY = False
    # Define dummy classes/functions if volatility isn't available to avoid runtime errors later
    class DummyContext: pass
    class DummyPluginInterface: pass
    class DummyAutomagic: pass
    contexts = None
    automagic = None
    plugins = None
    interfaces = None
    requirements = None
    PrintedProgress = MutedProgress = None # type: ignore
    format_hints = None


logger = logging.getLogger(__name__)

# --- Volatility 3 Plugin List ---
# Keep a list of commonly used plugins we want to expose in the GUI
# Format: "Plugin Name for GUI": "volatility3.plugin.full.path"
# This allows finding the class later using volatility3.framework.class_subclasses
# Example: Fetching all plugins might be too much initially.
SUPPORTED_PLUGINS = {
    # Windows
    "Windows Process List (pslist)": "volatility3.plugins.windows.pslist.PsList",
    "Windows Network Connections (netscan)": "volatility3.plugins.windows.netscan.NetScan",
    "Windows Command Line": "volatility3.plugins.windows.cmdline.CmdLine",
    "Windows Registry Hives": "volatility3.plugins.windows.registry.hivelist.HiveList",
    "Windows Services": "volatility3.plugins.windows.svcscan.SvcScan",
    "Windows Running Drivers": "volatility3.plugins.windows.modules.Modules",
    # Linux
    "Linux Process List (pslist)": "volatility3.plugins.linux.pslist.PsList",
    "Linux Network Connections (netstat)": "volatility3.plugins.linux.sockstat.SockStat", # Note: Vol3 uses sockstat
    "Linux Mounts": "volatility3.plugins.linux.mountinfo.MountInfo",
    "Linux Loaded Modules (lsmod)": "volatility3.plugins.linux.lsmod.LsMod",
    # Mac
    "Mac Process List (pslist)": "volatility3.plugins.mac.pslist.PsList",
    "Mac Network Connections (netstat)": "volatility3.plugins.mac.netstat.NetStat",
    "Mac Mounts": "volatility3.plugins.mac.mount.Mount",
    "Mac Loaded Modules (lsmod)": "volatility3.plugins.mac.lsmod.LsMod",
    # Framework/Generic (less common for direct GUI use initially)
    # "Framework Info": "volatility3.plugins.frameworkinfo.FrameworkInfo",
}


def get_volatility_context(memory_image_path: str) -> Optional[interfaces.context.ContextInterface]:
    """
    Creates and initializes a Volatility 3 context.

    Args:
        memory_image_path: Path to the memory image file.

    Returns:
        A configured Volatility 3 context object, or None on failure.
    """
    if not HAS_VOLATILITY:
        logger.error("Volatility 3 library is not available.")
        return None
    if not os.path.exists(memory_image_path):
        logger.error(f"Memory image file not found: {memory_image_path}")
        return None

    try:
        ctx = contexts.Context()  # Create a new context
        ctx.config['automagic.general.single_location'] = f"file://{os.path.abspath(memory_image_path)}"
        # Disable banner for library use unless debugging
        # ctx.config['plugins.banners.Banner.banner'] = False # Doesn't seem to work this way easily
        logger.info(f"Volatility context created for: {memory_image_path}")
        return ctx
    except Exception as e:
        logger.error(f"Failed to create Volatility context: {e}", exc_info=True)
        return None

def run_volatility_plugin(
    context: interfaces.context.ContextInterface,
    plugin_name: str,
    plugin_options: Optional[Dict[str, Any]] = None,
    show_progress: bool = True
) -> Tuple[Optional[interfaces.renderers.TreeGrid], Optional[str]]:
    """
    Runs the Automagic setup and executes a specific Volatility 3 plugin.

    Args:
        context: The initialized Volatility 3 context.
        plugin_name: The full class name of the plugin (e.g., "volatility3.plugins.windows.pslist.PsList").
        plugin_options: Optional dictionary of plugin-specific options (e.g., {'pid': [1234]}).
        show_progress: Whether to use PrintedProgress (True) or MutedProgress (False).

    Returns:
        A tuple containing:
        - The result TreeGrid object if successful, None otherwise.
        - An error message string if failed, None otherwise.
    """
    if not HAS_VOLATILITY:
        return None, "Volatility 3 library is not available."
    if not context:
        return None, "Invalid Volatility context provided."

    plugin_class = None
    try:
        # Find the plugin class from its name
        available_plugins = {f"{p.__module__}.{p.__name__}": p for p in interfaces.plugins.PluginInterface.get_plugin_classes()}
        if plugin_name not in available_plugins:
             # Fallback: try searching subclasses if direct lookup fails (might happen with custom plugins)
            all_classes = list(interfaces.plugins.PluginInterface.class_subclasses(True))
            found = False
            for cls in all_classes:
                 full_name = f"{cls.__module__}.{cls.__name__}"
                 if full_name == plugin_name:
                      plugin_class = cls
                      found = True
                      break
            if not found:
                 logger.error(f"Plugin class not found: {plugin_name}")
                 return None, f"Plugin '{plugin_name}' not found or registered."
        else:
            plugin_class = available_plugins[plugin_name]

        if plugin_class is None: # Should not happen if logic above is correct
             return None, f"Could not locate plugin class for '{plugin_name}'"

        logger.info(f"Running Volatility plugin: {plugin_name} with options: {plugin_options}")

        # --- Automagic Setup ---
        # Determine the progress class
        progress_class = PrintedProgress if show_progress and PrintedProgress else MutedProgress
        if progress_class is None: # Safety check if even MutedProgress failed import
             progress_callback = None
             logger.warning("No progress callback available.")
        else:
             progress_callback = progress_class()

        # Run automagic components (e.g., Layer stacking, OS detection, Symbol finding)
        # We need to run the automagic relevant to the *plugin* to ensure its requirements are met
        chosen_automagics = automagic.available(context) # Get all available automagic modules
        plugin_automagic = automagic.choose_automagic(chosen_automagics, plugin_class) # Find the right one

        logger.info(f"Running automagic: {plugin_automagic.__class__.__name__}")
        plugin_automagic.run(progress_callback) # Setup layers, find symbols etc.

        # Check if the primary layer (memory image) is present
        if requirements.TranslationLayerRequirement.primary_layer_name not in context.layers:
             raise ValueError(f"Primary memory layer '{requirements.TranslationLayerRequirement.primary_layer_name}' not found after automagic. Check image format/path.")
             
        # Check if a kernel symbol table was found (usually needed)
        if requirements.SymbolTableRequirement.primary_symbol_table_name not in context.symbol_space:
             # Not always fatal, some plugins might work without kernel symbols, but most won't.
             logger.warning(f"Primary symbol table '{requirements.SymbolTableRequirement.primary_symbol_table_name}' not found after automagic. Plugin may fail.")
             # Consider making this an error depending on strictness needed.
             # return None, "Kernel symbols not found. Cannot proceed."


        # --- Plugin Execution ---
        # Construct the plugin configuration path (used internally by Volatility)
        plugin_config_path = interfaces.configuration.path_join('plugins', plugin_class.__name__)

        # Add any plugin-specific options to the context configuration
        if plugin_options:
            for key, value in plugin_options.items():
                context.config[interfaces.configuration.path_join(plugin_config_path, key)] = value

        # Instantiate and run the plugin
        constructed_plugin = plugin_class(context=context,
                                          config_path=plugin_config_path,
                                          progress_callback=progress_callback)

        result_grid = constructed_plugin.run()
        logger.info(f"Plugin {plugin_name} finished execution.")
        return result_grid, None

    except requirements.RequirementError as e:
        err_msg = f"Requirement Error for {plugin_name}: {e}. Check image/profile."
        logger.error(err_msg, exc_info=True)
        return None, err_msg
    except Exception as e:
        err_msg = f"Error running plugin {plugin_name}: {type(e).__name__}: {e}"
        logger.error(err_msg, exc_info=True)
        # Attempt to get more specific error details from Volatility exceptions if possible
        if hasattr(e, 'message'): err_msg += f" - Details: {getattr(e, 'message')}"
        return None, err_msg


def treegrid_to_list(grid: interfaces.renderers.TreeGrid) -> Tuple[List[str], List[List[Any]]]:
    """
    Converts a Volatility TreeGrid object into a list of headers and list of rows.

    Args:
        grid: The TreeGrid object returned by a plugin's run() method.

    Returns:
        A tuple containing:
        - list[str]: The column headers.
        - list[list[Any]]: A list where each inner list represents a row of data.
                           Values are formatted based on their type hints.
    """
    if not HAS_VOLATILITY or grid is None:
        return [], []

    headers = [col.name for col in grid.columns]
    all_rows_data = []

    def format_value(value):
        """Format values based on type hints for better display."""
        if isinstance(value, interfaces.renderers.BaseAbsentValue):
            return "N/A" # Or "" or "Absent"
        elif isinstance(value, format_hints.Hex):
            return hex(value)
        elif isinstance(value, format_hints.HexBytes):
             # Limit length of hex bytes dump for table display
             MAX_HEX_DISPLAY = 32
             hex_str = value.hex()
             if len(hex_str) > MAX_HEX_DISPLAY * 2:
                 return "0x" + hex_str[:MAX_HEX_DISPLAY*2] + "..."
             return "0x" + hex_str
        elif isinstance(value, int):
            return value # Keep ints as ints for potential sorting
        elif isinstance(value, datetime): # Handle datetime objects if plugins return them
             return value.strftime('%Y-%m-%d %H:%M:%S')
        # Add more formatting as needed (e.g., for specific object types)
        # Fallback to string representation
        return str(value)


    def process_node(node, parent_prefix=""):
        """Recursively processes nodes in the TreeGrid."""
        # Get data for the current node
        row_data = [format_value(grid.values(node, col_index)) for col_index, _ in enumerate(grid.columns)]

        # Optional: Add indentation based on tree depth if needed for display
        # indent = "    " * node.path_depth
        # row_data[0] = indent + str(row_data[0]) # Assuming first column is primary identifier

        all_rows_data.append(row_data)

        # Recursively process children
        for child_node in grid.children(node):
            process_node(child_node) # Pass parent info if needed for prefixing

    # Start processing from the root nodes
    for root_node in grid.roots:
        process_node(root_node)

    return headers, all_rows_data