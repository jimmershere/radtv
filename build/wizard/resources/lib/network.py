"""Show the wizard user their current public IP / ASN / country.

Hits three independent public IP echo services in parallel; if they all
agree the result is trustworthy. Used by the "Check anonymizer status"
wizard action so users can verify their VPN is actually doing something
before they start streaming.

Privacy note: this DOES reach out to third-party services (ipinfo.io,
ifconfig.io, icanhazip.com). The user explicitly invoked the action, and
those services see only one HTTPS request each. No caching, no
identifiers, nothing sent beyond what they would learn from any normal
web request.
"""
from __future__ import annotations

import json
import re
import ssl
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional


HTTP_TIMEOUT = 6
USER_AGENT = "B@Dtv-wizard-anonymizer-check/2.0"


@dataclass
class IPCheck:
    service: str
    ip: str = ""
    country: str = ""
    asn: str = ""
    error: str = ""


_SERVICES = [
    ("ipinfo.io",   "https://ipinfo.io/json",     "json"),
    ("ifconfig.io", "https://ifconfig.io/all.json", "json"),
    ("icanhazip",   "https://ipv4.icanhazip.com", "raw"),
]


def _fetch(url: str) -> tuple[Optional[bytes], Optional[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=ctx) as resp:
            return resp.read(), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ssl.SSLError) as exc:
        return None, str(exc)


_IP_RE     = re.compile(r'"ip"\s*:\s*"([^"]+)"')
_COUNTRY_RE = re.compile(r'"country(?:_iso)?"\s*:\s*"([^"]+)"')
_ASN_RE    = re.compile(r'"(?:org|asn|asn_org)"\s*:\s*"([^"]+)"')


def _parse(blob: bytes, kind: str) -> tuple[str, str, str]:
    text = blob.decode("utf-8", errors="replace")
    if kind == "raw":
        return text.strip(), "", ""
    ip = (_IP_RE.search(text) or [None, ""])
    country = (_COUNTRY_RE.search(text) or [None, ""])
    asn = (_ASN_RE.search(text) or [None, ""])
    return (
        ip.group(1) if hasattr(ip, "group") else "",
        country.group(1) if hasattr(country, "group") else "",
        asn.group(1) if hasattr(asn, "group") else "",
    )


def _probe(spec: tuple[str, str, str], out: List[IPCheck], idx: int) -> None:
    label, url, kind = spec
    blob, err = _fetch(url)
    if blob is None:
        out[idx] = IPCheck(service=label, error=err or "unknown")
        return
    try:
        ip, country, asn = _parse(blob, kind)
        out[idx] = IPCheck(service=label, ip=ip, country=country, asn=asn)
    except Exception as exc:  # pragma: no cover - parser is defensive already
        out[idx] = IPCheck(service=label, error=f"parse: {exc}")


def check_public_ip(timeout: float = HTTP_TIMEOUT + 2) -> List[IPCheck]:
    """Run all probes in parallel. Returns one IPCheck per service."""
    out: List[IPCheck] = [IPCheck(service=spec[0]) for spec in _SERVICES]
    threads: List[threading.Thread] = []
    for idx, spec in enumerate(_SERVICES):
        t = threading.Thread(target=_probe, args=(spec, out, idx), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=timeout)
    return out


def format_for_dialog(results: List[IPCheck]) -> str:
    ips = [r.ip for r in results if r.ip]
    consistent = len(ips) >= 2 and len(set(ips)) == 1

    lines = ["Public IP as seen by:"]
    for r in results:
        if r.error:
            lines.append(f"  [B]{r.service:12}[/B]  [COLOR=FF6B1A1F]ERROR[/COLOR]  {r.error}")
        else:
            country = r.country or "?"
            asn = r.asn or "?"
            lines.append(f"  [B]{r.service:12}[/B]  {r.ip}  [I]{country}[/I]  {asn}")
    lines.append("")

    if consistent:
        lines.append(
            f"[COLOR=FF1F6E4F]Services agree: {ips[0]}[/COLOR]\n\n"
            "If this IP and country match your VPN's exit node, you're anonymized.\n"
            "If they match your ISP, you are NOT on a VPN."
        )
    elif ips:
        lines.append(
            "[COLOR=FFD4A24C]Services disagree.[/COLOR] Treat the result with suspicion: "
            "one of the endpoints may be down, or a captive portal is in the way."
        )
    else:
        lines.append(
            "[COLOR=FF6B1A1F]No services responded.[/COLOR] You may be offline, "
            "or your kill-switch is blocking egress because the VPN tunnel is down."
        )
    return "\n".join(lines)
