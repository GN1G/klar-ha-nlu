"""Music Assistant, Alexa, and media-player helpers for intent dispatch."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from .dispatch_result import IntentStepResult, fail, ok
from .speech_render import spoken_after_execute, try_engine_speech
from .speech_snapshot import entity_from_state

_LOGGER = logging.getLogger(__name__)

MEDIA_SERVICES = {
    "HassMediaPause": "media_pause",
    "HassMediaUnpause": "media_play",
    "HassMediaNext": "media_next_track",
    "HassMediaPrevious": "media_previous_track",
    "HassMediaPlayerMute": "volume_mute",
    "HassMediaPlayerUnmute": "volume_mute",
    "HassSetVolume": "volume_set",
    "HassSetVolumeRelative": "volume_up",
}


async def run_mass(
    hass: HomeAssistant,
    name: str,
    slots: dict[str, Any],
    pack: str,
    item: dict,
    exposed: Callable[[str], bool],
) -> IntentStepResult:
    entity_id = str(slots.get("entity_id", {}).get("value") or "")
    state = hass.states.get(entity_id) if entity_id.startswith("media_player.") else None
    if state is None or not exposed(entity_id) or media_missing(state):
        return fail("mass_target_unavailable")
    if name == "MassFavorite":
        button = favorite_button(hass, entity_id)
        if not button:
            return fail("favorite_button_missing")
        try:
            await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
        except Exception as err:  # noqa: BLE001 — HA services are a boundary
            _LOGGER.debug("Favorit für %s nicht gesetzt: %s", entity_id, err)
            return fail(str(err) or "favorite_failed")
        extra = [row] if (row := entity_from_state(state)) else None
        return ok(await spoken_after_execute(hass, pack, "default", {**item, "name": name}, extra_entities=extra))
    try:
        if name == "MassGetQueue":
            response = await call_with_response(hass, "music_assistant", "get_queue", {}, {"entity_id": entity_id})
            extra = [row] if (row := entity_from_state(state)) else None
            queue = [{"title": str(item.get("name") or item.get("title") or "")} for item in _queue_rows(response)]
            spoken = await try_engine_speech(
                hass,
                pack,
                "default",
                {**item, "name": name},
                extra_entities=extra,
                media_queue=queue,
            )
            return ok(spoken)
        if name == "MassTransferQueue":
            data = clean_service_data(slots, ["source_player", "auto_play"])
            source_player = str(data.get("source_player") or "")
            source_state = (
                hass.states.get(source_player)
                if source_player.startswith("media_player.")
                else None
            )
            if (
                source_state is None
                or source_player == entity_id
                or not exposed(source_player)
                or media_missing(source_state)
            ):
                return fail("transfer_source_unavailable")
            await hass.services.async_call(
                "music_assistant", "transfer_queue", data, blocking=True, target={"entity_id": entity_id}
            )
        elif name == "MassPlayMedia":
            data = clean_service_data(
                slots, ["media_id", "media_type", "artist", "album", "enqueue", "radio_mode", "username"]
            )
            if "radio_mode" in data:
                data["radio_mode"] = str(data["radio_mode"]).lower() == "true"
            data = await resolve_mass_media(hass, data)
            await hass.services.async_call(
                "music_assistant", "play_media", data, blocking=True, target={"entity_id": entity_id}
            )
        else:
            return fail("unsupported_mass_intent")
    except Exception as err:  # noqa: BLE001 — Music Assistant is a service boundary
        _LOGGER.debug("Music Assistant Intent %s fehlgeschlagen: %s", name, err)
        return fail(str(err) or "mass_failed")
    extra = [row] if (row := entity_from_state(state)) else None
    return ok(await spoken_after_execute(hass, pack, "default", {**item, "name": name}, extra_entities=extra))


async def call_with_response(
    hass: HomeAssistant,
    domain: str,
    service: str,
    data: dict[str, Any],
    target: dict[str, Any],
) -> Any:
    try:
        return await hass.services.async_call(
            domain, service, data, blocking=True, target=target, return_response=True
        )
    except TypeError:
        await hass.services.async_call(domain, service, data, blocking=True, target=target)
        return None


def clean_service_data(slots: dict[str, Any], names: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for name in names:
        value = slots.get(name, {}).get("value")
        if value not in (None, ""):
            data[name] = value
    return data


async def resolve_mass_media(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Resolve radio names to MASS URIs so Spotify playlists do not win the search."""
    media_id = str(data.get("media_id") or "").strip()
    media_type = str(data.get("media_type") or "").strip().lower()
    if not media_id or "://" in media_id or media_id.startswith("http"):
        return data

    want_radio = media_type == "radio" or looks_like_radio_query(media_id)
    if not want_radio:
        return data

    query = canonicalize_radio_query(media_id)
    data["media_type"] = "radio"
    data.pop("radio_mode", None)

    entry_id = mass_config_entry_id(hass)
    if not entry_id:
        data["media_id"] = query
        return data

    uri = await search_radio_uri(hass, entry_id, query)
    if uri:
        _LOGGER.debug("Radio '%s' resolved to %s", query, uri)
        data["media_id"] = uri
    else:
        data["media_id"] = query
    return data


