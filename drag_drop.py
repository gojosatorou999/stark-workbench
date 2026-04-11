# +--------------------------------------------------------------------------------------------------------------------+
# |                                                                                             (module) drag_drop.py ||
# |                                                                               STARK OVERLAY — Pure Windows Control||
# +--------------------------------------------------------------------------------------------------------------------+

import cv2
import mediapipe as mp
import numpy as np
import time
import math
import os
import win32api
import win32con
import win32gui
from collections import deque
import threading

# =====================================================================================================================
# WINDOWS INPUT SIMULATION 
# =====================================================================================================================

def move_mouse(x: int, y: int):
    win32api.SetCursorPos((x, y))

def mouse_click(button="left", down=True):
    flags = 0
    if button == "left":
        flags = win32con.MOUSEEVENTF_LEFTDOWN if down else win32con.MOUSEEVENTF_LEFTUP
    elif button == "right":
        flags = win32con.MOUSEEVENTF_RIGHTDOWN if down else win32con.MOUSEEVENTF_RIGHTUP
    win32api.mouse_event(flags, 0, 0, 0, 0)

def mouse_scroll(delta: int):
    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, delta, 0)

def simulate_keyboard(*keys):
    """Simulate key presses (e.g., win+ctrl+left/right)."""
    # Press all
    for key in keys:
        win32api.keybd_event(key, 0, 0, 0)
    # Release all in reverse
    for key in reversed(keys):
        win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)


# =====================================================================================================================
# PER-HAND STATE TRACKER
# =====================================================================================================================

class HandState:
    def __init__(self, label: str):
        self.label = label
        self.landmarks = {}
        self.gesture = "NONE"
        self.pinch_active = False
        self.pinch_distance = 999.0
        
        # Debounce and click tracking
        self.last_pinch_time = 0
        self.last_click_time = 0
        self.click_count = 0
        self.last_gesture_time = 0
        
        # Pinched state logic (need consecutive frames)
        self.pinch_frames = 0
        self.is_dragging = False

        self.trail = deque(maxlen=15)

    def clear(self):
        self.landmarks = {}
        self.gesture = "NONE"
        self.pinch_distance = 999.0

    def index_pos(self):
        if 8 in self.landmarks:
            return (self.landmarks[8]['x'], self.landmarks[8]['y'])
        return None

    def thumb_pos(self):
        if 4 in self.landmarks:
            return (self.landmarks[4]['x'], self.landmarks[4]['y'])
        return None


# =====================================================================================================================
# ONSCREEN VISUAL EFFECTS
# =====================================================================================================================

class VisualEffect:
    def __init__(self, x, y, effect_type):
        self.x = x
        self.y = y
        self.type = effect_type
        self.start_time = time.time()
        self.duration = 0.5  # half second

    def is_alive(self):
        return time.time() - self.start_time < self.duration

    def draw(self, image):
        progress = (time.time() - self.start_time) / self.duration
        radius = int(20 + progress * 30)
        alpha = 1.0 - progress
        
        if self.type == "click":
            c = (int(255*alpha), int(255*alpha), int(255*alpha))
            cv2.circle(image, (self.x, self.y), radius, c, 2, cv2.LINE_AA)
        elif self.type == "right_click":
            c = (0, int(150*alpha), int(255*alpha)) # Orange
            cv2.circle(image, (self.x, self.y), radius, c, 3, cv2.LINE_AA)
        elif self.type == "double_click":
            c = (int(255*alpha), int(255*alpha), 0) # Cyan
            cv2.circle(image, (self.x, self.y), radius, c, 2, cv2.LINE_AA)
            cv2.circle(image, (self.x, self.y), radius - 10, c, 2, cv2.LINE_AA)
        elif self.type == "scroll_up":
            c = (0, int(255*alpha), 0)
            cv2.arrowedLine(image, (self.x, self.y + 15), (self.x, self.y - 15), c, 2, tipLength=0.3)
        elif self.type == "scroll_down":
            c = (0, int(255*alpha), 0)
            cv2.arrowedLine(image, (self.x, self.y - 15), (self.x, self.y + 15), c, 2, tipLength=0.3)


# =====================================================================================================================
# MAIN OVERLAY ENGINE
# =====================================================================================================================

