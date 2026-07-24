"""
Resolve Tailscale identity for a client IP via tailscaled local API (unix socket).
Ported from ChronoTrace/DoqumentWeb for Django on Synology.

Default socket: /volume6/@appdata/Tailscale/tailscaled.sock
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote


DEFAULT_SOCKET = os.environ.get(
    "TAILSCALE_SOCKET",
    "/volume6/@appdata/Tailscale/tailscaled.sock",
)
DEFAULT_CLI = os.environ.get("TAILSCALE_CLI", "/usr/local/bin/tailscale")


@dataclass
class TailscaleWhois:
    login_name: str
    display_name: str
    user_id: str = ""
    node_name: str = ""
    profile_pic_url: str = ""


def normalize_remote_ip(addr: Optional[str]) -> Optional[str]:
    if not addr:
        return None
    a = str(addr).strip()
    if a.startswith("[") and a.endswith("]"):
        a = a[1:-1]
    if a.startswith("::ffff:"):
        a = a[7:]
    a = a.split("%")[0]
    return a or None


def is_tailscale_ip(ip: str) -> bool:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)\.(\d+)$", ip)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return a == 100 and 64 <= b <= 127
    lower = ip.lower()
    if lower.startswith("fd7a:115c:a1e0:"):
        return True
    if lower.startswith("fd7a:"):
        return True
    return False


def _local_api_get(path: str, timeout: float = 3.0) -> Tuple[int, str]:
    sock_path = os.environ.get("TAILSCALE_SOCKET", DEFAULT_SOCKET)
    # HTTP over Unix domain socket
    request = (
        f"GET {path} HTTP/1.0\r\n"
        f"Host: local-tailscaled.sock\r\n"
        f"\r\n"
    ).encode("utf-8")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(sock_path)
        s.sendall(request)
        chunks: List[bytes] = []
        while True:
            try:
                data = s.recv(65536)
            except socket.timeout:
                break
            if not data:
                break
            chunks.append(data)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    if "\r\n\r\n" not in raw:
        return 0, raw
    header, body = raw.split("\r\n\r\n", 1)
    status = 0
    first = header.split("\r\n", 1)[0]
    m = re.search(r"HTTP/\d\.\d\s+(\d+)", first)
    if m:
        status = int(m.group(1))
    return status, body


def parse_whois_json(body: str) -> Optional[TailscaleWhois]:
    try:
        j = json.loads(body)
    except json.JSONDecodeError:
        return None
    profile = j.get("UserProfile") or j.get("User") or {}
    login = (
        profile.get("LoginName")
        or profile.get("loginName")
        or profile.get("Login")
        or ""
    )
    if not login:
        return None
    node = j.get("Node") or {}
    hostinfo = node.get("Hostinfo") or {}
    node_name = (
        node.get("ComputedName")
        or node.get("Name")
        or hostinfo.get("Hostname")
        or ""
    )
    return TailscaleWhois(
        login_name=str(login),
        display_name=str(profile.get("DisplayName") or profile.get("displayName") or login),
        user_id=str(profile.get("ID") or profile.get("id") or ""),
        node_name=str(node_name).rstrip("."),
        profile_pic_url=str(profile.get("ProfilePicURL") or profile.get("profilePicURL") or ""),
    )


def parse_whois_cli(text: str) -> Optional[TailscaleWhois]:
    email = re.search(r"([\w.+-]+@[\w.-]+\.\w+)", text)
    login = None
    m = re.search(r"^\s*Name:\s*(\S+)", text, re.M)
    if m:
        login = m.group(1)
    if email:
        login = email.group(1)
    if not login:
        return None
    machine = ""
    mm = re.search(r"Machine:\s*[\s\S]*?Name:\s*(\S+)", text)
    if mm:
        machine = mm.group(1).rstrip(".")
    return TailscaleWhois(
        login_name=login,
        display_name=login,
        user_id="",
        node_name=machine,
    )


def tailscale_whois(ip: str, port: Optional[int] = None) -> Optional[TailscaleWhois]:
    candidates: List[str] = []
    if ":" in ip:  # IPv6
        candidates.append(ip)
        if port is not None:
            candidates.append(f"[{ip}]:{port}")
    else:
        if port is not None:
            candidates.append(f"{ip}:{port}")
        candidates.append(f"{ip}:1")
        candidates.append(ip)

    for addr in candidates:
        try:
            status, body = _local_api_get(
                f"/localapi/v0/whois?addr={quote(addr, safe='')}"
            )
            if status == 200:
                parsed = parse_whois_json(body)
                if parsed:
                    return parsed
        except OSError:
            continue

    cli = os.environ.get("TAILSCALE_CLI", DEFAULT_CLI)
    try:
        proc = subprocess.run(
            [cli, "whois", ip],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if proc.returncode == 0 and proc.stdout:
            return parse_whois_cli(proc.stdout)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def parse_allow_logins() -> Optional[List[str]]:
    raw = os.environ.get("TAILSCALE_ALLOW_LOGINS") or ""
    # Also allow Django settings via env already loaded
    try:
        from django.conf import settings

        raw = raw or getattr(settings, "TAILSCALE_ALLOW_LOGINS", "") or ""
    except Exception:
        pass
    items = [s.strip().lower() for s in re.split(r"[,\s]+", raw) if s.strip()]
    return items or None


def is_login_allowed(login_name: str) -> bool:
    allow = parse_allow_logins()
    if not allow:
        # Empty allowlist = deny managers (safer for public search app)
        # Managers must be explicitly listed.
        return False
    return login_name.strip().lower() in allow


def _header(request, name: str) -> Optional[str]:
    # Django META uses HTTP_X_FOO
    key = "HTTP_" + name.upper().replace("-", "_")
    v = request.META.get(key) or request.META.get(name)
    if isinstance(v, (list, tuple)):
        return v[0] if v else None
    return v if isinstance(v, str) else None


def get_client_ip_port(request) -> Tuple[Optional[str], Optional[int]]:
    raw = request.META.get("REMOTE_ADDR")
    port_raw = request.META.get("REMOTE_PORT")
    try:
        port = int(port_raw) if port_raw else None
    except (TypeError, ValueError):
        port = None
    socket_ip = normalize_remote_ip(raw)

    if socket_ip in ("127.0.0.1", "::1"):
        xri = _header(request, "X-Real-IP")
        xff = _header(request, "X-Forwarded-For")
        if xri:
            ip = normalize_remote_ip(xri.split(",")[0].strip())
            if ip:
                return ip, port
        if xff:
            ip = normalize_remote_ip(xff.split(",")[0].strip())
            if ip:
                return ip, port
    elif not socket_ip:
        xri = _header(request, "X-Real-IP")
        xff = _header(request, "X-Forwarded-For")
        if xri:
            ip = normalize_remote_ip(xri.split(",")[0].strip())
            if ip:
                return ip, None
        if xff:
            ip = normalize_remote_ip(xff.split(",")[0].strip())
            if ip:
                return ip, None

    return socket_ip, port


def resolve_client_identity(request) -> Dict[str, Any]:
    """
    Paths:
    1) WhoIs on client IP
    2) Tailscale Serve identity headers
    3) Loopback + single-entry allowlist (Synology userspace proxy)
    """
    ip, port = get_client_ip_port(request)

    hdr_login = _header(request, "Tailscale-User-Login") or _header(
        request, "tailscale-user-login"
    )
    if hdr_login:
        return {
            "ip": ip,
            "port": port,
            "from_tailscale": True,
            "trust_path": "header",
            "whois": TailscaleWhois(
                login_name=hdr_login,
                display_name=_header(request, "Tailscale-User-Name")
                or _header(request, "tailscale-user-name")
                or hdr_login,
                user_id=_header(request, "Tailscale-User-Id")
                or _header(request, "tailscale-user-id")
                or "",
                node_name="",
            ),
        }

    if ip and ip not in ("127.0.0.1", "::1"):
        whois = tailscale_whois(ip, port)
        if whois:
            return {
                "ip": ip,
                "port": port,
                "from_tailscale": True,
                "trust_path": "whois",
                "whois": whois,
            }

    loopback = not ip or ip in ("127.0.0.1", "::1")
    if loopback:
        allow = parse_allow_logins()
        if allow and len(allow) == 1:
            login_name = allow[0]
            return {
                "ip": ip or "127.0.0.1",
                "port": port,
                "from_tailscale": True,
                "trust_path": "loopback-allowlist",
                "whois": TailscaleWhois(
                    login_name=login_name,
                    display_name=login_name,
                    user_id="loopback",
                    node_name="tailscale-userspace-proxy",
                ),
            }

    return {
        "ip": ip,
        "port": port,
        "from_tailscale": False,
        "trust_path": "none",
        "whois": None,
    }
