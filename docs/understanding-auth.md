# Understanding Authentication — A Complete Guide for Our Project

This document explains every component of the auth system we're about to build,
from first principles. Read this before we write any code.

---

## Table of Contents

1. [The Problem We're Solving](#1-the-problem-were-solving)
2. [The Two Halves: Authentication vs Authorization](#2-the-two-halves-authentication-vs-authorization)
3. [Passwords: Why We Never Store Them](#3-passwords-why-we-never-store-them)
4. [Tokens: How the Server Remembers You](#4-tokens-how-the-server-remembers-you)
5. [JWT: What's Inside a Token](#5-jwt-whats-inside-a-token)
6. [The Login Flow: Step by Step](#6-the-login-flow-step-by-step)
7. [Protecting API Routes](#7-protecting-api-routes)
8. [Roles & Permissions (RBAC)](#8-roles--permissions-rbac)
9. [User Management (Admin Side)](#9-user-management-admin-side)
10. [The Frontend Side](#10-the-frontend-side)
11. [Security Threats & How We Handle Them](#11-security-threats--how-we-handle-them)
12. [How It All Fits Into Our Project](#12-how-it-all-fits-into-our-project)
13. [Glossary](#13-glossary)

---

## 1. The Problem We're Solving

Right now, anyone with the URL can access our dashboard. That means:

- A random person could see our stock levels, pricing, and supplier info
- Anyone could build POs, change supplier settings, or reclassify parties
- There's no record of who did what

What we want:

- Each team member gets a username and password
- They log in before seeing anything
- Different people have different permissions (not everyone should change settings)
- We know who performed each action

---

## 2. The Two Halves: Authentication vs Authorization

These are two separate questions:

### Authentication (AuthN) = "Who are you?"

> Kshitij types his username and password. The server checks if they're correct.
> If yes, it knows who is making requests. That's authentication.

### Authorization (AuthZ) = "What are you allowed to do?"

> Kshitij is an admin. He can change supplier lead times.
> Priya is a viewer. She can see the dashboard but can't modify anything.
> Same system, same login flow, but different permissions. That's authorization.

We implement both, but they're handled by different pieces of code:
- **Authentication** = the login endpoint, password checking, token issuing
- **Authorization** = role checks on each API route

---

## 3. Passwords: Why We Never Store Them

### The rule

**Never store a password in plain text. Ever.**

If someone gets access to our database (SQL injection, backup leak, stolen laptop),
and passwords are stored as plain text, every account is instantly compromised.

### What we store instead: a hash

A **hash** is a one-way mathematical function. It turns a password into a
fixed-length string of gibberish:

```
Password:  "mango42"
    |
    v  [Argon2id hash function]
    |
Hash:  "$argon2id$v=19$m=19456,t=2,p=1$abc123...$xyz789..."
```

Key properties:
- **One-way**: You cannot reverse the hash back to "mango42"
- **Deterministic**: Same password always produces the same hash (with the same salt)
- **Unique per user**: A random "salt" is mixed in, so two users with password
  "mango42" get different hashes

### How login works with hashes

```
User types: "mango42"
    |
    v
Server hashes the input: hash("mango42") --> "$argon2id$v=19$..."
    |
    v
Server compares with stored hash in database
    |
    v
Match? --> Login success
No match? --> "Invalid credentials" (don't say which field was wrong)
```

### Why Argon2id?

There are several hashing algorithms. Here's why we chose Argon2id:

| Algorithm | Status | Why/Why Not |
|-----------|--------|-------------|
| MD5 | **Broken** | Can be cracked in seconds. Never use for passwords. |
| SHA-256 | **Not for passwords** | Fast by design — attackers can try billions/second. |
| bcrypt | Good | Intentionally slow. Industry standard for 15+ years. |
| **Argon2id** | **Best** | Winner of the Password Hashing Competition (2015). Resists both GPU attacks and side-channel attacks. OWASP's #1 recommendation. |

Argon2id is intentionally **slow and memory-hungry**. Hashing one password takes
~200ms and uses 19 MB of RAM. That's nothing for a legitimate login, but it makes
brute-force attacks (trying millions of passwords) impractical.

### The library we'll use

`pwdlib` — FastAPI's officially recommended library (replaces the older `passlib`
which broke on Python 3.13+). Usage is simple:

```python
from pwdlib import PasswordHash

hasher = PasswordHash.recommended()

# When creating a user:
hash = hasher.hash("mango42")  # Store this in the database

# When logging in:
hasher.verify("mango42", hash)  # Returns True/False
```

---

## 4. Tokens: How the Server Remembers You

### The problem

HTTP is **stateless**. Every request is independent — the server doesn't remember
the previous one. So after you log in successfully, how does the server know that
the NEXT request (e.g., "GET /api/brands") is coming from you and not a stranger?

### The solution: tokens

After a successful login, the server gives you a **token** — a long string that
proves your identity. You attach this token to every subsequent request.

```
1. POST /api/auth/login  { username: "kshitij", password: "mango42" }
   --> Server checks password, generates token
   <-- Response: { "token": "eyJhbGciOiJIUz..." }

2. GET /api/brands
   Header: Authorization: Bearer eyJhbGciOiJIUz...
   --> Server reads token, confirms it's Kshitij, returns data

3. GET /api/skus?brand=WINSOR
   Header: Authorization: Bearer eyJhbGciOiJIUz...
   --> Same token, server knows it's still Kshitij
```

Think of it like a wristband at an event. You show your ID once at the gate
(login), get a wristband (token), and then just flash the wristband to get into
each area (API requests).

### Two approaches: Stateful vs Stateless

| Approach | How it works | Pros | Cons |
|----------|-------------|------|------|
| **Session-based** (stateful) | Server stores a session ID in a database. Your token is just a random ID that looks up the session. | Can revoke instantly (delete from DB). | Requires a session table, DB lookup on every request. |
| **JWT** (stateless) | The token itself contains your identity. Server just verifies the signature — no DB lookup needed. | Fast, no session table, simple. | Can't revoke a token before it expires (unless you add a denylist). |

**We're using JWT** because:
- We have 5-15 users, not millions. Revocation isn't a critical concern.
- No extra database table needed.
- Simpler code.
- If we ever need revocation, we can add a small denylist table later.

---

## 5. JWT: What's Inside a Token

JWT stands for **JSON Web Token**. It's not encrypted — it's **signed**. Anyone
can read its contents, but nobody can tamper with them.

A JWT has three parts separated by dots:

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJrc2hpdGlqIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzEwMTIzNDU2fQ.abc123signature
|_____________________| |______________________________________________________________________________| |________________|
       HEADER                                        PAYLOAD                                              SIGNATURE
```

### Header
```json
{ "alg": "HS256" }
```
Says "this token is signed using HMAC-SHA256."

### Payload
```json
{
  "sub": "kshitij",        // Subject: who this token belongs to
  "role": "admin",         // Their role
  "exp": 1710123456        // Expiration: Unix timestamp (e.g., 30 min from now)
}
```
This is the actual data. **Not encrypted** — anyone can decode it with base64.
That's fine — it doesn't contain the password, just identity info.

### Signature
```
HMAC-SHA256(
  base64(header) + "." + base64(payload),
  SECRET_KEY
)
```
This is the security part. The server signs the header+payload using a
**secret key** that only the server knows. If anyone changes even one character
in the payload (e.g., changes "viewer" to "admin"), the signature won't match
and the server rejects it.

### The secret key

A random string stored as an environment variable on Railway:

```
JWT_SECRET=a1b2c3d4e5f6...  (64 hex characters, generated once)
```

**This key must stay secret.** If someone gets it, they can forge tokens for any
user. That's why it lives in Railway environment variables, not in code.

### Token expiration

Tokens expire after a set time (we'll use 24 hours for convenience, since this
is an internal tool with few users). After expiration, the user must log in again.

Why expire at all? If a token is ever leaked (browser history, shared screenshot,
etc.), it stops working after the expiration window.

---

## 6. The Login Flow: Step by Step

Here's the complete flow from typing your password to seeing the dashboard:

```
                    BROWSER                              SERVER
                    -------                              ------

 1. User opens app  ------>  GET /
                             Is there a token in localStorage?
                             No --> redirect to /login

 2. User types credentials
    and clicks "Sign In"  -->  POST /api/auth/login
                               { "username": "kshitij", "password": "mango42" }

                                        |
                                        v
                               3. Server looks up "kshitij" in users table
                                  Found? Yes --> get stored password_hash
                                  No --> return 401 "Invalid credentials"

                                        |
                                        v
                               4. Server hashes the submitted password
                                  and compares to stored hash
                                  Match? Yes --> continue
                                  No --> return 401 "Invalid credentials"

                                        |
                                        v
                               5. Server creates JWT:
                                  { sub: "kshitij", role: "admin", exp: +24h }
                                  Signs it with SECRET_KEY

                    <------  6. Response: { "token": "eyJ...", "user": { ... } }

 7. Browser stores token
    in localStorage

 8. Browser redirects
    to / (dashboard)  ------>  GET /api/brands
                               Header: Authorization: Bearer eyJ...

                                        |
                                        v
                               9. Server extracts token from header
                                  Verifies signature with SECRET_KEY
                                  Checks expiration
                                  Valid? --> extract username + role

                    <------  10. Response: { brands: [...] }

 11. Dashboard renders
     with brand data
```

Every subsequent API call (steps 8-11) repeats automatically. The browser's
HTTP client (axios) attaches the token to every request via an interceptor.

---

## 7. Protecting API Routes

### How it works in FastAPI

FastAPI uses **dependency injection**. You declare what a route needs, and
FastAPI provides it automatically:

```python
# Before auth: anyone can call this
@router.get("/api/brands")
def get_brands():
    return fetch_brands()

# After auth: must be logged in
@router.get("/api/brands")
def get_brands(user = Depends(get_current_user)):
    return fetch_brands()
```

The `Depends(get_current_user)` part:
1. Reads the `Authorization: Bearer <token>` header
2. Decodes and verifies the JWT
3. Looks up the user
4. If anything fails, returns 401 (Unauthorized) automatically
5. If valid, passes the user object to the route function

### Adding role checks

```python
# Only admin can change settings
@router.put("/api/settings")
def update_settings(user = Depends(require_role("admin"))):
    ...

# Purchaser or admin can build POs
@router.post("/api/po/export")
def export_po(user = Depends(require_role("purchaser"))):
    ...
```

`require_role("purchaser")` means "purchaser OR any higher role (admin)."
It's a hierarchy: admin > purchaser > viewer.

### What routes need what?

| Route Pattern | Required Role | Why |
|---|---|---|
| `GET /api/*` (all reads) | Any authenticated user | Everyone should see data |
| `POST /api/po/export` | purchaser | Building POs is a purchasing action |
| `PUT /api/parties/*/classify` | purchaser | Classifying affects velocity calculations |
| `POST /api/overrides` | purchaser | Overrides change reorder calculations |
| `PUT /api/suppliers/*` | admin | Supplier config affects all brands |
| `PUT /api/settings/*` | admin | Global settings affect the whole system |
| `POST /api/users` | admin | Only admins create/manage users |
| `POST /api/auth/login` | **None** (public) | Can't require login to log in! |

---

## 8. Roles & Permissions (RBAC)

RBAC = **Role-Based Access Control**. Instead of assigning permissions to each
user individually, you assign a role, and the role defines what's allowed.

### Our three roles

```
ADMIN
  |
  |-- Everything a Purchaser can do, PLUS:
  |-- Manage suppliers (add, edit lead times, buffer overrides)
  |-- Change global settings (buffer multipliers, thresholds)
  |-- Create and manage user accounts
  |-- View system health and sync status
  |
PURCHASER
  |
  |-- Everything a Viewer can do, PLUS:
  |-- Build and export Purchase Orders
  |-- Classify parties into channels
  |-- Add velocity/stock overrides
  |-- Set reorder intent (must_stock, do_not_reorder)
  |
VIEWER
  |
  |-- View all dashboards and data
  |-- View brand overview, SKU details, stock timelines
  |-- Search and filter
  |-- View PO history (but not create new ones)
```

### Why not per-permission instead of per-role?

Per-permission systems have a `permissions` table with entries like:

```
user_id=3, permission="can_build_po"
user_id=3, permission="can_classify_parties"
user_id=3, permission="can_edit_suppliers"
```

This is flexible but complex. With 5-15 users, you'd spend more time managing
permissions than using the app. Three roles is simple to understand, simple to
implement, and covers all the cases we have.

If a role doesn't quite fit someone (e.g., "purchaser who can also edit suppliers
but not other settings"), we can add a `permissions` JSON column later. But let's
start simple.

### Where roles are stored

Just a column on the `users` table:

```sql
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'viewer',
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

One column. No joins. No permissions table. The role goes into the JWT payload
when the user logs in, so the server doesn't even need a DB lookup on every
request to check permissions.

---

## 9. User Management (Admin Side)

Authentication isn't just login — someone has to create accounts, reset passwords,
and deactivate users who leave. This is the **admin's job**.

### How the first admin gets created

Chicken-and-egg problem: you need to be logged in as admin to create users, but
there are no users yet. Solution: a **CLI seed command** that runs once.

```bash
cd src && ./venv/Scripts/python -m api.seed_admin --username kshitij --password "your-password"
```

This script:
1. Hashes the password with Argon2id
2. Inserts a row into the `users` table with `role = 'admin'`
3. Prints confirmation

You run it once on Railway (or locally + sync). After that, everything is done
through the UI.

### Creating new users

Only admins see the **Users** page in the dashboard. The flow:

```
Admin clicks "Add User"
  --> Form: username, temporary password, role dropdown (viewer/purchaser/admin)
  --> Submit

          POST /api/users
          { "username": "priya", "password": "temp1234", "role": "purchaser" }
                |
                v
          Server hashes password, inserts into users table
                |
                v
          Response: { "id": 3, "username": "priya", "role": "purchaser" }

Admin tells Priya her username and temporary password (in person, WhatsApp, etc.)
Priya logs in and changes her password.
```

**Important:** The admin sets a **temporary password**. The admin never sees
or stores the real password — they give the user a throwaway one, and the user
changes it on first login (or whenever they want).

### Password reset (admin-initiated)

When someone forgets their password, they can't reset it themselves (we don't
have email-based reset — that's a future enhancement). Instead:

```
Team member: "I forgot my password"
    |
    v
Admin opens Users page
  --> Finds the user
  --> Clicks "Reset Password"
  --> Types a new temporary password
  --> Clicks Save

          PUT /api/users/3/reset-password
          { "new_password": "temp5678" }
                |
                v
          Server hashes new password, updates the users table
          (Optionally: set a "must_change_password" flag)
                |
                v
          Response: 200 OK

Admin tells the team member their new temporary password.
Team member logs in and changes it.
```

The admin **cannot see the old password** (it's hashed — irreversible). They can
only set a new one.

### Changing your own password

Any logged-in user can change their own password:

```
User goes to profile / account settings
  --> Types current password (proof they're not someone who found an unlocked laptop)
  --> Types new password
  --> Confirms new password
  --> Submit

          PUT /api/auth/change-password
          { "current_password": "temp5678", "new_password": "myR3alP@ss" }
                |
                v
          Server verifies current_password against stored hash
          If correct: hash new password, update the row
          If wrong: return 401
```

**Why require the current password?** If someone walks away from their laptop
while logged in, a passerby shouldn't be able to permanently change their
password. Requiring the current password adds a second layer of proof.

### Deactivating users

When someone leaves the team, you don't delete them — you **deactivate** them.
This preserves any audit trail (who created which PO, etc.) while preventing login.

```
Admin opens Users page
  --> Finds the user
  --> Clicks "Deactivate"

          PUT /api/users/3
          { "is_active": false }
                |
                v
          Server sets is_active = FALSE in the users table
```

Next time that user tries to log in, the server checks `is_active` and rejects
them even if the password is correct. Their existing JWT tokens will also be
rejected (we check `is_active` in the `get_current_user` dependency, not just
the JWT signature).

### Changing a user's role

If Priya gets promoted from viewer to purchaser:

```
Admin opens Users page
  --> Finds Priya
  --> Changes role dropdown from "viewer" to "purchaser"
  --> Saves

          PUT /api/users/3
          { "role": "purchaser" }
```

**Note:** Priya's existing JWT still says `role: "viewer"` until it expires
and she gets a new one. With 24-hour tokens, the role change takes effect
within a day. For immediate effect, she can log out and back in.

### The Users management page

This is a new page in the dashboard, visible only to admins:

```
/users
  +----------------------------------------------------+
  | Users                              [+ Add User]     |
  +----------------------------------------------------+
  | Username    | Role       | Status   | Last Login    |
  |-------------|------------|----------|---------------|
  | kshitij     | admin      | Active   | 2 hours ago   |
  | priya       | purchaser  | Active   | Today 9:15am  |
  | rahul       | viewer     | Active   | Yesterday     |
  | durai       | purchaser  | Inactive | Feb 12        |
  +----------------------------------------------------+

  Click a row to edit: change role, reset password, deactivate/reactivate
```

### API endpoints for user management

| Endpoint | Method | Who | What |
|----------|--------|-----|------|
| `POST /api/users` | POST | admin | Create a new user |
| `GET /api/users` | GET | admin | List all users |
| `PUT /api/users/:id` | PUT | admin | Update role, is_active |
| `PUT /api/users/:id/reset-password` | PUT | admin | Set a new temporary password |
| `PUT /api/auth/change-password` | PUT | any user | Change your own password |
| `GET /api/auth/me` | GET | any user | Get your own profile |

### What we're NOT building (future enhancements)

- **Email-based password reset** ("Forgot password?" link that sends an email) —
  requires SMTP setup, token-based reset links, expiring reset tokens.
  For 5-15 known team members, asking the admin is simpler.

- **Self-registration** — No sign-up page. Only admins create accounts.
  This is an internal tool, not a public service.

- **Two-factor authentication (2FA)** — TOTP/authenticator app support.
  Nice to have but not necessary for an internal inventory tool.

- **Audit log** ("Kshitij changed supplier lead time at 3:42pm") —
  Very useful, can be added later as a separate `audit_log` table.

- **Password complexity rules** — Minimum length yes (8 chars), but we
  won't enforce "must contain uppercase + special character" rules. They
  annoy users without meaningfully improving security (NIST agrees).

---

## 10. The Frontend Side

### What changes in the React app

```
BEFORE                              AFTER
------                              -----
User opens app                      User opens app
  --> sees dashboard                  --> sees login page
                                      --> types credentials
                                      --> sees dashboard

All routes accessible               Routes wrapped in <ProtectedRoute>
                                     Unauthenticated --> redirect to /login

All UI elements visible              UI adapts to role:
                                     - Viewer: no edit buttons
                                     - Purchaser: can build POs
                                     - Admin: sees Settings, Users
```

### Where the token lives

After login, the token is stored in `localStorage`:

```javascript
// After successful login:
localStorage.setItem('token', 'eyJhbGciOi...')

// On every API request (axios interceptor):
axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

// On logout:
localStorage.removeItem('token')
```

**Why localStorage and not cookies?**

| Storage | How it works | Tradeoff |
|---------|-------------|----------|
| **localStorage** | JavaScript reads/writes it. You manually attach the token to requests. | Simpler. Vulnerable to XSS (malicious scripts could read it). |
| **httpOnly cookie** | Browser sends it automatically. JavaScript can't read it at all. | More secure. But needs CSRF protection and more complex server config. |

For an internal business tool with known users and no user-generated content
(no comments, no file uploads from strangers), the XSS risk is very low.
localStorage is the pragmatic choice.

### Auth Context (React)

We create an AuthProvider that wraps the entire app:

```
<AuthProvider>         <-- holds current user + token in React state
  <Router>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<ProtectedRoute />}>     <-- checks if logged in
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/brands" element={<Brands />} />
        ...
      </Route>
    </Route>
  </Router>
</AuthProvider>
```

Any component can access the current user:

```javascript
const { user } = useAuth()

// Conditionally render based on role:
{user.role === 'admin' && <Link to="/settings">Settings</Link>}
```

### Login page

shadcn/ui has pre-built login form components. We'll use one that matches
our existing design system — clean, minimal, with username + password fields
and a "Sign In" button.

---

## 11. Security Threats & How We Handle Them

### Brute force attacks

**Threat:** Someone tries thousands of passwords against a username.

**Defense:** Rate limiting with `slowapi` — max 5 login attempts per minute
per IP address. After that, return 429 (Too Many Requests). Argon2id's
intentional slowness (~200ms per hash) also helps — an attacker can only try
~5 passwords/second even without rate limiting.

### Token theft

**Threat:** Someone gets hold of a valid token (e.g., from browser dev tools
on a shared computer).

**Defense:** Tokens expire after 24 hours. For a higher security setup,
you'd use shorter expiration (30 min) + refresh tokens, but for an internal
tool with known users, 24h is a reasonable balance of security and convenience.

### Username enumeration

**Threat:** Attacker tries different usernames to find which ones exist.
If the error says "user not found" vs "wrong password," they learn which
usernames are valid.

**Defense:** Always return the same error message: "Invalid credentials."
Never reveal whether it was the username or password that was wrong. Also,
always run the password hash function even when the username doesn't exist
(to prevent timing attacks — where the response time reveals whether the
username was found).

### SQL injection

**Threat:** Attacker puts SQL code in the username field:
`admin'; DROP TABLE users; --`

**Defense:** We already use parameterized queries everywhere (`%s` placeholders
with psycopg2). The auth code will follow the same pattern. The input is never
concatenated into SQL strings.

### XSS (Cross-Site Scripting)

**Threat:** Malicious JavaScript runs in the browser and reads the token
from localStorage.

**Defense:** Our app doesn't accept user-generated HTML content. React
auto-escapes rendered values. We set security headers (X-Content-Type-Options,
X-XSS-Protection) via our existing middleware. The risk is very low for an
internal tool.

### CSRF (Cross-Site Request Forgery)

**Threat:** A malicious website tricks your browser into making requests
to our API using your credentials.

**Defense:** Not a concern for us. CSRF only works when the browser
automatically sends credentials (which happens with cookies). We use
Bearer tokens that must be explicitly attached by JavaScript — a
malicious site can't access our localStorage.

---

## 12. How It All Fits Into Our Project

### New files we'll create

```
src/
  api/
    auth.py              <-- Password hashing, JWT creation, get_current_user dependency
    seed_admin.py        <-- CLI script to create the first admin user
    routes/
      auth.py            <-- POST /login, GET /me, PUT /change-password
      users.py           <-- CRUD for user management (admin only)
  dashboard/
    src/
      contexts/
        AuthContext.tsx   <-- React auth provider
      components/
        ProtectedRoute.tsx
      pages/
        Login.tsx         <-- Login page
        Users.tsx         <-- User management page (admin only)
```

### Files we'll modify

```
src/
  api/
    main.py              <-- Add auth routes, rate limiting middleware
    routes/
      po.py              <-- Add Depends(require_role("purchaser"))
      suppliers.py        <-- Add Depends(require_role("admin"))
      settings.py         <-- Add Depends(require_role("admin"))
      overrides.py        <-- Add Depends(require_role("purchaser"))
      parties.py          <-- Add Depends(require_role("purchaser")) on classify
      skus.py             <-- Add Depends(get_current_user) on all routes
      brands.py           <-- Add Depends(get_current_user) on all routes
  dashboard/
    src/
      App.tsx             <-- Wrap in AuthProvider, add /login route
      components/
        Layout.tsx        <-- Show/hide nav items based on role
```

### New dependencies

```
# Python (add to requirements.txt)
PyJWT          # JWT token creation and verification
pwdlib[argon2] # Argon2id password hashing
slowapi         # Rate limiting on login endpoint

# No new npm packages needed — React context + fetch/axios handles the frontend
```

### New environment variable (Railway)

```
JWT_SECRET=<64-character random hex string>
```

Generated once with: `openssl rand -hex 32`

### Database migration

```sql
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'viewer',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login    TIMESTAMPTZ
);

-- Seed the first admin (password set via CLI command)
```

### The three-phase rollout

**Phase 1: Add auth infrastructure** (nothing breaks)
- Create users table
- Add auth.py + auth routes
- Seed your admin account
- Deploy — existing routes still work without login

**Phase 2: Require login** (everyone sees everything)
- Add login page
- Wrap React routes in ProtectedRoute
- Add axios interceptor for token
- Add `Depends(get_current_user)` to all API routes
- Deploy — users must log in, but all authenticated users have full access

**Phase 3: Enforce roles** (lock down permissions)
- Add `require_role()` to write routes
- Hide/show UI elements based on role
- Create user management page (admin only)
- Deploy — full RBAC active

Each phase is a separate commit. If anything goes wrong, revert one commit.

---

## 13. Glossary

| Term | Meaning |
|------|---------|
| **Argon2id** | Password hashing algorithm. Intentionally slow and memory-intensive to resist brute force. |
| **Authentication (AuthN)** | Verifying who someone is (username + password check). |
| **Authorization (AuthZ)** | Checking what they're allowed to do (role check). |
| **Bearer token** | A token sent in the HTTP `Authorization` header. Format: `Bearer eyJ...` |
| **Brute force** | Trying many passwords until one works. Defeated by rate limiting + slow hashing. |
| **CSRF** | Attack where a malicious site tricks your browser into making requests. Not a risk with Bearer tokens. |
| **Hash** | One-way function that turns a password into an irreversible string. |
| **httpOnly cookie** | A cookie that JavaScript cannot read. More secure but more complex than localStorage. |
| **JWT** | JSON Web Token. A signed (not encrypted) token containing user identity. |
| **localStorage** | Browser storage where we keep the auth token. Persists across page refreshes. |
| **OWASP** | Open Web Application Security Project. Sets industry standards for web security. |
| **Payload** | The data part of a JWT (username, role, expiration). |
| **RBAC** | Role-Based Access Control. Permissions defined by role, not per-user. |
| **Rate limiting** | Capping how many requests an IP can make in a time window. |
| **Salt** | Random data mixed into a password before hashing, so identical passwords produce different hashes. |
| **Secret key** | Server-side key used to sign JWTs. If leaked, tokens can be forged. |
| **Signature** | The tamper-proof seal on a JWT, generated using the secret key. |
| **Stateless** | The server doesn't store session data — the JWT itself is the proof of identity. |
| **Token** | A string that proves your identity after login, attached to every request. |
| **XSS** | Cross-Site Scripting. Malicious JavaScript running in the browser. |

---

*Document created for Kshitij Shah — Art Lounge ReOrdering Project, March 2026*
