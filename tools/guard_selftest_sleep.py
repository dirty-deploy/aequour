"""CPU-only 30-second sleep used to self-test run_guarded.py: prints one tick per second."""
import time

t0 = time.time()
for i in range(30):
    print(f"tick {i} at {time.time() - t0:.1f}s", flush=True)
    time.sleep(1)
print(f"done, wall {time.time() - t0:.1f}s", flush=True)
