import logging
import ssl
import tempfile
from pathlib import Path
from pprint import pformat
from typing import Optional, cast

from requests.utils import DEFAULT_CA_BUNDLE_PATH, extract_zipped_paths

logger = logging.getLogger(__name__)


def get_cafile_path(use_system_ssl_ca: bool) -> Optional[str]:
    if use_system_ssl_ca:
        return None

    return str(extract_zipped_paths(DEFAULT_CA_BUNDLE_PATH))


def log_ssl_debug_info(backend_host: str, use_system_ssl_ca: bool) -> None:
    cert_info = _get_ssl_cert_info(backend_host)
    cert_domains = ", ".join(_parse_cert_domains(cert_info))
    cert_serial_number = cert_info.get("serialNumber")
    cert_expiration = cert_info.get("notAfter")

    cafile = get_cafile_path(use_system_ssl_ca)

    if use_system_ssl_ca:
        logger.debug("SSL CA store: system")
    else:
        logger.debug("SSL CA store: certifi")
        logger.debug(f"SSL CA store path: {cafile}")

    context = ssl.create_default_context(cafile=cafile)

    logger.debug(f"SSL store stats: {context.cert_store_stats()}")
    logger.debug(f"Received SSL certificate for host '{backend_host}':")
    logger.debug(pformat(cert_info))
    logger.debug(f"SSL certificate domain(s): {cert_domains}")
    logger.debug(f"SSL certificate serial number: {cert_serial_number}")
    logger.debug(f"SSL certificate expiration date: {cert_expiration}")

    ssl_verify_url = f"https://mxtoolbox.com/SuperTool.aspx?action=https%3a{backend_host}&run=toolpage"

    logger.debug(f"You can verify it here: {ssl_verify_url}")
    logger.debug(
        "Certificate serial number should match,"
        " otherwise your firewall or proxy is intercepting HTTPS traffic"
    )
    logger.debug(
        "If certificate serial number is OK,"
        " then bundled CA store (certifi) is outdated and you should try using --use-system-ssl-ca flag"
    )


def _get_ssl_cert_info(hostname: str, port: int = 443) -> dict:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
    ) as tmp_cert_file:
        tmp_cert_file.write(ssl.get_server_certificate((hostname, port)))
        tmp_cert_file_path = Path(tmp_cert_file.name)

    cert_dict = ssl._ssl._test_decode_cert(str(tmp_cert_file_path))  # type: ignore

    tmp_cert_file_path.unlink()

    return cast(dict, cert_dict)


def _parse_cert_domains(cert_dict: dict) -> list[str]:
    domains = set()

    for type_name, value in cert_dict.get("subjectAltName", []):
        if type_name == "DNS":
            domains.add(value)

    for field in cert_dict.get("subject", []):
        for key, value in field:
            if key == "commonName":
                domains.add(value)
                break

    return sorted(domains)
