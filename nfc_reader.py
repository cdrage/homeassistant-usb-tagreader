#!/usr/bin/env python3
"""
NFC Tag Reader using libnfc
Listens for NFC tags on any available USB NFC reader and prints their contents.
"""

import time
import signal
import sys
from typing import Optional, List, Dict, Any
import logging

try:
    import nfc
except ImportError:
    print("Error: nfc library not found. Install it with: pip install nfcpy")
    sys.exit(1)


class NFCReader:
    """NFC Reader class to handle tag detection and reading."""
    
    def __init__(self) -> None:
        """Initialize the NFC reader."""
        self.running: bool = True
        self.clf: Optional[nfc.ContactlessFrontend] = None
        self.setup_logging()
        
    def setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def signal_handler(self, signum: int, frame: Any) -> None:
        """Handle interrupt signals for graceful shutdown."""
        self.logger.info("Received interrupt signal. Shutting down...")
        self.running = False
        if self.clf:
            self.clf.close()
        sys.exit(0)
    
    def connect_reader(self) -> bool:
        """
        Connect to an available NFC reader.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.logger.info("Searching for NFC readers...")
            self.clf = nfc.ContactlessFrontend('usb')
            if self.clf:
                self.logger.info(f"Connected to NFC reader: {self.clf}")
                return True
            else:
                self.logger.error("No NFC readers found")
                return False
        except Exception as e:
            self.logger.error(f"Failed to connect to NFC reader: {e}")
            return False
    
    def format_tag_data(self, tag: nfc.tag.Tag) -> Dict[str, Any]:
        """
        Format tag data for display.
        
        Args:
            tag: The NFC tag object
            
        Returns:
            Dict containing formatted tag information
        """
        tag_info = {
            'type': str(type(tag).__name__),
            'identifier': tag.identifier.hex() if tag.identifier else 'Unknown',
            'ndef_capacity': getattr(tag, 'ndef', {}).get('capacity', 'N/A'),
            'ndef_length': getattr(tag, 'ndef', {}).get('length', 'N/A'),
        }
        
        # Try to read NDEF records if available
        if hasattr(tag, 'ndef') and tag.ndef:
            try:
                tag_info['ndef_records'] = []
                if tag.ndef.records:
                    for record in tag.ndef.records:
                        record_info = {
                            'type': record.type,
                            'name': record.name,
                            'data': record.data if len(record.data) < 100 else f"{record.data[:100]}... (truncated)"
                        }
                        tag_info['ndef_records'].append(record_info)
                else:
                    tag_info['ndef_records'] = 'No NDEF records found'
            except Exception as e:
                tag_info['ndef_error'] = str(e)
        
        return tag_info
    
    def on_tag_connect(self, tag: nfc.tag.Tag) -> bool:
        """
        Callback function when a tag is detected.
        
        Args:
            tag: The detected NFC tag
            
        Returns:
            bool: Always returns True to keep listening
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
            
            if 'ndef_records' in tag_data:
                print("\nNDEF Records:")
                if isinstance(tag_data['ndef_records'], list):
                    for i, record in enumerate(tag_data['ndef_records']):
                        print(f"  Record {i + 1}:")
                        print(f"    Type: {record['type']}")
                        print(f"    Name: {record['name']}")
                        print(f"    Data: {record['data']}")
                else:
                    print(f"  {tag_data['ndef_records']}")
            
            if 'ndef_error' in tag_data:
                print(f"\nNDEF Error: {tag_data['ndef_error']}")
            
        except Exception as e:
            self.logger.error(f"Error reading tag: {e}")
        
        print("\n" + "=" * 50)
        print("Waiting for next tag...")
        print("=" * 50 + "\n")
        
        return True  # Keep listening for more tags
    
    def start_listening(self) -> None:
        """Start listening for NFC tags."""
        if not self.connect_reader():
            return
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.logger.info("NFC Reader started. Listening for tags...")
        self.logger.info("Press Ctrl+C to stop")
        
        try:
            while self.running:
                # Listen for tags with a timeout to allow checking self.running
                tag = self.clf.connect(rdwr={'on-connect': self.on_tag_connect}, terminate=lambda: not self.running)
                if not self.running:
                    break
                time.sleep(0.1)  # Small delay to prevent busy waiting
                
        except Exception as e:
            self.logger.error(f"Error during tag listening: {e}")
        finally:
            if self.clf:
                self.clf.close()
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