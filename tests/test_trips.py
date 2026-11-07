from datetime import date, timedelta
from uuid import uuid4

from httpx import AsyncClient

from app.trips.messages import TripMessages
from tests.helpers import encode_access_token


def _auth_header(user_id) -> dict[str, str]:
  return {'Authorization': f'Bearer {encode_access_token(user_id=user_id)}'}


async def test_create_list_get_and_publish_trip(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='trips@example.com')
  headers = _auth_header(user.id)

  create = await client.post(
    '/api/v1/trips',
    headers=headers,
    json={
      'name': 'Tokyo Spring',
      'destination': 'Tokyo',
      'description': 'Cherry blossoms',
      'start_date': '2026-04-01',
      'end_date': '2026-04-05',
      'pace': 'balanced',
      'timezone': 'Asia/Tokyo',
      'note': 'Pack light',
    },
  )
  assert create.status_code == 201
  trip = create.json()
  assert trip['lifecycle'] == 'draft'
  assert trip['start_date'] == '2026-04-01'
  assert trip['created_at'].endswith('Z')
  trip_id = trip['id']

  listed = await client.get('/api/v1/trips', headers=headers)
  assert listed.status_code == 200
  body = listed.json()
  assert body['total'] == 1
  assert body['items'][0]['id'] == trip_id

  detail = await client.get(f'/api/v1/trips/{trip_id}', headers=headers)
  assert detail.status_code == 200
  assert detail.json()['note'] == 'Pack light'

  activity = await client.post(
    f'/api/v1/trips/{trip_id}/activities',
    headers=headers,
    json={
      'title': 'Senso-ji',
      'activity_date': '2026-04-02',
      'activity_type': 'explore',
      'start_minute': 600,
      'end_minute': 720,
      'note': '',
    },
  )
  assert activity.status_code == 201
  assert activity.json()['start_minute'] == 600

  published = await client.post(
    f'/api/v1/trips/{trip_id}/publish',
    headers=headers,
  )
  assert published.status_code == 200
  assert published.json()['lifecycle'] == 'published'
  assert published.json()['published_at'].endswith('Z')


async def test_soft_delete_and_restore(client: AsyncClient, make_user) -> None:
  user = await make_user(email='delete@example.com')
  headers = _auth_header(user.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json={
      'name': 'Da Nang',
      'start_date': '2026-12-01',
      'end_date': '2026-12-03',
      'pace': 'relaxed',
    },
  )
  trip_id = created.json()['id']

  deleted = await client.delete(f'/api/v1/trips/{trip_id}', headers=headers)
  assert deleted.status_code == 200

  missing = await client.get(f'/api/v1/trips/{trip_id}', headers=headers)
  assert missing.status_code == 404

  trash = await client.get('/api/v1/trips/deleted', headers=headers)
  assert trash.status_code == 200
  assert trash.json()['total'] == 1

  restored = await client.post(
    f'/api/v1/trips/{trip_id}/restore', headers=headers
  )
  assert restored.status_code == 200
  assert restored.json()['deleted_at'] is None


async def test_cover_upload_and_validation(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='cover@example.com')
  headers = _auth_header(user.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  trip_id = created.json()['id']
  storage = client.storage  # type: ignore[attr-defined]

  bad = await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=headers,
    files={'file': ('x.gif', b'not-an-image', 'image/gif')},
  )
  assert bad.status_code == 400
  assert bad.json()['detail'] == TripMessages.INVALID_COVER.model_dump()

  ok = await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=headers,
    files={'file': ('cover.jpg', b'\xff\xd8\xff' + b'0' * 100, 'image/jpeg')},
  )
  assert ok.status_code == 200
  assert ok.json()['cover_url'] is not None
  assert ok.json()['cover_path'] is not None
  assert len(storage.objects) == 1

  cleared = await client.delete(
    f'/api/v1/trips/{trip_id}/cover', headers=headers
  )
  assert cleared.status_code == 200
  assert cleared.json()['cover_url'] is None
  assert len(storage.objects) == 0


async def test_ownership_isolation(client: AsyncClient, make_user) -> None:
  owner = await make_user(email='owner@example.com')
  other = await make_user(email='other@example.com')
  created = await client.post(
    '/api/v1/trips',
    headers=_auth_header(owner.id),
    json={'name': 'Private'},
  )
  trip_id = created.json()['id']

  response = await client.get(
    f'/api/v1/trips/{trip_id}',
    headers=_auth_header(other.id),
  )
  assert response.status_code == 404


async def test_invalid_date_range(client: AsyncClient, make_user) -> None:
  user = await make_user(email='dates@example.com')
  response = await client.post(
    '/api/v1/trips',
    headers=_auth_header(user.id),
    json={
      'start_date': '2026-05-10',
      'end_date': '2026-05-01',
    },
  )
  assert response.status_code == 400
  assert (
    response.json()['detail'] == TripMessages.INVALID_TRIP_DATES.model_dump()
  )


async def test_one_active_draft_per_user(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='drafts@example.com')
  headers = _auth_header(user.id)
  first = await client.post('/api/v1/trips', headers=headers, json={})
  assert first.status_code == 201
  second = await client.post('/api/v1/trips', headers=headers, json={})
  assert second.status_code == 409
  assert (
    second.json()['detail'] == TripMessages.DRAFT_ALREADY_EXISTS.model_dump()
  )


async def test_activity_outside_trip_rejected(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='activity@example.com')
  headers = _auth_header(user.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json={
      'start_date': '2026-06-01',
      'end_date': '2026-06-03',
    },
  )
  trip_id = created.json()['id']
  response = await client.post(
    f'/api/v1/trips/{trip_id}/activities',
    headers=headers,
    json={
      'title': 'Too late',
      'activity_date': '2026-06-10',
      'activity_type': 'meal',
      'start_minute': 0,
      'end_minute': 60,
      'note': '',
    },
  )
  assert response.status_code == 400
  assert (
    response.json()['detail'] == TripMessages.ACTIVITY_OUTSIDE_TRIP.model_dump()
  )


async def test_requires_auth(client: AsyncClient) -> None:
  response = await client.get('/api/v1/trips')
  assert response.status_code == 401


async def test_past_filter_uses_end_date(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='status@example.com')
  headers = _auth_header(user.id)
  past_end = (date.today() - timedelta(days=3)).isoformat()
  past_start = (date.today() - timedelta(days=5)).isoformat()
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json={
      'name': 'Past trip',
      'start_date': past_start,
      'end_date': past_end,
      'pace': 'active',
    },
  )
  assert created.status_code == 201
  await client.post(
    f'/api/v1/trips/{created.json()["id"]}/publish',
    headers=headers,
  )

  past = await client.get(
    '/api/v1/trips',
    headers=headers,
    params={'status': 'past'},
  )
  assert past.status_code == 200
  assert past.json()['total'] == 1
  assert past.json()['items'][0]['status'] == 'past'


async def test_foreign_trip_id_not_found(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='missing@example.com')
  response = await client.get(
    f'/api/v1/trips/{uuid4()}',
    headers=_auth_header(user.id),
  )
  assert response.status_code == 404
