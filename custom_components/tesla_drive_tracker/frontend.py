"""Serve the card bundle and register it as a Lovelace resource.

Adapted from ``ha-teslamate-cards``, including the HA 2026.7
``mode`` -> ``resource_mode`` rename fallback.

The ``?v=`` on the resource URL is the only cache-buster. The bundle is served
with a 31-day ``max-age``, so a browser that already has it will not ask again
until that URL changes -- there is no revalidation to fall back on.

The key is ``<manifest version>.<content hash>``, and the hash half is not
belt-and-braces. The version alone is only a correct cache key for *released*
installs: deploy straight from a branch, or hand-copy the package, and the
bundle changes while release-please has not yet bumped the manifest, so the URL
stays byte-identical and every browser keeps running the previous module. That
is a silent failure -- the server is serving the new bundle the whole time.

Measured, deploying the Statistics card that way: the new tab rendered Home
Assistant's generic "Configuration error" card, because the element simply was
not defined in the module the browser still held, while ``curl`` on the same URL
returned a bundle that defined it.

Hashing the bytes actually served makes the URL stale only when the bundle is
unchanged, which is exactly when a stale cache is the right answer. It also
makes the console banner a real build id, since that reads its version back off
this URL.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import CARD_FILENAME, LOGGER, URL_BASE

_CARD_URL_PATH = f"{URL_BASE}/{CARD_FILENAME}"


def _read_bundle(card_path: Path) -> bytes | None:
    """Read the bundle, or None if it has not been built.

    Both the existence check and the read happen here so they cost one trip to
    the executor: Home Assistant's blocking-I/O detector flags file reads made
    on the event loop, and this one is ~120 KB.
    """
    try:
        return card_path.read_bytes()
    except OSError:
        return None


async def async_register_card(hass: HomeAssistant, version: str) -> None:
    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME

    bundle = await hass.async_add_executor_job(_read_bundle, card_path)
    if bundle is None:
        # A source checkout without `npm run build`. The integration still
        # works; only the card is missing, so say so rather than fail.
        LOGGER.warning("Card bundle not found at %s: run 'npm run build'", card_path)
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(_CARD_URL_PATH, str(card_path), cache_headers=True)]
    )

    # Truncated to 8 hex characters: this is a cache key, not a signature, and
    # a collision would only mean one browser keeps a stale module -- the same
    # failure the full-length hash is protecting against, at 2^-32 odds.
    fingerprint = hashlib.sha256(bundle).hexdigest()[:8]
    versioned_url = f"{_CARD_URL_PATH}?v={version}.{fingerprint}"
    resources = _storage_resources(hass)
    if resources is None:
        LOGGER.info(
            "Lovelace is in YAML mode; add the card resource manually: url: %s, type: module",
            versioned_url,
        )
        return

    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True

    for item in resources.async_items():
        if (item.get("url") or "").split("?")[0] == _CARD_URL_PATH:
            if item["url"] != versioned_url:
                await resources.async_update_item(item["id"], {"res_type": "module", "url": versioned_url})
                LOGGER.debug("Updated Lovelace resource to %s", versioned_url)
            return

    await resources.async_create_item({"res_type": "module", "url": versioned_url})
    LOGGER.debug("Registered Lovelace resource %s", versioned_url)


def _storage_resources(hass: HomeAssistant):
    """Return the resource storage collection, or None in YAML resource mode."""
    lovelace = hass.data.get("lovelace")
    # HA 2026.7 renamed LovelaceData.mode to resource_mode; check both so
    # older cores (>= 2025.7) keep working.
    mode = getattr(lovelace, "resource_mode", None) or getattr(lovelace, "mode", None)
    if mode != "storage":
        return None
    return getattr(lovelace, "resources", None)