def scrub_player_destination(media_id: str) -> str:
    """Drop leftover 'im Web' / chrome / browser tokens from STT (no web player path)."""
    parts = media_id.split()
    drop = {"web", "chrome", "browser", "webplayer", "im"}
    keep = [p for p in parts if p.casefold() not in drop]
    return " ".join(keep).strip(" -,\t") or media_id


def canonicalize_radio_query(media_id: str) -> str:
    media_id = scrub_player_destination(media_id)
    parts = media_id.casefold().replace(".", " ").replace("punkt", " ").split()
    compact = " ".join(parts)
    aliases = {
        "housetime",
        "housetime fm",
        "house time",
        "house time fm",
        "haustime",
        "haustime fm",
        "haus time",
        "haus time fm",
        "hostheim",
        "hostheim fm",
        "host heim",
        "host heim fm",
        "hostime",
        "hostime fm",
        "host time",
        "host time fm",
        "housetime web",
        "haustime web",
    }
    if compact in aliases or compact.removesuffix(" web") in {
        "housetime",
        "haustime",
        "house time",
        "haus time",
        "hostheim",
        "hostime",
        "host time",
    }:
        return "housetime.fm"
    if len(parts) >= 2 and parts[-1] in {"fm", "am", "radio"} and "." not in media_id:
        return f"{''.join(parts[:-1])}.{parts[-1]}" if parts[-1] in {"fm", "am"} else media_id
    return media_id


def looks_like_radio_query(media_id: str) -> bool:
    folded = scrub_player_destination(media_id).casefold().replace(" ", "")
    if folded.endswith(".fm") or folded.endswith(".am") or folded.endswith("radio"):
        return True
    return any(
        token in folded
        for token in ("housetime", "haustime", "hostime", "hosttime", "hostheim", "housetimefm", "haustimefm", "hostimefm")
    )

def mass_config_entry_id(hass: HomeAssistant) -> str:
    try:
        entries = hass.config_entries.async_entries("music_assistant")
    except Exception:  # noqa: BLE001 — config entries are a system boundary
        return ""
    return str(entries[0].entry_id) if entries else ""


async def search_radio_uri(hass: HomeAssistant, entry_id: str, query: str) -> str:
    response = await call_with_response(
        hass,
        "music_assistant",
        "search",
        {
            "config_entry_id": entry_id,
            "name": query,
            "media_type": "radio",
            "limit": 10,
            "library_only": False,
        },
        {},
    )
    radios = radio_rows(response)
    if not radios:
        response = await call_with_response(
            hass,
            "music_assistant",
            "get_library",
            {
                "config_entry_id": entry_id,
                "media_type": "radio",
                "search": query,
                "limit": 20,
            },
            {},
        )
        radios = radio_rows(response)
    picked = pick_radio_match(query, radios)
    return str(picked.get("uri") or picked.get("media_id") or "") if picked else ""


def radio_rows(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    # Service responses are often {entry_id: {...}} or flat.
    candidates: list[Any] = [response]
    candidates.extend(response.values())
    rows: list[dict[str, Any]] = []
    for blob in candidates:
        if not isinstance(blob, dict):
            continue
        for key in ("radio", "radios", "items"):
            value = blob.get(key)
            if isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, dict))
        # nested under media type groups
        for value in blob.values():
            if isinstance(value, dict):
                nested = value.get("radio") or value.get("radios") or value.get("items")
                if isinstance(nested, list):
                    rows.extend(item for item in nested if isinstance(item, dict))
    return rows


