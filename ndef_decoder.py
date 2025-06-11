#!/usr/bin/python3
"""NDEF decoder for analyzing NFC tag data"""

import sys
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

# Configure logging for this module
logger = logging.getLogger(__name__)

@dataclass
class NDEFRecord:
    """Strongly typed NDEF record representation"""
    tnf: int
    tnf_name: str
    record_type: bytes
    type_str: str
    record_id: bytes
    id_str: str
    payload: bytes
    payload_str: str
    message_begin: bool
    last_record: bool
    chunked: bool
    short_record: bool
    has_id: bool
    
    @property
    def is_uri_record(self) -> bool:
        """Check if this is a URI record"""
        return self.record_type == b'U'
    
    @property
    def is_android_app_record(self) -> bool:
        """Check if this is an Android Application Record"""
        return self.type_str == 'android.com:pkg'
    
    def get_decoded_uri(self) -> Optional[str]:
        """Get decoded URI if this is a URI record"""
        if self.is_uri_record:
            return decode_uri_payload(self.payload)
        return None
    
    def get_android_package_name(self) -> Optional[str]:
        """Get Android package name if this is an AAR"""
        if self.is_android_app_record:
            return self.payload_str
        return None

class NDEFDecoder:
    """Decode NDEF records according to NFC Forum specification"""
    
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0
    
    def decode_records(self) -> List[NDEFRecord]:
        """Decode all NDEF records in the data"""
        records: List[NDEFRecord] = []
        
        while self.offset < len(self.data):
            record = self.decode_record()
            if record is None:
                break
            records.append(record)
            
            # If this was the last record (ME flag set), stop
            if record.last_record:
                break
        
        return records
    
    def decode_record(self) -> Optional[NDEFRecord]:
        """Decode a single NDEF record"""
        if self.offset >= len(self.data):
            return None
        
        # Read the TNF and flags byte
        tnf_flags = self.data[self.offset]
        self.offset += 1
        
        # Extract flags
        mb = (tnf_flags & 0x80) != 0  # Message Begin
        me = (tnf_flags & 0x40) != 0  # Message End
        cf = (tnf_flags & 0x20) != 0  # Chunk Flag
        sr = (tnf_flags & 0x10) != 0  # Short Record
        il = (tnf_flags & 0x08) != 0  # ID Length present
        tnf = tnf_flags & 0x07        # Type Name Format
        
        # Read Type Length
        type_length = self.data[self.offset]
        self.offset += 1
        
        # Read Payload Length (1 or 4 bytes depending on SR flag)
        if sr:
            payload_length = self.data[self.offset]
            self.offset += 1
        else:
            payload_length = (self.data[self.offset] << 24) | \
                           (self.data[self.offset + 1] << 16) | \
                           (self.data[self.offset + 2] << 8) | \
                           self.data[self.offset + 3]
            self.offset += 4
        
        # Read ID Length if present
        id_length = 0
        if il:
            id_length = self.data[self.offset]
            self.offset += 1
        
        # Read Type
        record_type = self.data[self.offset:self.offset + type_length]
        self.offset += type_length
        
        # Read ID if present
        record_id = b""
        if il:
            record_id = self.data[self.offset:self.offset + id_length]
            self.offset += id_length
        
        # Read Payload
        payload = self.data[self.offset:self.offset + payload_length]
        self.offset += payload_length
        
        return NDEFRecord(
            tnf=tnf,
            tnf_name=self.get_tnf_name(tnf),
            record_type=record_type,
            type_str=record_type.decode('utf-8', errors='ignore'),
            record_id=record_id,
            id_str=record_id.decode('utf-8', errors='ignore') if record_id else '',
            payload=payload,
            payload_str=payload.decode('utf-8', errors='ignore'),
            message_begin=mb,
            last_record=me,
            chunked=cf,
            short_record=sr,
            has_id=il
        )
    
    def get_tnf_name(self, tnf: int) -> str:
        """Get human-readable TNF name"""
        tnf_names: Dict[int, str] = {
            0x00: "Empty",
            0x01: "NFC Forum well-known type",
            0x02: "Media type (RFC 2046)",
            0x03: "Absolute URI (RFC 3986)", 
            0x04: "NFC Forum external type",
            0x05: "Unknown",
            0x06: "Unchanged",
            0x07: "Reserved"
        }
        return tnf_names.get(tnf, f"Unknown ({tnf})")

