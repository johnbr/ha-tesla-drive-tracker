# Tesla Drive Tracker for Home Assistant

A Home Assistant integration with a bundled Lovelace card that will show a Tesla's
drive live on a map: the car pointing the way it's going, the real route line, the
destination, ETA, distance left and battery at arrival. It will also give
automations a clean set of hooks for trips and arrivals.

> **This integration isn't usable yet.** It has no config flow, entities or card,
> so installing it does nothing. There are no releases.

## Status

Written and tested so far, none of it needing Home Assistant:

* The trip engine, which decides when a drive starts and ends and when the car is
  arriving
* Destination pairing, which only trusts coordinates that belong to the destination
  name on screen, because the car can send a new name without its location
* The `RouteLine` decoder
* Source selection across the Tesla integrations a car can report through
* Destination privacy: a hidden destination is redacted at the source

Still to come: the config flow, entities, websocket API and card.

## Requirements

* Home Assistant 2026.10.0 or later
* [Tesla Fleet Telemetry](https://github.com/johnbr/ha-tesla-fleet-telemetry) 0.15.0
  or later for the route line, with `RouteLine` added from its signal catalog

## License

MIT. This project is not affiliated with or endorsed by Tesla, Inc.
