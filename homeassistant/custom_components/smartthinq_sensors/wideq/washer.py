"""------------------for Washer"""
import logging
from typing import Optional

from .device import (
    Device,
    DeviceStatus,
    STATE_OPTIONITEM_NONE,
)

from .washer_states import (
    STATE_WASHER,
    STATE_WASHER_ERROR,
    WASHERSTATES,
    WASHERWATERTEMPS,
    WASHERSPINSPEEDS,
    WASHREFERRORS,
)

from .dryer_states import (
    DRYERDRYLEVELS,
)

_LOGGER = logging.getLogger(__name__)


class WasherDevice(Device):
    """A higher-level interface for a washer."""
    def __init__(self, client, device):
        super().__init__(client, device, WasherStatus(self, None))

    def poll(self) -> Optional["WasherStatus"]:
        """Poll the device's current state."""

        res = self.device_poll("washerDryer")
        if not res:
            return None

        self._status = WasherStatus(self, res)
        return self._status


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
            if not state:
                return STATE_WASHER.POWER_OFF
            self._run_state = self._set_unknown(
                state=WASHERSTATES.get(state, None), key=state, type="status"
            )
        return self._run_state

    def _get_pre_state(self):
        if not self._pre_state:
            state = self.lookup_enum(["PreState", "preState"])
            if not state:
                return STATE_WASHER.POWER_OFF
            self._pre_state = self._set_unknown(
                state=WASHERSTATES.get(state, None), key=state, type="status"
            )
        return self._pre_state

    def _get_error(self):
        if not self._error:
            error = self.lookup_reference(["Error", "error"])
            if not error:
                return STATE_WASHER_ERROR.OFF
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
        if not self.is_on:
            return STATE_OPTIONITEM_NONE
        error = self._get_error()
        return error.value

    @property
    def current_course(self):
        if self.is_info_v2:
            course_key = self._device.model_info.config_value(
                "courseType"
            )
        else:
            course_key = ["APCourse", "Course"]
        course = self.lookup_reference(course_key)
        return course

    @property
    def current_smartcourse(self):
        if self.is_info_v2:
            course_key = self._device.model_info.config_value(
                "smartCourseType"
            )
        else:
            course_key = "SmartCourse"
        smart_course = self.lookup_reference(course_key)
        return smart_course

    @property
    def remaintime_hour(self):
        if self.is_info_v2:
            return DeviceStatus.int_or_none(self._data.get("remainTimeHour"))
        return self._data.get("Remain_Time_H")

    @property
    def remaintime_min(self):
        if self.is_info_v2:
            return DeviceStatus.int_or_none(self._data.get("remainTimeMinute"))
        return self._data.get("Remain_Time_M")

    @property
    def initialtime_hour(self):
        if self.is_info_v2:
            return DeviceStatus.int_or_none(self._data.get("initialTimeHour"))
        return self._data.get("Initial_Time_H")

    @property
    def initialtime_min(self):
        if self.is_info_v2:
            return DeviceStatus.int_or_none(self._data.get("initialTimeMinute"))
        return self._data.get("Initial_Time_M")

    @property
    def reservetime_hour(self):
        if self.is_info_v2:
            return DeviceStatus.int_or_none(self._data.get("reserveTimeHour"))
        return self._data.get("Reserve_Time_H")

    @property
    def reservetime_min(self):
        if self.is_info_v2:
            return DeviceStatus.int_or_none(self._data.get("reserveTimeMinute"))
        return self._data.get("Reserve_Time_M")

    @property
    def spin_option_state(self):
        spin_speed = self.lookup_enum(["SpinSpeed", "spin"])
        if not spin_speed:
            return STATE_OPTIONITEM_NONE
        return self._set_unknown(
            state=WASHERSPINSPEEDS.get(spin_speed, None),
            key=spin_speed,
            type="SpinSpeed",
        ).value

    @property
    def water_temp_option_state(self):
        water_temp = self.lookup_enum(["WTemp", "WaterTemp", "temp"])
        if not water_temp:
            return STATE_OPTIONITEM_NONE
        return self._set_unknown(
            state=WASHERWATERTEMPS.get(water_temp, None),
            key=water_temp,
            type="WaterTemp",
        ).value

    @property
    def dry_level_option_state(self):
        dry_level = self.lookup_enum(["DryLevel", "dryLevel"])
        if not dry_level:
            return STATE_OPTIONITEM_NONE
        return self._set_unknown(
            state=DRYERDRYLEVELS.get(dry_level, None),
            key=dry_level,
            type="DryLevel",
        ).value

    @property
    def tubclean_count(self):
        if self.is_info_v2:
            result = DeviceStatus.int_or_none(self._data.get("TCLCount"))
        else:
            result = self._data.get("TCLCount")
        if result is None:
            return "N/A"
        return result

    @property
    def doorlock_state(self):
        if self.is_info_v2:
            return self.lookup_bit("doorLock")
        return self.lookup_bit("DoorLock")

    @property
    def childlock_state(self):
        if self.is_info_v2:
            return self.lookup_bit("childLock")
        return self.lookup_bit("ChildLock")

    @property
    def remotestart_state(self):
        if self.is_info_v2:
            return self.lookup_bit("remoteStart")
        return self.lookup_bit("RemoteStart")

    @property
    def creasecare_state(self):
        if self.is_info_v2:
            return self.lookup_bit("creaseCare")
        return self.lookup_bit("CreaseCare")

    @property
    def steam_state(self):
        if self.is_info_v2:
            return self.lookup_bit("steam")
        return self.lookup_bit("Steam")

    @property
    def steam_softener_state(self):
        if self.is_info_v2:
            return self.lookup_bit("steamSoftener")
        return self.lookup_bit("SteamSoftener")

    @property
    def prewash_state(self):
        if self.is_info_v2:
            return self.lookup_bit("preWash")
        return self.lookup_bit("PreWash")

    @property
    def turbowash_state(self):
        if self.is_info_v2:
            return self.lookup_bit("turboWash")
        return self.lookup_bit("TurboWash")
