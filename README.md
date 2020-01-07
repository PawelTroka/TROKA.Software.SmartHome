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


## Devices/systems integration state matrix

| Devices\Systems 	| Home Assistant 	| Amazon Alexa 	| Google Home 	| App 	|
|-----------------	|----------------	|--------------	|-------------	|--------------	|
| LIFX Lights     	|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
| MiLight Lights   	|:heavy_check_mark:|:heavy_check_mark:<sup>1</sup>|:heavy_check_mark:<sup>1</sup>|:heavy_check_mark:|
| Sonos Multi-room audio|:heavy_check_mark:|:warning:<sup>6</sup>|:warning:<sup>6</sup>|:heavy_check_mark:|
| Living room TV|:heavy_check_mark:|:x:|:heavy_check_mark:|:heavy_check_mark:|
| Bedroom TV|:heavy_check_mark:|:x:|:heavy_check_mark:|:heavy_check_mark:|
| A/V Receiver|:heavy_check_mark:<sup>7</sup>|:warning:<sup>13</sup>|:warning:<sup>14</sup>|:heavy_check_mark:|
| nVidia Shield|:heavy_check_mark:|:x:<sup>17</sup>|:heavy_check_mark:|:x:|
| XBOX ONE X|:x:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
| Netatmo Weather Station|:heavy_check_mark:|:heavy_check_mark:|:x:|:heavy_check_mark:|
| Nest Protect|:heavy_check_mark:|:x:|:x:|:heavy_check_mark:|
|Tado radiator thermostats|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
|WarmUp 4iE Underfloor heating|:heavy_check_mark:<sup>2</sup>|:heavy_check_mark:|:x:|:heavy_check_mark:|
|BTicino Classe 300X13E (video intercom)|:x:<sup>16</sup>|:x:|:x:|:heavy_check_mark:|
|Miele Fridge-Freezer|:heavy_check_mark:<sup>3</sup>|:x:|:x:|:heavy_check_mark:|
|Siemens Cooktop|:warning:<sup>4</sup>|:x:|:x:|:heavy_check_mark:|
|LG Washer-Dryer|:x:<sup>10</sup>|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
|Wyze Cams|:heavy_check_mark:<sup>11</sup>|:warning:<sup>12</sup>|:heavy_check_mark:|:heavy_check_mark:|
|Aotec Multisensors 6|:warning:<sup>9</sup>|:x:|:x:|:x:|
|Fibaro door sensors|:heavy_check_mark:|:x:|:x:|:x:|
|Aotec WallMotes|:warning:<sup>8</sup>|:x:|:x:|:x:|
|D-Link flood sensors|:x:<sup>15</sup>|:x:|:x:|:heavy_check_mark:|
|Whirlpool W11 Oven|:x:|:x:|:x:|:heavy_check_mark:<sup>5</sup>|
|Whirlpool W11 Microwave|:x:|:x:|:x:|:heavy_check_mark:<sup>5</sup>|
|Eight Sleep|:heavy_check_mark:|:x:<sup>17</sup>|:x:|:heavy_check_mark:|




<sup>1</sup> Exposed via Home Assistant Addon, requires open ports in network configuration


<sup>2</sup> Via custom component https://github.com/ha-warmup/warmup


<sup>3</sup> Via custom component https://github.com/docbobo/home-assistant-miele

<sup>4</sup> API does not support Cooktop yet (https://developer.home-connect.com/docs/cooktop/supported_programs_and_options). Only very basic functionality is exposed via custom component https://github.com/DavidMStraub/homeassistant-homeconnect. Is coming to official Home Assistant soon via PR https://github.com/home-assistant/home-assistant/pull/29214.

<sup>5</sup> Mobile app (https://play.google.com/store/apps/details?id=com.adbglobal.whirlpool&hl=en) sucks hard but at least it finally shows connected appliances correctly.


<sup>6</sup> Doesn't work with all the functionality - e.g. playback from Tidal is region-locked, grouping is limited.

<sup>7</sup> Zones and avanced features like sound modes do not work because DENON AVR Home Assistant component is not working (https://community.home-assistant.io/t/denonavr-with-avr-x6300/14744 https://github.com/scarface-4711/denonavr/issues/32). Is also integrated through HEOS component but it seems to have less capabilities. Scripts are in place to call both entities, so basic functionality works pretty well.

<sup>8</sup> Swipe left/right and up/down doesn't work.

<sup>9</sup> Works really slow and often does not trigger motion correctly. Vibration alarms not implemented.


<sup>10</sup> Should be possible via custom component and some tinkering. See https://community.home-assistant.io/t/in-development-lg-smartthinq-component/40157/249


<sup>11</sup> Through alternative RTSP firmware (https://support.wyzecam.com/hc/en-us/articles/360026245231-Wyze-Cam-RTSP)


<sup>12</sup> Only `show camera` is supported


<sup>13</sup> Only very limited subset of functionality is supported. See http://rn.dmglobal.com/usheos/HeosCP118.png and https://denon.custhelp.com/app/answers/detail/a_id/5930


<sup>14</sup> Extremely limited subset of functionality is supported, more is coming soon. See https://www.denon.co.uk/uk/googleassistant


<sup>15</sup> Currently not supported. Should be possible to develop a component for it (https://community.home-assistant.io/t/d-link-water-sensor-dch-s160/40397), or simply use IFTTT and webhooks (https://www.reddit.com/r/homeassistant/comments/cv9y1m/dlink_water_sensor/).

<sup>16</sup> Currently not supported but there seems to be some motion in the development community: https://community.home-assistant.io/t/bticino-door-entry-for-classe300x13e/116517 and API is open: https://portal.developer.legrand.com/docs/services/classe-300x13e-v2

<sup>17</sup> Is integrated but doesn't work for some reason
