from evernote.edam.type.ttypes import TType
from evernote.edam.userstore import UserStore
from thrift.protocol import TBinaryProtocol
from thrift.Thrift import TMessageType
from thrift.transport import TTransport

try:
    from thrift.protocol import fastbinary
except ImportError:
    fastbinary = None


class authenticateLongSessionV2_args(object):
    """
    Attributes:
     - usernameOrEmail
     - password
     - ssoLoginToken
     - consumerKey
     - consumerSecret
     - deviceIdentifier
     - deviceDescription
     - supportsTwoFactor
     - supportsBusinessOnlyAccounts
    """

    thrift_spec = (
        None,
        (1, TType.STRING, "usernameOrEmail", None, None),
        (2, TType.STRING, "password", None, None),
        (3, TType.STRING, "ssoLoginToken", None, None),
        (4, TType.STRING, "consumerKey", None, None),
        (5, TType.STRING, "consumerSecret", None, None),
        (6, TType.STRING, "deviceIdentifier", None, None),
        (7, TType.STRING, "deviceDescription", None, None),
        (8, TType.BOOL, "supportsTwoFactor", None, None),
        (9, TType.BOOL, "supportsBusinessOnlyAccounts", None, None),
    )

    def __init__(
        self,
        usernameOrEmail=None,
        password=None,
        ssoLoginToken=None,
        consumerKey=None,
        consumerSecret=None,
        deviceIdentifier=None,
        deviceDescription=None,
        supportsTwoFactor=None,
        supportsBusinessOnlyAccounts=None,
    ):
        self.usernameOrEmail = usernameOrEmail
        self.password = password
        self.ssoLoginToken = ssoLoginToken
        self.consumerKey = consumerKey
        self.consumerSecret = consumerSecret
        self.deviceIdentifier = deviceIdentifier
        self.deviceDescription = deviceDescription
        self.supportsTwoFactor = supportsTwoFactor
        self.supportsBusinessOnlyAccounts = supportsBusinessOnlyAccounts

    def read(self, iprot):
        if (
            iprot.__class__ == TBinaryProtocol.TBinaryProtocolAccelerated
            and isinstance(iprot.trans, TTransport.CReadableTransport)
            and self.thrift_spec is not None
            and fastbinary is not None
        ):  # pragma: no cover
            fastbinary.decode_binary(
                self, iprot.trans, (self.__class__, self.thrift_spec)
            )
            return
        iprot.readStructBegin()
        while True:
            (fname, ftype, fid) = iprot.readFieldBegin()
            if ftype == TType.STOP:
                break
            if fid == 1:
                if ftype == TType.STRING:
                    self.usernameOrEmail = iprot.readString().decode("utf-8")
                else:  # pragma: no cover
                    iprot.skip(ftype)
            elif fid == 2:
                if ftype == TType.STRING:
                    self.password = iprot.readString().decode("utf-8")
                else:  # pragma: no cover
                    iprot.skip(ftype)
            elif fid == 3:
                if ftype == TType.STRING:
                    self.ssoLoginToken = iprot.readString().decode("utf-8")
                else:  # pragma: no cover
                    iprot.skip(ftype)
            elif fid == 4:
                if ftype == TType.STRING:
                    self.consumerKey = iprot.readString().decode("utf-8")
                else:  # pragma: no cover
                    iprot.skip(ftype)
            elif fid == 5:
                if ftype == TType.STRING:
                    self.consumerSecret = iprot.readString().decode("utf-8")
                else:  # pragma: no cover
                    iprot.skip(ftype)
            elif fid == 6:
                if ftype == TType.STRING:
                    self.deviceIdentifier = iprot.readString().decode("utf-8")
                else:  # pragma: no cover
                    iprot.skip(ftype)
            elif fid == 7:
                if ftype == TType.STRING:
                    self.deviceDescription = iprot.readString().decode("utf-8")
                else:  # pragma: no cover
                    iprot.skip(ftype)
            elif fid == 8:
                if ftype == TType.BOOL:
                    self.supportsTwoFactor = iprot.readBool()
                else:  # pragma: no cover
                    iprot.skip(ftype)
            elif fid == 9:
                if ftype == TType.BOOL:
                    self.supportsBusinessOnlyAccounts = iprot.readBool()
                else:  # pragma: no cover
                    iprot.skip(ftype)
            else:  # pragma: no cover
                iprot.skip(ftype)
            iprot.readFieldEnd()
        iprot.readStructEnd()

    def write(self, oprot):
        if (
            oprot.__class__ == TBinaryProtocol.TBinaryProtocolAccelerated
            and self.thrift_spec is not None
            and fastbinary is not None
        ):  # pragma: no cover
            oprot.trans.write(
                fastbinary.encode_binary(self, (self.__class__, self.thrift_spec))
            )
            return
        oprot.writeStructBegin("authenticateLongSession_args")
        if self.usernameOrEmail is not None:
            oprot.writeFieldBegin("username", TType.STRING, 1)
            oprot.writeString(self.usernameOrEmail.encode("utf-8"))
            oprot.writeFieldEnd()
        if self.password is not None:
            oprot.writeFieldBegin("password", TType.STRING, 2)
            oprot.writeString(self.password.encode("utf-8"))
            oprot.writeFieldEnd()
        if self.ssoLoginToken is not None:
            oprot.writeFieldBegin("ssoLoginToken", TType.STRING, 3)
            oprot.writeString(self.ssoLoginToken.encode("utf-8"))
            oprot.writeFieldEnd()
        if self.consumerKey is not None:
            oprot.writeFieldBegin("consumerKey", TType.STRING, 4)
            oprot.writeString(self.consumerKey.encode("utf-8"))
            oprot.writeFieldEnd()
        if self.consumerSecret is not None:
            oprot.writeFieldBegin("consumerSecret", TType.STRING, 5)
            oprot.writeString(self.consumerSecret.encode("utf-8"))
            oprot.writeFieldEnd()
        if self.deviceIdentifier is not None:
            oprot.writeFieldBegin("deviceIdentifier", TType.STRING, 6)
            oprot.writeString(self.deviceIdentifier.encode("utf-8"))
            oprot.writeFieldEnd()
        if self.deviceDescription is not None:
            oprot.writeFieldBegin("deviceDescription", TType.STRING, 7)
            oprot.writeString(self.deviceDescription.encode("utf-8"))
            oprot.writeFieldEnd()
        if self.supportsTwoFactor is not None:
            oprot.writeFieldBegin("supportsTwoFactor", TType.BOOL, 8)
            oprot.writeBool(self.supportsTwoFactor)
            oprot.writeFieldEnd()
        if self.supportsBusinessOnlyAccounts is not None:
            oprot.writeFieldBegin("supportsBusinessOnlyAccounts", TType.BOOL, 9)
            oprot.writeBool(self.supportsBusinessOnlyAccounts)
            oprot.writeFieldEnd()
        oprot.writeFieldStop()
        oprot.writeStructEnd()

    def validate(self):
        """not implemented"""

    def __repr__(self):  # pragma: no cover
        L = ["%s=%r" % (key, value) for key, value in self.__dict__.items()]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__


