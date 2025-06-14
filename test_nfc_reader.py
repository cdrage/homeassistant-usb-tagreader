#!/usr/bin/env python3
"""
Integration test for NFC card reading using virtual smart card emulation.
This test requires vsmartcard to be installed and configured.
"""

import subprocess
import time
import sys
import threading
import json
import logging
import pytest
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from virtualsmartcard.VirtualSmartcard import SmartcardOS, VirtualICC
import struct
import nfc_reader

# Configure logging for the test
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)

# Create logger for this module
logger = logging.getLogger(__name__)


@pytest.fixture
def mqtt_broker():
    """Pytest fixture for MQTT broker."""
    broker = MQTTBroker()
    if not broker.start():
        pytest.fail("Failed to start MQTT broker")
    yield broker
    broker.stop()


@pytest.fixture
def mqtt_client():
    """Pytest fixture for MQTT test client."""
    client = MQTTTestClient()
    if not client.start():
        pytest.fail("Failed to start MQTT test client")
    yield client
    client.stop()


@pytest.fixture
def virtual_card_emulator():
    """Pytest fixture for virtual card emulator."""
    emulator = VirtualCardEmulator()
    yield emulator
    emulator.stop_emulation()


@pytest.fixture(scope="session", autouse=True)
def setup_pcsc():
    """Pytest fixture to set up PC/SC environment before all tests."""
    if not setup_pcsc_environment():
        pytest.fail("Failed to set up PC/SC environment")


