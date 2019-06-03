# TROKA.Software.SmartHome
Home automation configuration, scripts and state of affairs


## Devices/systems integration state matrix

| Devices\Systems 	| Home Assistant 	| Amazon Alexa 	| Google Home 	| App 	|
|-----------------	|----------------	|--------------	|-------------	|--------------	|
| LIFX Lights     	|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
| MiLight Lights   	|:heavy_check_mark:|:heavy_check_mark:<sup>1</sup>|:x:|:heavy_check_mark:|
| Sonos Multi-room audio|:heavy_check_mark:|:warning:<sup>6</sup>|:warning:<sup>6</sup>|:heavy_check_mark:|
| Living room TV|:heavy_check_mark:|:x:|:heavy_check_mark:|:heavy_check_mark:|
| Bedroom TV|:heavy_check_mark:|:x:|:heavy_check_mark:|:heavy_check_mark:|
| XBOX ONE X|:x:|:heavy_check_mark:|:x:|:x:|
| Netatmo Weather Station|:heavy_check_mark:|:heavy_check_mark:|:x:|:heavy_check_mark:|
| Nest Protect|:heavy_check_mark:|:x:|:x:|:heavy_check_mark:|
|Tado radiator thermostats|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|
|WarmUp 4iE Underfloor heating|:x:<sup>2</sup>|:heavy_check_mark:|:x:|:heavy_check_mark:|
|BTicino Classe 300X13E (video intercom)|:x:|:x:|:x:|:heavy_check_mark:|
|Miele Fridge-Freezer|:heavy_check_mark:<sup>3</sup>|:x:|:x:|:heavy_check_mark:|
|Siemens Cooktop|:warning:<sup>4</sup>|:x:|:x:|:heavy_check_mark:|
|Whirlpool W11 Oven|:x:|:x:|:x:|:x:<sup>5</sup>|
|Whirlpool W11 Microwave|:x:|:x:|:x:|:x:<sup>5</sup>|





<sup>1</sup> Exposed via Home Assistant Addon, requires open ports in network configuration


<sup>2</sup> Is coming soon via https://github.com/home-assistant/home-assistant/pull/21144


<sup>3</sup> Via custom component https://github.com/docbobo/home-assistant-miele

<sup>4</sup> API does not support Cooktop yet (https://developer.home-connect.com/docs/cooktop/supported_programs_and_options). Only very basic functionality is exposed.

<sup>5</sup> Mobile app (https://play.google.com/store/apps/details?id=com.adbglobal.whirlpool&hl=en) doesn't work correctly, impossible to add new appliances. Problem reported to Whirlpool.


<sup>6</sup> Doesn't work with all the functionality - e.g. playback from Tidal is region-locked, grouping is limited.
