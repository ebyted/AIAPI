import pytest
import httpx
from main import app
from fastapi import FastAPI

@pytest.mark.asyncio
async def test_health():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "running"

@pytest.mark.asyncio
async def test_register_and_login():
    username = "testuser"
    password = "testpass123"
    transport = httpx.ASGITransport(app=app)
    # Register
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/register", json={
            "username": username,
            "full_name": "Test User",
            "password": password
        })
        assert response.status_code in (200, 201, 400)  # 400 si ya existe
    # Login
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/token", data={
            "username": username,
            "password": password
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        assert token
        return token

@pytest.mark.asyncio
async def test_generate_text():
    token = await test_register_and_login()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "Dame un consejo de vida.", "mode": "text"}
        )
        assert response.status_code == 200
        assert "text" in response.json()
