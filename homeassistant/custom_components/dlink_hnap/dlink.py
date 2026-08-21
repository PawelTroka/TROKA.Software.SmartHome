"""Read data from D-Link HNAP sensors."""

import asyncio
from datetime import datetime
import hmac
import logging
from io import BytesIO
from xml.parsers.expat import ExpatError
import xml.etree.ElementTree as ET

import aiohttp
import xmltodict

_LOGGER = logging.getLogger(__name__)

ACTION_BASE_URL = "http://purenetworks.com/HNAP1/"


def _response_has_error(result):
    """Return whether an HNAP result field reports an error."""
    if not isinstance(result, dict):
        return False
    return any(
        key.lower().endswith("result")
        and str(value).strip().upper().startswith(("ERROR", "FAIL"))
        for key, value in result.items()
    )


def _hmac(key, message):
    """Create the MD5 HMAC format expected by HNAP."""
    return (
        hmac.new(key.encode("utf-8"), message.encode("utf-8"), digestmod="MD5")
        .hexdigest()
        .upper()
    )


class AuthenticationError(Exception):
    """Raised when login fails."""


class HNAPClient:
    """Client for the HNAP protocol."""

    def __init__(self, soap, username, password, loop=None):
        """Initialize an HNAP client."""
        self.username = username
        self.password = password
        self.logged_in = False
        self.loop = loop or asyncio.get_event_loop()
        self.actions = None
        self._client = soap
        self._private_key = None
        self._cookie = None
        self._auth_token = None
        self._timestamp = None

    async def login(self):
        """Authenticate with the device and obtain a cookie."""
        self.logged_in = False
        response = await self.call(
            "Login",
            Action="request",
            Username=self.username,
            LoginPassword="",
            Captcha="",
        )
        challenge = response["Challenge"]
        public_key = response["PublicKey"]
        self._cookie = response["Cookie"]

        self._private_key = _hmac(public_key + str(self.password), challenge)
        try:
            password = _hmac(self._private_key, challenge)
            response = await self.call(
                "Login",
                Action="login",
                Username=self.username,
                LoginPassword=password,
                Captcha="",
            )
            if response["LoginResult"].lower() != "success":
                self._reset_session()
                raise AuthenticationError("Incorrect username or password")
            if not self.actions:
                self.actions = await self.device_actions()
        except ExpatError as error:
            raise AuthenticationError("Bad response from device") from error

        self.logged_in = True

    async def device_actions(self):
        """Return the actions supported by the device."""
        actions = await self.call("GetDeviceSettings")
        action_items = actions["SOAPActions"]["string"]
        if isinstance(action_items, str):
            action_items = [action_items]
        return [item[item.rfind("/") + 1 :] for item in action_items]

    async def soap_actions(self, module_id):
        """Return the actions supported by a sensor module."""
        return await self.call("GetModuleSOAPActions", ModuleID=module_id)

    async def call(self, method, **kwargs):
        """Call an HNAP method."""
        if not self._private_key and method != "Login":
            await self.login()
        self._update_auth_token(method)
        try:
            result = await self.soap().call(method, **kwargs)
        except Exception as error:
            self._reset_session()
            raise ConnectionError("D-Link HNAP request failed") from error

        if _response_has_error(result):
            self._reset_session()
            raise ConnectionError(f"D-Link HNAP {method} returned an error")
        return result

    def _reset_session(self):
        """Clear all authentication state after a failed request."""
        self.logged_in = False
        self._private_key = None
        self._cookie = None
        self._auth_token = None
        self._timestamp = None
        self._client.headers.pop("Cookie", None)
        self._client.headers.pop("HNAP_AUTH", None)

    def _update_auth_token(self, action):
        """Update the HNAP authentication token for an action."""
        if not self._private_key:
            return
        self._timestamp = int(datetime.now().timestamp())
        self._auth_token = _hmac(
            self._private_key,
            f'{self._timestamp}"{ACTION_BASE_URL}{action}"',
        )

    def soap(self):
        """Return the SOAP client with updated authentication headers."""
        if self._cookie:
            self._client.headers["Cookie"] = f"uid={self._cookie}"
        if self._auth_token:
            self._client.headers["HNAP_AUTH"] = (
                f"{self._auth_token} {self._timestamp}"
            )
        return self._client


