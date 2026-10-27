"""Test the GUDE PDU API client."""  # codespell:ignore gude

from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.gude_pdu.api import (
    GudeAuthError,
    GudeClient,
    GudeConnectionError,
    GudeError,
)


def _create_client(
    host: str = "192.168.1.1",
    port: int = 80,
    ssl: bool = False,
    verify_ssl: bool = True,
    session: aiohttp.ClientSession | None = None,
    username: str | None = None,
    password: str | None = None,
) -> GudeClient:
    """Create a GudeClient instance."""
    mock_session = session or MagicMock(spec=aiohttp.ClientSession)
    return GudeClient(
        host=host,
        port=port,
        ssl=ssl,
        verify_ssl=verify_ssl,
        session=mock_session,
        username=username,
        password=password,
    )


async def test_client_urls() -> None:
    """Test URL generation with and without SSL."""
    client_http = _create_client("192.168.1.1", port=80, ssl=False)
    assert client_http.base_url == "http://192.168.1.1:80"

    client_custom_port = _create_client("192.168.1.1", port=8080, ssl=False)
    assert client_custom_port.base_url == "http://192.168.1.1:8080"

    client_https = _create_client("192.168.1.1", port=443, ssl=True)
    assert client_https.base_url == "https://192.168.1.1:443"

    client_https_port = _create_client("192.168.1.1", port=8443, ssl=True)
    assert client_https_port.base_url == "https://192.168.1.1:8443"


async def test_client_auth_headers() -> None:
    """Test Basic Auth header generation."""
    client_no_auth = _create_client()
    assert "Authorization" not in client_no_auth._headers

    client_auth = _create_client(username="admin", password="password")
    assert "Authorization" in client_auth._headers
    assert client_auth._headers["Authorization"].startswith("Basic ")


async def test_client_http_errors() -> None:
    """Test handling of HTTP error status codes."""
    session = MagicMock(spec=aiohttp.ClientSession)

    # 401 Unauthorized
    resp_401 = AsyncMock()
    resp_401.status = 401
    resp_401.raise_for_status.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=401
    )
    session.get.return_value.__aenter__.return_value = resp_401

    client = _create_client(session=session)
    with pytest.raises(GudeAuthError):
        await client._request({"components": 1})

    # 500 Server Error
    resp_500 = AsyncMock()
    resp_500.status = 500
    resp_500.raise_for_status.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=500
    )
    session.get.return_value.__aenter__.return_value = resp_500
    with pytest.raises(GudeError):
        await client._request({"components": 1})

    # ClientError
    session.get.side_effect = aiohttp.ClientError("Failed to connect")
    with pytest.raises(GudeConnectionError):
        await client._request({"components": 1})

    # TimeoutError
    session.get.side_effect = TimeoutError("Timed out")
    with pytest.raises(GudeConnectionError):
        await client._request({"components": 1})


async def test_client_invalid_payloads() -> None:
    """Test handling of invalid device info payloads."""
    client = _create_client()

    # Missing ethernet / mac
    with (
        patch.object(
            client, "_request", return_value={"misc": {"product_name": "PDU"}}
        ),
        pytest.raises(
            GudeError,
            match="PDU did not return a device MAC address",
        ),
    ):
        await client.authenticate()

    # Missing product_name defaults gracefully
    info = client._parse_device_info(
        {"ethernet": {"mac": "00:19:32:00:00:00"}, "misc": {}}
    )
    assert info.product_name == "GUDE PDU"  # codespell:ignore gude
    assert info.vendor_name == "GUDE Systems"  # codespell:ignore gude


async def test_client_get_fallback_to_statusjsn() -> None:
    """Test GET /status.json falling back to GET /statusjsn.js on 404."""
    session = MagicMock(spec=aiohttp.ClientSession)

    resp_404 = AsyncMock()
    resp_404.status = 404

    resp_ok = AsyncMock()
    resp_ok.status = 200
    resp_ok.text.return_value = (
        '{"ethernet":{"mac":"00:19:32:01:a3:3e"},'
        '"misc":{"product_name":"Expert Power Control 8041-1"}}'
    )

    get_ctx_1 = MagicMock()
    get_ctx_1.__aenter__.return_value = resp_404
    get_ctx_2 = MagicMock()
    get_ctx_2.__aenter__.return_value = resp_ok
    get_ctx_3 = MagicMock()
    get_ctx_3.__aenter__.return_value = resp_ok
    session.get.side_effect = [get_ctx_1, get_ctx_2, get_ctx_3]

    client = _create_client(session=session)
    info = await client.authenticate()

    assert info.mac == "00:19:32:01:a3:3e"
    assert client._legacy_endpoint is True
    assert session.get.call_count == 2
    assert session.get.call_args_list[0].args[0] == "http://192.168.1.1:80/status.json"
    assert session.get.call_args_list[1].args[0] == "http://192.168.1.1:80/statusjsn.js"

    # Subsequent calls go directly to statusjsn.js
    await client.authenticate()
    assert session.get.call_count == 3
    assert session.get.call_args_list[2].args[0] == "http://192.168.1.1:80/statusjsn.js"


