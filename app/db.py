import os
import boto3
import uuid
from datetime import datetime
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.getenv("DYNAMODB_TABLE", "playlists")
DYNAMODB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT_URL") or None
REGION = os.getenv("DYNAMODB_REGION", "us-east-1")

if DYNAMODB_ENDPOINT:
    dynamodb = boto3.resource("dynamodb", region_name=REGION, endpoint_url=DYNAMODB_ENDPOINT)
else:
    dynamodb = boto3.resource("dynamodb", region_name=REGION)

table = dynamodb.Table(TABLE_NAME)


def create_playlist(user_id, name, description=""):
    now = datetime.utcnow().isoformat()
    item = {
        "id": str(uuid.uuid4()),
        "userId": user_id,
        "name": name,
        "description": description,
        "tracks": [],
        "createdAt": now,
        "updatedAt": now,
    }
    table.put_item(Item=item)
    return item


def get_playlists_for_user(user_id, genre_filter=None):
    resp = table.query(
        IndexName="userId-index",
        KeyConditionExpression=Key("userId").eq(user_id)
    )
    items = resp.get("Items", [])
    if genre_filter:
        genres = set([g.strip().lower() for g in genre_filter.split(",")])
        for it in items:
            it["tracks"] = [t for t in it.get("tracks", []) if t.get("genre") and t["genre"].lower() in genres]
    return items


def get_playlist(playlist_id):
    resp = table.get_item(Key={"id": playlist_id})
    return resp.get("Item")


def update_playlist(playlist_id, name=None, description=None):
    update_expr = []
    expr_values = {}
    if name:
        update_expr.append("name = :n")
        expr_values[":n"] = name
    if description:
        update_expr.append("description = :d")
        expr_values[":d"] = description

    if not update_expr:
        return get_playlist(playlist_id)

    # always update updatedAt
    update_expr.append("updatedAt = :u")
    expr_values[":u"] = datetime.utcnow().isoformat()

    response = table.update_item(
        Key={"id": playlist_id},
        UpdateExpression="SET " + ", ".join(update_expr),
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW"
    )
    return response.get("Attributes")


def delete_playlist(playlist_id):
    table.delete_item(Key={"id": playlist_id})
    return {"message": "Playlist deleted successfully"}


def add_track(playlist_id, track):
    """
    track = {
        "trackId": "...",
        "title": "...",
        "artist": "...",
        "albumArt": "...",
        "genre": "..."
    }
    """
    playlist = get_playlist(playlist_id)
    if not playlist:
        return None
    tracks = playlist.get("tracks", [])
    tracks.append(track)
    updated = table.update_item(
        Key={"id": playlist_id},
        UpdateExpression="SET tracks = :t, updatedAt = :u",
        ExpressionAttributeValues={
            ":t": tracks,
            ":u": datetime.utcnow().isoformat()
        },
        ReturnValues="ALL_NEW"
    )
    return updated.get("Attributes")


def remove_track(playlist_id, track_id):
    playlist = get_playlist(playlist_id)
    if not playlist:
        return None
    tracks = playlist.get("tracks", [])
    tracks = [t for t in tracks if t.get("trackId") != track_id]
    updated = table.update_item(
        Key={"id": playlist_id},
        UpdateExpression="SET tracks = :t, updatedAt = :u",
        ExpressionAttributeValues={
            ":t": tracks,
            ":u": datetime.utcnow().isoformat()
        },
        ReturnValues="ALL_NEW"
    )
    return updated.get("Attributes")
