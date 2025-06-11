#!/usr/bin/python3
"""Test NDEF decoding with sample Home Assistant data"""

import logging
import os
from ndef_decoder import analyze_home_assistant_data

# Configure logging for the test
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Based on the output we saw, let's try to reconstruct what the NDEF data might look like
# The string we saw suggests it contains:
# 1. URI: home-assistant.io/tag/library://artist/172
# 2. AAR: io.homeassistant.companion.android  
# 3. AAR: io.homeassistant.companion.android.minimal

def test_with_sample_data():
    """Test with some sample NDEF data to show the format"""
    
    # Let's create a sample NDEF message with URI + AAR records
    # This is what Home Assistant companion app typically creates
    
    logger.info("=== NDEF Format Analysis ===")
    logger.info("The Home Assistant Companion app typically creates NDEF messages with:")
    logger.info("1. A URI record pointing to home-assistant.io/tag/...")
    logger.info("2. Android Application Record (AAR) for the companion app")
    logger.info("3. Sometimes additional AAR for backup/minimal app")
    
    logger.info("NDEF Record Structure (per NFC Forum specification):")
    logger.info("- Header byte: TNF (Type Name Format) + flags")
    logger.info("- Type Length: 1 byte")
    logger.info("- Payload Length: 1 or 4 bytes (depending on Short Record flag)")
    logger.info("- ID Length: 1 byte (if ID present flag is set)")
    logger.info("- Type: variable length")
    logger.info("- ID: variable length (if present)")
    logger.info("- Payload: variable length")
    
    logger.info("Common TNF values:")
    logger.info("- 0x01: NFC Forum well-known type (like 'U' for URI)")
    logger.info("- 0x04: NFC Forum external type (like 'android.com:pkg' for AAR)")
    
    logger.info("Common record types:")
    logger.info("- 'U': URI record")
    logger.info("- 'android.com:pkg': Android Application Record")
    
    logger.info("To decode the actual data from your tag, run:")
    logger.info("./docker-build.sh && ./deploy.sh lasath@speakerpi.home.lasath.com --sync")
    logger.info("Then when you see the hex output, use:")
    logger.info("python ndef_decoder.py <hex_data>")

if __name__ == "__main__":
    test_with_sample_data()