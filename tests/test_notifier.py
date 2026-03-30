import pytest
from unittest.mock import MagicMock
from oracle_arm_manager.notifier import LineNotifier, TelegramNotifier, DiscordNotifier, NotificationError

def test_line_notifier_skip_without_token(mocker):
    mocker.patch("os.getenv", return_value=None)
    mock_post = mocker.patch("requests.Session.post")
    
    notifier = LineNotifier()
    notifier.send("Title", "Content")
    assert mock_post.call_count == 0

def test_telegram_notifier_payload(mocker):
    mocker.patch("os.getenv", side_effect=lambda k: "id123" if k == "TELEGRAM_CHAT_ID" else "tok456" if k == "TELEGRAM_BOT_TOKEN" else None)
    mock_post = mocker.patch("requests.Session.post")
    mock_post.return_value.status_code = 200
    
    notifier = TelegramNotifier()
    notifier.send("Hello", "World", is_success=True)
    
    # Check payload
    args, kwargs = mock_post.call_args
    assert "id123" in kwargs["json"]["chat_id"]
    assert "🟢 *Hello*" in kwargs["json"]["text"]

def test_notifier_retry_logic(mocker):
    # This is harder to test without deep internal mocking, but we can check if it throws/logs
    mocker.patch("os.getenv", return_value="webhook_url")
    mock_post = mocker.patch("requests.Session.post", side_effect=Exception("Network Error"))
    
    notifier = DiscordNotifier()
    with pytest.raises(NotificationError):
        notifier.send("Title", "Content")
    
    # session.post should have been called exactly once before throwing (requests internally handles retries if configured via Adapter)
    assert mock_post.call_count == 1