async def test_client_post_fallback_to_statusjsn() -> None:
    """Test POST /status.json falling back to GET /statusjsn.js on 405."""
    session = MagicMock(spec=aiohttp.ClientSession)

    resp_405 = AsyncMock()
    resp_405.status = 405
    session.post.return_value.__aenter__.return_value = resp_405

    resp_ok = AsyncMock()
    resp_ok.status = 200
    resp_ok.text.return_value = '{"outputs":[{"name":"Port 1","state":1,"type":1}]}'
    session.get.return_value.__aenter__.return_value = resp_ok

    client = _create_client(session=session)
    result = await client.set_outlet_state(1, True)

    assert result is True
    assert client._legacy_endpoint is True
    session.post.assert_called_once()
    session.get.assert_called_once_with(
        "http://192.168.1.1:80/statusjsn.js",
        params={"components": 1, "cmd": 1, "p": 1, "s": 1},
        headers={},
        ssl=True,
        timeout=client.timeout,
    )

    # Subsequent command calls skip POST and use GET statusjsn.js directly
    await client.set_outlet_state(1, False)
    assert session.post.call_count == 1
    assert session.get.call_count == 2


async def test_client_set_outlet_state() -> None:
    """Test set_outlet_state sends POST to status.json with string form values."""
    session = MagicMock(spec=aiohttp.ClientSession)
    resp = AsyncMock()
    resp.status = 200
    resp.text.return_value = '{"outputs":[{"name":"Port 1","state":1,"type":1}]}'
    session.post.return_value.__aenter__.return_value = resp

    client = _create_client(session=session)
    result = await client.set_outlet_state(1, True)

    assert result is True
    session.post.assert_called_once_with(
        "http://192.168.1.1:80/status.json",
        data={"components": "1", "cmd": "1", "p": "1", "s": "1"},
        headers={},
        ssl=True,
        timeout=client.timeout,
        allow_redirects=False,
    )


async def test_client_set_outlet_state_reauth_on_redirect() -> None:
    """Test set_outlet_state logs in and retries when POST receives a 307 redirect."""
    session = MagicMock(spec=aiohttp.ClientSession)

    resp_redirect = AsyncMock()
    resp_redirect.status = 307

    cookies: SimpleCookie = SimpleCookie()
    cookies["sessionid"] = "abc123session"
    resp_login = AsyncMock()
    resp_login.status = 200
    resp_login.cookies = cookies
    resp_login.text.return_value = '{"login":1,"sessionidX":"token_xyz"}'

    resp_ok = AsyncMock()
    resp_ok.status = 200
    resp_ok.text.return_value = '{"outputs":[{"name":"Port 9","state":1,"type":1}]}'

    post_ctx_1 = MagicMock()
    post_ctx_1.__aenter__.return_value = resp_redirect
    post_ctx_2 = MagicMock()
    post_ctx_2.__aenter__.return_value = resp_login
    post_ctx_3 = MagicMock()
    post_ctx_3.__aenter__.return_value = resp_ok
    session.post.side_effect = [post_ctx_1, post_ctx_2, post_ctx_3]

    client = _create_client(session=session, username="admin", password="secret")
    result = await client.set_outlet_state(1, True)

    assert result is True
    assert session.post.call_count == 3
    assert client._headers["sessionidX"] == "token_xyz"
    assert client._headers["Cookie"] == "sessionid=abc123session"


@pytest.mark.parametrize(
    ("post_status", "expected_error"),
    [
        pytest.param(401, GudeAuthError, id="post_401"),
        pytest.param(500, GudeError, id="post_500"),
    ],
)
async def test_client_post_http_status_errors(
    post_status: int,
    expected_error: type[GudeError],
) -> None:
    """Test non-200 HTTP status codes returned by status.json POST."""
    session = MagicMock(spec=aiohttp.ClientSession)
    resp = AsyncMock()
    resp.status = post_status
    session.post.return_value.__aenter__.return_value = resp

    client = _create_client(session=session)
    with pytest.raises(expected_error):
        await client.set_outlet_state(1, True)


