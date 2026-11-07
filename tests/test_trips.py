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
  assert ok.json()['cover_url'] == f'/api/v1/trips/{trip_id}/cover'
  assert ok.json()['cover_path'] is not None
  assert len(storage.objects) == 1

  cover = await client.get(f'/api/v1/trips/{trip_id}/cover', headers=headers)
  assert cover.status_code == 200
  assert cover.headers['content-type'] == 'image/jpeg'

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


async def test_public_published_cover_is_anonymous(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='public-cover@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json={
      'name': 'Public cover',
      'start_date': '2026-07-01',
      'end_date': '2026-07-03',
      'pace': 'balanced',
      'visibility': 'public',
    },
  )
  trip_id = created.json()['id']
  await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=headers,
    files={'file': ('cover.jpg', b'\xff\xd8\xff' + b'1' * 100, 'image/jpeg')},
  )
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)

  anonymous = await client.get(f'/api/v1/trips/{trip_id}/cover')
  assert anonymous.status_code == 200
  detail = await client.get(f'/api/v1/trips/{trip_id}')
  assert detail.status_code == 200
  assert detail.json()['visibility'] == 'public'


async def test_private_cover_requires_membership(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='private-cover@example.com')
  stranger = await make_user(email='stranger-cover@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json={
      'name': 'Private cover',
      'start_date': '2026-08-01',
      'end_date': '2026-08-03',
      'pace': 'active',
      'visibility': 'private',
    },
  )
  trip_id = created.json()['id']
  await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=headers,
    files={'file': ('cover.jpg', b'\xff\xd8\xff' + b'2' * 100, 'image/jpeg')},
  )
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)

  anonymous = await client.get(f'/api/v1/trips/{trip_id}/cover')
  assert anonymous.status_code == 404
  other = await client.get(
    f'/api/v1/trips/{trip_id}/cover',
    headers=_auth_header(stranger.id),
  )
  assert other.status_code == 404


async def test_member_can_view_private_trip(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='owner-member@example.com')
  invitee = await make_user(email='invitee-member@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json={
      'name': 'Shared',
      'start_date': '2026-09-01',
      'end_date': '2026-09-03',
      'pace': 'relaxed',
      'visibility': 'private',
    },
  )
  trip_id = created.json()['id']
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)

  added = await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'invitee-member@example.com'},
  )
  assert added.status_code == 201
  assert added.json()['role'] == 'member'

  viewed = await client.get(
    f'/api/v1/trips/{trip_id}',
    headers=_auth_header(invitee.id),
  )
  assert viewed.status_code == 200

  listed = await client.get(
    '/api/v1/trips',
    headers=_auth_header(invitee.id),
  )
  assert listed.status_code == 200
  assert listed.json()['total'] == 1


async def test_cannot_remove_owner(client: AsyncClient, make_user) -> None:
  owner = await make_user(email='owner-remove@example.com')
  headers = _auth_header(owner.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  trip_id = created.json()['id']
  response = await client.delete(
    f'/api/v1/trips/{trip_id}/members/{owner.id}',
    headers=headers,
  )
  assert response.status_code == 400
  assert (
    response.json()['detail'] == TripMessages.CANNOT_REMOVE_OWNER.model_dump()
  )


def _publishable_trip_payload(**overrides: object) -> dict:
  payload: dict = {
    'name': 'Shared trip',
    'start_date': '2027-10-01',
    'end_date': '2027-10-03',
    'pace': 'balanced',
    'visibility': 'private',
  }
  payload.update(overrides)
  return payload


async def test_create_defaults_private_and_owner_membership(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='default-owner@example.com')
  headers = _auth_header(owner.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  assert created.status_code == 201
  trip = created.json()
  assert trip['visibility'] == 'private'
  trip_id = trip['id']

  members = await client.get(
    f'/api/v1/trips/{trip_id}/members', headers=headers
  )
  assert members.status_code == 200
  items = members.json()['items']
  assert len(items) == 1
  assert items[0]['user_id'] == str(owner.id)
  assert items[0]['role'] == 'owner'
  assert items[0]['email'] == 'default-owner@example.com'


async def test_update_visibility_and_anonymous_public_read(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='visibility-update@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(visibility='private'),
  )
  trip_id = created.json()['id']
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)

  anonymous_private = await client.get(f'/api/v1/trips/{trip_id}')
  assert anonymous_private.status_code == 404

  updated = await client.patch(
    f'/api/v1/trips/{trip_id}',
    headers=headers,
    json={'visibility': 'public'},
  )
  assert updated.status_code == 200
  assert updated.json()['visibility'] == 'public'

  anonymous_public = await client.get(f'/api/v1/trips/{trip_id}')
  assert anonymous_public.status_code == 200
  assert anonymous_public.json()['visibility'] == 'public'


async def test_draft_stays_private_even_when_visibility_public(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='draft-public@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(visibility='public'),
  )
  trip_id = created.json()['id']
  assert created.json()['lifecycle'] == 'draft'
  assert created.json()['visibility'] == 'public'

  anonymous = await client.get(f'/api/v1/trips/{trip_id}')
  assert anonymous.status_code == 404
  anonymous_cover = await client.get(f'/api/v1/trips/{trip_id}/cover')
  assert anonymous_cover.status_code == 404


async def test_member_can_view_and_stream_private_cover(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='cover-owner@example.com')
  invitee = await make_user(email='cover-invitee@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Cover shared'),
  )
  trip_id = created.json()['id']
  image = b'\xff\xd8\xff' + b'9' * 120
  await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=headers,
    files={'file': ('cover.jpg', image, 'image/jpeg')},
  )
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)
  await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'cover-invitee@example.com'},
  )

  cover = await client.get(
    f'/api/v1/trips/{trip_id}/cover',
    headers=_auth_header(invitee.id),
  )
  assert cover.status_code == 200
  assert cover.headers['content-type'] == 'image/jpeg'
  assert cover.content == image


