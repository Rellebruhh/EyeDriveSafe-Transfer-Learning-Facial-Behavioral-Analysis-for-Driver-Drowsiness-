from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_imageclassification import VideoImageClassification
from arduino.app_bricks.arduino_cloud import ArduinoCloud
from datetime import datetime, UTC
import json
import time
import urllib.request
from collections import deque

ui = WebUI()
detection_stream = VideoImageClassification(confidence=0.5, debounce_sec=0.5)

# ==================== ARDUINO IOT CLOUD ====================
iot_cloud = ArduinoCloud()


CLOUD_PUSH_INTERVAL = 3.0
last_cloud_push = 0


iot_cloud.register("alertState", value=0)
iot_cloud.register("drowsyEpisodes", value=0)
iot_cloud.register("drowsyFrameRatio", value=0.0)
iot_cloud.register("alertCount", value=0)
iot_cloud.register("fatigueReport", value="")

def push_to_cloud(state, drowsy_episodes, dfr, alert_count):
    """Push current metrics to Arduino IoT Cloud."""
    global last_cloud_push
    now = time.time()
    if now - last_cloud_push < CLOUD_PUSH_INTERVAL:
        return
    last_cloud_push = now

    try:
        iot_cloud.register("alertState", value=state)
        iot_cloud.register("drowsyEpisodes", value=drowsy_episodes)
        iot_cloud.register("drowsyFrameRatio", value=round(dfr, 1))
        iot_cloud.register("alertCount", value=alert_count)
    except Exception as e:
        print(f"[CLOUD] Push error: {e}")

def push_report_to_cloud(report_text):
    """Push the AI fatigue report to Arduino IoT Cloud Messenger widget.
    The Messenger widget renders each push as a timestamped chat bubble.
    Arduino Cloud String properties accept ~256 chars per update, so the
    report is split into sentence-boundary chunks and pushed sequentially.
    Each chunk appears as a separate message in the Messenger history."""
    CHUNK_LIMIT = 250  # Leave margin below 256
    try:
        chunks = _split_report_into_chunks(report_text, CHUNK_LIMIT)
        for i, chunk in enumerate(chunks):
            iot_cloud.register("fatigueReport", value=chunk)
       
            try:
                iot_cloud.loop()
            except Exception:
                pass
            if i < len(chunks) - 1:
                time.sleep(0.5)
        print(f"[CLOUD] Fatigue report pushed ({len(chunks)} message(s), {len(report_text)} chars total)")
    except Exception as e:
        print(f"[CLOUD] Report push error: {e}")

def _split_report_into_chunks(text, limit):
    """Split text into chunks at sentence boundaries, each under limit chars.
    Falls back to word boundaries if a single sentence exceeds the limit."""
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break


        cut = -1
        for sep in ['. ', '! ', '? ']:
            idx = remaining.rfind(sep, 0, limit)
            if idx > cut:
                cut = idx + len(sep) - 1  

     
        if cut <= 0:
            cut = remaining.rfind(' ', 0, limit)

       
        if cut <= 0:
            cut = limit

        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()

    return chunks

# ========= LLM ChatBot =========

# GITHUB_TOKEN = "Enter Your GitHub Token Here"     
LLM_ENDPOINT = "https://models.github.ai/inference/chat/completions"
LLM_MODEL = "openai/gpt-4.1-mini" # Note: You may use other models of your preference

