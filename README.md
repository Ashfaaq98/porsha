<p align="center">
  <img src="./assets/images/Porsha_Banner.png" alt="Porsha Digital Forensics Toolkit Banner" width="700" height="450">
</p>


# Porsha Digital Forensics Toolkit

Porsha is a foundational, graphical digital forensics toolkit designed to provide a user-friendly interface for common forensic tasks. It leverages standard open-source Python libraries for backend processing and PyQt6 for the graphical user interface.

**Note:** This version focuses on Disk Analysis, Network Analysis, and File Utilities (Hashing, Metadata). Memory analysis features are not included in this build.

## Features

* **Graphical User Interface:** Built with PyQt6, providing a tabbed interface for different analysis types.
* **Disk Analysis:**
    * Open and parse raw disk images (`.dd`, `.raw`, `.img`).
    * Display volume/partition information using `pytsk3`.
    * Browse filesystem structures within supported partitions (FAT, NTFS, etc.).
    * List files and directories with metadata (name, size, timestamps, deleted status).
* **Network Analysis:**
    * Analyze PCAP files (`.pcap`, `.pcapng`).
    * Display summary information (packet count, start/end times) using `scapy`.
    * List unique network conversations (IP/TCP/UDP).
* **Utilities:**
    * **Hashing:** Calculate MD5 and SHA-256 hashes for any selected file using `hashlib`.
    * **Metadata Extraction:** Extract metadata from various file types (images, documents, etc.) using `hachoir`.
* **Responsive Interface:** Long-running analysis tasks are performed in background threads (`QThread`) to keep the GUI responsive.
* **Logging:** Actions and errors are logged to `porsha_toolkit.log` and the console.

## Requirements

* **Python:** Python 3.8 or higher.
* **Operating System:** Linux, macOS, or Windows. Note that installation requirements for `pytsk3` vary by OS.
* **Core Dependencies:**
    * `PyQt6`: For the graphical user interface.
    * `pytsk3`: For disk image analysis.
    * `scapy`: For network packet analysis.
    * `hachoir`: For metadata extraction.
* **(Potential) System Libraries:** `pytsk3` often requires the underlying Sleuth Kit development libraries to be installed:
    * **Debian/Ubuntu:** `sudo apt-get update && sudo apt-get install python3-dev libtsk-dev`
    * **Fedora/CentOS/RHEL:** `sudo dnf install python3-devel libtsk-devel`
    * **macOS (Homebrew):** `brew install tsk`
    * **Windows:** May require specific pre-compiled wheels or build tools. Refer to `pytsk3` documentation.

## Installation

It is highly recommended to use a Python virtual environment.

1.  **Clone the Repository (or download the source code):**
    ```bash
    git clone [https://github.com/ashfaaq98/porsha.git](https://github.com/ashfaaq98/porsha.git) 
    cd porsha
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    # Create
    python -m venv myenv
    # Activate (Linux/macOS)
    source myenv/bin/activate
    # Activate (Windows CMD)
    # myenv\Scripts\activate.bat
    # Activate (Windows PowerShell - might need policy adjustment)
    # myenv\Scripts\Activate.ps1
    ```
    Your terminal prompt should now start with `(myenv)`.

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    Ensure any system-level libraries (like `libtsk-dev`) are installed *before* running this command if needed for `pytsk3`.

## Usage

1.  **Activate Virtual Environment:** If not already active, navigate to the project directory and activate the environment (`source myenv/bin/activate` or similar).
2.  **Run the Application:**
    ```bash
    python run.py
    ```
3.  **Using the Interface:**
    * The application will open with several tabs:
        * **Disk Analysis:** Use "Browse..." to select a raw disk image file. Volumes/partitions will be listed. Double-click a volume to attempt opening its filesystem and browse files/directories in the lower panel.
        * **Network Analysis:** Use "Browse..." to select a PCAP file. Click "Analyze" to view summary information and a list of network conversations found in the capture.
        * **Utilities (Hash/Meta):** Use "Browse..." to select any file. Click "Calculate Hashes" or "Extract Metadata" to perform the respective action on the selected file.
    * The status bar at the bottom will show progress updates and completion messages.
    * Check the console or `porsha_toolkit.log` for detailed logs and error messages.

## Dependencies

This toolkit relies on the following core libraries:

* [PyQt6](https://riverbankcomputing.com/software/pyqt/): GUI Framework
* [pytsk3](https://github.com/py4n6/pytsk): Disk Image Analysis (The Sleuth Kit bindings)
* [Scapy](https://scapy.net/): Network Packet Manipulation and Analysis
* [Hachoir](https://hachoir.readthedocs.io/): File Metadata Extraction


## License

This project is licensed under the MIT License - see the LICENSE file for details. 