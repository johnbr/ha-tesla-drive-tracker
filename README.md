# Tesla Drive Tracker for Home Assistant

A Home Assistant integration with a bundled Lovelace card that will show a Tesla's
drive live on a map: the car pointing the way it's going, the real route line, the
destination, ETA, distance left and battery at arrival. It will also give
automations a clean set of hooks for trips and arrivals.

> **This integration is still being built.** The backend and the card work. The
> automation hooks are still to come, and there are no releases yet.

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

## The card

The integration registers `custom:tesla-drive-tracker-card` itself, so there is no
resource to add. With one car it needs no options at all:

```yaml
type: custom:tesla-drive-tracker-card
```

It draws on Home Assistant's own map, so it needs no API key and follows your theme.
Between fixes it predicts where the car is, along the route when there is one, for up
to 15 seconds. After 30 seconds with no fix it says how old the last one is.

| Group | Options |
|---|---|
| Car | `model`, `color` (a Tesla paint name or hex), `roof`, `marker_style` (`car`, `arrow`, `dot`), `marker_size`, `image` and `image_nose` for your own picture |
| Map | `follow` (`auto`, `car`, `fit`, `off`), `recenter_after`, `speed_zoom`, `height`, `show_zones`, `when_parked` (`map`, `compact`, `hide`), `smooth_motion` |
| Lines | `show_route`, `route_color`, `show_trail`, `trail_color`, `trail_minutes` |
| Info panel | `hud` (`full`, `compact`, `off`), `hud_fields`, `hud_position`, `units` |
| Other | `entry_id`, to choose a car when you have more than one |

With `follow: auto`, the map stays close to a car that has nowhere set, and frames the
car, route and destination when it does. A hidden destination is never framed.

The model and paint come from the car when it reports them. `ExteriorColor`,
`RoofColor` and `CarType` can be added from the Tesla Fleet Telemetry signal catalog,
and the integration's options can set both by hand. A picture must be a path on this
Home Assistant or an https URL.

## Privacy

**Hide destination starts off**, so a new install shows the destination. Turn it on
to hide it, and it stays on across restarts.

While hidden, the integration publishes no destination, distance, route line or
heading home, so the card never receives them. Arrival time stays, because when isn't where.

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
