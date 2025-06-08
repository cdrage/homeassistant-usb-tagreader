#!/usr/bin/env python3
"""
NFC Tag Reader using PCSC
Listens for NFC tags on any available USB NFC reader and prints their contents.
"""

import time
import signal
import sys
from typing import Optional, Dict, Any, Tuple, List
import logging
from smartcard.System import readers
from smartcard.CardConnection import CardConnection
from smartcard.util import toHexString, toBytes


class NFCHandler:
    """Handles NFC tag operations with PCSC."""

    # PCSC constants
    INS_READ = 0xB0
    NDEF_TAG = 0x03
    
    def __init__(self, connection: CardConnection, logger) -> None:
        """Initialize the handler with a PCSC connection."""
        self.connection = connection
        self.logger = logger
        self.running = True

    def set_running(self, running: bool) -> None:
        """Set the running state."""
        self.running = running

    def close(self) -> None:
        """Close the PCSC connection."""
        try:
            self.connection.disconnect()
        except Exception as e:
            self.logger.debug(f"Error closing connection: {e}")

    def _send_apdu(self, apdu: List[int]) -> Tuple[List[int], int, int]:
        """Send APDU command and return response."""
        try:
            response, sw1, sw2 = self.connection.transmit(apdu)
            return response, sw1, sw2
        except Exception as e:
            self.logger.error(f"APDU transmission error: {e}")
            raise

    def read_t2_ndef(self) -> Tuple[Optional[str], Optional[bytes]]:
        """
        Read NDEF data from Type 2 tag.
        
        Returns:
            Tuple of (error_message, ndef_data)
        """
        try:
            # Read capabilities container (CC) from block 3
            response, sw1, sw2 = self._send_apdu([0xff, self.INS_READ, 0x00, 0x03, 4])
            
            if sw1 != 0x90 or sw2 != 0x00:
                return f"Failed to read CC: {sw1:02x}{sw2:02x}", None
                
            if len(response) < 4:
                return "Invalid CC response length", None
                
            # Extract data area size from CC
            data_area_size = response[2] * 8
            max_ndef_size = data_area_size - 2
            
            self.logger.info(f"Data area size: {data_area_size}, Max NDEF size: {max_ndef_size}")
            
            # Start reading from block 4 (NDEF data area)
            ndef_data = bytearray()
            block_offset = 4
            
            # Read first block to get NDEF TLV
            response, sw1, sw2 = self._send_apdu([0xff, self.INS_READ, 0x00, block_offset, 4])
            
            if sw1 != 0x90 or sw2 != 0x00:
                return f"Failed to read NDEF TLV: {sw1:02x}{sw2:02x}", None
                
            if len(response) < 2:
                return "Invalid NDEF TLV response", None
                
            # Check for NDEF TLV tag
            if response[0] != self.NDEF_TAG:
                return f"No NDEF tag found, got: 0x{response[0]:02x}", None
                
            ndef_length = response[1]
            self.logger.info(f"NDEF message length: {ndef_length}")
            
            if ndef_length == 0:
                return None, b""  # Empty NDEF message
                
            # Read NDEF data starting from position 2 in the first block
            bytes_read = 0
            remaining_in_block = min(2, ndef_length)  # Max 2 bytes from first block
            
            if remaining_in_block > 0:
                ndef_data.extend(response[2:2 + remaining_in_block])
                bytes_read += remaining_in_block
            
            # Read additional blocks if needed
            block_offset += 1
            while bytes_read < ndef_length and block_offset < 256:
                response, sw1, sw2 = self._send_apdu([0xff, self.INS_READ, 0x00, block_offset, 4])
                
                if sw1 != 0x90 or sw2 != 0x00:
                    return f"Failed to read block {block_offset}: {sw1:02x}{sw2:02x}", None
                    
                remaining_bytes = ndef_length - bytes_read
                bytes_to_copy = min(4, remaining_bytes)
                
                ndef_data.extend(response[:bytes_to_copy])
                bytes_read += bytes_to_copy
                block_offset += 1
                
            return None, bytes(ndef_data)
            
        except Exception as e:
            return f"Exception during NDEF read: {e}", None

    def format_tag_data(self, atr: List[int]) -> Dict[str, Any]:
        """
        Format tag data for display.

        Args:
            atr: Answer to Reset from the card

        Returns:
            Dict containing formatted tag information
        """
        tag_info = {
            "type": "Type 2 (assumed)",
            "atr": toHexString(atr),
        }

        # Try to read NDEF data
        try:
            error_msg, ndef_data = self.read_t2_ndef()
            
            if error_msg:
                tag_info["ndef_error"] = error_msg
            elif ndef_data is not None:
                tag_info["ndef_length"] = len(ndef_data)
                tag_info["ndef_data_hex"] = ndef_data.hex()
                
                # Try to decode as text if it looks like a text record
                if len(ndef_data) > 3:
                    try:
                        # Simple text record detection (very basic)
                        if ndef_data[0] == 0xD1 and ndef_data[1] == 0x01:  # Well-known text record
                            payload_length = ndef_data[2]
                            if len(ndef_data) >= 3 + payload_length:
                                # Skip language code (first byte of payload)
                                text_start = 6 if len(ndef_data) > 5 else 4
                                text_data = ndef_data[text_start:3 + payload_length]
                                tag_info["ndef_text"] = text_data.decode('utf-8', errors='ignore')
                    except Exception as e:
                        tag_info["text_decode_error"] = str(e)
                        
        except Exception as e:
            tag_info["ndef_error"] = str(e)

        return tag_info

    def on_tag_connect(self, atr: List[int]) -> None:
        """
        Process detected NFC tag.

        Args:
            atr: Answer to Reset from the card
        """
        self.logger.info("=" * 50)
        self.logger.info("NFC TAG DETECTED!")
        self.logger.info("=" * 50)

        tag_data = self.format_tag_data(atr)
        
        # Print tag information
        for key, value in tag_data.items():
            self.logger.info(f"{key}: {value}")

    def listen_for_tags(self) -> None:
        """Listen for NFC tags continuously."""
        try:
            while self.running:
                try:
                    # Wait for card
                    atr = self.connection.connect()
                    self.logger.debug(f"Card connected with ATR: {toHexString(atr)}")
                    
                    # Process the tag
                    self.on_tag_connect(atr)
                    
                    # Wait for card removal
                    self.logger.info("Waiting for card removal...")
                    while self.running:
                        try:
                            # Send a simple command to check if card is still present
                            self.connection.transmit([0xff, 0xca, 0x00, 0x00, 0x00])
                            time.sleep(0.5)
                        except Exception:
                            # Card removed
                            self.logger.info("Card removed")
                            break
                    
                    time.sleep(0.1)  # Brief pause before next scan

                except Exception as e:
                    # Card not present or communication error
                    time.sleep(0.5)  # Wait before retrying

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
        Connect to an available PCSC reader and create handler.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.logger.info("Searching for PCSC readers...")
            reader_list = readers()
            
            if not reader_list:
                self.logger.error("No PCSC readers found")
                return False
                
            # Use the first available reader
            reader = reader_list[0]
            self.logger.info(f"Found reader: {reader}")
            
            # Create connection
            connection = reader.createConnection()
            
            self.logger.info("Connected to PCSC reader")
            self.nfc_handler = NFCHandler(connection, self.logger)
            self.nfc_handler.set_running(self.running)
            return True
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to connect to PCSC reader: %s", e)
            return False

    def start_listening(self) -> None:
        """Start listening for NFC tags."""
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        # Keep trying to connect until successful or interrupted
        while self.running and not self.connect_reader():
            self.logger.warning(
                "Could not connect to PCSC reader. Retrying in 5 seconds...")
            time.sleep(5)

        self.logger.info("PCSC Reader started. Listening for tags...")
        self.logger.info("Press Ctrl+C to stop")

        try:
            while self.running:
                try:
                    if self.nfc_handler:
                        self.nfc_handler.listen_for_tags()
                    if not self.running:
                        break
                    time.sleep(0.1)  # Small delay to prevent busy waiting

                except Exception as e:
                    self.logger.error("Error during tag scanning: %s", e)
                    self.logger.info("Attempting to reconnect to PCSC reader...")

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
            self.logger.error("Fatal error during tag listening: %s", e)
        finally:
            if self.nfc_handler:
                self.nfc_handler.close()
                self.logger.info("PCSC reader connection closed")


def main() -> None:
    """Main function to start the NFC reader."""
    print("NFC Tag Reader (PCSC)")
    print("=" * 50)
    print("This program will listen for NFC tags and display their contents.")
    print("Make sure your NFC reader is connected and PCSC daemon is running.")
    print("=" * 50 + "\n")

    reader = NFCReader()
    reader.start_listening()


if __name__ == "__main__":
    main()
