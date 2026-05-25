"""Authentication routes."""

import uuid
from datetime import datetime

import psycopg2
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import routes.deps as deps
from auth import AUTH_COOKIE, create_auth_token, hash_password, verify_password
from core.security_config import get_cookie_secure
from database.pool import get_conn

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.state.user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return deps.templates.TemplateResponse(
        request=request, name="login.html", context={"error": ""},
    )


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))

    if not deps.TEST_MODE:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, password_hash FROM users WHERE email = %s",
                        (email,),
                    )
                    row = cur.fetchone()
        except Exception:
            row = None

        if not row or not verify_password(password, row[1]):
            return deps.templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Incorrect email or password — please try again."},
                status_code=401,
            )
        user_id = row[0]
    else:
        user_id = "test-user"

    token = create_auth_token(user_id)
    resp = RedirectResponse(url="/dashboard", status_code=302)
    resp.set_cookie(
        AUTH_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
        secure=get_cookie_secure(),
    )
    return resp


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    if request.state.user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return deps.templates.TemplateResponse(
        request=request, name="signup.html", context={"error": ""},
    )


@router.post("/signup")
async def signup_submit(request: Request):
    form = await request.form()
    email = str(form.get("email", "")).strip().lower()
    display_name = str(form.get("display_name", "")).strip()
    password = str(form.get("password", ""))
    confirm = str(form.get("confirm_password", ""))

    if not email or not password:
        return deps.templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "Email and password are required."},
            status_code=422,
        )
    if password != confirm:
        return deps.templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "Passwords do not match."},
            status_code=422,
        )
    if len(password) < 8:
        return deps.templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "Password must be at least 8 characters."},
            status_code=422,
        )

    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    now = datetime.now().isoformat()

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (user_id, email, password_hash, display_name, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        user_id,
                        email,
                        password_hash,
                        display_name or email.split("@")[0],
                        now,
                        now,
                    ),
                )
    except psycopg2.IntegrityError:
        return deps.templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "An account with that email already exists."},
            status_code=409,
        )

    token = create_auth_token(user_id)
    resp = RedirectResponse(url="/dashboard", status_code=302)
    resp.set_cookie(
        AUTH_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
        secure=get_cookie_secure(),
    )
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(AUTH_COOKIE)
    return resp
