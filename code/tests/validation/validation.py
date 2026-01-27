import pytest
import json
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from agents.config import RESERVE_CONFIG

def test_config_integrity():
    """Sprawdza czy granice rezerwatu mają sens."""
    assert RESERVE_CONFIG["X_MAX"] > RESERVE_CONFIG["X_MIN"]
    assert RESERVE_CONFIG["Y_MAX"] > RESERVE_CONFIG["Y_MIN"]
    assert RESERVE_CONFIG["ESCAPE_MARGIN"] >= 0

def test_message_payload_structure():
    """Symuluje walidację JSONa wysyłanego przez sensora."""
    
    payload = {
        "sensor_id": "sensor@localhost",
        "coords": {"x": 50, "y": 50},
        "type": "camera",
        "timestamp": 1234567890,
        "metadata": {"detected_object": "human"}
    }
    
   
    json_str = json.dumps(payload)
    decoded = json.loads(json_str)
    
    
    assert "coords" in decoded
    assert "metadata" in decoded
    assert isinstance(decoded["coords"]["x"], (int, float))