async def test_member_cannot_mutate_trip_or_cover(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='mutate-owner@example.com')
  invitee = await make_user(email='mutate-invitee@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Read only member'),
  )
  trip_id = created.json()['id']
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)
  await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'mutate-invitee@example.com'},
  )
  member_headers = _auth_header(invitee.id)

  patched = await client.patch(
    f'/api/v1/trips/{trip_id}',
    headers=member_headers,
    json={'name': 'Hacked'},
  )
  assert patched.status_code == 403
  assert patched.json()['detail'] == TripMessages.FORBIDDEN.model_dump()

  upload = await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=member_headers,
    files={'file': ('cover.jpg', b'\xff\xd8\xff' + b'0' * 40, 'image/jpeg')},
  )
  assert upload.status_code == 403

  add = await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=member_headers,
    json={'email': 'mutate-owner@example.com'},
  )
  assert add.status_code == 403


async def test_add_remove_member_lifecycle(
  client: AsyncClient, make_user, session
) -> None:
  owner = await make_user(email='lifecycle-owner@example.com')
  invitee = await make_user(email='lifecycle-invitee@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Lifecycle'),
  )
  trip_id = created.json()['id']
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)

  added = await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'lifecycle-invitee@example.com'},
  )
  assert added.status_code == 201
  member_user_id = added.json()['user_id']

  listed = await client.get(f'/api/v1/trips/{trip_id}/members', headers=headers)
  assert listed.status_code == 200
  roles = {item['role'] for item in listed.json()['items']}
  assert roles == {'owner', 'member'}

  duplicate = await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'lifecycle-invitee@example.com'},
  )
  assert duplicate.status_code == 409
  assert (
    duplicate.json()['detail'] == TripMessages.ALREADY_A_MEMBER.model_dump()
  )

  removed = await client.delete(
    f'/api/v1/trips/{trip_id}/members/{member_user_id}',
    headers=headers,
  )
  assert removed.status_code == 200

  # Shared test session may keep loaded relationships; drop identity map.
  session.expunge_all()

  remaining = await client.get(
    f'/api/v1/trips/{trip_id}/members', headers=headers
  )
  assert remaining.status_code == 200
  assert [item['role'] for item in remaining.json()['items']] == ['owner']

  listed_for_invitee = await client.get(
    '/api/v1/trips',
    headers=_auth_header(invitee.id),
  )
  assert listed_for_invitee.status_code == 200
  assert listed_for_invitee.json()['total'] == 0

  after = await client.get(
    f'/api/v1/trips/{trip_id}',
    headers=_auth_header(invitee.id),
  )
  assert after.status_code == 404


async def test_add_member_unknown_or_unverified_user(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='lookup-owner@example.com')
  await make_user(
    email='unverified@example.com',
    is_email_verified=False,
  )
  headers = _auth_header(owner.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  trip_id = created.json()['id']

  missing = await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'nobody@example.com'},
  )
  assert missing.status_code == 404
  assert missing.json()['detail'] == TripMessages.USER_NOT_FOUND.model_dump()

  unverified = await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'unverified@example.com'},
  )
  assert unverified.status_code == 404
  assert unverified.json()['detail'] == TripMessages.USER_NOT_FOUND.model_dump()


