# Mnemosyne UI

This optional local dashboard exposes a small, inspectable interface over the
Mnemosyne runtime. It is intentionally offline-first: the server binds to the
loopback interface, serves static assets without a frontend build step, and
does not require a hosted service.

## Scope

The UI is a local companion, not a replacement for the Python engine. It can
display runtime information, surface plans and queues, and provide bounded
task and decision workflows through the existing API contract.

The current launcher targets macOS on Apple Silicon because local inference is
provided through MLX. The core repository remains useful without the UI.

## Run locally

From the repository root:

```bash
make ui
```

Then open the loopback address printed by the launcher. Stop it with:

```bash
make ui-stop
```

## Design constraints

- No network exposure by default: the server listens on `127.0.0.1`.
- No remote frontend dependency at runtime.
- UI actions use the same explicit policy boundaries as command-line actions.
- The data contract is defined and tested in
  `system/lib/mnemosyne/production/ui_contract.py`.

For setup and the repository-wide architecture, return to the root
[`README.md`](../README.md).