class StarkOverlay(object):
    def __init__(self, camera_id: int = 0):
        self.cap = cv2.VideoCapture(camera_id)
        
        # Force camera resolution to 1280x720 for better landmark detection accuracy
        self.cam_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        self.cam_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        if self.cam_w < 1280 or self.cam_h < 720:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cam_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.cam_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        print(f"[STARK] Camera initialized at {self.cam_w}x{self.cam_h} @ {actual_fps} fps")

        # Display dims
        self.screen_w = win32api.GetSystemMetrics(0)
        self.screen_h = win32api.GetSystemMetrics(1)
        
        print(f"[STARK] Screen Resolution: {self.screen_w}x{self.screen_h}")

        # MediaPipe Hands
        _model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand_landmarker.task')
        BaseOptions = mp.tasks.BaseOptions
        HandLandmarker = mp.tasks.vision.HandLandmarker
        HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        # Note: mapping legacy parameters to modern Tasks API equivalents
        self._landmarker_options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_model_path),
            running_mode=VisionRunningMode.VIDEO,  # (equivalent to static_image_mode=False)
            num_hands=2,                           # (equivalent to max_num_hands=2)
            min_hand_detection_confidence=0.75,    # (increased strictness per request)
            min_hand_presence_confidence=0.75,
            min_tracking_confidence=0.6,           # (increased tracking minimum)
        )
        self._landmarker = HandLandmarker.create_from_options(self._landmarker_options)
        self._frame_timestamp_ms = 0

        self._left_hand = HandState("LEFT")
        self._right_hand = HandState("RIGHT")
        self._hands_list = [self._left_hand, self._right_hand]

        # Window state
        self.window_name = "STARK OVERLAY"
        self._window_init = False
        
        # State
        self.running = True
        self.paused = False
        self.debug_mode = False
        self.debug_end_time = 0
        
        # Cursor smoothing
        self.cursor_x = self.screen_w // 2
        self.cursor_y = self.screen_h // 2
        self.alpha_pos = 0.4  # Smoothing factor
        self.dead_zone = 5    # pixels
        
        self.startup_time = time.time()
        self.effects = []
        
        # Scroll tracking
        self.last_scroll_y = None
        
        # Two hand scale
        self.two_hand_baseline = None
        
        # Win keys for virtual desktop
        self.VK_LWIN = 0x5B
        self.VK_CONTROL = 0x11
        self.VK_LEFT = 0x25
        self.VK_RIGHT = 0x27

    def _apply_transparency(self):
        """Make OpenCV window click-through, topmost, and transparent black."""
        hwnd = win32gui.FindWindow(None, self.window_name)
        if hwnd:
            # Set to Layered, Transparent (click-through), TopMost
            exStyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exStyle | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST)
            # Black (0,0,0) is fully transparent
            win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(0,0,0), 0, win32con.LWA_COLORKEY)
            self._window_init = True
            print("[STARK] Glass mode activated.")

    def _finger_extended(self, landmarks, tip_id, pip_id, is_thumb=False):
        if tip_id not in landmarks or pip_id not in landmarks:
            return False
        if is_thumb:
            if 0 not in landmarks: return False
            wrist_x = landmarks[0]['x']
            return abs(landmarks[tip_id]['x'] - wrist_x) > abs(landmarks[pip_id]['x'] - wrist_x)
        return landmarks[tip_id]['y'] < landmarks[pip_id]['y']

    def _detect_gesture(self, landmarks, pinch_dist):
        if not landmarks or len(landmarks) < 21: return "NONE"
        thumb = self._finger_extended(landmarks, 4, 3, is_thumb=True)
        index = self._finger_extended(landmarks, 8, 6)
        middle = self._finger_extended(landmarks, 12, 10)
        ring = self._finger_extended(landmarks, 16, 14)
        pinky = self._finger_extended(landmarks, 20, 18)

        ext = [thumb, index, middle, ring, pinky]
        n_ext = sum(ext)
        if pinch_dist < 40: return "PINCH"
        if n_ext == 0: return "FIST"
        if n_ext == 5: return "OPEN_HAND"
        if index and middle and not ring and not pinky: return "PEACE"
        if index and not middle and not ring and not pinky: return "POINT"
        return "NONE"

    def ProcessFrame(self):
        auth, frame = self.cap.read()
        if not auth or frame is None:
            return False

        # Raw frame mirrored
        frame = cv2.flip(frame, 1)

        # Pure Black transparent background
        self.image = np.zeros((self.screen_h, self.screen_w, 3), dtype=np.uint8)

        if self.paused:
            return True

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        
        self._frame_timestamp_ms += 33
        res = self._landmarker.detect_for_video(mp_image, self._frame_timestamp_ms)

        self._left_hand.clear()
        self._right_hand.clear()

        if res.hand_landmarks:
            for idx, lm in enumerate(res.hand_landmarks):
                lbl = "RIGHT" if idx == 0 else "LEFT"
                if res.handedness and idx < len(res.handedness):
                    lbl = res.handedness[idx][0].category_name.upper()

                hs = self._right_hand if lbl == "RIGHT" else self._left_hand
                for num_id, m in enumerate(lm):
                    # Map to SCREEN coordinates directly
                    hs.landmarks[num_id] = {
                        'x': int(m.x * self.screen_w),
                        'y': int(m.y * self.screen_h)
                    }

        self.HandleLogic()
        self.DrawFeedback()

        # Debug skeleton
        if self.debug_mode and time.time() < self.debug_end_time:
            self._draw_skeleton()
        elif self.debug_mode:
            self.debug_mode = False

        return True

    def HandleLogic(self):
        now = time.time()

        # Update Hands
        for hs in self._hands_list:
            if not hs.landmarks:
                # Hand lost -> release things
                if hs.is_dragging:
                    mouse_click("left", False)
                    hs.is_dragging = False
                continue

            # Distance
            if 4 in hs.landmarks and 8 in hs.landmarks:
                t = hs.landmarks[4]
                i = hs.landmarks[8]
                d = math.sqrt((t['x']-i['x'])**2 + (t['y']-i['y'])**2)
                hs.pinch_distance = d
            
            hs.gesture = self._detect_gesture(hs.landmarks, hs.pinch_distance)
            idx_pos = hs.index_pos()
            if idx_pos:
                hs.trail.append(idx_pos)


        # --- LEFT HAND CONTROL (Modifier) ---
        lh = self._left_hand
        if lh.landmarks:
            if lh.gesture == "FIST":
                # Pause cursor
                return 
            
            # Virtual Desktop Swipe detection (OPEN_HAND moving horizontally fast)
            if lh.gesture == "OPEN_HAND":
                if len(lh.trail) >= 5:
                    dx = lh.trail[-1][0] - lh.trail[0][0]
                    if now - lh.last_gesture_time > 1.5:
                        if dx > 400: # Swipe Right (go Left desktop)
                            simulate_keyboard(self.VK_LWIN, self.VK_CONTROL, self.VK_LEFT)
                            lh.last_gesture_time = now
                            print("[STARK] Swiped Desktop LEFT")
                        elif dx < -400: # Swipe Left (go Right desktop)
                            simulate_keyboard(self.VK_LWIN, self.VK_CONTROL, self.VK_RIGHT)
                            lh.last_gesture_time = now
                            print("[STARK] Swiped Desktop RIGHT")


        # --- RIGHT HAND CONTROL (Pointer) ---
        rh = self._right_hand
        if not rh.landmarks:
            self.last_scroll_y = None
            return

        ix, iy = rh.index_pos()
        tpos = rh.thumb_pos()

        # Cursor Smoothing
        target_x, target_y = ix, iy
        # Center of pinch if pinching
        if rh.gesture == "PINCH" and tpos:
            target_x = (ix + tpos[0]) // 2
            target_y = (iy + tpos[1]) // 2

        dx = target_x - self.cursor_x
        dy = target_y - self.cursor_y
        
        # Deadzone filter
        if math.sqrt(dx**2 + dy**2) > self.dead_zone:
            self.cursor_x = int(self.cursor_x + self.alpha_pos * dx)
            self.cursor_y = int(self.cursor_y + self.alpha_pos * dy)
            move_mouse(self.cursor_x, self.cursor_y)


        # Interactions
        # 1. PINCH / DRAG
        if rh.gesture == "PINCH":
            rh.pinch_frames += 1
            if rh.pinch_frames == 3 and not rh.is_dragging:
                # Trigger click down
                
                # Check for double click
                if now - rh.last_pinch_time < 0.5:
                    self.effects.append(VisualEffect(self.cursor_x, self.cursor_y, "double_click"))
                    mouse_click("left", True)
                    mouse_click("left", False)
                    mouse_click("left", True)
                    mouse_click("left", False)
                    rh.last_pinch_time = 0
                    print("[STARK] Double Click")
                else:
                    self.effects.append(VisualEffect(self.cursor_x, self.cursor_y, "click"))
                    mouse_click("left", True)
                    rh.is_dragging = True
                    rh.last_pinch_time = now
                    print("[STARK] Pinch Down (Drag Start)")
        else:
            rh.pinch_frames = 0
            if rh.is_dragging:
                # Release
                mouse_click("left", False)
                rh.is_dragging = False
                print("[STARK] Pinch Release (Drag End)")


        # 2. RIGHT CLICK
        if rh.gesture == "PEACE" and now - rh.last_click_time > 1.0:
            self.effects.append(VisualEffect(self.cursor_x, self.cursor_y, "right_click"))
            mouse_click("right", True)
            mouse_click("right", False)
            rh.last_click_time = now
            print("[STARK] Right Click")

        
        # 3. SCROLL
        if rh.gesture == "OPEN_HAND":
            if self.last_scroll_y is None:
                self.last_scroll_y = self.cursor_y
            else:
                s_dy = self.cursor_y - self.last_scroll_y
                if abs(s_dy) > 40:
                    delta = 120 if s_dy < 0 else -120  # Up movement = scroll up
                    mouse_scroll(delta)
                    e_type = "scroll_up" if delta > 0 else "scroll_down"
                    self.effects.append(VisualEffect(self.cursor_x, self.cursor_y, e_type))
                    self.last_scroll_y = self.cursor_y
        else:
            self.last_scroll_y = None


        # --- TWO HAND GLOBAL PINCH (Max/Min) ---
        if lh.landmarks and rh.landmarks and lh.gesture == "PINCH" and rh.gesture == "PINCH":
            lx, ly = lh.index_pos()
            rx, ry = rh.index_pos()
            dist = math.sqrt((lx-rx)**2 + (ly-ry)**2)
            
            if self.two_hand_baseline is None:
                self.two_hand_baseline = dist
            else:
                scale_diff = dist - self.two_hand_baseline
                if now - rh.last_gesture_time > 1.5:
                    if scale_diff > 200: # Spread -> Maximize
                        simulate_keyboard(self.VK_LWIN, win32api.VK_UP)
                        rh.last_gesture_time = now
                        print("[STARK] Window Maximize")
                    elif scale_diff < -200: # Pinch Close -> Minimize
                        simulate_keyboard(self.VK_LWIN, win32api.VK_DOWN)
                        rh.last_gesture_time = now
                        print("[STARK] Window Minimize")
        else:
            self.two_hand_baseline = None


    def DrawFeedback(self):
        # Startup countdown
        now = time.time()
        elapsed = now - self.startup_time
        if elapsed < 3.0:
            count = 3 - int(elapsed)
            txt = f"{count}... ONLINE" if count == 1 else f"{count}..."
            cv2.putText(self.image, txt, (self.screen_w//2 - 100, self.screen_h//2), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,0), 2, cv2.LINE_AA)

        # Draw trails and indicators
        trail_colors = {"RIGHT": (255, 255, 0), "LEFT": (0, 140, 255)} # Cyan, Orange

        for hs in self._hands_list:
            if not hs.landmarks: continue
            
            col = trail_colors[hs.label]

            # Trail
            n = len(hs.trail)
            for i, p in enumerate(hs.trail):
                alpha = (i+1)/n
                r = int(alpha * 5)
                c = tuple(int(ch*alpha) for ch in col)
                cv2.circle(self.image, p, r, c, cv2.FILLED, cv2.LINE_AA)
            
            # Tips
            idx = hs.index_pos()
            thm = hs.thumb_pos()
            if idx:
                cv2.circle(self.image, idx, 8, col, cv2.FILLED, cv2.LINE_AA)
                cv2.circle(self.image, idx, 12, col, 1, cv2.LINE_AA)
            if thm:
                cv2.circle(self.image, thm, 6, (0, 140, 255), cv2.FILLED, cv2.LINE_AA)

            # Pinch indicator line
            if hs.pinch_distance < 60 and idx and thm:
                c = (255,255,255) if hs.gesture == "PINCH" else (100,100,100)
                cv2.line(self.image, idx, thm, c, 2, cv2.LINE_AA)


        # Draw FX
        for fx in reversed(self.effects):
            if fx.is_alive():
                fx.draw(self.image)
            else:
                self.effects.remove(fx)


    def _draw_skeleton(self):
        for hs in self._hands_list:
            if not hs.landmarks: continue
            for p in hs.landmarks.values():
                cv2.circle(self.image, (p['x'], p['y']), 3, (100,100,100), -1)

    def Run(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        while self.running and self.cap.isOpened():
            if not self.ProcessFrame():
                continue

            cv2.imshow(self.window_name, self.image)

            if not self._window_init:
                self._apply_transparency()

            # CLI-only keyboard shortcuts via waitKey (requires window focus)
            # Or terminal input... waitKey is safest.
            k = cv2.waitKey(1)
            if k != -1:
                char = chr(k & 0xFF).lower()
                if char == 'q' or k == 27:
                    self.running = False
                elif char == 'p':
                    self.paused = not self.paused
                    print(f"[STARK] PAUSED: {self.paused}")
                elif char == 'd':
                    self.debug_mode = True
                    self.debug_end_time = time.time() + 5.0
                    print("[STARK] Debug mode 5s")

        self._landmarker.close()
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    print("[STARK] Initializing Full Windows Overlay Engine...")
    system = StarkOverlay()
    system.Run()