class MQTTBroker:
    """Manages a local MQTT broker for testing."""

    def __init__(self):
        self.broker_process = None

    def start(self):
        """Start a local MQTT broker using mosquitto."""
        # Start mosquitto broker
        self.broker_process = subprocess.Popen(
            ["mosquitto", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        time.sleep(2)  # Give broker time to start

        # Check if broker is running
        if self.broker_process.poll() is None:
            logger.info("✓ MQTT broker started")
            return True
        else:
            # Log any error output
            stdout, stderr = self.broker_process.communicate()
            if stderr:
                logger.error(f"✗ MQTT broker failed to start: {stderr.decode()}")
            else:
                logger.error(f"✗ MQTT broker failed to start: {stdout.decode()}")
            return False

    def stop(self):
        """Stop the MQTT broker."""
        if self.broker_process:
            self.broker_process.terminate()
            self.broker_process.wait()
            self.broker_process = None
            logger.info("✓ MQTT broker stopped")


class MQTTTestClient:
    """MQTT client for testing NFC reader integration."""

    def __init__(self):
        self.client = None
        self.received_messages = []
        self.message_event = threading.Event()

    def start(self):
        """Start MQTT test client."""
        try:
            self.client = mqtt.Client(
                CallbackAPIVersion.VERSION2, client_id="test_client"
            )
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message

            self.client.connect("localhost", 1883, 60)
            self.client.loop_start()

            time.sleep(1)  # Give client time to connect
            return True

        except Exception as e:
            logger.error(f"✗ Failed to start MQTT test client: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for MQTT connection."""
        if rc == 0:
            logger.info("✓ MQTT test client connected")
            # Subscribe to Home Assistant topics
            client.subscribe("homeassistant/sensor/nfc_reader/+")
        else:
            logger.error(f"✗ MQTT test client connection failed: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback for received MQTT messages."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            message = {"topic": topic, "payload": payload}
            self.received_messages.append(message)
            self.message_event.set()
            logger.info(f"✓ Received MQTT message: {topic} = {payload}")
        except Exception as e:
            logger.warning(f"⚠ Error processing MQTT message: {e}")

    def wait_for_message(self, timeout=10):
        """Wait for an MQTT message."""
        self.message_event.clear()
        return self.message_event.wait(timeout)

    def stop(self):
        """Stop MQTT test client."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None


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
        pages[3] = [
            0xE1,
            0x10,
            0x12,
            0x00,
        ]  # CC: NDEF capable, ver 1.0, 18 bytes data area

        if self.ndef_data:
            # Create NDEF TLV structure
            if len(self.ndef_data) < 0xFF:
                # Short form length
                ndef_tlv = bytes([0x03, len(self.ndef_data)]) + self.ndef_data
            else:
                # Long form length (3-byte length field)
                length_bytes = struct.pack(">H", len(self.ndef_data))
                ndef_tlv = bytes([0x03, 0xFF]) + length_bytes + self.ndef_data

            # Add terminator TLV
            ndef_tlv += bytes([0xFE])

            # Pack NDEF TLV into pages starting at page 4
            page_num = 4
            offset = 0
            while offset < len(ndef_tlv):
                page_data = list(ndef_tlv[offset : offset + 4])
                page_data.extend([0x00] * (4 - len(page_data)))  # Pad to 4 bytes
                pages[page_num] = page_data
                page_num += 1
                offset += 4
        else:
            # Empty NDEF with just terminator TLV
            pages[4] = [0xFE, 0x00, 0x00, 0x00]

        return pages

    def getATR(self):  # type: ignore
        """Return ATR for T2 NFC card."""
        # Simplified ATR for NFC Type 2 card
        return bytes(
            [
                0x3B,
                0x8F,
                0x80,
                0x01,
                0x80,
                0x4F,
                0x0C,
                0xA0,
                0x00,
                0x00,
                0x03,
                0x06,
                0x03,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x00,
                0x68,
            ]
        )

    def execute(self, msg):  # type: ignore
        """Process APDU commands for T2 NFC card."""
        if len(msg) < 4:
            return bytes([0x6F, 0x00])  # Wrong length

        cla, ins, p1, p2 = msg[:4]
        lc = msg[4] if len(msg) > 4 else 0

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


class VirtualCardEmulator:
    """Manages virtual smart card emulation for testing."""

    def __init__(self):
        self.vicc = None
        self.vicc_thread = None
        self._stop_event = threading.Event()

    def start_emulation(self, ndef_data=None):
        """Start virtual card emulation with T2 NFC card containing NDEF data."""
        try:
            # Create T2 NFC card OS with NDEF data
            card_os = T2NFCCardOS(ndef_data)

            # Create virtual ICC
            self.vicc = VirtualICC("", "iso7816", "localhost", 35963)
            self.vicc.os = card_os

            # Create stop event for clean shutdown
            self._stop_event = threading.Event()

            # Start virtual ICC in a separate thread
            self.vicc_thread = threading.Thread(target=self._run_vicc, daemon=True)
            self.vicc_thread.start()

            time.sleep(2)  # Give vicc time to start and connect

            return True
        except Exception as e:
            logger.error(f"Failed to start emulation: {e}")
            self.stop_emulation()
            return False

    def _run_vicc(self):
        """Run the virtual ICC in a thread."""
        if not self.vicc:
            raise RuntimeError("Virtual ICC not initialized")

        try:
            self.vicc.run()
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"VICC error: {e}")

    def stop_emulation(self):
        """Stop virtual card emulation."""
        if self._stop_event:
            self._stop_event.set()

        if self.vicc:
            self.vicc.stop()
            self.vicc = None

        if self.vicc_thread and self.vicc_thread.is_alive():
            self.vicc_thread.join(timeout=2)
            self.vicc_thread = None


def create_test_ndef_data():
    """Create test NDEF data for a Type 2 NFC tag."""
    # Home Assistant URL record
    url = "www.home-assistant.io/tag/test123"

    # NDEF record: URI record with HTTP/HTTPS identifier
    ndef_record = bytes(
        [
            0xD1,  # Header: MB=1, ME=1, CF=0, SR=1, IL=0, TNF=1 (Well-known)
            0x01,  # Type length = 1
            len(url) + 1,  # Payload length
            0x55,  # Type: 'U' (URI)
            0x04,  # URI identifier: "https://"
        ]
    ) + url.encode("utf-8")

    return ndef_record


def test_nfc_reader_integration(mqtt_broker, mqtt_client, virtual_card_emulator):
    """Test the full NFC reader integration with MQTT."""
    logger.info("Testing full NFC reader integration with MQTT...")

    # Create test NDEF data
    test_ndef = create_test_ndef_data()

    # Start virtual card emulation
    if not virtual_card_emulator.start_emulation(test_ndef):
        pytest.fail("Failed to start card emulation")

    # Start the NFC reader in a thread
    logger.info("Starting NFC reader thread...")
    nfc_reader_thread = threading.Thread(target=nfc_reader.main, daemon=True)
    nfc_reader_thread.start()

    # Give NFC reader time to start and detect the card
    time.sleep(8)

    # Check if MQTT messages were received
    logger.info("Checking for MQTT messages...")

    # Assert that we received MQTT messages
    assert mqtt_client.received_messages, "No MQTT messages received from NFC reader"

    logger.info("✓ MQTT messages received from NFC reader")

    # Check the received messages
    tag_detected = False
    for msg in mqtt_client.received_messages:
        logger.info(f"  Topic: {msg['topic']}")
        logger.info(f"  Payload: {msg['payload']}")

        # Verify we got the expected tag data
        if "state" in msg["topic"] and "tag_id" in msg["payload"]:
            tag_id = msg["payload"]["tag_id"]
            if tag_id and "test123" in tag_id:
                logger.info(
                    "✓ Test PASSED: NFC reader correctly detected Home Assistant tag"
                )
                tag_detected = True
                break

    # Assert that we detected the expected tag
    assert tag_detected, "Expected Home Assistant tag with 'test123' not detected"


def setup_pcsc_environment():
    """Set up PC/SC environment for testing."""
    logger.info("Setting up PC/SC environment...")

    # Check if pcscd is already running
    result = subprocess.run(["pgrep", "pcscd"], capture_output=True)
    if result.returncode == 0:
        logger.info("✓ PC/SC daemon already running")
        return True

    # Start pcscd
    try:
        subprocess.run(["sudo", "pcscd"], check=True, timeout=10)
        logger.info("✓ PC/SC daemon started")
        time.sleep(1)  # Give pcscd time to initialize
        return True
    except subprocess.TimeoutExpired:
        logger.info("✓ PC/SC daemon started (backgrounded)")
        return True