class authenticateLongSessionV2_request(object):
    """
    Attributes:
     - auth_args
    """

    thrift_spec = (
        (
            1,
            TType.STRUCT,
            "auth_args",
            (
                authenticateLongSessionV2_args,
                authenticateLongSessionV2_args.thrift_spec,
            ),
            None,
        ),
    )

    def __init__(
        self,
        auth_args=None,
    ):
        self.auth_args = auth_args

    def read(self, iprot):
        if (
            iprot.__class__ == TBinaryProtocol.TBinaryProtocolAccelerated
            and isinstance(iprot.trans, TTransport.CReadableTransport)
            and self.thrift_spec is not None
            and fastbinary is not None
        ):  # pragma: no cover
            fastbinary.decode_binary(
                self, iprot.trans, (self.__class__, self.thrift_spec)
            )
            return
        iprot.readStructBegin()
        while True:
            (fname, ftype, fid) = iprot.readFieldBegin()
            if ftype == TType.STOP:
                break
            if fid == 1:
                if ftype == TType.STRUCT:
                    self.auth_args = authenticateLongSessionV2_args()
                    self.auth_args.read(iprot)
                else:  # pragma: no cover
                    iprot.skip(ftype)
            else:  # pragma: no cover
                iprot.skip(ftype)
            iprot.readFieldEnd()
        iprot.readStructEnd()

    def write(self, oprot):
        if (
            oprot.__class__ == TBinaryProtocol.TBinaryProtocolAccelerated
            and self.thrift_spec is not None
            and fastbinary is not None
        ):  # pragma: no cover
            oprot.trans.write(
                fastbinary.encode_binary(self, (self.__class__, self.thrift_spec))
            )
            return
        oprot.writeStructBegin("authenticateLongSessionV2_args")
        if self.auth_args is not None:
            oprot.writeFieldBegin("auth_args", TType.STRUCT, 1)
            self.auth_args.write(oprot)
            oprot.writeFieldEnd()
        oprot.writeFieldStop()
        oprot.writeStructEnd()

    def validate(self):
        """not implemented"""

    def __repr__(self):  # pragma: no cover
        L = ["%s=%r" % (key, value) for key, value in self.__dict__.items()]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__


class ClientV2(UserStore.Client):
    def authenticateLongSessionV2(
        self,
        username,
        password,
        ssoLoginToken,
        consumerKey,
        consumerSecret,
        deviceIdentifier,
        deviceDescription,
        supportsTwoFactor,
        supportsBusinessOnlyAccounts,
    ):
        self.send_authenticateLongSessionV2(
            username,
            password,
            ssoLoginToken,
            consumerKey,
            consumerSecret,
            deviceIdentifier,
            deviceDescription,
            supportsTwoFactor,
            supportsBusinessOnlyAccounts,
        )
        return self.recv_authenticateLongSession()

    def send_authenticateLongSessionV2(
        self,
        username,
        password,
        ssoLoginToken,
        consumerKey,
        consumerSecret,
        deviceIdentifier,
        deviceDescription,
        supportsTwoFactor,
        supportsBusinessOnlyAccounts,
    ):
        self._oprot.writeMessageBegin(
            "authenticateLongSessionV2", TMessageType.CALL, self._seqid
        )

        args = authenticateLongSessionV2_args()
        args.usernameOrEmail = username
        args.password = password
        args.ssoLoginToken = ssoLoginToken
        args.consumerKey = consumerKey
        args.consumerSecret = consumerSecret
        args.deviceIdentifier = deviceIdentifier
        args.deviceDescription = deviceDescription
        args.supportsTwoFactor = supportsTwoFactor
        args.supportsBusinessOnlyAccounts = supportsBusinessOnlyAccounts

        request = authenticateLongSessionV2_request()
        request.auth_args = args

        request.write(self._oprot)
        self._oprot.writeMessageEnd()
        self._oprot.trans.flush()
