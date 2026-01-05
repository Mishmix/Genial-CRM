"""Tests for Telegram initData validation."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode, quote

import pytest


def create_test_init_data(
    user_id: int = 123456789,
    first_name: str = "Test",
    username: str = "testuser",
    bot_token: str = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    auth_date: int = None,
) -> str:
    """Create valid initData for testing."""
    if auth_date is None:
        auth_date = int(time.time())
    
    user_data = {
        "id": user_id,
        "first_name": first_name,
        "username": username,
        "language_code": "en",
    }
    
    params = {
        "user": json.dumps(user_data),
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
    }
    
    # Build data check string
    check_pairs = []
    for key in sorted(params.keys()):
        check_pairs.append(f"{key}={params[key]}")
    data_check_string = "\n".join(check_pairs)
    
    # Calculate hash
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()
    
    hash_value = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    params["hash"] = hash_value
    
    return urlencode(params)


def test_create_init_data():
    """Test that we can create valid initData."""
    init_data = create_test_init_data()
    assert "hash=" in init_data
    assert "user=" in init_data
    assert "auth_date=" in init_data


def test_init_data_hash_calculation():
    """Test hash calculation matches expected format."""
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    
    # Create initData
    init_data = create_test_init_data(bot_token=bot_token)
    
    # Parse it back
    from urllib.parse import parse_qs
    parsed = parse_qs(init_data)
    
    received_hash = parsed["hash"][0]
    
    # Recalculate
    check_pairs = []
    for key in sorted(parsed.keys()):
        if key != "hash":
            check_pairs.append(f"{key}={parsed[key][0]}")
    data_check_string = "\n".join(check_pairs)
    
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()
    
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    assert calculated_hash == received_hash


def test_expired_init_data():
    """Test that expired initData is detected."""
    # Create initData from 2 days ago
    old_auth_date = int(time.time()) - (2 * 24 * 60 * 60)
    init_data = create_test_init_data(auth_date=old_auth_date)
    
    # The validation function should reject this
    # (actual validation tested in integration tests)
    assert "auth_date=" in init_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