LLM_SYSTEM_PROMPT = (
    "You are EYEDRIVESAFE's onboard fatigue analyst. "
    "You receive driving session data including timestamps, alert states, "
    "Drowsy Frame Ratio (DFR), and drowsy episode counts from a drowsiness "
    "detection system installed in a vehicle in the Philippines. "
    "DFR is the percentage of frames classified as drowsy over a rolling "
    "window. Drowsy episodes are distinct continuous sequences where the "
    "classifier detected drowsiness. "
    "Generate a unified fatigue report with the following structure: "
    "Start with a one-sentence session overview (duration, overall fatigue level). "
    "Then describe key fatigue events and when they occurred. "
    "Then describe any patterns such as fatigue worsening over time or recurring intervals. "
    "End with actionable recommendations for the driver. "
    "Keep the report concise, under 200 words. "
    "Use plain language a non-technical driver or family member can understand. "
    "Do not use markdown formatting, bullet points, or headers. "
    "Write in short paragraphs as a single continuous report."
    "Avoid hallucinations and always be factual."
)

analysis_running = False

def call_llm(prompt):
    """Call GitHub Models API. Returns full response text."""
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }).encode("utf-8")

    req = urllib.request.Request(
        LLM_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GITHUB_TOKEN}"
        }
    )

    resp = urllib.request.urlopen(req, timeout=45)
    data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]

# ==================== STATE CONSTANTS ====================
STATE_AWAKE = 0
STATE_WARNING = 1
STATE_ALERT = 2

# State tracking
current_state = STATE_AWAKE
drowsy_start_time = None
last_state_change = 0


drowsy_threshold = 0.7

# Configuration
WARNING_DELAY = 1.5           # Seconds of drowsiness before WARNING
ALERT_DELAY = 3.0             # Seconds of drowsiness before ALERT
AWAKE_RESET_DELAY = 0.5       # Seconds of awake before resetting state
STATE_COOLDOWN = 1.0          # Minimum time between state changes

# Awake tracking
awake_start_time = None

# ==================== DROWSY EPISODE TRACKING ====================
# A drowsy episode is a distinct continuous sequence where the classifier
# output "drowsy" above threshold. Each awake-to-drowsy transition marks
# the start of a new episode. This is a session-total count.
drowsy_episode_count = 0
last_drowsy_onset = None
was_drowsy = False

# ==================== DFR TRACKING ====================
# Drowsy Frame Ratio (DFR): the proportion of frames classified as drowsy
# over a rolling time window, expressed as a percentage.
# Analogous in concept to PERCLOS but derived from binary classification
# output rather than geometric eyelid measurement.
DFR_WINDOW = 60.0
frame_history = deque()

# ==================== SESSION LOG ====================
SESSION_LOG_INTERVAL = 5.0
last_log_time = 0
session_log = []
session_events = []
session_start_time = time.time()
total_alert_count = 0

def log_session_snapshot(state, drowsy_episodes, dfr, confidence):
    """Record a periodic snapshot of session metrics."""
    global last_log_time
    now = time.time()
    if now - last_log_time < SESSION_LOG_INTERVAL:
        return
    last_log_time = now

    elapsed = now - session_start_time
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)

    session_log.append({
        "time": f"{mins:02d}:{secs:02d}",
        "state": ["AWAKE", "WARNING", "ALERT"][state],
        "drowsy_episodes": drowsy_episodes,
        "dfr": round(dfr, 1),
        "confidence": round(confidence, 2)
    })

def log_session_event(old_state, new_state):
    """Record a state transition event."""
    global total_alert_count
    elapsed = time.time() - session_start_time
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)

    session_events.append({
        "time": f"{mins:02d}:{secs:02d}",
        "from": ["AWAKE", "WARNING", "ALERT"][old_state],
        "to": ["AWAKE", "WARNING", "ALERT"][new_state]
    })

    if new_state == STATE_ALERT:
        total_alert_count += 1

