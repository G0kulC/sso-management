# 🔐 Secure Single Sign-On (SSO) & Identity Management System

A centralized authentication server built with **FastAPI**, **PostgreSQL**, and **JWT tokens**.  
Users log in once and can securely access multiple client applications.

---

## 📁 Project Structure

```
project/
├── app/
│   ├── main.py          # FastAPI app, middleware, startup
│   ├── config.py        # Settings from environment variables
│   ├── database.py      # SQLAlchemy engine & session
│   ├── models.py        # ORM models (User, Application, Session, LoginLog)
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── auth.py          # JWT auth dependencies (get_current_user, require_admin)
│   ├── security.py      # bcrypt hashing, JWT create/verify, blacklist
│   └── routers/
│       ├── auth.py      # /auth/* endpoints
│       ├── users.py     # /users/* endpoints
│       └── apps.py      # /apps/* endpoints + SSO verify
├── frontend/
│   ├── login.html       # Login / Register page
│   ├── dashboard.html   # User & Admin dashboard
│   └── script.js        # All frontend JS (API calls, token management)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 14+
- (Optional) Node.js for serving frontend

### 2. Clone & Install

```bash
git clone <repo-url>
cd sso-project

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials and a strong SECRET_KEY
```

### 4. Set Up PostgreSQL

```sql
-- Run in psql
CREATE USER sso_user WITH PASSWORD 'sso_password';
CREATE DATABASE sso_db OWNER sso_user;
GRANT ALL PRIVILEGES ON DATABASE sso_db TO sso_user;
```

### 5. Start the Server

```bash
# From project root
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server starts at: http://localhost:8000  
Interactive API docs: http://localhost:8000/docs

### 6. Open Frontend

Open `frontend/login.html` directly in your browser, or serve it:

```bash
cd frontend
python -m http.server 3000
# Visit http://localhost:3000/login.html
```

### 7. Default Admin Credentials

```
Username: admin
Password: Admin@1234
```
> ⚠️ Change these immediately in production!

---

## 🔌 API Reference

### Authentication

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/register` | Register new user | No |
| POST | `/auth/login` | Login (OAuth2 form) | No |
| POST | `/auth/logout` | Logout & blacklist token | Yes |
| POST | `/auth/refresh` | Refresh access token | No (refresh token) |
| GET  | `/auth/me` | Get current user | Yes |

### User Management

| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| GET | `/users/` | List all users | Admin |
| GET | `/users/{id}` | Get user by ID | Admin / Own |
| PUT | `/users/{id}` | Update user | Admin / Own |
| DELETE | `/users/{id}` | Delete user | Admin |
| GET | `/users/logs` | Login audit logs | Admin |

### Application Management

| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| POST | `/apps/register` | Register client app | Admin |
| GET  | `/apps/` | List all apps | Any Auth |
| GET  | `/apps/{id}` | Get app details | Any Auth |
| DELETE | `/apps/{id}` | Remove app | Admin |
| POST | `/apps/verify-token` | Verify SSO token | App credentials |

---

## 🔄 SSO Flow

```
1. User visits Client App
        ↓
2. Client App redirects → SSO Login page
        ↓
3. User enters credentials
        ↓
4. SSO validates & returns JWT access_token + refresh_token
        ↓
5. User presents access_token to Client App
        ↓
6. Client App calls POST /apps/verify-token with:
   { token, client_id, client_secret }
        ↓
7. SSO returns { valid: true, user_id, username, role }
        ↓
8. Client App grants access
```

---

## 🛡 Security Features

| Feature | Implementation |
|---------|---------------|
| Password hashing | bcrypt (passlib) |
| Authentication | JWT (HS256) via python-jose |
| Token types | Short-lived access (30min) + refresh (7 days) |
| Logout | Token blacklist table in DB |
| Refresh rotation | Old refresh token blacklisted on use |
| RBAC | Admin / User roles enforced per endpoint |
| Audit logging | All login attempts recorded with IP |
| CORS | Configurable allowed origins |
| Request timing | X-Process-Time header on every response |

---

## 📊 Database Models

```
User            → username, email, password_hash, role, is_active
Application     → name, client_id, client_secret, redirect_uri
Session         → user_id, token, refresh_token, expiry, is_revoked
LoginLog        → user_id, login_time, ip_address, success, failure_reason
TokenBlacklist  → token, blacklisted_at, expires_at
```

---

## 🧪 Test with curl

```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@test.com","password":"Test@1234"}'

# 2. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=Test@1234"

# 3. Get profile (use token from step 2)
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <access_token>"

# 4. List users (admin only)
curl http://localhost:8000/users/ \
  -H "Authorization: Bearer <admin_token>"
```

---

## 🔧 Development Tips

- API docs available at `/docs` (Swagger) and `/redoc`
- Health check: `GET /health`
- Set `DEBUG=True` in `.env` for detailed error messages
- Generate a secure SECRET_KEY: `python -c "import secrets; print(secrets.token_hex(32))"`
