FAKE_CERT = (
    "-----BEGIN CERTIFICATE-----\n"
    "MIIFNzCCBB+gAwIBAgISdvFeodKvOk9dXwxXsmEqh9LTMA0GCSqGSIb3DQEBCwUA"
    "MEUxCzAJBgNVBAYTAlVTMRIwEAYDVQQKEwlDZXJ0YWlubHkxIjAgBgNVBAMTGUNl"
    "cnRhaW5seSBJbnRlcm1lZGlhdGUgUjEwHhcNMjUwMzMwMjIzMjM4WhcNMjUwNDI5"
    "MjIzMjM3WjAfMR0wGwYDVQQDExRtZXRyaWNzLmV2ZXJub3RlLmNvbTCCASIwDQYJ"
    "KoZIhvcNAQEBBQADggEPADCCAQoCggEBALEAv036TEI/xnvvNN0Bgjy7h6b+ybr6"
    "EUtIXnXO/N7FKofdDnMbMFNubJ2zBLCk0zKl7Treh6uJSGTS5oemROQxQItErOqf"
    "G/ac5UOlwkzzTNb+2rO69BS9ujt/z5pCdhhwWgyJ3Ki1zQIsLGkvF8nNDhw2Gza1"
    "+eUz1YM0hGHrlYPr9jArR68Khpak2YB2Xa02lyA7wjmigzEux39cSjA77hgUKEMU"
    "zbuw47dGxrvrLCUHgZsTsC5KDYSyn4uLqco3R4QX9Re54K90vFAIuasOj/PcQ1YK"
    "TgCVlzprC1St0G7hPNPUYMSjTU645+7dy95zbVfMehCRrL8Sn9TwAWUCAwEAAaOC"
    "AkUwggJBMA4GA1UdDwEB/wQEAwIFoDATBgNVHSUEDDAKBggrBgEFBQcDATAMBgNV"
    "HRMBAf8EAjAAMB0GA1UdDgQWBBQ/coRC0hg4cl7LlDd/8wwtCKaijzAfBgNVHSME"
    "GDAWgBS9l53fodgbJZnjDAQGiWQS12UkxzBlBggrBgEFBQcBAQRZMFcwLAYIKwYB"
    "BQUHMAGGIGh0dHA6Ly9vY3NwLmludC1yMS5jZXJ0YWlubHkuY29tMCcGCCsGAQUF"
    "BzAChhtodHRwOi8vaW50LXIxLmNlcnRhaW5seS5jb20wRwYDVR0RBEAwPoIUY29u"
    "dGVudC5ldmVybm90ZS5jb22CFG1ldHJpY3MuZXZlcm5vdGUuY29tghB3d3cuZXZl"
    "cm5vdGUuY29tMBMGA1UdIAQMMAowCAYGZ4EMAQIBMIIBBQYKKwYBBAHWeQIEAgSB"
    "9gSB8wDxAHYAzxFW7tUufK/zh1vZaS6b6RpxZ0qwF+ysAdJbd87MOwgAAAGV6WUM"
    "dQAABAMARzBFAiBGq117LNYc/u3qm9doKY9arYRdHJcCYzbyZVkRHcZyPAIhAPh5"
    "Ti9oeVR16znviJS5VzBRLcZn+bYzb5CCig7CkFulAHcAouMK5EXvva2bfjjtR2d3"
    "U9eCW4SU1yteGyzEuVCkR+cAAAGV6WUPaQAABAMASDBGAiEA9RH/1rxClvRJR+74"
    "/12els+MRYUP8ZDjrzWIh8Qn1RoCIQDuNzJ6NrxVgIShq7XFIaempay+hbrFQYZ7"
    "v4Ka60OkijANBgkqhkiG9w0BAQsFAAOCAQEADqEepHIdpxBGFlqht2VtDcNUtSR4"
    "hL7yZSngA6BZxMnmxEFu6tnXEVAIfJsCDtAFbsYn7kk7VA9I0UvGLcWHuoFGAjSs"
    "Qotu/hOTWqztDeFe72Jb8U4sJ1FO51F6ylKFtISQY9VWGkzfoihKbN8genH3AlYj"
    "bg6I8TRiJd/FEetFwmJasPNu5/mNPmervjsZSk/gArHffBiUGzjOIrEVI+FI8rzP"
    "x1R3y0rrDdlUee6ZmkPBqbXbYvBkkcmzqPb0RevBaG/JhFtsi+arWXkJBrZCxGSD"
    "GQ5Btop/mGPwQMDCm6FOgpNKzcQpkX3KZMBtG+AhBZpNDYBCwrcgd300gA==\n"
    "-----END CERTIFICATE-----"
)


def test_manage_ping_ok(cli_invoker, mock_evernote_client):
    result = cli_invoker("manage", "ping")

    assert result.exit_code == 0
    assert "Connection OK" in result.output


def test_manage_ping_bad_ssl(cli_invoker, mock_evernote_client, mocker):
    mock_evernote_client.fake_ping_ssl_error = True

    fake_ssl_cert = mocker.patch(
        "evernote_backup.evernote_client_util_ssl.ssl.get_server_certificate"
    )
    fake_ssl_cert.return_value = FAKE_CERT

    result = cli_invoker("-v", "manage", "ping")

    assert result.exit_code == 1
    assert "test ssl error" in result.output


def test_manage_ping_certifi_ssl(cli_invoker, mock_evernote_client, mocker):
    mock_evernote_client.fake_ping_ssl_error = True

    fake_ssl_cert = mocker.patch(
        "evernote_backup.evernote_client_util_ssl.ssl.get_server_certificate"
    )
    fake_ssl_cert.return_value = FAKE_CERT

    result = cli_invoker("-v", "manage", "ping")

    assert result.exit_code == 1
    assert "SSL CA store: certifi" in result.output


def test_manage_ping_system_ssl(cli_invoker, mock_evernote_client, mocker):
    mock_evernote_client.fake_ping_ssl_error = True

    fake_ssl_cert = mocker.patch(
        "evernote_backup.evernote_client_util_ssl.ssl.get_server_certificate"
    )
    fake_ssl_cert.return_value = FAKE_CERT

    result = cli_invoker("-v", "manage", "ping", "--use-system-ssl-ca")

    assert result.exit_code == 1
    assert "SSL CA store: system" in result.output
