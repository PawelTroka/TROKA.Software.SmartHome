[Sonos Notify component](https://github.com/ulfalfa/sonos_tts) for homeassistant

# What This Is:

This is a custom component to use sonos speakers with the notifier plattform of [Homeassistant](https://home-assistant.io) instead of writing custom scripts. E.g. it enables us to user the [alert functionality](https://www.home-assistant.io/integrations/alert/)

By the way: It is using the first tts plattform that is found - I'm currently using VOICERSS (and it's not tested with any other tts plattform)

# Installation and Configuration

Use copy the repo to the `custom_components` folder of your config folder. See also [https://developers.home-assistant.io/docs/en/creating_component_loading.html]

Then edit your configuration and add notify entities to your `configuration.yaml`

```yaml
notify:
  - name: Desk
    platform: sonos_tts
    entities: media_player.desk
    tts: google_translate
  - name: Bedroom
    platform: sonos_tts
    entities: media_player.bedroom
  - name: SomePlayers
    platform: sonos_tts
    entities:
      - media_player.desk
      - media_player.bedroom
```

# Usage

Finally you can send notifications

```yaml
# Example configuration.yaml entry
alert:
  garage_door:
    name: Garage is open
    done_message: Garage is closed
    entity_id: input_boolean.garage_door
    state: 'on'
    repeat: 30
    can_acknowledge: true
    skip_first: true
    notifiers:
      - desk
```

or you just send a notification in a script

```yaml
....
    service: notify.someplayers
      data:
        volume_level: 0.5
      message: This is notification
```

# Disclaimer

This is my first component for home assistant and even my first code written in python. So don't expect, that is all working and use it on your own risk.

# Known Limitation(s)

- When interrupting a single playing player, the pause notification comes to late and is interpreted, that the tts output is over and the old state is restored. This does not happen if using notification group or interrupting a joined player - I didn't figured out the problem yet.
