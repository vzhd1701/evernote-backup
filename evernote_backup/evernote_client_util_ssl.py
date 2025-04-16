import logging
import os
import ssl
import tempfile
from pprint import pformat
from ssl import create_default_context, get_server_certificate

from requests.utils import DEFAULT_CA_BUNDLE_PATH, extract_zipped_paths

logger = logging.getLogger(__name__)


def log_ssl_debug_info(backend_host: str, use_system_ssl_ca: bool):
    cert_info = _get_ssl_cert_info(backend_host)
    cert_domains = ", ".join(_parse_cert_domains(cert_info))
    cert_serial_number = cert_info.get("serialNumber")
    cert_expiration = cert_info.get("notAfter")

    if use_system_ssl_ca:
        cafile = None
        logger.debug("SSL CA store: system")
    else:
        cafile = extract_zipped_paths(DEFAULT_CA_BUNDLE_PATH)
        logger.debug("SSL CA store: certifi")
        logger.debug(f"SSL CA store path: {cafile}")

    context = create_default_context(cafile=cafile)

    logger.debug(f"SSL store stats: {context.cert_store_stats()}")
    logger.debug(f"Received SSL certificate for host '{backend_host}':")
    logger.debug(pformat(cert_info))
    logger.debug(f"SSL certificate domain(s): {cert_domains}")
    logger.debug(f"SSL certificate serial number: {cert_serial_number}")
    logger.debug(f"SSL certificate expiration date: {cert_expiration}")

    ssl_verify_url = f"https://mxtoolbox.com/SuperTool.aspx?action=https%3a{backend_host}&run=toolpage"

    logger.debug(f"You can verify it here: {ssl_verify_url}")
    logger.debug(
        f"Certificate serial number should match,"
        " otherwise your firewall or proxy is intercepting HTTPS traffic"
    )


def _get_ssl_cert_info(hostname, port=443):
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
    ) as tmp_cert_file:
        tmp_cert_file.write(get_server_certificate((hostname, port)))

    cert_dict = ssl._ssl._test_decode_cert(tmp_cert_file.name)

    os.unlink(tmp_cert_file.name)

    return cert_dict


def _parse_cert_domains(cert_dict):
    domains = set()

    if "subjectAltName" in cert_dict:
        for type_name, value in cert_dict["subjectAltName"]:
            if type_name == "DNS":
                domains.add(value)

    if "subject" in cert_dict:
        for field in cert_dict["subject"]:
            for key, value in field:
                if key == "commonName":
                    domains.add(value)
                    break

    return sorted(domains)
