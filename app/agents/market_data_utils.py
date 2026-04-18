import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests


_MARKET_CACHE = {
    "cached_at": 0.0,
    "payload": None,
}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_cache_ttl_seconds() -> int:
    raw_value = os.getenv("MARKET_DATA_CACHE_TTL_SECONDS", "300")
    try:
        return max(60, int(raw_value))
    except (TypeError, ValueError):
        return 300


def _build_quote(name: str, raw_data: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_data, dict):
        return None

    bid = _safe_float(raw_data.get("bid") or raw_data.get("compra"))
    ask = _safe_float(raw_data.get("ask") or raw_data.get("venta"))
    last = _safe_float(
        raw_data.get("last")
        or raw_data.get("price")
        or raw_data.get("promedio")
        or raw_data.get("close")
    )

    # Si no viene `last`, usamos un promedio simple compra/venta.
    if last is None and bid is not None and ask is not None:
        last = round((bid + ask) / 2, 2)

    if bid is None and ask is None and last is None:
        return None

    updated_at = (
        raw_data.get("updated_at")
        or raw_data.get("fechaActualizacion")
        or raw_data.get("timestamp")
        or raw_data.get("time")
    )

    return {
        "name": name,
        "bid": bid,
        "ask": ask,
        "last": last,
        "updated_at": updated_at,
        "source": source,
    }


def _fetch_from_criptoya(timeout: int = 10) -> Dict[str, Any]:
    response = requests.get("https://criptoya.com/api/dolar", timeout=timeout)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        return {"status": "error", "message": "Formato inválido de CriptoYa", "quotes": {}}

    quotes: Dict[str, Any] = {}

    blue_quote = _build_quote("Dolar Blue", data.get("blue", {}), "criptoya.blue")
    if blue_quote:
        quotes["dolar_blue"] = blue_quote

    mep_quote = _build_quote("Dolar MEP", data.get("mep", {}), "criptoya.mep")
    if mep_quote:
        quotes["dolar_mep"] = mep_quote

    ccl_raw = data.get("ccl") or data.get("contadoconliqui") or {}
    ccl_quote = _build_quote("Dolar CCL", ccl_raw, "criptoya.ccl")
    if ccl_quote:
        quotes["dolar_ccl"] = ccl_quote

    status = "success" if quotes else "error"
    return {
        "status": status,
        "message": "ok" if quotes else "No se encontraron cotizaciones en CriptoYa",
        "source": "criptoya",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "quotes": quotes,
    }


def _fetch_from_dolarapi(timeout: int = 10) -> Dict[str, Any]:
    response = requests.get("https://dolarapi.com/v1/dolares", timeout=timeout)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list):
        return {"status": "error", "message": "Formato inválido de DolarAPI", "quotes": {}}

    quotes: Dict[str, Any] = {}

    for item in data:
        if not isinstance(item, dict):
            continue

        token = f"{item.get('casa', '')} {item.get('nombre', '')}".lower()

        if "blue" in token:
            parsed = _build_quote("Dolar Blue", item, "dolarapi.blue")
            if parsed:
                quotes["dolar_blue"] = parsed
        elif "bolsa" in token or "mep" in token:
            parsed = _build_quote("Dolar MEP", item, "dolarapi.mep")
            if parsed:
                quotes["dolar_mep"] = parsed
        elif "contado" in token or "liqui" in token or "ccl" in token:
            parsed = _build_quote("Dolar CCL", item, "dolarapi.ccl")
            if parsed:
                quotes["dolar_ccl"] = parsed

    status = "success" if quotes else "error"
    return {
        "status": status,
        "message": "ok" if quotes else "No se encontraron cotizaciones en DolarAPI",
        "source": "dolarapi",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "quotes": quotes,
    }


def get_market_data_snapshot(force_refresh: bool = False, timeout: int = 10) -> Dict[str, Any]:
    ttl_seconds = _read_cache_ttl_seconds()
    now = time.time()

    cached_payload = _MARKET_CACHE.get("payload")
    cached_at = _MARKET_CACHE.get("cached_at", 0.0)

    if not force_refresh and cached_payload and (now - cached_at) < ttl_seconds:
        response_payload = dict(cached_payload)
        response_payload["cache_hit"] = True
        return response_payload

    errors = []
    for fetcher in (_fetch_from_criptoya, _fetch_from_dolarapi):
        try:
            result = fetcher(timeout=timeout)
            if result.get("status") == "success" and result.get("quotes"):
                result["cache_hit"] = False
                _MARKET_CACHE["payload"] = result
                _MARKET_CACHE["cached_at"] = now
                return result
            errors.append(result.get("message", "respuesta vacía"))
        except Exception as exc:
            errors.append(str(exc))

    return {
        "status": "error",
        "message": " | ".join(errors) if errors else "No se pudieron obtener cotizaciones",
        "source": "none",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "quotes": {},
        "cache_hit": False,
    }
