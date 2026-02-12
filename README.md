## Description
Inspired by [Crystools extension for ComfyUI](https://github.com/crystian/ComfyUI-Crystools?tab=readme-ov-file#general), simple-recourse-monitor is an always-on-top overlay that displays real-time CPU, RAM, GPU, VRAM, and GPU temperature usage in a compact, draggable bar. <br><br>Designed to sit over the taskbar and keep you informed at a glance.
<br>
<br>Especially useful when working with local LLM's outside of ComfyUI.
<br><br>
<img width="735" height="77" alt="2026-02-12_19-24-32" src="https://github.com/user-attachments/assets/54a4f297-c3dd-4b00-b6fb-c6423727aec4" />

## Installation
Clone or download this repository.

Create a virtual environment inside the project folder:
```
python -m venv .
```
Activate the virtual environment:

```
.\Scripts\activate
```
Install the required dependencies:
```
pip install -r requirements.txt
```
Run the monitor:
```
python main.py
```

## Usage
- The overlay will appear in the top‑right corner of your screen.

- Move the window by clicking and dragging anywhere on it.

- Hide to tray – close the window (or click the tray icon) to minimise.

- Restore – click the tray icon again.

- Exit – right‑click the tray icon and select Exit.

## Known Issues / Limitations
- GPU monitoring works only with NVIDIA GPUs. If no compatible GPU is found, the GPU, VRAM and temperature bubbles will show 0.

## License
This project is open source and available under the MIT License.