async def test_client_session_auth_success() -> None:
    """Test session login when PDU returns authreq redirect payload."""
    session = MagicMock(spec=aiohttp.ClientSession)

    resp_authreq = AsyncMock()
    resp_authreq.status = 200
    resp_authreq.text.return_value = (
        '{"authreq":1,"welcome_msg":"Expert Power Control 8045-1"}'
    )

    resp_status = AsyncMock()
    resp_status.status = 200
    resp_status.text.return_value = (
        '{"ethernet":{"mac":"00:19:32:01:a3:3e"},'
        '"misc":{"product_name":"Expert Power Control 8045-1"}}'
    )

    get_ctx_1 = MagicMock()
    get_ctx_1.__aenter__.return_value = resp_authreq
    get_ctx_2 = MagicMock()
    get_ctx_2.__aenter__.return_value = resp_status
    session.get.side_effect = [get_ctx_1, get_ctx_2]

    cookies: SimpleCookie = SimpleCookie()
    cookies["sessionid"] = "abc123session"
    resp_login = AsyncMock()
    resp_login.status = 200
    resp_login.cookies = cookies
    resp_login.text.return_value = (
        '{"login":1,"sessionidX":"token_xyz","href":"dashboard.html"}'
    )
    session.post.return_value.__aenter__.return_value = resp_login

    client = _create_client(
        session=session, username="admin", password="secretpassword"
    )
    device_info = await client.authenticate()

    assert device_info.mac == "00:19:32:01:a3:3e"
    assert client._headers["sessionidX"] == "token_xyz"
    assert client._headers["Cookie"] == "sessionid=abc123session"
    assert session.post.call_count == 1
    assert session.get.call_count == 2


async def test_client_session_auth_invalid_credentials() -> None:
    """Test session login raises GudeAuthError when login.json returns login=0."""
    session = MagicMock(spec=aiohttp.ClientSession)

    resp_authreq = AsyncMock()
    resp_authreq.status = 200
    resp_authreq.text.return_value = (
        '{"authreq":1,"welcome_msg":"Expert Power Control 8045-1"}'
    )
    session.get.return_value.__aenter__.return_value = resp_authreq

    resp_login = AsyncMock()
    resp_login.status = 200
    resp_login.cookies = SimpleCookie()
    resp_login.text.return_value = '{"login":0,"user_id":0,"href":"dashboard.html"}'
    session.post.return_value.__aenter__.return_value = resp_login

    client = _create_client(session=session, username="admin", password="wrong")
    with pytest.raises(GudeAuthError):
        await client.authenticate()


async def test_client_session_auth_no_credentials() -> None:
    """Test authreq response raises GudeAuthError when no credentials are set."""
    session = MagicMock(spec=aiohttp.ClientSession)

    resp_authreq = AsyncMock()
    resp_authreq.status = 200
    resp_authreq.text.return_value = (
        '{"authreq":1,"welcome_msg":"Expert Power Control 8045-1"}'
    )
    session.get.return_value.__aenter__.return_value = resp_authreq

    client = _create_client(session=session)
    with pytest.raises(GudeAuthError):
        await client.authenticate()

    session.post.assert_not_called()


async def test_client_session_auth_still_authreq_after_login() -> None:
    """Test GudeAuthError is raised if status still returns authreq after login."""
    session = MagicMock(spec=aiohttp.ClientSession)

    resp_authreq = AsyncMock()
    resp_authreq.status = 200
    resp_authreq.text.return_value = '{"authreq":1}'
    session.get.return_value.__aenter__.return_value = resp_authreq

    resp_login = AsyncMock()
    resp_login.status = 200
    resp_login.cookies = SimpleCookie()
    resp_login.text.return_value = '{"login":1}'
    session.post.return_value.__aenter__.return_value = resp_login

    client = _create_client(session=session, username="admin", password="password")
    with pytest.raises(GudeAuthError):
        await client.authenticate()


@pytest.mark.parametrize(
    ("login_status", "expected_error"),
    [
        pytest.param(401, GudeAuthError, id="login_401"),
        pytest.param(500, GudeError, id="login_500"),
    ],
)
async def test_client_session_login_http_status_errors(
    login_status: int,
    expected_error: type[GudeError],
) -> None:
    """Test non-200 HTTP status codes returned by login.json."""
    session = MagicMock(spec=aiohttp.ClientSession)

    resp_authreq = AsyncMock()
    resp_authreq.status = 200
    resp_authreq.text.return_value = '{"authreq":1}'
    session.get.return_value.__aenter__.return_value = resp_authreq

    resp_login = AsyncMock()
    resp_login.status = login_status
    session.post.return_value.__aenter__.return_value = resp_login

    client = _create_client(session=session, username="admin", password="password")
    with pytest.raises(expected_error):
        await client.authenticate()


async def test_client_invalid_json_and_missing_outputs() -> None:
    """Test invalid JSON response and malformed outputs array handling."""
    session = MagicMock(spec=aiohttp.ClientSession)
    resp = AsyncMock()
    resp.status = 200
    resp.text.return_value = "not-valid-json"
    session.get.return_value.__aenter__.return_value = resp

    client = _create_client(session=session)
    with pytest.raises(GudeError):
        await client.authenticate()

    assert client._parse_outputs({"outputs": "not-a-list"}) == {}
    assert client._parse_outputs({"outputs": ["not-a-dict"]}) == {}
