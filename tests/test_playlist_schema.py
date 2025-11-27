from pydantic import ValidationError

from app import schemas


def test_playlist_create_happy_path():
    payload = {"name": "Roadtrip Mix", "description": "Songs for long drives"}
    p = schemas.PlaylistCreate(**payload)

    assert p.name == payload["name"]
    assert p.description == payload["description"]


def test_playlist_create_missing_name_raises():
    payload = {"description": "missing name"}
    try:
        schemas.PlaylistCreate(**payload)
        assert False, "Expected ValidationError for missing required field 'name'"
    except ValidationError as e:
        assert "name" in str(e)
