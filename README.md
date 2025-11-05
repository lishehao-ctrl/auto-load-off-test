# LoadoffTest — Instrument Control GUI

A Python/Tkinter GUI to control an Arbitrary Waveform Generator (AWG) and an Oscilloscope via VISA (PyVISA).  
Features include frequency sweeps, amplitude/impedance control, auto-range on the scope, plotting, and basic calibration.

> Entry point: `main.py` launches the Tkinter UI
---

## 🔌 Supported Instruments

**AWGs**
- Rigol DSG4102
- Rigol DSG836 *(RF output only; 50 Ω output impedance)*

**Oscilloscopes**
- Tektronix MDO34
- Tektronix MDO3024
- Rigol DHO1202
- Rigol DHO1204

## 🔽 Quick Start (Binary, Windows)

1) Install **NI-VISA Runtime** (required), then reboot if prompted.  
2) (Optional, if you also use Keysight instruments) Install **Keysight IO Libraries Suite** after NI-VISA.  
3) Download and run `LoadoffTest-<version>-win64.exe` from the **Releases** page.

> Note: The EXE uses PyVISA to talk to the system VISA backend. NI-VISA itself is **not** bundled—users must install it on their machine
**Verify VISA:**

---

## 🛠 Run from Source

### Requirements
See `requirements.txt` (core libs: pyvisa, numpy, scipy, matplotlib, mplcursors, pyserial, tkinter)

### Run
```bash
python main.py
