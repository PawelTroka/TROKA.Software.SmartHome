# D-Link HNAP

This is a vendored copy of
[postlund/dlink_hnap](https://github.com/postlund/dlink_hnap) at upstream commit
`6b1c9bf` for the three locally configured D-Link water sensors.

The local `1.0.1` patch exposes Home Assistant entity availability correctly:
an unreachable sensor is `unavailable`, never silently retained as a safe
`off`/dry reading. Repeated connection failures are logged once per outage.

The upstream integration is MIT licensed and supports DCH-S160 and DCH-S161
water-leak sensors through local HNAP polling.
