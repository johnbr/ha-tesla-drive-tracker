# Replay fixtures

Each file is a window of a real car's history, kept because something in it once
went wrong. Rows are `[seconds from the start of the window, role, value]`.

They were scrubbed before coming here. They hold only speed, gear, occupancy,
charging, route names and arrival times:

- No coordinates. Even a shifted track has a recognisable shape, so positions are
  invented by the tests.
- Route names are replaced with `Place 1`, `Place 2` and so on. `Home` stays,
  because it is a rule.
- No dates. Arrival times are offsets, and speed is rounded and thinned to about
  one row every 15 s.

Keep any new fixture to the same rules.
