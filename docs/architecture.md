# Architecture

## Layers

- `app/presentation/tk`
  - Tk widgets, variable bindings, dialogs, chart rendering.
  - Consumes application events and dispatches user intents.
- `app/application`
  - Use-case orchestration (`start_sweep`, `stop_sweep`, `save/load`, `settings`).
  - Emits typed events for UI; no Tk or message boxes.
- `app/domain`
  - Pure dataclasses, enums, validation, sweep generation, DSP, calibration.
- `app/infrastructure`
  - Adapter wrappers around `equips.py`.
  - JSON settings and MAT/CSV/TXT persistence.

## Dependency Rules

Allowed:

- `presentation -> application`
- `application -> domain`
- `application -> infrastructure` (ports / repositories)
- `infrastructure -> domain`

Forbidden:

- `domain` importing Tkinter / PyVISA / Matplotlib
- `application` showing dialogs (`messagebox` / `filedialog`)
- UI accessing `equips` directly

## Event Flow

1. UI collects parameters from `ViewModel`.
2. Controller maps to `AppSettings` and starts `StartSweepUseCase` in worker thread.
3. Use case emits:
   - `SweepStarted`
   - `SweepProgress`
   - `SweepDataUpdated`
   - `SweepWarning` / `SweepFailed`
   - `SweepCompleted` / `SweepStopped`
4. Controller polls event queue on main thread via `after()` and updates UI safely.

## Instrument Access

- Instrument model + address resolve through `equips_factory`.
- AWG and OSC commands are executed via `AwgPort` / `OscPort` adapters.
- Connection scanning is provided by `PyVisaResourceScanner` and `ConnectionMonitor`.

## Persistence

- Settings: `__config__/settings.json`
- Measurement files: MAT/CSV/TXT (+ optional plot PNG)
- Reference files: MAT
