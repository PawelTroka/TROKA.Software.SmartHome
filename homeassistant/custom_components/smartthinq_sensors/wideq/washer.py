"""------------------for Washer"""
import logging
from typing import Optional

from .device import (
    Device,
    DeviceStatus,
    STATE_OPTIONITEM_OFF,
    STATE_OPTIONITEM_UNKNOWN,
)

from .washer_states import (
    STATE_WASHER,
    STATE_WASHER_ERROR,
    WASHERSTATES,
    WASHERWATERTEMPS,
    WASHERSPINSPEEDS,
    WASHREFERRORS,
    WASHERERRORS,
)

from .dryer_states import (
    DRYERDRYLEVELS,
)

_LOGGER = logging.getLogger(__name__)


class WasherDevice(Device):
    """A higher-level interface for a washer."""

    def poll(self) -> Optional["WasherStatus"]:
        """Poll the device's current state."""

        res = self.device_poll("washerDryer")
        if not res:
            return None

        return WasherStatus(self, res)


class WasherStatus(DeviceStatus):
    """Higher-level information about a washer's current status.

    :param device: The Device instance.
    :param data: JSON data from the API.
    """

    def __init__(self, device, data):
        super().__init__(device, data)
        self._run_state = None
        self._pre_state = None
        self._error = None

    def _get_run_state(self):
        if not self._run_state:
            state = self.lookup_enum(["State", "state"])
            self._run_state = self._set_unknown(
                state=WASHERSTATES.get(state, None), key=state, type="status"
            )
        return self._run_state

    def _get_pre_state(self):
        if not self._pre_state:
            state = self.lookup_enum(["PreState", "preState"])
            self._pre_state = self._set_unknown(
                state=WASHERSTATES.get(state, None), key=state, type="status"
            )
        return self._pre_state

    def _get_error(self):
        if not self._error:
            error = self.lookup_reference(["Error", "error"])
            self._error = self._set_unknown(
                state=WASHREFERRORS.get(error, None), key=error, type="error_status"
            )
        return self._error

    @property
    def is_on(self):
        run_state = self._get_run_state()
        return run_state != STATE_WASHER.POWER_OFF

    @property
    def is_run_completed(self):
        run_state = self._get_run_state()
        pre_state = self._get_pre_state()
        if run_state == STATE_WASHER.END or (
            run_state == STATE_WASHER.POWER_OFF and pre_state == STATE_WASHER.END
        ):
            return True
        return False

    @property
    def is_error(self):
        error = self._get_error()
        if error != STATE_WASHER_ERROR.NO_ERROR and error != STATE_WASHER_ERROR.OFF:
            return True
        return False

    @property
    def run_state(self):
        run_state = self._get_run_state()
        return run_state.value

    @property
    def pre_state(self):
        pre_state = self._get_pre_state()
        return pre_state.value

    @property
    def error_state(self):
        error = self._get_error()
        return error.value

    #    error = self.lookup_reference('Error')
    #    if error == '-':
    #        return 'OFF'
    #    elif error == 'No Error':
    #        return 'NO_ERROR'
    #    else:
    #        return WASHERERROR(error)

    @property
    def current_course(self):
        course = self.lookup_reference(
            ["APCourse", "Course", "courseFL24inchBaseTitan"]
        )
        if course == "-":
            return STATE_OPTIONITEM_OFF
        return course

    @property
    def current_smartcourse(self):
        smartcourse = self.lookup_reference(
            ["SmartCourse", "smartCourseFL24inchBaseTitan"]
        )
        if smartcourse == "-":
            return STATE_OPTIONITEM_OFF
        else:
            return smartcourse

    @property
    def remaintime_hour(self):
        if self.is_api_v2:
            return DeviceStatus.int_or_none(self._data.get("remainTimeHour"))
        return self._data.get("Remain_Time_H")

    @property
    def remaintime_min(self):
        if self.is_api_v2:
            return DeviceStatus.int_or_none(self._data.get("remainTimeMinute"))
        return self._data.get("Remain_Time_M")

    @property
    def initialtime_hour(self):
        if self.is_api_v2:
            return DeviceStatus.int_or_none(self._data.get("initialTimeHour"))
        return self._data.get("Initial_Time_H")

    @property
    def initialtime_min(self):
        if self.is_api_v2:
            return DeviceStatus.int_or_none(self._data.get("initialTimeMinute"))
        return self._data.get("Initial_Time_M")

    @property
    def reservetime_hour(self):
        if self.is_api_v2:
            return DeviceStatus.int_or_none(self._data.get("reserveTimeHour"))
        return self._data.get("Reserve_Time_H")

    @property
    def reservetime_min(self):
        if self.is_api_v2:
            return DeviceStatus.int_or_none(self._data.get("reserveTimeMinute"))
        return self._data.get("Reserve_Time_M")

    @property
    def spin_option_state(self):
        spinspeed = self.lookup_enum(["SpinSpeed", "spin"])
        if spinspeed == "-":
            return STATE_OPTIONITEM_OFF
        return self._set_unknown(
            state=WASHERSPINSPEEDS.get(spinspeed, None),
            key=spinspeed,
            type="spin_option",
        ).value

    @property
    def water_temp_option_state(self):
        water_temp = self.lookup_enum(["WTemp", "WaterTemp", "temp"])
        if water_temp == "-":
            return STATE_OPTIONITEM_OFF
        return self._set_unknown(
            state=WASHERWATERTEMPS.get(water_temp, None),
            key=water_temp,
            type="water_temp",
        ).value

    @property
    def dry_level_option_state(self):
        dry_level = self.lookup_enum(["DryLevel", "dryLevel"])
        if dry_level == STATE_OPTIONITEM_UNKNOWN or dry_level == "0":
            return None
        if dry_level == "-":
            return STATE_OPTIONITEM_OFF
        return self._set_unknown(
            state=DRYERDRYLEVELS.get(dry_level, None), key=dry_level, type="DryLevel",
        ).value

    @property
    def creasecare_state(self):
        if self.is_api_v2:
            return self.lookup_bit_v2("creaseCare")
        return self.lookup_bit("Option1", 1)

    @property
    def childlock_state(self):
        if self.is_api_v2:
            return self.lookup_bit_v2("childLock")
        return self.lookup_bit("Option2", 7)

    @property
    def steam_state(self):
        if self.is_api_v2:
            return self.lookup_bit_v2("steam")
        return self.lookup_bit("Option1", 7)

    @property
    def steam_softener_state(self):
        if self.is_api_v2:
            return self.lookup_bit_v2("steamSoftener")
        return self.lookup_bit("Option1", 2)

    @property
    def doorlock_state(self):
        if self.is_api_v2:
            return self.lookup_bit_v2("doorLock")
        return self.lookup_bit("Option2", 6)

    @property
    def prewash_state(self):
        if self.is_api_v2:
            return self.lookup_bit_v2("preWash")
        return self.lookup_bit("Option1", 6)

    @property
    def remotestart_state(self):
        if self.is_api_v2:
            return self.lookup_bit_v2("remoteStart")
        return self.lookup_bit("Option2", 1)

    @property
    def turbowash_state(self):
        if self.is_api_v2:
            return self.lookup_bit_v2("turboWash")
        return self.lookup_bit("Option1", 0)

    @property
    def tubclean_count(self):
        if self.is_api_v2:
            return str(int(self._data.get("TCLCount", -1)))
        return self._data.get("TCLCount")
