# Filter Translation Pitfalls

When translating effects between formats (e.g., MLT → ffmpeg), watch for these common issues.

## Duplicate Filter Types

Some tools (ffmpeg) don't allow the same filter twice in a chain. If your project has both `brightness` and `saturation` filters, and both map to ffmpeg's `eq=`, you must **merge** them into a single `eq=brightness=X:saturation=Y`.

## Ordering Constraints

ffmpeg's `concat` filter requires **interleaved** stream ordering:
`[v0][a0][v1][a1][v2][a2]`, NOT grouped `[v0][v1][v2][a0][a1][a2]`.

The error message ("media type mismatch") is cryptic if you don't know this.

## Parameter Space Differences

Effect parameters often use different scales:
- MLT brightness `1.15` = +15%
- ffmpeg `eq=brightness=0.06` on a -1..1 scale

Document every mapping explicitly.

## Unmappable Effects

Some effects have no equivalent in the render tool. Handle gracefully (warn, skip) rather than crash.
