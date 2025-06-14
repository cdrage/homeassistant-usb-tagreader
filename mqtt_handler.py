#!/usr/bin/python3
"""MQTT handler for NFC tag reader Home Assistant integration"""

import json
import logging
import os
import time
from typing import Optional
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.reasoncodes import ReasonCode
from paho.mqtt.properties import Properties
from typing import Any

# MQTT Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "nfc_tag_reader")
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "homeassistant/sensor/nfc_reader")
MQTT_DISCOVERY_TOPIC = f"{MQTT_TOPIC_PREFIX}/config"
MQTT_STATE_TOPIC = f"{MQTT_TOPIC_PREFIX}/state"

logger = logging.getLogger(__name__)


class MQTTHandler:
    """Handle MQTT communication for Home Assistant integration"""

    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.current_tag_id: Optional[str] = None
        self.connected = False

    def setup(self) -> bool:
        """Setup MQTT client and publish Home Assistant discovery configuration"""
        if not MQTT_BROKER:
            logger.warning("MQTT_BROKER not configured, skipping MQTT setup")
            return False

        try:
            # Create MQTT client
            self.client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=MQTT_CLIENT_ID,
            )

            # Set username and password if provided
            if MQTT_USERNAME and MQTT_PASSWORD:
                self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

            # Set callback functions
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish

            # Connect to broker
            logger.info("Connecting to MQTT broker: %s:%d", MQTT_BROKER, MQTT_PORT)
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)

            # Start the network loop in a separate thread
            self.client.loop_start()

            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to setup MQTT: %s", e)
            return False

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        rc: ReasonCode,
        properties: Optional[Properties],
    ) -> None:
        """Callback for when MQTT client connects"""
        if rc.value == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            self._publish_ha_discovery()
            self.publish_tag_state(None)  # Initial state: no tag present
        else:
            self.connected = False
            logger.error("Failed to connect to MQTT broker, return code %d", rc.value)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.DisconnectFlags,
        rc: ReasonCode,
        properties: Optional[Properties],
    ) -> None:
        """Callback for when MQTT client disconnects"""
        self.connected = False
        if rc.value != 0:
            logger.warning("Unexpected MQTT disconnection")
        else:
            logger.info("MQTT client disconnected")

    def _on_publish(
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_code: ReasonCode,
        properties: Properties,
    ) -> None:
        """Callback for when a message is published"""
        logger.debug("MQTT message published, mid: %d", mid)

    def _publish_ha_discovery(self):
        """Publish Home Assistant MQTT discovery configuration"""
        if not self.client or not self.connected:
            logger.debug("Skipping HA discovery publish - MQTT not connected")
            return

        discovery_config = {
            "name": "NFC Reader Current Tag",
            "unique_id": "nfc_reader_current_tag",
            "state_topic": MQTT_STATE_TOPIC,
            "value_template": "{{ value_json.tag_id }}",
            "json_attributes_topic": MQTT_STATE_TOPIC,
            "device": {
                "identifiers": ["nfc_tag_reader"],
                "name": "NFC Tag Reader",
                "model": "Python NFC Reader",
                "manufacturer": "Custom",
            },
            "icon": "mdi:nfc-variant",
        }

        try:
            payload = json.dumps(discovery_config)
            result = self.client.publish(MQTT_DISCOVERY_TOPIC, payload, retain=True)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info("Published Home Assistant discovery configuration")
            else:
                logger.error(
                    "Failed to publish discovery configuration, rc: %d", result.rc
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error publishing discovery configuration: %s", e)

    def publish_tag_state(self, tag_id: Optional[str]):
        """Publish current tag state to MQTT"""
        if not self.client or not self.connected:
            logger.debug(
                "Skipping tag state publish - MQTT not connected (tag_id: %s)", tag_id
            )
            return

        self.current_tag_id = tag_id

        state_data = {
            "tag_id": tag_id,
            "present": tag_id is not None,
            "timestamp": time.time(),
        }

        try:
            payload = json.dumps(state_data)
            result = self.client.publish(MQTT_STATE_TOPIC, payload, retain=True)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(
                    "Published tag state: %s", "present" if tag_id else "absent"
                )
                if tag_id:
                    logger.info("Current tag ID: %s", tag_id)
            else:
                logger.error("Failed to publish tag state, rc: %d", result.rc)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error publishing tag state: %s", e)

    def cleanup(self):
        """Cleanup MQTT client"""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("MQTT client disconnected and cleaned up")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Error cleaning up MQTT: %s", e)
            finally:
                self.client = None
                self.connected = False
