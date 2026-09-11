# Model directory

This directory intentionally does not contain model weights yet.

Before adding any model:

1. Verify the model and weight license.
2. Verify redistribution is allowed if the weights will be distributed with the project.
3. Record model name, version, license, source, languages and SHA-256 in `config/voices.json`.
4. Prefer an optimized ONNX/browser-compatible model for zero-backend deployments when quality and license allow it.
5. Keep large weights outside normal Git history unless their size and license make repository storage appropriate.

The backend engine interface is deliberately model-agnostic so the project can support multiple legal model choices without changing the frontend.
