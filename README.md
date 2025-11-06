# LoadoffTest — Instrument Control GUI

A Python/Tkinter GUI to control an Arbitrary Waveform Generator (AWG) and an Oscilloscope via VISA (PyVISA).  
Features include frequency sweeps, amplitude/impedance control, auto-range on the scope, plotting, and basic calibration.

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
1. Install **NI-VISA Runtime** (required), then reboot if prompted.  
2. Download `LoadoffTest-<version>-win64.exe` from the **Releases** page and run it.
> The EXE uses PyVISA with the system VISA backend. NI-VISA is **not** bundled; please install it first.



### 🎥 Demo Video  
Click the [**image**](https://youtu.be/mykzLSdMx8w) below to watch a quick demonstration of *LoadoffTest* in action:
[![Watch the video](https://img.youtube.com/vi/mykzLSdMx8w/sddefault.jpg)](https://youtu.be/mykzLSdMx8w?si=-zHm-ErftVF0S7o9)
