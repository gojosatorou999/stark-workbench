![](https://img.shields.io/github/stars/pandao/editor.md.svg) ![](https://img.shields.io/github/forks/pandao/editor.md.svg) ![](https://img.shields.io/github/tag/pandao/editor.md.svg) ![](https://img.shields.io/github/release/pandao/editor.md.svg) ![](https://img.shields.io/github/issues/pandao/editor.md.svg) ![](https://img.shields.io/bower/v/editor.md.svg)

![header](https://github.com/RP11-AI/personal-data/blob/main/general/header.png?raw=true)

# Stark Workbench V3 — Transparent OS Interaction Engine
The Stark Workbench is a next-generation accessibility and productivity tool that converts your bare hands into a high-precision, gesture-driven controller for the Windows Desktop.

By combining the **MediaPipe Tasks API**, **OpenCV**, and **PyWin32**, this application creates a completely invisible, click-through overlay on top of your entire screen. It maps your fingertips directly to your OS, allowing you to manipulate real desktop apps, folders, and windows without ever touching a mouse or keyboard.

## ✨ Core Features
- **Pure Transparent Overlay:** Runs borderless and completely transparent. The camera feed is hidden. You only see subtle, glowing interaction artifacts (trails and pinch outlines) floating over your actual Windows environment.
- **Dual-Hand Operating System:** Your right hand acts as a precision pointer, while your left hand acts as a powerful modifier, running fully parallel state engines.
- **True OS Hooks:** Simulates genuine Windows events (`MOUSEEVENTF_LEFTDOWN`, scrolling, `Win+Ctrl` key combinations) rather than moving fake in-app objects.
- **Micro-Jitter Suppression:** Mathematical exponential smoothing (EMA) and dead-zones translate raw webcam frames into a stable, usable cursor.

---

## ✋ Gesture Operations

### **Right Hand (Primary Pointer)**
Moves the physical Windows cursor based on your index fingertip.
| Gesture | Action |
| --- | --- |
| **PINCH** *(Hold index + thumb)* | **Left Click / Drag** — Drag real desktop files, or drag window title bars. |
| **DOUBLE PINCH** *(Quickly)* | **Double Click** — Opens folders or executes applications. |
| **PEACE SIGN** *(Hold 1s)* | **Right Click** — Opens Windows context menus. |
| **OPEN HAND** *(Move Up/Down)* | **Scroll Wheel** — Scrolls web pages natively. |

### **Left Hand (Secondary Modifier)**
Controls OS-level environment macros.
| Gesture | Action |
| --- | --- |
| **FIST** | **Freeze State** — Halts the cursor instantly to stabilize viewing. |
| **OPEN HAND SWIPE** *(Left/Right)* | **Virtual Desktops** — Snaps between your Windows workspaces. |

### **Both Hands Simultaneously**
| Gesture | Action |
| --- | --- |
| **DUAL PINCH -> SPREAD** | **Maximize** the focused window. |
| **DUAL PINCH -> CLOSE** | **Minimize** the focused window. |

---

## ⚙️ Installation & Usage

1. Install the required dependencies:
```cmd
pip install opencv-python mediapipe numpy pywin32 pyautogui
```

2. Run the engine:
```cmd
python main.py
```

### Keyboard Shortcuts (Terminal)
Ensure your terminal is focused to trigger these failsafes:
- `Q` — Cleanly exit the engine.
- `P` — Pause tracking.
- `D` — Enable Debug Mode (temporarily shows 3D landmark skeleton).

*(Note: The system automatically searches for a `hand_landmarker.task` model file on boot.)*

![board](https://github.com/RP11-AI/personal-data/blob/main/general/baseboard.png?raw=true)
