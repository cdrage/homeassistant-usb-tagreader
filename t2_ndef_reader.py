#!/usr/bin/python3
"""T2 NDEF Reader for NFC Type 2 tags using PC/SC"""

from smartcard.CardConnection import CardConnection

# Logic taken mostly from:
# https://github.com/Giraut/pcsc-ndef/blob/master/pcsc_ndef.py

CC_MAGIC = 0xE1
NDEF_TAG = 0x03
INS_READ = 0xB0
SW1_OK = 0x90
SW2_OK = 0x00


def read_uid(connection: CardConnection):
    """Read UID from NFC tag (pages 0-1)"""
    uid_bytes = []

    # Read page 0 (first 4 bytes of UID)
    response, sw1, sw2 = connection.transmit([0xFF, INS_READ, 0x00, 0x00, 4])
    if sw1 != SW1_OK or sw2 != SW2_OK:
        return None, f"UID page 0 read error: {sw1:02X}{sw2:02X}"
    uid_bytes.extend(response)

    # Read page 1 (next 4 bytes, includes check bytes)
    response, sw1, sw2 = connection.transmit([0xFF, INS_READ, 0x00, 0x01, 4])
    if sw1 != SW1_OK or sw2 != SW2_OK:
        return None, f"UID page 1 read error: {sw1:02X}{sw2:02X}"
    uid_bytes.extend(response[:3])  # Only first 3 bytes are UID

    # UID is 7 bytes: page0[0:4] + page1[0:3]
    uid = ''.join(f'{b:02X}' for b in uid_bytes[:7])
    return uid, None


def read_ndef(connection: CardConnection):
    """Read NDEF data from T2 tag using modern smartcard API"""

    # Read capabilities container at page 3
    response, sw1, sw2 = connection.transmit([0xFF, INS_READ, 0x00, 0x03, 4])

    if sw1 != SW1_OK or sw2 != SW2_OK:
        return None, f"CC read error: {sw1:02X}{sw2:02X}"

    if len(response) != 4 or response[0] != CC_MAGIC:
        return None, "Invalid capability container"

    # Read NDEF TLV at page 4
    response, sw1, sw2 = connection.transmit([0xFF, INS_READ, 0x00, 0x04, 4])

    if sw1 != SW1_OK or sw2 != SW2_OK:
        return None, f"NDEF TLV read error: {sw1:02X}{sw2:02X}"

    if response[0] != NDEF_TAG:
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
        response, sw1, sw2 = connection.transmit([0xFF, INS_READ, 0x00, page, 4])

        if sw1 != SW1_OK or sw2 != SW2_OK:
            return None, f"Page {page} read error: {sw1:02X}{sw2:02X}"

        bytes_needed = min(4, ndef_len - bytes_read)
        ndef_data += bytes(response[:bytes_needed])
        bytes_read += bytes_needed
        page += 1

    return ndef_data, None
