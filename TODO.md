# TODO (Tusky Compatibility)

This file tracks work items for maximizing Mastodon client compatibility,
prioritizing Tusky.

How to use:
- Keep tasks small and check them off as they land.
- Prefer linking to a PR/commit in the checkbox line when done.
- Add brief notes under a task only when it helps (e.g., endpoints involved).

## Now (High Priority)

- [x] Mentions + hashtags parsing in status create/edit
  - Populate `mentions` and `tags` in `utils/serializers.py`
  - Extract `@user@domain` and `#tag` from HTML/plain text; keep safe + minimal
- [x] Notifications: support common Tusky flows
  - Verify list + pagination + unread count behave like Mastodon
  - Add optional `?exclude_types[]` and `?types[]` behavior parity (already partially)
  - Ensure dismiss/clear endpoints return expected JSON shapes
- [x] Status source text: ensure Tusky “delete and redraft” works
  - Confirm `/api/v1/statuses/:id/source` and delete response include the right plain text
  - Consider storing a separate `text`/`source` if current HTML causes issues
- [x] Media UX parity (image thumbnails)
  - Generate thumbnails for images (and basic poster/preview for videos if feasible)
  - Ensure `meta` fields (width/height/aspect) are present and correct
- [x] Fix/align error responses for common client expectations (invalid IDs)
  - Standardize 401/404/422 response shapes across endpoints
  - Ensure invalid IDs return JSON error, not 500

## Done

- [x] Add a minimal `unittest` test suite scaffold
- [x] Report effectively unlimited `max_characters` in `/api/v1/instance` when `MAX_STATUS_LENGTH=0`

## Next (Medium Priority)

- [x] Account fields that clients display (local counts)
  - Add stable `followers_count`, `following_count`, `statuses_count` for local + remote where possible
  - Ensure `verify_credentials` and `update_credentials` match Mastodon fields
- [ ] Status visibility + direct messages
  - Verify `public/unlisted/private/direct` behavior; direct can be stubbed but consistent
  - Ensure timelines respect visibility
- [ ] Timeline parity
  - Public timeline: handle `local`, `only_media`, pagination, and muted/blocked exclusions consistently
  - Home timeline: verify it includes local posts + followed remote posts, excludes reblogs where appropriate
- [ ] Filters/lists/trends stubs: confirm they don’t break clients
  - Keep stubs returning valid empty shapes and correct status codes
- [ ] Instance metadata
  - Confirm `/api/v1/instance`, `/api/v2/instance`, nodeinfo, webfinger
  - Ensure `max_characters` etc. match `config.py` limits

## Later (Low Priority)

- [ ] Bookmarks/favourites listing pagination
- [ ] Streaming API (Tusky can run without it; optional)
- [ ] Polls (currently stubbed)
- [ ] Push notifications (currently stubbed)
- [ ] More complete federation bookkeeping (reblogs/likes/undo correctness)

## Acceptance Checklist (Tusky)

- [ ] App registration + OAuth flow succeeds end-to-end
- [ ] Home + public timeline load without errors
- [ ] Compose: post text + CW + language + media attachments
- [ ] Edit + delete + delete-and-redraft behave sensibly
- [ ] Favourite + reblog + bookmark actions work
- [ ] Notifications list + unread count behave
- [ ] Search accounts + statuses returns valid shapes

## Quick Smoke Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python setup.py
python wsgi.py
```

Suggested manual checks (while server runs):
- `/.well-known/webfinger`
- `/api/v1/instance`
- `/api/v1/timelines/public`
