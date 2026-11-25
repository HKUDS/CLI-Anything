# Flowise test plan

Unit tests exercise graph input validation, request encoding, management and
prediction credentials, and failures through the Click entry point.

The opt-in server test invokes the installed CLI as separate processes. It
creates a fixture flow, discovers it in the list, verifies its exported graph,
updates and deploys it, verifies persisted state, and runs a prediction against
the actual server before cleaning up the fixture.
