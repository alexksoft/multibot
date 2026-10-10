"""Tests for GoogleSheetsCatalog, DialogLogger, and KiroGatewayProvider."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.multibot.config.sections import CatalogItem, SheetsSource
from src.multibot.core.catalog import GoogleSheetsCatalog, LocalCatalog


# ── LocalCatalog ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_local_catalog_filters_inactive():
    items = [
        CatalogItem(category="A", item="x", price=10.0, source_name="S", source_url="u", collected_at="2026-01", active=True),
        CatalogItem(category="A", item="y", active=False),
    ]
    cat = LocalCatalog(items)
    result = await cat.items()
    assert len(result) == 1
    assert result[0].item == "x"


# ── GoogleSheetsCatalog ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_google_sheets_catalog_no_creds():
    cat = GoogleSheetsCatalog("nonexistent.json", "sheet123", None, 300)
    result = await cat.items()
    assert result == []


@pytest.mark.asyncio
async def test_google_sheets_catalog_discards_price_without_source():
    cat = GoogleSheetsCatalog.__new__(GoogleSheetsCatalog)
    cat._creds_path = "fake.json"
    cat._sheet_id = "sid"
    cat._worksheet = None
    cat._ttl = 300
    cat._cache = []
    cat._cache_time = 0.0

    row_with_source = {"category": "A", "item": "x", "price": "100", "unit": "грн",
                       "source_name": "Shop", "source_url": "https://x.ua",
                       "collected_at": "2026-01", "active": "true", "notes": ""}
    row_no_source = {"category": "A", "item": "y", "price": "200", "unit": "грн",
                     "source_name": "", "source_url": "", "collected_at": "", "active": "true", "notes": ""}
    row_inactive = {"category": "A", "item": "z", "price": "", "unit": "",
                    "source_name": "", "source_url": "", "collected_at": "", "active": "false", "notes": ""}

    parsed = [cat._parse_row(r) for r in [row_with_source, row_no_source, row_inactive]]
    valid = [p for p in parsed if p is not None and p.active]
    assert len(valid) == 1
    assert valid[0].item == "x"


@pytest.mark.asyncio
async def test_google_sheets_catalog_cache():
    """Within TTL, second call should not re-fetch."""
    import time
    cat = GoogleSheetsCatalog.__new__(GoogleSheetsCatalog)
    cat._creds_path = "fake.json"
    cat._sheet_id = "sid"
    cat._worksheet = None
    cat._ttl = 300
    cat._cache = [CatalogItem(category="A", item="x", price=10.0,
                               source_name="S", source_url="u", collected_at="2026-01")]
    cat._cache_time = time.monotonic()  # fresh cache

    with patch.object(cat, "_get_client", return_value=None) as mock_client:
        result = await cat.items()
        mock_client.assert_not_called()
    assert len(result) == 1


# ── KiroGatewayProvider ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kiro_gateway_success():
    from src.multibot.core.providers.kiro_gateway import KiroGatewayProvider
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello!", "tool_calls": None}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        provider = KiroGatewayProvider("http://localhost:9000", "test-key")
        result = await provider.complete("sys", [{"role": "user", "content": "hi"}])
        assert result.content == "Hello!"


@pytest.mark.asyncio
async def test_kiro_gateway_timeout_uses_fallback():
    import httpx
    from src.multibot.core.providers.kiro_gateway import KiroGatewayProvider

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        provider = KiroGatewayProvider("http://localhost:9000", "test-key")
        result = await provider.complete("sys", [{"role": "user", "content": "hi"}])
        assert "недоступний" in result.content or result.content != ""


@pytest.mark.asyncio
async def test_kiro_gateway_not_configured_uses_fallback():
    from src.multibot.core.providers.kiro_gateway import KiroGatewayProvider
    provider = KiroGatewayProvider("", "")
    result = await provider.complete("sys", [{"role": "user", "content": "hi"}])
    assert result.content != ""


# ── DialogLogger ──────────────────────────────────────────────────────────────

def test_dialog_log_disabled_does_nothing():
    from src.multibot.core.dialog_log import log_message
    # Should not raise, just return immediately
    log_message("bot1", 123, "in", "hello", enabled=False, sheet_id="", creds_path="")


def test_dialog_log_no_sheets_graceful():
    from src.multibot.core.dialog_log import log_message
    # With no valid creds, should silently skip
    log_message("bot1", 123, "in", "hello", enabled=True, sheet_id="fake_id", creds_path="nonexistent.json")
