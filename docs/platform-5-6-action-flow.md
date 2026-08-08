# Platform 5.6 — Action State Machine

State-changing callbacks use one deterministic lifecycle:

1. execute the action once;
2. treat telemetry as best-effort;
3. answer the callback exactly once;
4. reload current state;
5. render the current screen once.

Covered in this release: weekly reward, season reward, personal daily-plan reward, and anonymous contact removal.
