# Flowise harness

The Click command and REPL use the same HTTP client. Flow definitions and
deployment state live on the Flowise server. Local graph files are only inputs
and exports.

Management commands use `/api/v1/chatflows`. The CLI encodes the graph as
the API's `flowData` JSON string and exposes the deploy flag as an explicit
operation. The prediction command uses `/api/v1/prediction/{id}`. Flowise owns
authentication and execution for each route.

See the official [chatflows](https://docs.flowiseai.com/api-reference/chatflows)
and [prediction](https://docs.flowiseai.com/api-reference/prediction) references.
