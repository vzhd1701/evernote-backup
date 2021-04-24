from io import BytesIO

import pytest
from thrift.protocol import TBinaryProtocol
from thrift.transport import TTransport

from evernote_backup.evernote_client import ClientV2, Store
from evernote_backup.evernote_client_classes import (
    authenticateLongSessionV2_args,
    authenticateLongSessionV2_request,
)
from evernote_backup.evernote_client_util import network_retry


class TMemoryProper(TTransport.TMemoryBuffer):
    def __init__(self, value=None):
        if value is not None:
            self._buffer = BytesIO(value)
        else:
            self._buffer = BytesIO()

    def readAll(self, sz):
        return self.read(sz)


authenticateLongSessionV2_args_obj = authenticateLongSessionV2_args(
    usernameOrEmail="fake_user",
    password="fake_pass",
    ssoLoginToken="fake_sso",
    consumerKey="en-fake",
    consumerSecret="ffffffffffffffff",
    deviceIdentifier="000000000",
    deviceDescription="Test",
    supportsTwoFactor=True,
    supportsBusinessOnlyAccounts=True,
)

authenticateLongSessionV2_request_bin = (
    b"\x80\x01\x00\x01\x00\x00\x00\x19authenticateLongSessionV2\x00"
    b"\x00\x00\x00\x0c\x00\x01\x0b\x00\x01\x00\x00\x00\tfake_user\x0b"
    b"\x00\x02\x00\x00\x00\tfake_pass\x0b\x00\x03\x00\x00\x00\x08"
    b"fake_sso\x0b\x00\x04\x00\x00\x00\x07en-fake\x0b\x00\x05\x00\x00"
    b"\x00\x10ffffffffffffffff\x0b\x00\x06\x00\x00\x00\t000000000\x0b"
    b"\x00\x07\x00\x00\x00\x04Test\x02\x00\x08\x01\x02\x00\t\x01"
    b"\x00\x00"
)


def test_network_retry(mocker):
    mocker.patch("evernote_backup.evernote_client_util.time.sleep")

    call_count = 0

    @network_retry
    def test_error_function():
        nonlocal call_count
        call_count += 1
        raise ConnectionError

    with pytest.raises(ConnectionError):
        test_error_function()
    assert call_count == 50


def test_authenticateLongSessionV2_request_write(mocker):
    data = TMemoryProper()
    prot = TBinaryProtocol.TBinaryProtocol(data)

    client = ClientV2(prot)
    mocker.patch.object(client, "recv_authenticateLongSession")

    client.authenticateLongSessionV2(
        username=authenticateLongSessionV2_args_obj.usernameOrEmail,
        password=authenticateLongSessionV2_args_obj.password,
        ssoLoginToken=authenticateLongSessionV2_args_obj.ssoLoginToken,
        consumerKey=authenticateLongSessionV2_args_obj.consumerKey,
        consumerSecret=authenticateLongSessionV2_args_obj.consumerSecret,
        deviceIdentifier=authenticateLongSessionV2_args_obj.deviceIdentifier,
        deviceDescription=authenticateLongSessionV2_args_obj.deviceDescription,
        supportsTwoFactor=authenticateLongSessionV2_args_obj.supportsTwoFactor,
        supportsBusinessOnlyAccounts=authenticateLongSessionV2_args_obj.supportsBusinessOnlyAccounts,
    )

    assert data.getvalue() == authenticateLongSessionV2_request_bin


def test_authenticateLongSessionV2_request_read(mocker):
    expected_request = authenticateLongSessionV2_request(
        auth_args=authenticateLongSessionV2_args_obj
    )

    data = TMemoryProper(authenticateLongSessionV2_request_bin)
    prot = TBinaryProtocol.TBinaryProtocol(data)

    (fname, mtype, rseqid) = prot.readMessageBegin()
    test_request = authenticateLongSessionV2_request()
    test_request.read(prot)

    assert test_request == expected_request
