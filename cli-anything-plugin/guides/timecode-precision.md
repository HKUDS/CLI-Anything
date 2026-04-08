# Timecode Precision

Non-integer frame rates (29.97fps = 30000/1001) cause cumulative rounding errors. Follow these rules to avoid drift.

## Use `round()`, Not `int()`

For float-to-frame conversion:
- `int(9000 * 29.97)` — **wrong**, truncates and loses frames
- `round(9000 * 29.97)` — **correct**, gets the right answer

## Use Integer Arithmetic for Timecode Display

Convert frames → total milliseconds via:
```python
total_ms = round(frames * fps_den * 1000 / fps_num)
```

Then decompose with integer division. Avoid intermediate floats that drift over long durations.

## Accept ±1 Frame Tolerance

In roundtrip tests at non-integer FPS, exact equality is mathematically impossible. Accept ±1 frame tolerance.
