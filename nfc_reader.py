#!/usr/bin/env python3
"""
NFC Tag Reader using libnfc
Listens for NFC tags on any available USB NFC reader and prints their contents.
"""

import time
import signal
import sys
from typing import Optional, Dict, Any
import logging
import nfc


class NFCHandler:
    """Handles NFC tag operations with a ContactlessFrontend instance."""

    def __init__(self, clf: nfc.ContactlessFrontend, logger) -> None:
        """Initialize the handler with a ContactlessFrontend instance."""
        self.clf: nfc.ContactlessFrontend = clf
        self.logger = logger
        self.running = True

    def set_running(self, running: bool) -> None:
        """Set the running state."""
        self.running = running

    def close(self) -> None:
        """Close the NFC connection."""
        self.clf.close()

    def format_tag_data(self, tag: nfc.tag.Tag) -> Dict[str, Any]:
        """
        Format tag data for display.

        Args:
            tag: The NFC tag object

        Returns:
            Dict containing formatted tag information
        """
        tag_info = {
            "type": str(type(tag).__name__),
            "identifier": tag.identifier.hex() if tag.identifier else "Unknown",
            "ndef_capacity": getattr(getattr(tag, "ndef", None), "capacity", "N/A") if hasattr(tag, "ndef") and tag.ndef else "N/A",
            "ndef_length": getattr(getattr(tag, "ndef", None), "length", "N/A") if hasattr(tag, "ndef") and tag.ndef else "N/A",
        }

        # Try to read NDEF records if available
        if hasattr(tag, "ndef") and tag.ndef:
            try:
                tag_info["ndef_records"] = []
                if tag.ndef.records:
                    for record in tag.ndef.records:
                        record_info = {
                            "type": record.type,
                            "name": record.name,
                            "data": (
                                record.data
                                if len(record.data) < 100
                                else f"{record.data[:100]}... (truncated)"
                            ),
                        }
                        tag_info["ndef_records"].append(record_info)
                else:
                    tag_info["ndef_records"] = "No NDEF records found"
            except Exception as e:  # pylint: disable=broad-exception-caught
                tag_info["ndef_error"] = str(e)

        return tag_info

    def on_tag_connect(self, tag: nfc.tag.Tag) -> bool:
        """
        Callback function when a tag is detected.

        Args:
            tag: The detected NFC tag

        Returns:
            bool: False to stop listening and trigger reconnection on I/O errors
        """
        self.logger.info("=" * 50)
        self.logger.info("NFC TAG DETECTED!")
        self.logger.info("=" * 50)

        try:
            tag_data = self.format_tag_data(tag)

            print(f"Tag Type: {tag_data['type']}")
            print(f"Identifier: {tag_data['identifier']}")
            print(f"NDEF Capacity: {tag_data['ndef_capacity']}")
            print(f"NDEF Length: {tag_data['ndef_length']}")

            if "ndef_records" in tag_data:
                print("\nNDEF Records:")
                if isinstance(tag_data["ndef_records"], list):
                    for i, record in enumerate(tag_data["ndef_records"]):
                        print(f"  Record {i + 1}:")
                        print(f"    Type: {record['type']}")
                        print(f"    Name: {record['name']}")
                        print(f"    Data: {record['data']}")
                else:
                    print(f"  {tag_data['ndef_records']}")

            if "ndef_error" in tag_data:
                print(f"\nNDEF Error: {tag_data['ndef_error']}")

        except (OSError, IOError) as e:
            self.logger.error("I/O error reading tag: %s", e)
            self.logger.info("Tag read caused I/O error, will reconnect...")
            return False  # Stop listening to trigger reconnection

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Error reading tag: %s", e)

        print("\n" + "=" * 50)
        print("Waiting for next tag...")
        print("=" * 50 + "\n")

        return True  # Keep listening for more tags

    def listen_for_tags(self) -> None:
        """Listen for NFC tags continuously."""
        error_count = 0
        max_errors = 10  # Maximum consecutive errors before reconnecting

        try:
            while self.running:
                try:
                    # Use a timer to detect if we're stuck in error loops
                    start_time = time.time()
                    connection_result = self.clf.connect(
                        rdwr={"on-connect": self.on_tag_connect},
                        terminate=lambda: not self.running,
                    )

                    # If connect call returns quickly, it might be an error loop
                    elapsed = time.time() - start_time
                    if elapsed < 0.5:  # Returned too quickly
                        error_count += 1
                        if error_count >= max_errors:
                            self.logger.warning(
                                f"Detected {error_count} quick returns, forcing reconnection...")
                            raise OSError(
                                "Forced reconnection due to error loop")
                    else:
                        error_count = 0  # Reset counter on successful operation

                    # If connection returns False, it may indicate an error
                    if connection_result is False:
                        self.logger.warning(
                            "Connection returned False, may indicate communication issues")
                        time.sleep(1)  # Brief pause before continuing
                    if not self.running:
                        break
                    time.sleep(0.1)  # Small delay to prevent busy waiting

                except (OSError, IOError) as e:
                    self.logger.error("I/O error during tag scanning: %s", e)
                    raise  # Re-raise to trigger reconnection in parent

                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.error(
                        "Unexpected error during tag listening: %s", e)
                    time.sleep(1)  # Brief pause before continuing

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Fatal error during tag listening: %s", e)
            raise


