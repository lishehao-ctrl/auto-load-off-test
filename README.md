# LoadoffTest (Decoupled Architecture)

LoadoffTest is a Python desktop tool for AWG/OSC sweep measurement and calibration.

This version is fully refactored into a layered architecture:

- `presentation` (Tkinter UI only)
- `application` (use cases and event flow)
- `domain` (pure business models and algorithms)
- `infrastructure` (instrument adapters and persistence)

## Project Layout

```text
src/
  main.py
  app/
    presentation/tk/
    application/
    domain/
    infrastructure/
```

Legacy coupled modules (`src/ui.py`, `src/test.py`, `src/channel.py`, `src/deviceMng.py`) are removed.

## Run

```bash
python3 src/main.py
```

## Configuration

Settings are stored in JSON:

- `__config__/settings.json`

Schema version is tracked in the settings payload (`schema_version`).

## Output Files

Save operation writes:

- `*.mat`
- `*.csv`
- `*.txt`
- plot images (`*_gain.png`, `*_gain_db.png`) when figure handles are provided

## Testing

Run automated tests:

```bash
python3 -m unittest discover -s tests
```

Tests cover:

- domain sweep generation
- signal processing behavior
- start-sweep use case event flow with mock ports
- settings repository round-trip

## Notes

- The application remains local single-process.
- No HTTP backend is introduced.
- UI thread safety is enforced through event queue dispatch (`Tk.after`).
