#!/usr/bin/python3
"""Read NDEF from a T2 tag, output to stdout"""

import sys
import signal
import atexit
from typing import Optional
from smartcard.CardRequest import CardRequest
from smartcard.CardType import AnyCardType
from smartcard.CardConnection import CardConnection
import smartcard.scard

from ndef_decoder import NDEFDecoder

# Global variables for resource cleanup
_connection: Optional[CardConnection] = None


def cleanup_resources() -> None:
    """Cleanup function to be called on exit"""
    global _connection
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
    signal_names = {
        signal.SIGTERM: "SIGTERM",
        signal.SIGINT: "SIGINT"
    }
    signal_name = signal_names.get(signum, f"signal {signum}")
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
    """Main function"""
    global _connection
    
    # Setup signal handlers for proper cleanup
    setup_signal_handlers()
    
    try:
        # Wait for a card (wait indefinitely)
        cardrequest = CardRequest(
            cardType=AnyCardType(), timeout=smartcard.scard.INFINITE
        )
        cardservice = cardrequest.waitforcard()

        if not cardservice:
            print("No card found", file=sys.stderr)
            return 1

        # Connect to the card and store globally for cleanup
        _connection = cardservice.connection
        if _connection is None:
            print("Failed to get card connection", file=sys.stderr)
            return 1
        _connection.connect()

        print(f"Connected to card: {cardservice.cardname}", file=sys.stderr)

        # Read NDEF data
        reader = T2NDEFReader()
        data, error = reader.read_ndef(_connection)

        if error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

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
                # Special handling for Android Application Record (AAR)
                elif record.is_android_app_record:
                    package_name = record.get_android_package_name()
                    print(f"  Android Package: {package_name}", file=sys.stderr)
                print(f"  Flags: MB={record.message_begin}, ME={record.last_record}, "
                      f"CF={record.chunked}, SR={record.short_record}, IL={record.has_id}", file=sys.stderr)
                print(file=sys.stderr)

            # Output raw binary data to stdout for piping
            sys.stdout.buffer.write(data)
            
            # Clean disconnect (will also be called by atexit)
            cleanup_resources()
            return 0
        else:
            print("No NDEF data found", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit(main())
