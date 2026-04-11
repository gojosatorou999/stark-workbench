# +--------------------------------------------------------------------------------------------------------------------+
# |                                                                                                           main.py ||
# |                                                                               STARK OVERLAY — Pure Windows Control||
# +--------------------------------------------------------------------------------------------------------------------+

import drag_drop as dd

if __name__ == '__main__':
    print("[STARK] Booting up Stark Interaction Engine...")
    print("[STARK] WARNING: Camera feed will be completely hidden. Press 'Q' while focused on the invisible overlay to quit, or close the terminal.")
    
    # Optional performance hint
    # os.environ["OMP_NUM_THREADS"] = "1"
    
    try:
        system = dd.StarkOverlay()
        system.Run()
    except KeyboardInterrupt:
        print("\n[STARK] Shutting down from KeyboardInterrupt")
    finally:
        print("[STARK] System offline.")
