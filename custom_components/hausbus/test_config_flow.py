import sys
import os

# Pfad zu ~/.homeassistant hinzufügen
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from unittest.mock import MagicMock
sys.modules['custom_components'] = MagicMock()
sys.modules['custom_components.hausbus'] = MagicMock()
sys.modules['custom_components.hausbus.sensor'] = MagicMock()

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from hausbus.const import DOMAIN
from hausbus import config_flow


@pytest.mark.asyncio
async def test_user_flow_success(hass):
    """Testet den erfolgreichen User Config Flow."""
    # ⚠️ Für neuere HA-Versionen muss der async_generator aufgelöst werden
    if hasattr(hass, "__anext__"):
        hass_instance = await hass.__anext__()
    else:
        hass_instance = hass

    # Init Config Flow
    result = await hass_instance.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    user_input = {"host": "127.0.0.1", "port": 1234}

    result2 = await hass_instance.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Hausbus"
    assert result2["data"]["host"] == "127.0.0.1"
    assert result2["data"]["port"] == 1234


@pytest.mark.asyncio
async def test_user_flow_invalid_input(hass: HomeAssistant):
    """Testet den Config Flow mit ungültigen Eingaben."""
    # ⚠️ Für neuere HA-Versionen muss der async_generator aufgelöst werden
    if hasattr(hass, "__anext__"):
        hass_instance = await hass.__anext__()
    else:
        hass_instance = hass

    # Init Config Flow
    result = await hass_instance.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Ungültige Eingaben (Port ist kein Integer)
    user_input = {"host": "127.0.0.1", "port": "nicht-zahl"}

    result2 = await hass_instance.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input
    )

    # Prüfen, dass Fehler zurückgegeben wird
    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert "port" in result2["errors"]