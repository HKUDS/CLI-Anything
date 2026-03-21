"""CLI-Anything Cloud API — Hosted harness service.

Run CLI-Anything commands via REST API without installing anything.

Usage:
    # Start server
    uvicorn cli_anything.api.server:app --host 0.0.0.0 --port 8000

    # Call API
    curl -X POST https://api.cli-anything.dev/v1/gimp/convert \
        -H "Authorization: Bearer <token>" \
        -H "Content-Type: application/json" \
        -d '{"input": "photo.jpg", "output": "thumb.png", "width": 320}'
"""

import json
import subprocess
import os
import time
import hashlib
from typing import Optional
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, Depends, Header
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ── Models ──────────────────────────────────────────────────────

if HAS_FASTAPI:

    class CommandRequest(BaseModel):
        command: str
        timeout: Optional[int] = 300

    class HarnessRequest(BaseModel):
        args: list[str] = []
        timeout: Optional[int] = 300

    class APIResponse(BaseModel):
        status: str
        stdout: str = ""
        stderr: str = ""
        duration_ms: int = 0
        harness: str = ""

    class UsageResponse(BaseModel):
        calls_today: int
        calls_month: int
        limit: int
        plan: str


# ── Rate Limiter ────────────────────────────────────────────────


class RateLimiter:
    def __init__(self):
        self.calls = {}

    def check(self, token: str, limit: int = 100) -> bool:
        today = time.strftime("%Y-%m-%d")
        key = f"{token}:{today}"
        count = self.calls.get(key, 0)
        if count >= limit:
            return False
        self.calls[key] = count + 1
        return True

    def get_usage(self, token: str) -> dict:
        today = time.strftime("%Y-%m-%d")
        month = time.strftime("%Y-%m")
        daily_key = f"{token}:{today}"
        monthly_keys = [k for k in self.calls if k.startswith(f"{token}:{month}")]
        return {
            "calls_today": self.calls.get(daily_key, 0),
            "calls_month": sum(self.calls.get(k, 0) for k in monthly_keys),
            "limit": 100,
            "plan": "free",
        }


rate_limiter = RateLimiter()


# ── App ─────────────────────────────────────────────────────────

if HAS_FASTAPI:
    app = FastAPI(
        title="CLI-Anything API",
        description="Run CLI-Anything harnesses via REST API",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    AVAILABLE_HARNESSSES = [
        "gimp",
        "blender",
        "inkscape",
        "vlc",
        "freecad",
        "ffmpeg",
        "imagemagick",
        "sox",
        "docker",
        "git",
        "pandoc",
        "tesseract",
    ]

    def verify_token(authorization: str = Header(None)):
        """Verify API token."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing or invalid Authorization header")
        token = authorization.replace("Bearer ", "")
        if not rate_limiter.check(token):
            raise HTTPException(429, "Rate limit exceeded")
        return token

    @app.get("/")
    async def root():
        return {
            "name": "CLI-Anything API",
            "version": "1.0.0",
            "harnesses": AVAILABLE_HARNESSSES,
            "docs": "/docs",
        }

    @app.get("/v1/harnesses")
    async def list_harnesses(token: str = Depends(verify_token)):
        """List available harnesses."""
        return {"harnesses": AVAILABLE_HARNESSSES}

    @app.post("/v1/{harness}/run", response_model=APIResponse)
    async def run_harness(
        harness: str,
        req: HarnessRequest,
        token: str = Depends(verify_token),
    ):
        """Run a command on a harness."""
        if harness not in AVAILABLE_HARNESSSES:
            raise HTTPException(404, f"Harness '{harness}' not available")

        cmd = f"cli-anything-{harness}"
        args = ["--json"] + req.args

        start = time.time()
        try:
            result = subprocess.run(
                [cmd] + args,
                capture_output=True,
                text=True,
                timeout=req.timeout,
            )
            duration_ms = int((time.time() - start) * 1000)

            return APIResponse(
                status="success" if result.returncode == 0 else "error",
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                harness=harness,
            )
        except FileNotFoundError:
            raise HTTPException(500, f"Harness '{harness}' not installed on server")
        except subprocess.TimeoutExpired:
            raise HTTPException(408, "Command timed out")

    @app.get("/v1/usage", response_model=UsageResponse)
    async def get_usage(token: str = Depends(verify_token)):
        """Get API usage for current token."""
        return rate_limiter.get_usage(token)

    @app.get("/v1/health")
    async def health():
        return {"status": "ok", "timestamp": time.time()}
else:
    app = None
    print("Install fastapi: pip install fastapi uvicorn")
