import ipaddress
import re


_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def normalize_host(host: str) -> str:
    value = host.strip()
    if not value or len(value) > 253 or any(char.isspace() for char in value):
        raise ValueError("Host must be an IPv4/IPv6 address or a valid DNS hostname.")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass

    hostname = value[:-1] if value.endswith(".") else value
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Host is not a valid DNS hostname.") from exc
    labels = ascii_hostname.split(".")
    if not labels or any(not _HOST_LABEL.fullmatch(label) for label in labels):
        raise ValueError("Host is not a valid DNS hostname.")
    return ascii_hostname.lower()