async def test_cover_missing_and_stranger_members_list(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='missing-cover@example.com')
  stranger = await make_user(email='missing-stranger@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='No cover'),
  )
  trip_id = created.json()['id']
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)

  missing = await client.get(f'/api/v1/trips/{trip_id}/cover', headers=headers)
  assert missing.status_code == 404
  assert missing.json()['detail'] == TripMessages.COVER_NOT_FOUND.model_dump()

  stranger_members = await client.get(
    f'/api/v1/trips/{trip_id}/members',
    headers=_auth_header(stranger.id),
  )
  assert stranger_members.status_code == 404


async def test_remove_unknown_member(client: AsyncClient, make_user) -> None:
  owner = await make_user(email='unknown-member-owner@example.com')
  headers = _auth_header(owner.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  trip_id = created.json()['id']

  response = await client.delete(
    f'/api/v1/trips/{trip_id}/members/{uuid4()}',
    headers=headers,
  )
  assert response.status_code == 404
  assert response.json()['detail'] == TripMessages.MEMBER_NOT_FOUND.model_dump()


async def test_publish_validation_requires_fields(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='publish-validation@example.com')
  headers = _auth_header(user.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  trip_id = created.json()['id']

  response = await client.post(
    f'/api/v1/trips/{trip_id}/publish', headers=headers
  )
  assert response.status_code == 400
  assert (
    response.json()['detail']
    == TripMessages.PUBLISH_VALIDATION_FAILED.model_dump()
  )


async def test_cannot_mutate_deleted_trip(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='deleted-mutate@example.com')
  headers = _auth_header(user.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Soon deleted'),
  )
  trip_id = created.json()['id']
  await client.delete(f'/api/v1/trips/{trip_id}', headers=headers)

  patched = await client.patch(
    f'/api/v1/trips/{trip_id}',
    headers=headers,
    json={'name': 'Nope'},
  )
  assert patched.status_code in {404, 409}

  cover = await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=headers,
    files={'file': ('cover.jpg', b'\xff\xd8\xff' + b'0' * 40, 'image/jpeg')},
  )
  assert cover.status_code in {404, 409}


async def test_restore_requires_deleted_trip(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='restore-active@example.com')
  headers = _auth_header(user.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  trip_id = created.json()['id']

  response = await client.post(
    f'/api/v1/trips/{trip_id}/restore', headers=headers
  )
  assert response.status_code == 409
  assert response.json()['detail'] == TripMessages.TRIP_NOT_DELETED.model_dump()


async def test_cover_rejects_oversized_and_unsupported_types(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='cover-limits@example.com')
  headers = _auth_header(user.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  trip_id = created.json()['id']

  oversized = await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=headers,
    files={
      'file': (
        'big.jpg',
        b'\xff\xd8\xff' + b'0' * (2 * 1024 * 1024 + 10),
        'image/jpeg',
      )
    },
  )
  assert oversized.status_code == 400
  assert oversized.json()['detail'] == TripMessages.INVALID_COVER.model_dump()

  png_ok = await client.post(
    f'/api/v1/trips/{trip_id}/cover',
    headers=headers,
    files={
      'file': (
        'cover.png',
        b'\x89PNG\r\n\x1a\n' + b'1' * 40,
        'image/png',
      )
    },
  )
  assert png_ok.status_code == 200
  assert png_ok.json()['cover_url'] == f'/api/v1/trips/{trip_id}/cover'


async def test_activity_time_validation_and_crud(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='activity-crud@example.com')
  headers = _auth_header(user.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Activity trip'),
  )
  trip_id = created.json()['id']

  bad_time = await client.post(
    f'/api/v1/trips/{trip_id}/activities',
    headers=headers,
    json={
      'title': 'Bad',
      'activity_date': '2027-10-01',
      'activity_type': 'meal',
      'start_minute': 600,
      'end_minute': 600,
      'note': '',
    },
  )
  assert bad_time.status_code == 400
  assert (
    bad_time.json()['detail'] == TripMessages.INVALID_ACTIVITY_TIME.model_dump()
  )

  created_activity = await client.post(
    f'/api/v1/trips/{trip_id}/activities',
    headers=headers,
    json={
      'title': 'Breakfast',
      'activity_date': '2027-10-01',
      'activity_type': 'meal',
      'start_minute': 480,
      'end_minute': 540,
      'note': 'Cafe',
    },
  )
  assert created_activity.status_code == 201
  activity_id = created_activity.json()['id']

  updated = await client.patch(
    f'/api/v1/trips/{trip_id}/activities/{activity_id}',
    headers=headers,
    json={'title': 'Brunch', 'note': 'Updated'},
  )
  assert updated.status_code == 200
  assert updated.json()['title'] == 'Brunch'

  deleted = await client.delete(
    f'/api/v1/trips/{trip_id}/activities/{activity_id}',
    headers=headers,
  )
  assert deleted.status_code == 200

  detail = await client.get(f'/api/v1/trips/{trip_id}', headers=headers)
  assert detail.status_code == 200
  assert detail.json()['activities'] == []

  restored = await client.post(
    f'/api/v1/trips/{trip_id}/activities/{activity_id}/restore',
    headers=headers,
  )
  assert restored.status_code == 200
  assert restored.json()['title'] == 'Brunch'

  restore_again = await client.post(
    f'/api/v1/trips/{trip_id}/activities/{activity_id}/restore',
    headers=headers,
  )
  assert restore_again.status_code == 409
  assert (
    restore_again.json()['detail']
    == TripMessages.ACTIVITY_NOT_DELETED.model_dump()
  )


async def test_get_draft_and_list_status_filters(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='draft-filters@example.com')
  headers = _auth_header(user.id)

  missing = await client.get('/api/v1/trips/draft', headers=headers)
  assert missing.status_code == 404

  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Upcoming filter'),
  )
  trip_id = created.json()['id']
  draft = await client.get('/api/v1/trips/draft', headers=headers)
  assert draft.status_code == 200
  assert draft.json()['id'] == trip_id

  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)

  upcoming = await client.get(
    '/api/v1/trips', headers=headers, params={'status': 'upcoming'}
  )
  assert upcoming.status_code == 200
  assert upcoming.json()['total'] == 1

  past = await client.get(
    '/api/v1/trips', headers=headers, params={'status': 'past'}
  )
  assert past.status_code == 200
  assert past.json()['total'] == 0


