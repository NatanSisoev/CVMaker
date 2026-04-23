# ADR-0004: Custom user model with email as identifier

- **Status:** accepted
- **Date:** 2026-04-22
- **Phase:** 1.5

## Context

Django's default `User` model uses `username` as the login identifier,
inherits from `AbstractUser`, and is wired into `django.contrib.auth`. It
works out of the box — which is exactly why it's dangerous to ship with it.

The Django documentation is blunt:

> If you have an existing project and want to change your user model mid-way,
> it is likely easier to keep your existing one and work around the problem.

Once real users exist, swapping `AUTH_USER_MODEL` is a multi-day migration
involving data copies, FK rewrites, and downtime. The cheap window is now,
pre-launch, with no real data.

Three specific problems with the default:

1. **Username is a poor identifier for a public SaaS.** Users enter their
   email to sign up, expect to log in with email, and get confused when
   asked for a separate username. Email is what password resets key off of;
   making it the primary identifier eliminates an entire category of
   "I forgot my username" support tickets.

2. **No place to hang user-scoped preferences.** Every feature we'll add in
   Phase 2+ (preferred UI language, translation style guide, billing plan
   flag, referrer code) wants a home on the user object. A custom model
   gives us a first-class place to put them without a JSONField-of-shame or
   a separate `Profile` model that doubles every query.

3. **Future-proofing for auth changes.** Phase 6 introduces allauth,
   Phase 7 introduces Stripe customer IDs, Phase 9 considers passkeys.
   Every one of these is cleaner when we own the User class.

## Decision

Replace the default `User` with a custom `accounts.User(AbstractUser)`:

```python
# apps/accounts/models.py
class User(AbstractUser):
    email = models.EmailField(_("email address"), unique=True)
    display_name = models.CharField(max_length=150, blank=True)
    preferred_language = models.CharField(max_length=5, default="en")
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
```

Key choices:

- **`AbstractUser`, not `AbstractBaseUser`.** We want groups, permissions,
  is_staff/is_active/is_superuser, the admin integration, and the password
  reset flow for free. Going down to `AbstractBaseUser` would force us to
  reimplement all of that. We only need to *swap the identifier*.
- **Keep `username` as a non-null, unique field.** Some Django internals
  assume `user.username` exists (e.g. `get_username()` in URLs, `__str__` in
  the admin). We default it from the email's local part at signup and hide
  the field in most UIs. Users can change it later if we want to surface
  human-readable URLs.
- **`USERNAME_FIELD = "email"`.** Email is what `authenticate()` receives,
  what password reset mails to, what `LoginView` checks against.
- **Custom `UserManager`.** `BaseUserManager` can't create users keyed on
  email without overriding `create_user`/`create_superuser`. We do that
  explicitly so `createsuperuser` and fixtures work correctly.
- **All FKs reference `settings.AUTH_USER_MODEL`, not the concrete User
  class.** Prevents the cyclic-import and swapped-model errors that show up
  when you do `from accounts.models import User` in a model file.

`AUTH_USER_MODEL = "accounts.User"` lives in `settings/base.py` and must
never change after first migration.

## Migration plan (Phase 1 one-shot)

1. Delete every existing migration file in `accounts/cv/entries/sections/`.
   None reference real data; they all point at `auth.User` which we're
   swapping out.
2. Drop and recreate the dev database.
3. Run `makemigrations` — generates fresh `0001_initial.py` per app, now
   referencing `accounts.User` everywhere.
4. Run `migrate`.
5. `createsuperuser` to get back into the admin.

All scripted in `scripts/phase1_migrate.ps1`.

## Consequences

### Positive

- Email-based login from day one; no retrofit.
- A home for user-scoped fields without a Profile table.
- Every `FK(settings.AUTH_USER_MODEL)` resolves through Django's swap system,
  so if we ever need to swap again (we won't) there's one lever to pull.
- Admin integration, permissions, password reset, and session auth all keep
  working unchanged.

### Negative

- Requires a database reset. Paid once, during Phase 1, with no real users.
- Every existing migration is regenerated, which loses Phase 0's migration
  history. That history recorded nothing except `auth.User` FKs that are
  about to disappear, so the loss is cosmetic.
- Third-party packages that hardcode `django.contrib.auth.models.User`
  (rare today, but real) won't work. We'll cross that bridge if we hit it;
  django-allauth, djstripe, DRF, and everything else mainstream use
  `get_user_model()` correctly.

## Alternatives considered

- **Ship with the default User, migrate later.** Rejected — this ADR exists
  precisely because "later" is when migrations are expensive.
- **Use `AbstractBaseUser` + `PermissionsMixin`.** More flexible but forces
  us to implement password hashing, groups, and admin integration ourselves.
  We don't need the flexibility; the cost outweighs the benefit.
- **Add a `Profile` model with OneToOne to the default User.** Doubles
  every "get user's language preference" query into a JOIN. Solves nothing
  the custom User doesn't solve better.
- **Use a third-party User package like django-improved-user.** Adds an
  external dependency we don't need. The custom User is ~80 lines of code.

## References

- [Django: Substituting a custom User model](https://docs.djangoproject.com/en/5.1/topics/auth/customizing/#substituting-a-custom-user-model)
- [Django: AbstractUser vs AbstractBaseUser](https://docs.djangoproject.com/en/5.1/topics/auth/customizing/#specifying-a-custom-user-model)