def build_analysis_prompt():
    """Construct the prompt from session data for the LLM."""
    elapsed = time.time() - session_start_time
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)

    prompt = f"Session duration: {mins} minutes {secs} seconds.\n\n"

    if session_events:
        prompt += "State transitions:\n"
        for evt in session_events[-20:]:
            prompt += f"  {evt['time']} - {evt['from']} -> {evt['to']}\n"
        prompt += "\n"

    if session_log:
        prompt += "Metric snapshots (sampled every 5 seconds):\n"
        prompt += "Time | State | Drowsy Episodes | DFR | Confidence\n"
        for entry in session_log[-30:]:
            prompt += (
                f"  {entry['time']} | {entry['state']} | "
                f"{entry['drowsy_episodes']} | {entry['dfr']}% | "
                f"{entry['confidence']}\n"
            )

    prompt += f"\nTotal alerts triggered: {total_alert_count}\n"
    prompt += "\nGenerate the fatigue report."

    return prompt

def run_analysis(sid=None, msg=None):
    """Triggered by the web UI. Runs LLM analysis and sends result back."""
    global analysis_running

    if analysis_running:
        ui.send_message("analysis_status", message=json.dumps({
            "status": "busy",
            "text": "Analysis is already running."
        }))
        return

    if not session_log and not session_events:
        ui.send_message("analysis_status", message=json.dumps({
            "status": "empty",
            "text": "No session data to analyze yet. Drive for a few minutes first."
        }))
        return

    analysis_running = True

    try:
        ui.send_message("analysis_status", message=json.dumps({
            "status": "started",
            "text": ""
        }))

        prompt = build_analysis_prompt()
        print(f"[LLM] Sending analysis prompt ({len(prompt)} chars)")

        result = call_llm(prompt)
        ui.send_message("analysis_status", message=json.dumps({
            "status": "done",
            "text": result
        }))
        print(f"[LLM] Analysis complete ({len(result)} chars)")

        # Push the report to Arduino IoT Cloud
        push_report_to_cloud(result)

    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        print(f"[LLM] {error_msg}")
        ui.send_message("analysis_status", message=json.dumps({
            "status": "error",
            "text": error_msg
        }))

    finally:
        analysis_running = False

# ==================== METRIC FUNCTIONS ====================
def compute_drowsy_episodes():
    """Return the total number of drowsy episodes this session."""
    return drowsy_episode_count

def compute_dfr():
    """Compute Drowsy Frame Ratio over the rolling window.
    DFR = (frames classified drowsy / total frames) * 100
    over the last DFR_WINDOW seconds."""
    now = time.time()
    while frame_history and (now - frame_history[0][0]) > DFR_WINDOW:
        frame_history.popleft()
    if len(frame_history) < 2:
        return 0.0
    drowsy_count = sum(1 for _, is_d in frame_history if is_d)
    return (drowsy_count / len(frame_history)) * 100.0

# ==================== BRIDGE ====================
def linux_started():
    return True

def from_mcu(data: int):
    print(f"[MCU] Received: {data}")

Bridge.provide("linux_started", linux_started)
Bridge.provide("from_mcu", from_mcu)

def set_alert_state(state):
    """Send state to Arduino MCU via Bridge (triggers buzzer)."""
    global last_state_change
    now = time.time()
    if now - last_state_change < STATE_COOLDOWN:
        return
    try:
        Bridge.notify("set_alert_state", state)
        last_state_change = now
        print(f"[BRIDGE] Sent: {['AWAKE','WARNING','ALERT'][state]}")
    except Exception as e:
        print(f"[ERROR] Bridge failed: {e}")

def handle_threshold_override(sid, threshold):
    global drowsy_threshold
    try:
        val = float(threshold)
        val = max(0.0, min(1.0, val))
        drowsy_threshold = val
        detection_stream.override_threshold(val)
        print(f"[THRESHOLD] Updated to {val:.2f}")
    except (ValueError, TypeError) as e:
        print(f"[THRESHOLD] Invalid value: {threshold} ({e})")

# ==================== UI EVENT HANDLERS ====================
ui.on_message("override_th", handle_threshold_override)
ui.on_message("request_analysis", run_analysis)

