"""SD card file operations wrapper.

Wraps BambuPrinter FTP/SD methods with error handling and
routes operations through the PrinterManager.
"""

import logging

_logger = logging.getLogger("octoprint.plugins.bambuboard.file_manager")


class FileManager:
    """Wraps SD card operations for managed printers."""

    def __init__(self, printer_manager):
        self._pm = printer_manager

    def _get_instance(self, printer_id: str):
        managed = self._pm.get_printer(printer_id)
        if managed is None:
            raise ValueError(f"Printer {printer_id} not found")
        if not managed.connected:
            raise ConnectionError(f"Printer {managed.name} is not connected")
        return managed.instance

    def get_contents(self, printer_id: str) -> dict:
        """Get all SD card file/folder contents."""
        instance = self._get_instance(printer_id)
        try:
            return instance.get_sdcard_contents()
        except Exception as e:
            _logger.exception("Failed to list SD card for %s", printer_id)
            raise RuntimeError(f"Failed to list files: {e}") from e

    def get_3mf_files(self, printer_id: str) -> dict:
        """Get only .3mf files from SD card."""
        instance = self._get_instance(printer_id)
        try:
            return instance.get_sdcard_3mf_files()
        except Exception as e:
            _logger.exception("Failed to list 3mf files for %s", printer_id)
            raise RuntimeError(f"Failed to list 3mf files: {e}") from e

    def upload_file(self, printer_id: str, local_path: str, remote_path: str):
        """Upload a file from local filesystem to printer SD card."""
        instance = self._get_instance(printer_id)
        try:
            instance.upload_sdcard_file(local_path, remote_path)
        except Exception as e:
            _logger.exception("Failed to upload file to %s", printer_id)
            raise RuntimeError(f"Upload failed: {e}") from e

    def download_file(self, printer_id: str, remote_path: str, local_path: str):
        """Download a file from printer SD card to local filesystem."""
        instance = self._get_instance(printer_id)
        try:
            instance.download_sdcard_file(remote_path, local_path)
        except Exception as e:
            _logger.exception("Failed to download file from %s", printer_id)
            raise RuntimeError(f"Download failed: {e}") from e

    def delete_file(self, printer_id: str, path: str):
        """Delete a file from printer SD card."""
        instance = self._get_instance(printer_id)
        try:
            instance.delete_sdcard_file(path)
        except Exception as e:
            _logger.exception("Failed to delete file on %s", printer_id)
            raise RuntimeError(f"Delete failed: {e}") from e

    def make_directory(self, printer_id: str, path: str):
        """Create a directory on printer SD card."""
        instance = self._get_instance(printer_id)
        try:
            instance.make_sdcard_directory(path)
        except Exception as e:
            _logger.exception("Failed to create directory on %s", printer_id)
            raise RuntimeError(f"Create directory failed: {e}") from e
