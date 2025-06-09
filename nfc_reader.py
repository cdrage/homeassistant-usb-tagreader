#!/usr/bin/python3
"""Read NDEF from a T2 tag, output to stdout"""

import sys
import signal
import atexit
import time
import threading
import requests
import logging
import os
from typing import Optional
from smartcard.CardConnection import CardConnection
from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.util import toHexString
from smartcard.Exceptions import CardConnectionException, NoCardException
from smartcard.System import readers

from ndef_decoder import NDEFDecoder

HA_TAG_PREFIX = "https://www.home-assistant.io/tag/"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

# Global variables for resource cleanup
_connection: Optional[CardConnection] = None
_card_monitor: Optional[CardMonitor] = None


def send_ha_webhook(tag_id: str) -> bool:
    """Send Home Assistant tag ID to webhook endpoint"""
    if not WEBHOOK_URL:
        print(f"⚠️  WEBHOOK_URL not configured, skipping webhook for tag: {tag_id}", file=sys.stderr)
        return False
        
    try:
        data = {"tag_id": tag_id}
        response = requests.post(WEBHOOK_URL, data=data, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Webhook sent successfully for tag: {tag_id}", file=sys.stderr)
            return True
        else:
            print(f"❌ Webhook failed with status {response.status_code} for tag: {tag_id}", file=sys.stderr)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Webhook request failed for tag {tag_id}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Unexpected error sending webhook for tag {tag_id}: {e}", file=sys.stderr)
        return False


def check_pcsc_system() -> bool:
    """Check PC/SC system status and available readers"""
    try:
        print("🔍 Checking PC/SC system status...", file=sys.stderr)
        
        # Get available readers
        available_readers = readers()
        print(f"🔍 Available readers: {len(available_readers)}", file=sys.stderr)
        
        for i, reader in enumerate(available_readers):
            print(f"  Reader {i}: {reader}", file=sys.stderr)
            
            try:
                # Try to connect to see if there's a card
                connection = reader.createConnection()
                connection.connect()
                print(f"  ✅ Reader {i} has a card present", file=sys.stderr)
                print(f"  ATR: {toHexString(connection.getATR())}", file=sys.stderr)
                connection.disconnect()
            except NoCardException:
                print(f"  ℹ️  Reader {i} has no card", file=sys.stderr)
            except Exception as e:
                print(f"  ⚠️  Reader {i} error: {e}", file=sys.stderr)
        
        if not available_readers:
            print("❌ No PC/SC readers found!", file=sys.stderr)
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ PC/SC system check failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


class NFCCardObserver(CardObserver):
    """Observer for NFC card insertion and removal events"""
    
    def __init__(self):
        self.cards_processed = 0
        self.processing_lock = threading.Lock()
        print("🔍 NFCCardObserver initialized", file=sys.stderr)
        
    def update(self, observable, handlers):
        """Called when card events occur"""
        print(f"🔍 Observer update called with {len(handlers) if handlers else 0} handlers", file=sys.stderr)
        
        try:
            (addedcards, removedcards) = handlers
            print(f"🔍 Added cards: {len(addedcards)}, Removed cards: {len(removedcards)}", file=sys.stderr)
            
            # Handle card insertions
            for card in addedcards:
                print(f"📟 Card inserted: {toHexString(card.atr)}", file=sys.stderr)
                print(f"🔍 Starting thread to process card", file=sys.stderr)
                threading.Thread(target=self._process_card, args=(card,), daemon=True).start()
            
            # Handle card removals
            for card in removedcards:
                print(f"📤 Card removed: {toHexString(card.atr)}", file=sys.stderr)
                
        except Exception as e:
            print(f"❌ Error in observer update: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    def _process_card(self, card):
        """Process a card in a separate thread"""
        global _connection
        
        with self.processing_lock:
            try:
                # Connect to the card
                connection = card.createConnection()
                if not isinstance(connection, CardConnection):
                    print("Error: Card connection is not valid", file=sys.stderr)
                    return

                _connection = connection
                _connection.connect()
                
                print(f"Connected to card", file=sys.stderr)
                
                # Read NDEF data
                reader = T2NDEFReader()
                data, error = reader.read_ndef(_connection)
                
                if error:
                    print(f"Error reading NDEF: {error}", file=sys.stderr)
                    return
                
                if data:
                    # Output hex representation to stderr for debugging
                    print(f"Raw NDEF data ({len(data)} bytes): {data.hex()}", file=sys.stderr)
                    
                    decoder = NDEFDecoder(data)
                    records = decoder.decode_records()
                    
                    print("=== NDEF Records ===", file=sys.stderr)
                    for i, record in enumerate(records):
                        print(f"Record {i + 1}:", file=sys.stderr)
                        print(f"  TNF: {record.tnf} ({record.tnf_name})", file=sys.stderr)
                        print(f"  Type: {record.type_str} (hex: {record.record_type.hex()})", file=sys.stderr)
                        if record.id_str:
                            print(f"  ID: {record.id_str}", file=sys.stderr)
                        print(f"  Payload length: {len(record.payload)} bytes", file=sys.stderr)
                        print(f"  Payload (hex): {record.payload.hex()}", file=sys.stderr)
                        print(f"  Payload (string): {repr(record.payload_str)}", file=sys.stderr)
                        
                        # Special handling for URI records
                        if record.is_uri_record:
                            uri = record.get_decoded_uri()
                            print(f"  Decoded URI: {uri}", file=sys.stderr)

                            # Check if it's a Home Assistant tag
                            if uri and uri.startswith(HA_TAG_PREFIX):
                                tag_id = uri[len(HA_TAG_PREFIX):]
                                print(f"  Home Assistant Tag ID: {tag_id}", file=sys.stderr)
                                
                                # Send webhook request in background thread
                                webhook_thread = threading.Thread(
                                    target=send_ha_webhook, 
                                    args=(tag_id,), 
                                    daemon=True
                                )
                                webhook_thread.start()

                        # Special handling for Android Application Record (AAR)
                        elif record.is_android_app_record:
                            package_name = record.get_android_package_name()
                            print(f"  Android Package: {package_name}", file=sys.stderr)
                        print(f"  Flags: MB={record.message_begin}, ME={record.last_record}, "
                              f"CF={record.chunked}, SR={record.short_record}, IL={record.has_id}", file=sys.stderr)
                        print(file=sys.stderr)
                    
                    # Output raw binary data to stdout for piping
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    
                    self.cards_processed += 1
                    print(f"--- Card read completed --- (Total: {self.cards_processed})", file=sys.stderr)
                else:
                    print("No NDEF data found on card", file=sys.stderr)
                    
            except Exception as e:
                print(f"Error processing card: {e}", file=sys.stderr)
            
            finally:
                # Always disconnect the card
                if _connection:
                    try:
                        _connection.disconnect()
                        print("Card processing finished", file=sys.stderr)
                    except Exception as e:
                        print(f"Warning: Error disconnecting card: {e}", file=sys.stderr)
                    finally:
                        _connection = None


def cleanup_resources() -> None:
    """Cleanup function to be called on exit"""
    global _connection, _card_monitor
    
    # Stop card monitoring
    if _card_monitor:
        try:
            # Remove all observers and stop monitoring
            for observer in _card_monitor.observers[:]:  # Copy list to avoid modification during iteration
                _card_monitor.deleteObserver(observer)
            print("Card monitor stopped.", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error stopping card monitor: {e}", file=sys.stderr)
        finally:
            _card_monitor = None
    
    # Disconnect any active card connection
    if _connection:
        try:
            _connection.disconnect()
            print("Card connection closed.", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error closing card connection: {e}", file=sys.stderr)
        finally:
            _connection = None


def signal_handler(signum: int, frame) -> None:
    """Handle termination signals"""
    signal_name = "SIGTERM" if signum == signal.SIGTERM else \
                  "SIGINT" if signum == signal.SIGINT else \
                  f"signal {signum}"
    print(f"\nReceived {signal_name}, cleaning up...", file=sys.stderr)
    cleanup_resources()
    sys.exit(128 + signum)


def setup_signal_handlers() -> None:
    """Setup signal handlers for proper cleanup"""
    # Handle SIGTERM (docker stop, systemctl stop, etc.)
    signal.signal(signal.SIGTERM, signal_handler)
    # Handle SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    # Register cleanup function to run at normal exit
    atexit.register(cleanup_resources)


class T2NDEFReader:
    """Simple T2 NDEF reader using PC/SC"""

    CC_MAGIC = 0xE1
    NDEF_TAG = 0x03
    INS_READ = 0xB0
    SW1_OK = 0x90
    SW2_OK = 0x00

    def read_ndef(self, connection: CardConnection):
        """Read NDEF data from T2 tag using modern smartcard API"""

        try:
            # Read capabilities container at page 3
            response, sw1, sw2 = connection.transmit(
                [0xFF, self.INS_READ, 0x00, 0x03, 4]
            )

            if sw1 != self.SW1_OK or sw2 != self.SW2_OK:
                return None, f"CC read error: {sw1:02X}{sw2:02X}"

            if len(response) != 4 or response[0] != self.CC_MAGIC:
                return None, "Invalid capability container"

            # Read NDEF TLV at page 4
            response, sw1, sw2 = connection.transmit(
                [0xFF, self.INS_READ, 0x00, 0x04, 4]
            )

            if sw1 != self.SW1_OK or sw2 != self.SW2_OK:
                return None, f"NDEF TLV read error: {sw1:02X}{sw2:02X}"

            if response[0] != self.NDEF_TAG:
                return None, f"Invalid NDEF tag: {response[0]:02X}"

            # Get NDEF length
            if response[1] < 0xFF:
                ndef_len = response[1]
                data_start = 2
                ndef_data = bytes(response[2:4][:ndef_len])
            else:
                ndef_len = (response[2] << 8) + response[3]
                data_start = 4
                ndef_data = b""

            # Read remaining NDEF data
            bytes_read = len(ndef_data)
            page = 5 if data_start == 2 else 6

            while bytes_read < ndef_len:
                response, sw1, sw2 = connection.transmit(
                    [0xFF, self.INS_READ, 0x00, page, 4]
                )

                if sw1 != self.SW1_OK or sw2 != self.SW2_OK:
                    return None, f"Page {page} read error: {sw1:02X}{sw2:02X}"

                bytes_needed = min(4, ndef_len - bytes_read)
                ndef_data += bytes(response[:bytes_needed])
                bytes_read += bytes_needed
                page += 1

            return ndef_data, None

        except Exception as e:
            return None, f"NDEF read error: {e}"


def main() -> int:
    """Main function - uses observer pattern for card monitoring"""
    global _card_monitor
    
    print("🚀 NFC Reader starting up...", file=sys.stderr)
    
    # Setup signal handlers for proper cleanup
    setup_signal_handlers()
    
    # Check PC/SC system first
    if not check_pcsc_system():
        print("❌ PC/SC system check failed - cannot continue", file=sys.stderr)
        return 1
    
    print("📡 NFC Reader started - waiting for cards...", file=sys.stderr)
    print("Press Ctrl+C to stop", file=sys.stderr)
    
    observer = None
    try:
        # Create card observer and monitor
        print("🔍 Creating CardObserver...", file=sys.stderr)
        observer = NFCCardObserver()
        
        print("🔍 Creating CardMonitor...", file=sys.stderr)
        _card_monitor = CardMonitor()
        
        print("🔍 Adding observer to monitor...", file=sys.stderr)
        _card_monitor.addObserver(observer)
        
        print("✅ Card monitoring started - place a card on the reader", file=sys.stderr)
        print("🔍 Monitoring thread active, main thread will sleep", file=sys.stderr)
        
        # Keep the main thread alive and periodically show we're still running
        loop_count = 0
        while True:
            time.sleep(5)  # Check every 5 seconds
            loop_count += 1
            if loop_count % 12 == 0:  # Every minute
                print(f"🔍 Still monitoring... ({loop_count * 5}s elapsed)", file=sys.stderr)
            
    except KeyboardInterrupt:
        cards_count = observer.cards_processed if observer else 0
        print(f"\n🛑 Shutting down... Processed {cards_count} cards.", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"❌ Unexpected error in main loop: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit(main())
