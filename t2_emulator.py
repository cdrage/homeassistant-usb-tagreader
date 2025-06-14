#!/usr/bin/env python3
"""
T2 NFC Card Emulator using virtualsmartcard.
This script creates a virtual T2 NFC card with NDEF data.
"""

import sys
import struct
from virtualsmartcard.VirtualSmartcard import SmartcardOS, VirtualICC


class T2NFCCardOS(SmartcardOS):
    """SmartcardOS implementation for T2 NFC card emulation with NDEF data."""
    
    def __init__(self, ndef_data=None):
        """Initialize T2 NFC card with optional NDEF data."""
        self.ndef_data = ndef_data or b""
        self.pages = self._create_t2_structure()
        
    def _create_t2_structure(self):
        """Create T2 tag page structure with NDEF data."""
        pages = {}
        
        # Page 0-1: UID (can be fixed for testing)
        pages[0] = [0x04, 0x12, 0x34, 0x56]  # UID part 1
        pages[1] = [0x78, 0x9A, 0xBC, 0xDE]  # UID part 2
        
        # Page 2: Internal/lock bytes
        pages[2] = [0x00, 0x00, 0x00, 0x00]
        
        # Page 3: Capability Container
        pages[3] = [0xE1, 0x10, 0x12, 0x00]  # CC: NDEF capable, ver 1.0, 18 bytes data area
        
        if self.ndef_data:
            # Create NDEF TLV structure
            if len(self.ndef_data) < 0xFF:
                # Short form length
                ndef_tlv = bytes([0x03, len(self.ndef_data)]) + self.ndef_data
            else:
                # Long form length (3-byte length field)
                length_bytes = struct.pack('>H', len(self.ndef_data))
                ndef_tlv = bytes([0x03, 0xFF]) + length_bytes + self.ndef_data
            
            # Add terminator TLV
            ndef_tlv += bytes([0xFE])
            
            # Pack NDEF TLV into pages starting at page 4
            page_num = 4
            offset = 0
            while offset < len(ndef_tlv):
                page_data = list(ndef_tlv[offset:offset+4])
                page_data.extend([0x00] * (4 - len(page_data)))  # Pad to 4 bytes
                pages[page_num] = page_data
                page_num += 1
                offset += 4
        else:
            # Empty NDEF with just terminator TLV
            pages[4] = [0xFE, 0x00, 0x00, 0x00]
            
        return pages
    
    def getATR(self):
        """Return ATR for T2 NFC card."""
        # Simplified ATR for NFC Type 2 card
        return bytes([0x3B, 0x8F, 0x80, 0x01, 0x80, 0x4F, 0x0C, 0xA0, 0x00, 0x00, 0x03, 0x06, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x68])
    
    def execute(self, apdu):
        """Process APDU commands for T2 NFC card."""
        if len(apdu) < 4:
            return bytes([0x6F, 0x00])  # Wrong length
            
        cla, ins, p1, p2 = apdu[:4]
        lc = apdu[4] if len(apdu) > 4 else 0
        
        # Handle T2 READ command (0xFF 0xB0)
        if cla == 0xFF and ins == 0xB0:
            page = p2
            length = lc if lc > 0 else 4
            
            if page in self.pages:
                page_data = self.pages[page][:length]
                # Pad with zeros if needed
                page_data.extend([0x00] * (length - len(page_data)))
                return bytes(page_data) + bytes([0x90, 0x00])
            else:
                # Return zeros for undefined pages
                return bytes([0x00] * length) + bytes([0x90, 0x00])
        
        # Handle SELECT command (basic support)
        elif cla == 0x00 and ins == 0xA4:
            return bytes([0x90, 0x00])  # Success
            
        # Unknown command
        else:
            return bytes([0x6D, 0x00])  # Instruction not supported


def main():
    """Main entry point for T2 NFC card emulator."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        # NDEF data provided as hex string
        try:
            ndef_data = bytes.fromhex(sys.argv[1])
        except ValueError:
            print(f"Error: Invalid hex string: {sys.argv[1]}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default test NDEF data (Home Assistant URL)
        url = "home-assistant.io/tag/test123"
        ndef_data = bytes([
            0xD1,  # Header: MB=1, ME=1, CF=0, SR=1, IL=0, TNF=1 (Well-known)
            0x01,  # Type length = 1
            len(url) + 1,  # Payload length
            0x55,  # Type: 'U' (URI)
            0x04,  # URI identifier: "https://"
        ]) + url.encode('utf-8')
    
    print(f"Starting T2 NFC card emulator with NDEF data: {ndef_data.hex()}")
    
    # Create the card OS with NDEF data
    card_os = T2NFCCardOS(ndef_data)
    
    # Create and run virtual ICC
    try:
        vicc = VirtualICC("", "iso7816", "localhost", 35963)
        vicc.os = card_os
        print("T2 NFC card emulator started. Press Ctrl+C to stop.")
        vicc.run()
    except KeyboardInterrupt:
        print("\nStopping T2 NFC card emulator...")
    except Exception as e:
        print(f"VICC error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()