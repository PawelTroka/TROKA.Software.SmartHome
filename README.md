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
| MiLight Lights   	|:heavy_check_mark:|:heavy_check_mark:<sup>1</sup>|:x:|:heavy_check_mark:|
| Sonos Multi-room audio|:heavy_check_mark:|:warning:<sup>6</sup>|:warning:<sup>6</sup>|:heavy_check_mark:|
| Living room TV|:heavy_check_mark:|:x:|:heavy_check_mark:|:heavy_check_mark:|
| Bedroom TV|:heavy_check_mark:|:x:|:heavy_check_mark:|:heavy_check_mark:|
| A/V Receiver|:warning:<sup>7</sup>|:x:|:x:|:heavy_check_mark:|
| XBOX ONE X|:x:|:heavy_check_mark:|:x:|:x:|
| Netatmo Weather Station|:heavy_check_mark:|:heavy_check_mark:|:x:|:heavy_check_mark:|
| Nest Protect|:heavy_check_mark:|:x:|:x:|:heavy_check_mark:|
|Tado radiator thermostats|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
|WarmUp 4iE Underfloor heating|:x:<sup>2</sup>|:heavy_check_mark:|:x:|:heavy_check_mark:|
|BTicino Classe 300X13E (video intercom)|:x:|:x:|:x:|:heavy_check_mark:|
|Miele Fridge-Freezer|:heavy_check_mark:<sup>3</sup>|:x:|:x:|:heavy_check_mark:|
|Siemens Cooktop|:warning:<sup>4</sup>|:x:|:x:|:heavy_check_mark:|
|LG Washer-Dryer|:x:<sup>10</sup>|:x:|:x:|:heavy_check_mark:|
|Wyze Cams|:x:|:x:|:heavy_check_mark:|:heavy_check_mark:|
|Aotec Multisensors 6|:warning:<sup>9</sup>|:x:|:x:|:x:|
|Fibaro door sensors|:heavy_check_mark:|:x:|:x:|:x:|
|Aotec WallMotes|:warning:<sup>8</sup>|:x:|:x:|:x:|
|D-Link flood sensors|:x:|:x:|:x:|:heavy_check_mark:|
|Whirlpool W11 Oven|:x:|:x:|:x:|:x:<sup>5</sup>|
|Whirlpool W11 Microwave|:x:|:x:|:x:|:x:<sup>5</sup>|





<sup>1</sup> Exposed via Home Assistant Addon, requires open ports in network configuration


<sup>2</sup> Is coming soon via https://github.com/home-assistant/home-assistant/pull/21144


<sup>3</sup> Via custom component https://github.com/docbobo/home-assistant-miele

<sup>4</sup> API does not support Cooktop yet (https://developer.home-connect.com/docs/cooktop/supported_programs_and_options). Only very basic functionality is exposed via custom component https://github.com/DavidMStraub/homeassistant-homeconnect.

<sup>5</sup> Mobile app (https://play.google.com/store/apps/details?id=com.adbglobal.whirlpool&hl=en) doesn't work correctly, impossible to add new appliances. Problem reported to Whirlpool.


<sup>6</sup> Doesn't work with all the functionality - e.g. playback from Tidal is region-locked, grouping is limited.

<sup>7</sup> Zones do not work. Turning off doesn't work. Better implementation is coming soon with https://github.com/home-assistant/home-assistant/pull/24260

<sup>8</sup> Swipe left/right and up/down doesn't work.

<sup>9</sup> Works really slow and often does not trigger motion correctly. Vibration alarms not implemented.


<sup>10</sup> Should be possible via custom component and some tinkering. See https://community.home-assistant.io/t/in-development-lg-smartthinq-component/40157/249