def decode_uri_payload(payload: bytes) -> str:
    """Decode URI record payload"""
    if not payload:
        return ""
    
    # First byte is URI identifier code
    uri_code = payload[0]
    uri_prefixes: Dict[int, str] = {
        0x00: "",
        0x01: "http://www.",
        0x02: "https://www.",
        0x03: "http://",
        0x04: "https://",
        0x05: "tel:",
        0x06: "mailto:",
        0x07: "ftp://anonymous:anonymous@",
        0x08: "ftp://ftp.",
        0x09: "ftps://",
        0x0A: "sftp://",
        0x0B: "smb://",
        0x0C: "nfs://",
        0x0D: "ftp://",
        0x0E: "dav://",
        0x0F: "news:",
        0x10: "telnet://",
        0x11: "imap:",
        0x12: "rtsp://",
        0x13: "urn:",
        0x14: "pop:",
        0x15: "sip:",
        0x16: "sips:",
        0x17: "tftp:",
        0x18: "btspp://",
        0x19: "btl2cap://",
        0x1A: "btgoep://",
        0x1B: "tcpobex://",
        0x1C: "irdaobex://",
        0x1D: "file://",
        0x1E: "urn:epc:id:",
        0x1F: "urn:epc:tag:",
        0x20: "urn:epc:pat:",
        0x21: "urn:epc:raw:",
        0x22: "urn:epc:",
        0x23: "urn:nfc:"
    }
    
    prefix = uri_prefixes.get(uri_code, f"[Unknown prefix {uri_code:02X}]")
    uri_suffix = payload[1:].decode('utf-8', errors='ignore')
    
    return prefix + uri_suffix

def analyze_home_assistant_data(data: bytes) -> None:
    """Analyze Home Assistant specific NDEF data"""
    logger.info("=== Home Assistant NDEF Analysis ===")
    logger.info("Raw data: %s", data.hex())
    logger.debug("Raw string: %r", data)
    logger.info("Length: %d bytes", len(data))
    
    decoder = NDEFDecoder(data)
    records = decoder.decode_records()
    
    for i, record in enumerate(records):
        logger.info("Record %d:", i + 1)
        logger.info("  TNF: %d (%s)", record.tnf, record.tnf_name)
        logger.info("  Type: %s (hex: %s)", record.type_str, record.record_type.hex())
        if record.id_str:
            logger.info("  ID: %s", record.id_str)
        logger.info("  Payload length: %d bytes", len(record.payload))
        logger.debug("  Payload (hex): %s", record.payload.hex())
        logger.debug("  Payload (string): %r", record.payload_str)
        
        # Special handling for URI records
        if record.is_uri_record:
            uri = record.get_decoded_uri()
            logger.info("  Decoded URI: %s", uri)
        
        # Special handling for Android Application Record (AAR)
        elif record.is_android_app_record:
            package_name = record.get_android_package_name()
            logger.info("  Android Package: %s", package_name)
        
        logger.debug("  Flags: MB=%s, ME=%s, CF=%s, SR=%s, IL=%s",
                    record.message_begin, record.last_record,
                    record.chunked, record.short_record, record.has_id)

if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example data from the Home Assistant tag we captured
    # This is the data we saw: "home-assistant.io/tag/library://artist/172"android.com:pkgio.homeassistant.companion.androidT*android.com:pkgio.homeassistant.companion.android.minimal"
    
    # Let's reconstruct the raw bytes (this would normally come from the NFC reader)
    if len(sys.argv) > 1:
        # Read from hex input
        hex_data: str = sys.argv[1].replace(' ', '').replace(':', '')
        data: bytes = bytes.fromhex(hex_data)
    else:
        # Use the captured data - we need to get the actual raw bytes from the NFC reader
        logger.error("Usage: python ndef_decoder.py <hex_data>")
        logger.error("Please provide the raw NDEF data as hex")
        sys.exit(1)
    
    analyze_home_assistant_data(data)