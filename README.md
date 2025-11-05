# LoadoffTest — Instrument Control GUI

A Python/Tkinter GUI to control an Arbitrary Waveform Generator (AWG) and an Oscilloscope via VISA (PyVISA).  
Features include frequency sweeps, amplitude/impedance control, auto-range on the scope, plotting, and basic calibration.

> Entry point: `main.py` launches the Tkinter UI (`UI().mainloop()`).:contentReference[oaicite:0]{index=0}

---

## 🔽 Quick Start (Binary, Windows)

1) Install **NI-VISA Runtime** (required), then reboot if prompted.  
2) (Optional, if you also use Keysight instruments) Install **Keysight IO Libraries Suite** after NI-VISA.  
3) Download and run `LoadoffTest-<version>-win64.exe` from the **Releases** page.

> Note: The EXE uses PyVISA to talk to the system VISA backend. NI-VISA itself is **not** bundled—users must install it on their machine first.:contentReference[oaicite:1]{index=1}

**Verify VISA:**
- Use **NI MAX** to check that VISA resources (USB/TCPIP/GPIB) are detected.  
- If running from source, `pyvisa-info` can confirm backend status.

---

## 🛠 Run from Source

### Requirements
See `requirements.txt` (core libs: pyvisa, numpy, scipy, matplotlib, mplcursors, pyserial, tkinter).:contentReference[oaicite:2]{index=2}:contentReference[oaicite:3]{index=3}

### Run
```bash
python main.py
