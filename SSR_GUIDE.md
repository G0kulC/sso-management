# Server-Side Rendering (SSR) with FastAPI & Jinja2

Your SSO project now uses **server-side HTML rendering** with Jinja2 templates!

## 🎯 What Changed

### Before (Static Files)
- HTML files served as-is from `frontend/` directory
- No dynamic content from server
- Hardcoded values in HTML

### After (Server-Side Rendering)
- HTML templates in `app/templates/` rendered by FastAPI
- Dynamic data injected from backend (app name, version, URLs, etc.)
- Template inheritance with `base.html`
- Server configuration passed to JavaScript

## 📁 Project Structure

```
sso-project/
├── app/
│   ├── templates/          # Jinja2 HTML templates
│   │   ├── base.html       # Base template (inheritance)
│   │   ├── home.html       # Home page (uses base.html)
│   │   ├── login.html      # Login page
│   │   └── dashboard.html  # Dashboard page
│   ├── main.py             # FastAPI app with SSR routes
│   └── config.py           # Settings (includes BACKEND_URL, BACKEND_PORT)
├── frontend/               # Static files (JS, CSS, images)
│   └── script.js           # Frontend JavaScript
└── .env                    # Environment configuration
```

## 🚀 How It Works

### 1. **Templates are Rendered Server-Side**

```python
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
```

### 2. **Templates Use Jinja2 Variables**

```html
<h1>{{ app_name }}</h1>
<p>Version {{ app_version }}</p>
<p>Server Time: {{ server_time }}</p>
```

### 3. **Template Inheritance**

```html
<!-- base.html -->
<!DOCTYPE html>
<html>
  {% block content %}{% endblock %}
</html>

<!-- home.html -->
{% extends "base.html" %}
{% block content %}
  <h1>Home Page</h1>
{% endblock %}
```

### 4. **Server Config → JavaScript**

```html
<script>
  window.API_BASE_URL = "{{ api_base }}";
  window.APP_VERSION = "{{ app_version }}";
</script>
<script src="/static/script.js"></script>
```

```javascript
// In script.js
const API_BASE = window.API_BASE_URL || window.location.origin;
```

## 🎨 Page Routes

| Route | Template | Description |
|-------|----------|-------------|
| `/` | `home.html` | Home page with server info |
| `/login` | `login.html` | Login & registration |
| `/dashboard` | `dashboard.html` | User dashboard |
| `/api` | JSON | API health check |
| `/docs` | Swagger | API documentation |

## ⚙️ Configuration (.env)

```bash
# Backend Server
BACKEND_URL=http://localhost:8004
BACKEND_PORT=8004

# Application
APP_NAME=SSO Identity Management System
APP_VERSION=1.0.0
DEBUG=True
```

## 🏃 Running the Server

```bash
# Activate virtual environment
D:\w\New folder\sso-env\Scripts\Activate.ps1

# Start with auto-reload (browser opens automatically)
python start.py

# Or use uvicorn directly
uvicorn app.main:app --reload --port 8004
```

## ✨ Benefits of SSR

✅ **Dynamic Content** - Server controls what data is shown  
✅ **SEO Friendly** - Search engines can crawl rendered HTML  
✅ **Security** - API keys and secrets stay on server  
✅ **Performance** - Initial page loads faster (no client-side rendering)  
✅ **Flexibility** - Easy to add server-side logic (auth checks, data fetching)  

## 🔧 Example: Adding More Dynamic Data

### In main.py:
```python
@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard(request: Request):
    # Fetch user data from database
    from app.database import SessionLocal
    db = SessionLocal()
    user_count = db.query(User).count()
    db.close()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "user_count": user_count,
        "is_admin": True  # Example: check user role
    })
```

### In dashboard.html:
```html
<h1>Welcome to {{ app_name }}</h1>
<p>Total Users: {{ user_count }}</p>

{% if is_admin %}
  <button>Admin Panel</button>
{% endif %}
```

## 📚 Jinja2 Template Features

```html
<!-- Variables -->
{{ variable_name }}

<!-- Conditionals -->
{% if condition %}
  <p>True</p>
{% else %}
  <p>False</p>
{% endif %}

<!-- Loops -->
{% for item in items %}
  <li>{{ item.name }}</li>
{% endfor %}

<!-- Template Inheritance -->
{% extends "base.html" %}
{% block content %}
  <!-- Your content -->
{% endblock %}

<!-- Include Other Templates -->
{% include "header.html" %}

<!-- Filters -->
{{ text|upper }}
{{ price|round(2) }}
{{ date|date("Y-m-d") }}
```

## 🎯 Next Steps

1. **Add Authentication Guards** - Check if user is logged in before rendering
2. **Pass User Data** - Show personalized content based on logged-in user
3. **Form Handling** - Process forms on the server side
4. **Flash Messages** - Show success/error messages after form submission
5. **Partial Templates** - Create reusable components (header, footer, sidebar)

---

**Your SSO system now has full server-side rendering! 🚀**
