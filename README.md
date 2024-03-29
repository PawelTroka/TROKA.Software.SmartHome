# TROKA.Software.SmartHome
Home automation configuration, scripts and state of affairs


## Goals for this project

1. Integrate everything. Automate everything.
2. Get the best possible devices for each device category
3. ZWave+ 700 series over Wi-Fi and Zigbee
4. Local processing over Cloud
5. Multiple ways to control stuff
    - Automated control (e.g. on movement, on open door)
    - Voice control
    - Physical switches and buttons
    - Wall-mounted tablets/phones with dashboards
    - Remotes
    - Dedicated apps

## Main dashboard
![main dashboard](https://raw.githubusercontent.com/PawelTroka/TROKA.Software.SmartHome/master/screenshots/dashboard-main.png "Dashboard main")
## Living room dashboard
![Living room dashboard](https://raw.githubusercontent.com/PawelTroka/TROKA.Software.SmartHome/master/screenshots/dashboard-living-room.png "Dashboard main")
## Office dashboard
![office dashboard](https://raw.githubusercontent.com/PawelTroka/TROKA.Software.SmartHome/master/screenshots/dashboard-office.png "Office dashboard")


## Devices/systems integration state matrix

| Devices\Systems 	| Protocol | Home Assistant 	| Amazon Alexa 	| Google Home 	| App 	|
|-----------------	|---------------- |----------------	|--------------	|-------------	|--------------	|
| LIFX Lights     	| Wi-Fi |:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
| MiLight Lights   	| 2.4GHz radio |:heavy_check_mark:|:heavy_check_mark:<sup>1</sup>|:heavy_check_mark:<sup>1</sup>|:heavy_check_mark:|
| Sonos Multi-room audio	| Ethernet |:heavy_check_mark:|:warning:<sup>6</sup>|:warning:<sup>6</sup>|:heavy_check_mark:|
| Living room TV	| Ethernet |:heavy_check_mark:|:x:|:heavy_check_mark:|:heavy_check_mark:|
| Bedroom TV	| Ethernet |:heavy_check_mark:|:x:|:heavy_check_mark:|:heavy_check_mark:|
| A/V Receiver	| Ethernet |:heavy_check_mark:<sup>7</sup>|:warning:<sup>13</sup>|:warning:<sup>14</sup>|:heavy_check_mark:|
| nVidia Shield	| Ethernet |:heavy_check_mark:|:x:<sup>17</sup>|:heavy_check_mark:|:x:|
| XBOX ONE X	| Ethernet |:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
| Netatmo Weather Station	| 433 MHz |:heavy_check_mark:|:heavy_check_mark:|:x:|:heavy_check_mark:|
| Nest Protect	| Wi-Fi |:heavy_check_mark:|:x:|:x:|:heavy_check_mark:|
|Tado radiator thermostats	| 6LoWPAN |:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
|WarmUp 4iE Underfloor heating	| Wi-Fi |:heavy_check_mark:<sup>2</sup>|:heavy_check_mark:|:x:|:heavy_check_mark:|
|BTicino Classe 300X13E (video intercom)	| Wi-Fi |:x:<sup>16</sup>|:x:|:x:|:heavy_check_mark:|
|Miele Fridge-Freezer	| Wi-Fi |:heavy_check_mark:<sup>3</sup>|:x:|:x:|:heavy_check_mark:|
|Siemens Cooktop	| Wi-Fi 5Ghz |:warning:<sup>4</sup>|:x:|:x:|:heavy_check_mark:|
|LG Washer-Dryer	| Wi-Fi |:heavy_check_mark:<sup>10</sup>|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
|Wyze Cams	| Wi-Fi |:heavy_check_mark:<sup>11</sup>|:warning:<sup>12</sup>|:heavy_check_mark:|:heavy_check_mark:|
|Aeotec Multisensors 6	| Z-Wave |:warning:<sup>9</sup>|:x:|:x:|:x:|
|Aeotec Siren 6	| Z-Wave |:x:<sup>21</sup>|:x:|:x:|:x:|
|Fibaro door sensors	| Z-Wave |:heavy_check_mark:|:x:|:x:|:x:|
|Aeotec WallMotes	| Z-Wave |:warning:<sup>8</sup>|:x:|:x:|:x:|
|D-Link flood sensors	| Wi-Fi |:heavy_check_mark:<sup>15</sup>|:x:|:x:|:heavy_check_mark:|
|Fibaro flood sensors	| Z-Wave |:heavy_check_mark:|:x:|:x:|:x:|
|Fibaro Single Switch	| Z-Wave |:heavy_check_mark:|:x:|:x:|:x:|
|Whirlpool W11 Oven	| Wi-Fi |:x:|:x:|:x:|:heavy_check_mark:<sup>5</sup>|
|Whirlpool W11 Microwave	| Wi-Fi |:x:|:x:|:x:|:heavy_check_mark:<sup>5</sup>|
|Eight Sleep	| Wi-Fi |:heavy_check_mark:|:x:<sup>17</sup>|:x:|:heavy_check_mark:|
|Gree A/C	| Wi-Fi |:heavy_check_mark:<sup>18</sup>|:x:|:x:|:heavy_check_mark:|
|BMW	| Cellular |:heavy_check_mark:|:x:|:x:|:heavy_check_mark:|
|Airthings Wave+	| Blutooth |:heavy_check_mark:<sup>19</sup>|:x:|:x:|:heavy_check_mark:|
|Ring Peephole Cam	| Wi-Fi |:heavy_check_mark:|:heavy_check_mark:|:x:|:heavy_check_mark:|
|Fibaro Motion Sensor	| Z-Wave |:heavy_check_mark:|:x:|:x:|:x:|
|August Smart Lock Pro	| Blutooth |:heavy_check_mark:|:x:|:x:|:heavy_check_mark:|
|Withings	| Wi-Fi |:heavy_check_mark:|:x:|:x:|:heavy_check_mark:|
|UPS PowerWalker VFI 1500 RMG PF1<sup>20</sup>	| Ethernet |:heavy_check_mark:|:x:|:x:|:x:|
|Brother MFC-J6930DW	| Ethernet |:heavy_check_mark:|:x:|:x:|:x:|
|UniFi	| Ethernet |:heavy_check_mark:|:x:|:x:|:x:|


<sup>1</sup> Exposed via Home Assistant Addon, requires open ports in network configuration


<sup>2</sup> Via custom component https://github.com/ha-warmup/warmup


<sup>3</sup> Via custom component https://github.com/HomeAssistant-Mods/home-assistant-miele

<sup>4</sup> API does not support Cooktop yet (https://developer.home-connect.com/docs/cooktop/supported_programs_and_options). Only very basic functionality is exposed https://github.com/DavidMStraub/homeassistant-homeconnect/issues/20.

<sup>5</sup> Mobile app (https://play.google.com/store/apps/details?id=com.adbglobal.whirlpool&hl=en) sucks hard but at least it finally shows connected appliances correctly. Some discussions about integrating `6th Sense Live` platform into Home Asssitant (possibly by reverse engineering) have already started (https://community.home-assistant.io/t/whirlpool-wifi-airconditioner/136237). Some initial attempts integrate only AC (https://github.com/abmantis/homeassistant-custom-components/tree/master/whirlpool).


<sup>6</sup> Doesn't work with all the functionality - e.g. playback from Tidal is region-locked, grouping is limited.

<sup>7</sup> Zones and advanced features like sound modes do not work because DENON AVR Home Assistant component is not working (https://community.home-assistant.io/t/denonavr-with-avr-x6300/14744 https://github.com/scarface-4711/denonavr/issues/32). Is also integrated through HEOS component but it seems to have less capabilities. Scripts are in place to call both entities, so basic functionality works pretty well.

<sup>8</sup> Swipe left/right and up/down doesn't work.

<sup>9</sup> Works really slow and often does not trigger motion correctly. Vibration alarms not implemented.


<sup>10</sup> Done via a fork (https://github.com/ollo69/ha-smartthinq-sensors) of custom component (https://community.home-assistant.io/t/in-development-lg-smartthinq-component/40157/249)


<sup>11</sup> Through alternative RTSP firmware (https://support.wyzecam.com/hc/en-us/articles/360026245231-Wyze-Cam-RTSP)


<sup>12</sup> Only `show camera` is supported


<sup>13</sup> Only very limited subset of functionality is supported. See http://rn.dmglobal.com/usheos/HeosCP118.png and https://denon.custhelp.com/app/answers/detail/a_id/5930


<sup>14</sup> Extremely limited subset of functionality is supported, more is coming soon. See https://www.denon.co.uk/uk/googleassistant


<sup>15</sup> Via custom component https://github.com/postlund/dlink_hnap

<sup>16</sup> Currently not supported but there seems to be some motion in the development community: https://community.home-assistant.io/t/bticino-door-entry-for-classe300x13e/116517 and API is open: https://portal.developer.legrand.com/docs/services/classe-300x13e-v2

<sup>17</sup> Is integrated but doesn't work for some reason

<sup>18</sup> Via custom Home Assistant component https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent

<sup>19</sup> Via custom Home Assistant component https://github.com/custom-components/sensor.airthings_wave

<sup>20</sup> Through SNMP module PowerWalker 10120505

<sup>21</sup> Need to wait for migration to ZwaveJS and sirens support in it (see: https://github.com/home-assistant/architecture/issues/375)
