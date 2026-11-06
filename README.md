# Tesla Drive Tracker for Home Assistant

A Home Assistant integration with a bundled Lovelace card that will show a Tesla's
drive live on a map: the car pointing the way it's going, the real route line, the
destination, ETA, distance left and battery at arrival. It will also give
automations a clean set of hooks for trips and arrivals.

> **This integration is still being built.** The backend works: it adds a car,
> follows its drives and publishes the entities below. The card and the automation
> hooks are still to come, and there are no releases yet.

## What it adds

For each car, using entities your Tesla integrations already provide:

| Entity | What it shows |
|---|---|
| Drive state | `parked`, `driving`, `navigating`, `arriving`, `charging` or `offline` |
| Driving, Heading home | Whether the car is on a drive, and whether that drive is going home |
| Destination (sensor and tracker) | The name, and a position only when it belongs to that name |
| ETA, Time remaining, Distance remaining | For the current route |
| Arrival battery, Traffic delay | When your car reports them |
| Trip distance, Trip duration | The current trip, held after it ends |
| Hide destination | See below |

A destination, its ETA and the other route figures appear only during a drive. The
car can set navigation home by itself while parked, which isn't a trip.

Every source can be replaced in the integration's options, for example pointing
the arrival time at a travel time sensor.

## Privacy

**Hide destination starts on, so a new install shows no destination until you turn
it off.** Anything but a clean `off` counts as hidden, because a destination shown
by mistake can't be taken back.

While hidden, the integration publishes no destination, distance, route line or
heading home. Arrival time stays, because when isn't where.

This is display privacy, not access control. Anyone logged in to Home Assistant can
still read the source entities.

## Requirements

* Home Assistant 2026.10.0 or later
* [Tesla Fleet Telemetry](https://github.com/johnbr/ha-tesla-fleet-telemetry) or the
  core [Tesla Fleet](https://www.home-assistant.io/integrations/tesla_fleet/)
  integration, or both
* For the route line: Tesla Fleet Telemetry 0.15.0 or later, with `RouteLine` added
  from its signal catalog

## License

MIT. This project is not affiliated with or endorsed by Tesla, Inc.