# ==================== MAIN DETECTION CALLBACK ====================
def send_detections_to_ui(classifications: dict):
    global current_state, drowsy_start_time, awake_start_time
    global was_drowsy, last_drowsy_onset, drowsy_episode_count

    if len(classifications) == 0:
        return

    awake_conf = classifications.get("awake", 0.0)
    drowsy_conf = classifications.get("drowsy", 0.0)

    now = time.time()
    old_state = current_state

    # FIX: Uses mutable drowsy_threshold instead of hardcoded DROWSY_THRESHOLD
    is_drowsy = drowsy_conf > awake_conf and drowsy_conf >= drowsy_threshold

    # DFR frame recording
    frame_history.append((now, is_drowsy))

    # Drowsy episode detection
    # Each awake-to-drowsy transition marks the start of a new episode
    if is_drowsy and not was_drowsy:
        drowsy_episode_count += 1
        last_drowsy_onset = now
    elif not is_drowsy and was_drowsy:
        last_drowsy_onset = None

    was_drowsy = is_drowsy

    # State machine
    if is_drowsy:
        awake_start_time = None
        if drowsy_start_time is None:
            drowsy_start_time = now
            print(f"[DETECT] Drowsy detected: {drowsy_conf:.1%}")
        else:
            elapsed = now - drowsy_start_time
            if elapsed >= ALERT_DELAY and current_state != STATE_ALERT:
                current_state = STATE_ALERT
                print(f"[ALERT] Drowsy for {elapsed:.1f}s - WAKE UP!")
            elif elapsed >= WARNING_DELAY and current_state == STATE_AWAKE:
                current_state = STATE_WARNING
                print(f"[WARNING] Drowsy for {elapsed:.1f}s")
    else:
        if awake_start_time is None:
            awake_start_time = now
        else:
            awake_elapsed = now - awake_start_time
            if awake_elapsed >= AWAKE_RESET_DELAY:
                if current_state != STATE_AWAKE:
                    print(f"[AWAKE] Driver alert - resetting")
                drowsy_start_time = None
                current_state = STATE_AWAKE

    # Bridge notification on state change
    if current_state != old_state:
        set_alert_state(current_state)
        log_session_event(old_state, current_state)

    # Compute metrics
    drowsy_episodes = compute_drowsy_episodes()
    dfr = compute_dfr()

    # Determine primary classification
    if drowsy_conf >= awake_conf:
        primary_class = "drowsy"
        primary_conf = drowsy_conf
    else:
        primary_class = "awake"
        primary_conf = awake_conf

    # Record session snapshot
    log_session_snapshot(current_state, drowsy_episodes, dfr, primary_conf)

    # Push to Arduino IoT Cloud
    push_to_cloud(current_state, drowsy_episodes, dfr, total_alert_count)

    # Emit single entry to local dashboard
    entry = {
        "content": primary_class,
        "confidence": primary_conf,
        "state": current_state,
        "state_name": ["AWAKE", "WARNING", "ALERT"][current_state],
        "drowsy_episodes": drowsy_episodes,
        "dfr": round(dfr, 1),
        "timestamp": datetime.now(UTC).isoformat()
    }

    ui.send_message("classifications", message=json.dumps([entry]))

detection_stream.on_detect_all(send_detections_to_ui)

# ==================== STARTUP ====================
print("=" * 50)
print("EYEDRIVESAFE - Driver Drowsiness Detection")
print("With Arduino IoT Cloud + AI Fatigue Analysis")
print("=" * 50)
print(f"Drowsy Threshold: {drowsy_threshold:.0%}")
print(f"Warning Delay: {WARNING_DELAY}s")
print(f"Alert Delay: {ALERT_DELAY}s")
print(f"Cloud Push Interval: {CLOUD_PUSH_INTERVAL}s")
print(f"LLM Model: {LLM_MODEL}")
print("=" * 50)

def loop():
    # Run Arduino Cloud client loop
    try:
        iot_cloud.loop()
    except Exception:
        pass

    time.sleep(0.1)

App.run(user_loop=loop)
