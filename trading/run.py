"""Main entry point for the Polymarket Trading Agent."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Run the trading agent."""
    behind_proxy = os.getenv("BEHIND_PROXY", "").lower() in ("1", "true", "yes")
    default_host = "0.0.0.0"
    host = os.getenv("HOST", default_host)
    port = int(os.getenv("PORT", "8000"))

    kwargs: dict = {
        "host": host,
        "port": port,
        "reload": False,
        "log_level": "info",
    }

    # Enable proxy headers when behind a reverse proxy
    if os.getenv("BEHIND_PROXY", "").lower() in ("1", "true", "yes"):
        kwargs["proxy_headers"] = True
        kwargs["forwarded_allow_ips"] = os.getenv("TRUSTED_PROXIES", "*")

    # TLS support for direct exposure
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")
    if ssl_keyfile and ssl_certfile:
        kwargs["ssl_keyfile"] = ssl_keyfile
        kwargs["ssl_certfile"] = ssl_certfile

    uvicorn.run("src.main:app", **kwargs)


if __name__ == "__main__":
    main()