class BaseSensor:
    """Base wrapper for a D-Link sensor module."""

    def __init__(self, client, module_id=1):
        """Initialize a sensor wrapper."""
        self.client = client
        self.module_id = module_id
        self._soap_actions = None

    async def latest_trigger(self):
        """Get the latest trigger time from a sensor."""
        if not self._soap_actions:
            await self._cache_soap_actions()
        if "GetLatestDetection" in self._soap_actions:
            response = await self.client.call(
                "GetLatestDetection", ModuleID=self.module_id
            )
            detected_at = response["LatestDetectTime"]
        else:
            response = await self.client.call(
                "GetMotionDetectorLogs",
                ModuleID=self.module_id,
                MaxCount=1,
                PageOffset=1,
                StartTime=0,
                EndTime="All",
            )
            log_list = response["MotionDetectorLogList"]
            detected_at = log_list["MotionDetectorLog"]["TimeStamp"]
        return datetime.fromtimestamp(float(detected_at))

    async def _cache_soap_actions(self):
        """Cache the module's supported SOAP actions."""
        response = await self.client.soap_actions(self.module_id)
        actions = response["ModuleSOAPList"]["SOAPActions"]["Action"]
        self._soap_actions = [actions] if isinstance(actions, str) else actions


class MotionSensor(BaseSensor):
    """Wrapper for a D-Link motion sensor."""


class WaterSensor(BaseSensor):
    """Wrapper for a D-Link water sensor."""

    async def water_detected(self):
        """Return whether the sensor currently detects water."""
        if not self._soap_actions:
            await self._cache_soap_actions()
        response = await self.client.call(
            "GetWaterDetectorState", ModuleID=self.module_id
        )
        water_state = response.get("IsWater")
        if isinstance(water_state, bool):
            return water_state
        if isinstance(water_state, str):
            normalized = water_state.strip().lower()
            if normalized in {"true", "false"}:
                return normalized == "true"
        raise ValueError("D-Link HNAP returned an invalid water state")


class NanoSOAPClient:
    """Small SOAP client for the subset of HNAP used by the sensors."""

    BASE_NS = {
        "xmlns:soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    ACTION_NS = {"xmlns": ACTION_BASE_URL}

    def __init__(self, address, action, loop=None, session=None):
        """Initialize a SOAP client."""
        self.address = f"http://{address}/HNAP1"
        self.action = action
        self.loop = loop or asyncio.get_event_loop()
        self.session = session or aiohttp.ClientSession(loop=loop)
        self.headers = {}

    def _generate_request_xml(self, method, **kwargs):
        """Create a SOAP request body."""
        body = ET.Element("soap:Body")
        action = ET.Element(method, self.ACTION_NS)
        body.append(action)
        for parameter, value in kwargs.items():
            element = ET.Element(parameter)
            element.text = str(value)
            action.append(element)

        envelope = ET.Element("soap:Envelope", self.BASE_NS)
        envelope.append(body)

        output = BytesIO()
        ET.ElementTree(envelope).write(
            output, encoding="utf-8", xml_declaration=True
        )
        return output.getvalue().decode("utf-8")

    async def call(self, method, **kwargs):
        """Send a SOAP request and parse its response."""
        request_xml = self._generate_request_xml(method, **kwargs)
        headers = self.headers.copy()
        headers["SOAPAction"] = f'"{self.action}{method}"'
        async with self.session.post(
            self.address,
            data=request_xml,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            response.raise_for_status()
            response_text = await response.text()

        parsed = xmltodict.parse(response_text)
        if "soap:Envelope" not in parsed:
            raise ValueError("Invalid SOAP response")
        return parsed["soap:Envelope"]["soap:Body"][f"{method}Response"]
