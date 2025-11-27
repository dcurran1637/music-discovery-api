from fastapi import HTTPException

from app import auth


def test_require_write_api_key_missing():
	try:
		auth.require_write_api_key(x_api_key=None)
		assert False, "Expected HTTPException for missing header"
	except HTTPException as e:
		assert e.status_code == 401


def test_require_write_api_key_invalid():
	try:
		auth.require_write_api_key(x_api_key="bad_key")
		assert False, "Expected HTTPException for invalid key"
	except HTTPException as e:
		assert e.status_code == 403


def test_require_write_api_key_success(monkeypatch):
	# ensure default demo key is used
	monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")
	assert auth.require_write_api_key(x_api_key="demo_write_key_123") is True