async def test_member_cannot_delete_or_restore_trip(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='member-delete-owner@example.com')
  member = await make_user(email='member-delete-user@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Protected'),
  )
  trip_id = created.json()['id']
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)
  await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'member-delete-user@example.com'},
  )

  deleted = await client.delete(
    f'/api/v1/trips/{trip_id}',
    headers=_auth_header(member.id),
  )
  assert deleted.status_code == 403


async def test_inactive_user_cannot_be_added_as_member(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='inactive-owner@example.com')
  await make_user(email='inactive-member@example.com', is_active=False)
  headers = _auth_header(owner.id)
  created = await client.post('/api/v1/trips', headers=headers, json={})
  trip_id = created.json()['id']

  response = await client.post(
    f'/api/v1/trips/{trip_id}/members',
    headers=headers,
    json={'email': 'inactive-member@example.com'},
  )
  assert response.status_code == 404
  assert response.json()['detail'] == TripMessages.USER_NOT_FOUND.model_dump()


async def test_update_trip_fields_and_note(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='update-fields@example.com')
  headers = _auth_header(user.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Original'),
  )
  trip_id = created.json()['id']

  updated = await client.patch(
    f'/api/v1/trips/{trip_id}',
    headers=headers,
    json={
      'name': 'Renamed',
      'destination': 'Hanoi',
      'description': 'Updated desc',
      'note': 'Bring cash',
      'visibility': 'public',
      'pace': 'active',
    },
  )
  assert updated.status_code == 200
  body = updated.json()
  assert body['name'] == 'Renamed'
  assert body['destination'] == 'Hanoi'
  assert body['note'] == 'Bring cash'
  assert body['visibility'] == 'public'
  assert body['pace'] == 'active'


async def test_stranger_cannot_list_private_trip(
  client: AsyncClient, make_user
) -> None:
  owner = await make_user(email='list-owner@example.com')
  stranger = await make_user(email='list-stranger@example.com')
  headers = _auth_header(owner.id)
  created = await client.post(
    '/api/v1/trips',
    headers=headers,
    json=_publishable_trip_payload(name='Hidden list'),
  )
  trip_id = created.json()['id']
  await client.post(f'/api/v1/trips/{trip_id}/publish', headers=headers)

  listed = await client.get('/api/v1/trips', headers=_auth_header(stranger.id))
  assert listed.status_code == 200
  assert listed.json()['total'] == 0
  assert all(item['id'] != trip_id for item in listed.json()['items'])
