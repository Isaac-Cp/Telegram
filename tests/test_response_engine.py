import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.services.response_engine import ResponseEngine
from app.models.lead import Lead

@pytest.fixture
def response_engine():
    return ResponseEngine()

@pytest.fixture
def mock_lead():
    lead = MagicMock(spec=Lead)
    lead.id = "test-lead-id"
    lead.message_text = "I need a new IPTV provider, mine is buffering too much."
    lead.user_id = "test-user-id"
    lead.group_id = "test-group-id"
    return lead

@pytest.mark.asyncio
async def test_generate_public_response(response_engine, mock_lead):
    persona = {
        "name": "Aiden",
        "role": "Expert",
        "expertise": "IPTV",
        "tone": "Professional"
    }
    
    with patch('app.services.ai_service.ai_service.chat_completion', return_value="This is a test response."):
        response = await response_engine.generate_public_response(mock_lead.id, mock_lead.message_text, persona)
        assert "test response" in response.lower()
        assert len(response) > 0

@pytest.mark.asyncio
async def test_generate_private_dm(response_engine, mock_lead):
    with patch('app.services.ai_service.ai_service.chat_completion', return_value="Hello, I saw your message about IPTV."):
        with patch('app.services.power_upgrades.power_upgrades_service.select_persona', return_value={"name": "Luca", "role": "Engineer", "expertise": "Network", "tone": "Direct"}):
            response = await response_engine.generate_private_dm(mock_lead)
            assert "hello" in response.lower()
            assert len(response) > 0

def test_within_natural_active_hours(response_engine):
    # This might depend on the current time, so we might need to mock datetime
    with patch('app.services.human_engine.human_engine.is_within_natural_active_hours', return_value=True):
        assert response_engine.is_within_natural_active_hours() is True