def pick_radio_match(query: str, radios: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not radios:
        return None
    needle = canonicalize_radio_query(query).casefold().replace(" ", "")
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in radios:
        name = str(row.get("name") or row.get("title") or "").casefold()
        uri = str(row.get("uri") or "").casefold()
        compact_name = name.replace(" ", "")
        score = 0
        if compact_name == needle or name == query.casefold():
            score += 100
        elif needle and (needle in compact_name or compact_name in needle):
            score += 50
        elif "housetime" in compact_name or "housetime" in uri:
            score += 40
        if uri.startswith("library://radio"):
            score += 20
        elif "radio" in uri:
            score += 10
        if "playlist" in uri or "spotify://playlist" in uri:
            score -= 100
        if score > 0:
            scored.append((score, row))
    if not scored:
        # Fall back to first library radio result rather than a playlist.
        for row in radios:
            uri = str(row.get("uri") or "")
            if "playlist" in uri:
                continue
            if "radio" in uri or uri.startswith("library://"):
                return row
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def retarget_satellite_media(
    hass: HomeAssistant,
    user_input: Any,
    name: str,
    slots: dict[str, Any],
    item: dict,
    entity_id: str,
) -> tuple[dict[str, Any], dict, str]:
    """When Assist speaks from a voice satellite, keep music on that satellite player.

    Bare play often resolves to a preferred HomePod in the same room. If the
    conversation carries a satellite/device id, force Music Assistant onto the
    MASS satellite player (or the ESPHome media_player as last resort).
    """
    if name not in {
        "MassPlayMedia",
        "HassMediaSearchAndPlay",
        "MassFavorite",
        "MassGetQueue",
        "MassTransferQueue",
        "HassSetVolume",
        "HassSetVolumeRelative",
        "HassMediaPlayerMute",
        "HassMediaPlayerUnmute",
        "HassMediaPause",
        "HassMediaUnpause",
        "HassMediaNext",
        "HassMediaPrevious",
    }:
        return slots, item, entity_id
    satellite_id = str(getattr(user_input, "satellite_id", None) or "")
    device_id = str(getattr(user_input, "device_id", None) or "")
    if not satellite_id and not device_id:
        return slots, item, entity_id
    if "satelit" in entity_id.lower() or "satellite" in entity_id.lower() or "respeaker" in entity_id.lower():
        return slots, item, entity_id

    volume_like = name in {
        "HassSetVolume",
        "HassSetVolumeRelative",
        "HassMediaPlayerMute",
        "HassMediaPlayerUnmute",
    }
    target = satellite_media_player(hass, satellite_id, device_id, prefer_mass=not volume_like)
    if not target or target == entity_id:
        return slots, item, entity_id

    _LOGGER.info("Satellite media retarget %s -> %s (%s)", entity_id or "-", target, name)
    slots = {**slots, "entity_id": {"value": target}}
    existing = [slot for slot in (item.get("slots") or []) if not (isinstance(slot, dict) and slot.get("name") == "entity_id")]
    item = {**item, "slots": [*existing, {"name": "entity_id", "value": target}]}
    return slots, item, target


def satellite_media_player(
    hass: HomeAssistant, satellite_id: str, device_id: str, *, prefer_mass: bool
) -> str:
    """Pick satellite media_player: MASS for play, ESPHome for volume."""
    registry = entity_registry.async_get(hass)
    wanted_devices: set[str] = {item for item in (device_id,) if item}
    for candidate in (satellite_id,):
        if not candidate:
            continue
        if "." in candidate:
            entry = registry.async_get(candidate)
            if entry and entry.device_id:
                wanted_devices.add(entry.device_id)
        else:
            wanted_devices.add(candidate)

    mass_hits: list[str] = []
    esp_hits: list[str] = []
    for state in hass.states.async_all("media_player"):
        eid = str(state.entity_id)
        blob = f"{eid} {getattr(state, 'name', '')}".casefold()
        if not any(token in blob for token in ("satelit", "satellite", "respeaker", "xvf3800")):
            continue
        entry = registry.async_get(eid)
        platform = str(getattr(entry, "platform", "") or "")
        same_device = bool(entry and entry.device_id and entry.device_id in wanted_devices)
        if music_assistant_player(hass, eid):
            mass_hits.append(eid)
            if prefer_mass and same_device:
                return eid
        else:
            esp_hits.append(eid)
            if (not prefer_mass) and same_device:
                return eid
            if "esphome" in platform and same_device and not prefer_mass:
                return eid

    if prefer_mass:
        for eid in mass_hits:
            if eid.endswith(".satelite") or eid.endswith(".satellite"):
                return eid
        if mass_hits:
            return mass_hits[0]
        return esp_hits[0] if esp_hits else ""

    for eid in esp_hits:
        if "media_player" in eid and "satelit" in eid:
            return eid
    if esp_hits:
        return esp_hits[0]
    return mass_hits[0] if mass_hits else ""


def media_missing(state: Any) -> bool:
    return str(getattr(state, "state", "")).lower() in {"unavailable", "unknown"}


def _queue_rows(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [row for row in response if isinstance(row, dict)]
    if not isinstance(response, dict):
        return []
    for key in ("items", "queue", "queue_items", "media_items"):
        nested = response.get(key)
        if isinstance(nested, list):
            return [row for row in nested if isinstance(row, dict)]
        if isinstance(nested, dict):
            found = _queue_rows(nested)
            if found:
                return found
    return []


async def start_idle_music(
    hass: HomeAssistant,
    entity_id: str,
    pack: str,
    item: dict,
    exposed: Callable[[str], bool],
) -> IntentStepResult | None:
    state = hass.states.get(entity_id) if entity_id.startswith("media_player.") else None
    if state is None or not exposed(entity_id) or media_missing(state):
        return None
    if str(getattr(state, "state", "")).lower() not in {"idle", "off", "on", "standby"}:
        return None
    if music_assistant_player(hass, entity_id):
        query = "Musik" if pack == "de" or pack.startswith("de-") else "music"
        return await run_mass(
            hass,
            "MassPlayMedia",
            {"entity_id": {"value": entity_id}, "media_id": {"value": query}},
            pack,
            {
                **item,
                "name": "MassPlayMedia",
                "slots": [*(item.get("slots") or []), {"name": "media_id", "value": query}],
            },
            exposed,
        )
    device_id = alexa_device_id(hass, entity_id)
    if not device_id:
        return None
    command = "spiel Musik" if pack == "de" or pack.startswith("de-") else "play music"
    try:
        await hass.services.async_call(
            "alexa_devices",
            "send_text_command",
            {"device_id": device_id, "text_command": command},
            blocking=True,
        )
    except Exception as err:  # noqa: BLE001 — Alexa is a service boundary
        _LOGGER.debug("Alexa-Wiedergabe für %s fehlgeschlagen: %s", entity_id, err)
        return fail(str(err) or "alexa_play_failed")
    spoken = {
        **item,
        "name": "HassMediaSearchAndPlay",
        "slots": [*(item.get("slots") or []), {"name": "name", "value": state.name}],
    }
    extra = [row] if (row := entity_from_state(state)) else None
    return ok(await spoken_after_execute(hass, pack, "default", spoken, extra_entities=extra))


def tv_request(text: str) -> bool:
    folded = f" {(text or '').casefold()} "
    return "fernseher" in folded or "television" in folded or " tv " in folded or folded.startswith(" tv")


def tv_named(entity_id: str, state: Any) -> bool:
    attrs = getattr(state, "attributes", None) or {} if state is not None else {}
    name = str(attrs.get("friendly_name") or "") if isinstance(attrs, dict) else ""
    name = name or str(getattr(state, "name", "") or "")
    blob = f"{entity_id} {name}".casefold()
    return "tv" in blob or "fernseher" in blob or "television" in blob


def registry_entry(hass: HomeAssistant, entity_id: str) -> Any:
    try:
        return entity_registry.async_get(hass).async_get(entity_id)
    except Exception:  # noqa: BLE001 — registry is a system boundary
        return None


def alexa_device_id(hass: HomeAssistant, entity_id: str) -> str:
    entry = registry_entry(hass, entity_id)
    if entry is None or getattr(entry, "platform", None) != "alexa_devices":
        return ""
    return str(getattr(entry, "device_id", "") or "")


def music_assistant_player(hass: HomeAssistant, entity_id: str) -> bool:
    if not entity_id.startswith("media_player."):
        return False
    state = hass.states.get(entity_id)
    attrs = getattr(state, "attributes", None) or {}
    if isinstance(attrs, dict) and (
        attrs.get("mass_player_type") or "music assistant" in str(attrs.get("source") or "").lower()
    ):
        return True
    entry = registry_entry(hass, entity_id)
    return bool(entry is not None and getattr(entry, "platform", None) == "music_assistant")


def favorite_button(hass: HomeAssistant, player: str) -> str:
    base = player.split(".", 1)[-1].removesuffix("_2")
    for state in hass.states.async_all("button"):
        entity_id = str(state.entity_id)
        label = f"{entity_id} {getattr(state, 'name', '')}".lower()
        if ("favorisieren" in label or "favorite" in label) and (not base or base in entity_id):
            return entity_id
    return ""
