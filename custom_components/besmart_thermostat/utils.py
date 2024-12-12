import logging
import requests
from datetime import datetime, timedelta
from http import HTTPStatus

_LOGGER = logging.getLogger(__name__)

# pylint: disable=abstract-method
# pylint: disable=too-many-instance-attributes
class BesmartClient(object):
    """Representation of a BeSMART thermostat."""

    BASE_URL = "http://www.besmart-home.com/Android_vokera_20160516/"
    LOGIN = "login.php"
    ROOM_MODE = "setRoomMode.php"
    ROOM_LIST = "getRoomList.php?deviceId={0}"
    ROOM_DATA = "getRoomData196.php?therId={0}&deviceId={1}"
    ROOM_PROGRAM = "getProgram.php?roomId={0}"
    ROOM_TEMP = "setRoomTemp.php"
    ROOM_ECON_TEMP = "setEconTemp.php"
    ROOM_FROST_TEMP = "setFrostTemp.php"
    ROOM_CONF_TEMP = "setComfTemp.php"
    GET_SETTINGS = "getSetting.php"
    SET_SETTINGS = "setSetting.php"

    def __init__(self, username, password):
        """Initialize the thermostat."""
        self._username = username
        self._password = password
        self._lastupdate = None
        self._device = None
        self._rooms = None
        self._timeout = 30
        self._s = requests.Session()

    def _fahToCent(self, temp):
        return str(round((temp - 32.0) / 1.8, 1))

    def _centToFah(self, temp):
        return str(round(32.0 + (temp * 1.8), 1))

    def login(self):
        try:
            url = self.BASE_URL + self.LOGIN
            reqData = {"un": self._username, "pwd": self._password, "version": "32"}
            res = self._s.post(url, data=reqData, timeout=self._timeout)

            if not res.ok:
                res.raise_for_status()

            resData = res.json()
            error = resData.get("error")

            if error == "1":
                res.status_code = HTTPStatus.UNAUTHORIZED
                raise requests.HTTPError("Invalid credentials", response=res)

            if error == "2":
                res.status_code = HTTPStatus.BAD_REQUEST
                raise requests.HTTPError("Bad request", response=res)

            if not error == "0":
                raise Exception("Unexpected error occured during auth process.")
            
            self._device = resData
        except Exception as ex:
            _LOGGER.warning(ex)
            self._device = None
            raise

    def rooms(self):
        try:
            if not self._device:
                self.login()

            if self._device:
                resp = self._s.post(
                    self.BASE_URL + self.ROOM_LIST.format(self._device.get("deviceId")),
                    timeout=self._timeout,
                )
                if resp.ok:
                    self._lastupdate = datetime.now()
                    self._rooms = dict(
                        (y.get("name").lower(), y)
                        for y in filter(lambda x: x.get("id") != None, resp.json())
                    )
                    _LOGGER.debug("rooms: {}".format(self._rooms))
                    if len(self._rooms) == 0:
                        self._device = None
                        self._lastupdate = None
                        return None

                    return self._rooms
                else:
                    _LOGGER.debug("get rooms failed!")
        except Exception as ex:
            _LOGGER.warning(ex)
            self._device = None

        return None

    def roomdata(self, room):
        try:
            self.login()

            if self._device:
                resp = self._s.get(
                    self.BASE_URL
                    + self.ROOM_DATA.format(
                        room.get("therId"), self._device.get("deviceId")
                    ),
                    timeout=self._timeout,
                )
                if resp.ok:
                    return resp.json()
                else:
                    _LOGGER.debug("refresh roomdata failed for: {}".format(room))
        except Exception as ex:
            _LOGGER.warning(ex)
            self._device = None

        return None

    def program(self, room):
        try:
            self.login()

            resp = self._s.get(
                self.BASE_URL + self.ROOM_PROGRAM.format(room.get("id")),
                timeout=self._timeout,
            )
            if resp.ok:
                return resp.json()
        except Exception as ex:
            _LOGGER.warning(ex)
            self._device = None
        return None

    def roomByName(self, name):
        if self._lastupdate is None or datetime.now() - self._lastupdate > timedelta(
            seconds=120
        ):
            _LOGGER.debug("refresh rooms state")
            self.rooms()

        if self._rooms:
            return self.roomdata(self._rooms.get(name.lower()))
        return None

    def setRoomMode(self, room_name, mode):
        room = self.roomByName(room_name)

        if self._device and room:
            data = {
                "deviceId": self._device.get("deviceId"),
                "therId": room.get("roomMark"),
                "mode": mode,
            }

            resp = self._s.post(
                self.BASE_URL + self.ROOM_MODE, data=data, timeout=self._timeout
            )
            if resp.ok:
                msg = resp.json()
                _LOGGER.debug("resp: {}".format(msg))
                if msg.get("error") == 1:
                    return True

        return None

    def setRoomConfortTemp(self, room_name, new_temp):
        return self.setRoomTemp(room_name, new_temp, self.ROOM_CONF_TEMP)

    def setRoomECOTemp(self, room_name, new_temp):
        return self.setRoomTemp(room_name, new_temp, self.ROOM_ECON_TEMP)

    def setRoomFrostTemp(self, room_name, new_temp):
        return self.setRoomTemp(room_name, new_temp, self.ROOM_FROST_TEMP)

    def setRoomTemp(self, room_name, new_temp, url=None):
        url = url or self.ROOM_TEMP
        room = self.roomByName(room_name)
        if room and self._device.get("deviceId"):
            new_temp = round(new_temp, 1)
            _LOGGER.debug("room: {}".format(room))

            if room.get("tempUnit") in {"N/A", "0"}:
                tpCInt, tpCIntFloat = str(new_temp).split(".")
            else:
                tpCInt, tpCIntFloat = self._fahToCent(new_temp).split(".")

            _LOGGER.debug(
                "setRoomTemp: {} - {} - {}".format(new_temp, tpCInt, tpCIntFloat)
            )

            data = {
                "deviceId": self._device.get("deviceId"),
                "therId": room.get("roomMark"),
                "tempSet": tpCInt + "",
                "tempSetFloat": tpCIntFloat + "",
            }
            _LOGGER.debug("url: {}".format(self.BASE_URL + url))
            _LOGGER.debug("data: {}".format(data))
            resp = self._s.post(self.BASE_URL + url, data=data, timeout=self._timeout)
            if resp.ok:
                msg = resp.json()
                _LOGGER.debug("resp: {}".format(msg))
                if msg.get("error") == 1:
                    return True
        else:
            _LOGGER.warning("error on get the room by name: {}".format(room_name))

        return None

    def getSettings(self, room_name):
        room = self.roomByName(room_name)

        if self._device and room:
            data = {
                "deviceId": self._device.get("deviceId"),
                "therId": room.get("roomMark"),
            }

            resp = self._s.post(
                self.BASE_URL + self.GET_SETTINGS, data=data, timeout=self._timeout
            )
            if resp.ok:
                msg = resp.json()
                _LOGGER.debug("resp: {}".format(msg))
                if msg.get("error") == 0:
                    return msg

        return None

    def setSettings(self, room_name, season):
        room = self.roomByName(room_name)

        if self._device and room:
            old_data = self.getSettings(room_name)
            if old_data.get("error") == 0:
                min_temp_set_point_ip, min_temp_set_point_fp = str(
                    old_data.get("minTempSetPoint", "30.0")
                ).split(".")
                max_temp_set_point_ip, max_temp_set_point_fp = str(
                    old_data.get("maxTempSetPoint", "30.0")
                ).split(".")
                temp_curver_ip, temp_curver_fp = str(
                    old_data.get("tempCurver", "0.0")
                ).split(".")
                data = {
                    "deviceId": self._device.get("deviceId"),
                    "therId": room.get("roomMark"),
                    "minTempSetPointIP": min_temp_set_point_ip,
                    "minTempSetPointFP": min_temp_set_point_fp,
                    "maxTempSetPointIP": max_temp_set_point_ip,
                    "maxTempSetPointFP": max_temp_set_point_fp,
                    "sensorInfluence": old_data.get("sensorInfluence", "0"),
                    "tempCurveIP": temp_curver_ip,
                    "tempCurveFP": temp_curver_fp,
                    "unit": old_data.get("unit", "0"),
                    "season": season,
                    "boilerIsOnline": old_data.get("boilerIsOnline", "0"),
                }

                resp = self._s.post(
                    self.BASE_URL + self.SET_SETTINGS, data=data, timeout=self._timeout
                )
                if resp.ok:
                    msg = resp.json()
                    _LOGGER.debug("resp: {}".format(msg))
                    if msg.get("error") == 0:
                        return msg
        return None
