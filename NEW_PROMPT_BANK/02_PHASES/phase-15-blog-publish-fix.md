# PHASE 15 — Blog Publish Fix

## Root Cause
Blog posts can only be published through Django admin UI.
There is no API endpoint to create, update, or publish posts.
The is_published flag is never set via API — it defaults to False and stays False.

## Goal
Expose full blog CRUD (create, update, publish, delete) via admin-protected API endpoints.

## Context
- blog.Post fields: title, slug, content, featured_image, published_at, is_published, created_at
- Existing public endpoints (keep unchanged):
  - GET /api/blog/posts → list published
  - GET /api/blog/posts/{slug} → detail published
- Admin endpoints use AdminBearer (is_staff check) — define it in blog/api.py
- No new model needed

## Deliverables

### blog/schemas.py (update)
Add:
```python
class PostCreateIn(Schema):
    title:           str
    slug:            str
    content:         str
    is_published:    bool = False

class PostUpdateIn(Schema):
    title:        Optional[str] = None
    content:      Optional[str] = None
    is_published: Optional[bool] = None

class PostAdminOut(Schema):
    id:            int
    title:         str
    slug:          str
    content:       str
    is_published:  bool
    published_at:  Optional[datetime] = None
    created_at:    datetime
```

### blog/services.py (update)
Add:
```python
def create_post(title: str, slug: str, content: str, is_published: bool = False) -> Post:
    from django.utils import timezone
    published_at = timezone.now() if is_published else None
    return Post.objects.create(
        title=title, slug=slug, content=content,
        is_published=is_published, published_at=published_at,
    )

def update_post(post_id: int, title: str | None, content: str | None, is_published: bool | None) -> Post:
    from django.utils import timezone
    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        raise NotFoundError(f"Post #{post_id} not found.")
    if title is not None:
        post.title = title
    if content is not None:
        post.content = content
    if is_published is not None:
        post.is_published = is_published
        if is_published and not post.published_at:
            post.published_at = timezone.now()
    post.save()
    return post

def delete_post(post_id: int) -> None:
    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        raise NotFoundError(f"Post #{post_id} not found.")
    post.delete()
```

### blog/api.py (update)
Add AdminBearer class (same pattern as store/api.py AuthBearer, but checks is_staff):
```python
class AdminBearer(HttpBearer):
    def authenticate(self, request, token):
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import TokenError
        try:
            validated = AccessToken(token)
            from accounts.models import User
            user = User.objects.get(pk=validated["user_id"])
            return user if user.is_staff else None
        except Exception:
            return None
```

Add admin router (separate from public router, prefix /admin):
```
admin_router = Router(tags=["Blog Admin"])

POST   /api/blog/admin/posts          → PostCreateIn → PostAdminOut
PATCH  /api/blog/admin/posts/{id}     → PostUpdateIn → PostAdminOut
DELETE /api/blog/admin/posts/{id}     → 204
```

Update config/urls.py:
- Add blog admin sub-router under /blog/admin

### No migration needed for this phase.

## Target Files
- blog/schemas.py
- blog/services.py
- blog/api.py
- config/urls.py

## Acceptance Criteria
- POST /api/blog/admin/posts with is_published=true → 201, post created, published_at set to now
- POST /api/blog/admin/posts with is_published=false → 201, post created, is_published=false
- PATCH /api/blog/admin/posts/1 with {"is_published": true} → 200, published_at filled
- DELETE /api/blog/admin/posts/1 → 204
- All admin endpoints return 401 without valid staff JWT
- GET /api/blog/posts still returns only is_published=true posts
- Swagger shows admin endpoints under "Blog Admin" tag
- No migration required
