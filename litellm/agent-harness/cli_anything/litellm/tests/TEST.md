# LiteLLM CLI Harness - Test Documentation

## Coverage

- Unit tests cover config resolution, YAML loading, patch safety, CLI behavior, and execution loops.
- Mocked end-to-end tests cover task and flow execution without a live LiteLLM proxy.

## Key scenarios

1. Health and model listing with mocked proxy responses.
2. YAML task validation and repo-scoped patch safety.
3. Auto-loop task execution with patch apply and verification.
4. Rollback and export of the last generated patch.
