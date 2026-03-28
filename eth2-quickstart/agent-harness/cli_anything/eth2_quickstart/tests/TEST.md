# cli-anything-eth2-quickstart Test Plan

## Unit

- repo root detection from explicit path and environment
- config file upsert behavior
- CLI help and JSON output
- phase 2 command construction
- validator guidance generation
- status and health aggregation with mocked subprocess results

## E2E

- skip automatically when no real `eth2-quickstart` checkout is configured
- verify wrapper discovery
- verify read-only commands (`help`, `health-check`) against a real checkout

