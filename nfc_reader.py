#!/usr/bin/python3
"""Read NDEF from a T2 tag, output to stdout"""

import sys
import smartcard.scard as sc
from smartcard.CardRequest import CardRequest
from smartcard.CardType import AnyCardType
from smartcard.CardConnection import CardConnection


class T2NDEFReader:
    """Simple T2 NDEF reader using PC/SC"""

    CC_MAGIC = 0xe1
    NDEF_TAG = 0x03
    INS_READ = 0xb0
    SW1_OK = 0x90
    SW2_OK = 0x00

    def read_ndef(self):
        """Read NDEF data from T2 tag and return it"""

        # Get PC/SC context
        try:
            r, hcontext = sc.SCardEstablishContext(sc.SCARD_SCOPE_USER)
            if r != sc.SCARD_S_SUCCESS:
                return None, "Cannot establish PC/SC context"
        except Exception as e:
            return None, f"PC/SC context error: {e}"

        try:
            # Get readers
            _, readers = sc.SCardListReaders(hcontext, [])
            if not readers:
                return None, "No readers found"

            # Connect to first reader
            r, hcard, protocol = sc.SCardConnect(hcontext, readers[0],
                                                 sc.SCARD_SHARE_SHARED,
                                                 sc.SCARD_PROTOCOL_T0 | sc.SCARD_PROTOCOL_T1)
            if r != sc.SCARD_S_SUCCESS:
                return None, "Cannot connect to card"

            try:
                # Read capabilities container at page 3
                r, response = sc.SCardTransmit(hcard, protocol,
                                               [0xff, self.INS_READ, 0x00, 0x03, 4])

                if r != sc.SCARD_S_SUCCESS or len(response) < 6:
                    return None, "Failed to read CC"

                if response[-2:] != [self.SW1_OK, self.SW2_OK]:
                    return None, f"CC read error: {response[-2]:02X}{response[-1]:02X}"

                cc = response[:-2]
                if len(cc) != 4 or cc[0] != self.CC_MAGIC:
                    return None, "Invalid capability container"

                # Read NDEF TLV at page 4
                r, response = sc.SCardTransmit(hcard, protocol,
                                               [0xff, self.INS_READ, 0x00, 0x04, 4])

                if r != sc.SCARD_S_SUCCESS or len(response) < 6:
                    return None, "Failed to read NDEF TLV"

                if response[-2:] != [self.SW1_OK, self.SW2_OK]:
                    return None, f"NDEF TLV read error: {response[-2]:02X}{response[-1]:02X}"

                tlv = response[:-2]
                if tlv[0] != self.NDEF_TAG:
                    return None, f"Invalid NDEF tag: {tlv[0]:02X}"

                # Get NDEF length
                if tlv[1] < 0xff:
                    ndef_len = tlv[1]
                    data_start = 2
                    ndef_data = bytes(tlv[2:4][:ndef_len])
                else:
                    ndef_len = (tlv[2] << 8) + tlv[3]
                    data_start = 4
                    ndef_data = b""

                # Read remaining NDEF data
                bytes_read = len(ndef_data)
                page = 5 if data_start == 2 else 6

                while bytes_read < ndef_len:
                    r, response = sc.SCardTransmit(hcard, protocol,
                                                   [0xff, self.INS_READ, 0x00, page, 4])

                    if r != sc.SCARD_S_SUCCESS or len(response) < 6:
                        return None, f"Failed to read page {page}"

                    if response[-2:] != [self.SW1_OK, self.SW2_OK]:
                        return None, f"Page {page} read error: {response[-2]:02X}{response[-1]:02X}"

                    page_data = response[:-2]
                    bytes_needed = min(4, ndef_len - bytes_read)
                    ndef_data += bytes(page_data[:bytes_needed])
                    bytes_read += bytes_needed
                    page += 1

                return ndef_data, None

            finally:
                sc.SCardDisconnect(hcard, sc.SCARD_UNPOWER_CARD)

        finally:
            sc.SCardReleaseContext(hcontext)


def main():
    """Main function"""
    cardrequest = CardRequest(cardType=AnyCardType(), timeout=sc.INFINITE)
    cardservice = cardrequest.waitforcard()

    if not cardservice:
        print("No card found")
        return 1

    print(cardservice.cardname)
    connection: CardConnection = cardservice.connection
    connection.connect()
    print(connection.getATR())
    print(connection.getReader())


if __name__ == "__main__":
    exit(main())