class NFCReader:
    """NFC Reader class to handle tag detection and reading."""

    def __init__(self) -> None:
        """Initialize the NFC reader."""
        self.running: bool = True
        self.nfc_handler: Optional[NFCHandler] = None
        self.setup_logging()

    def setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def signal_handler(self, _signum: int, _frame: Any) -> None:
        """Handle interrupt signals for graceful shutdown."""
        self.logger.info("Received interrupt signal. Shutting down...")
        self.running = False
        if self.nfc_handler:
            self.nfc_handler.set_running(False)
            self.nfc_handler.close()
        sys.exit(0)

    def connect_reader(self) -> bool:
        """
        Connect to an available NFC reader and create handler.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.logger.info("Searching for NFC readers...")
            clf = nfc.ContactlessFrontend("usb")
            if clf:
                self.logger.info("Connected to NFC reader: %s", clf)
                self.nfc_handler = NFCHandler(clf, self.logger)
                self.nfc_handler.set_running(self.running)
                return True
            self.logger.error("No NFC readers found")
            return False
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to connect to NFC reader: %s", e)
            return False

    def start_listening(self) -> None:
        """Start listening for NFC tags."""
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        # Keep trying to connect until successful or interrupted
        while self.running and not self.connect_reader():
            self.logger.warning(
                "Could not connect to NFC reader. Retrying in 5 seconds...")
            time.sleep(5)

        self.logger.info("NFC Reader started. Listening for tags...")
        self.logger.info("Press Ctrl+C to stop")

        try:
            while self.running:
                try:
                    if self.nfc_handler:
                        self.nfc_handler.listen_for_tags()
                    if not self.running:
                        break
                    time.sleep(0.1)  # Small delay to prevent busy waiting

                except (OSError, IOError) as e:
                    self.logger.error("I/O error during tag scanning: %s", e)
                    self.logger.info(
                        "Attempting to reconnect to NFC reader...")

                    # Close current connection and try to reconnect
                    if self.nfc_handler:
                        try:
                            self.nfc_handler.close()
                        except Exception:
                            pass
                        self.nfc_handler = None

                    # Wait before reconnecting
                    time.sleep(2)

                    # Try to reconnect
                    if not self.connect_reader():
                        self.logger.error(
                            "Failed to reconnect. Waiting 5 seconds before retry...")
                        time.sleep(5)
                        continue

                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.error(
                        "Unexpected error during tag listening: %s", e)
                    time.sleep(1)  # Brief pause before continuing

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Fatal error during tag listening: %s", e)
        finally:
            if self.nfc_handler:
                self.nfc_handler.close()
                self.logger.info("NFC reader connection closed")


def main() -> None:
    """Main function to start the NFC reader."""
    print("NFC Tag Reader")
    print("=" * 50)
    print("This program will listen for NFC tags and display their contents.")
    print("Make sure your NFC reader is connected via USB.")
    print("=" * 50 + "\n")

    reader = NFCReader()
    reader.start_listening()


if __name__ == "__main__":
    main()
