// EYEDRIVESAFE Monitoring Dashboard


const socket = io(`http://${window.location.host}`);

// ==================== DOM REFERENCES ====================
const recentDetectionsElement = document.getElementById('recentClassifications');
const statePanel = document.getElementById('statePanel');
const stateLabel = document.getElementById('stateLabel');
const stateConfidence = document.getElementById('stateConfidence');
const stateBar = document.getElementById('stateBar');
const drowsyEpisodesEl = document.getElementById('drowsyEpisodes');
const drowsyEpisodesStatusEl = document.getElementById('drowsyEpisodesStatus');
const dfrValueEl = document.getElementById('dfrValue');
const dfrStatusEl = document.getElementById('dfrStatus');
const warningCountEl = document.getElementById('warningCount');
const alertCountEl = document.getElementById('alertCount');
const connectionDot = document.getElementById('connectionDot');
const sessionClockEl = document.getElementById('sessionClock');
const fpsCounterEl = document.getElementById('fpsCounter');
const alertOverlay = document.getElementById('alertOverlay');
const errorContainer = document.getElementById('error-container');

// State icons
const iconAwake = document.getElementById('iconAwake');
const iconWarning = document.getElementById('iconWarning');
const iconAlert = document.getElementById('iconAlert');

// Fatigue report panel
const btnRunAnalysis = document.getElementById('btnRunAnalysis');
const analysisPlaceholder = document.getElementById('analysisPlaceholder');
const analysisContent = document.getElementById('analysisContent');
const analysisLoading = document.getElementById('analysisLoading');

// ==================== STATE ====================
let detectionLog = [];
const MAX_LOG_ENTRIES = 50;
let warningCount = 0;
let alertCount = 0;
let previousState = 0;
let sessionStartTime = Date.now();
let frameCount = 0;
let lastFpsUpdate = Date.now();
let currentFps = 0;

// ==================== CONNECTION ====================
socket.on('connect', () => {
    if (connectionDot) connectionDot.classList.add('connected');
    console.log('[WS] Connected');
});

socket.on('disconnect', () => {
    if (connectionDot) connectionDot.classList.remove('connected');
    console.log('[WS] Disconnected');
});

// ==================== VIDEO DETECTION ====================
socket.on('video-start', () => {
    const iframe = document.getElementById('dynamicIframe');
    const placeholder = document.getElementById('videoPlaceholder');
    if (iframe) iframe.style.display = 'block';
    if (placeholder) placeholder.style.display = 'none';
});

// ==================== MAIN DETECTION HANDLER ====================
socket.on('classifications', (data) => {
    let entries;
    try {
        entries = typeof data === 'string' ? JSON.parse(data) : data;
    } catch (e) {
        console.error('[PARSE] Classification parse error:', e);
        return;
    }

    if (!Array.isArray(entries) || entries.length === 0) return;

    // Use the first (and only) entry - single-entry emission from Python
    const entry = entries[0];

    // FPS counter
    frameCount++;
    const now = Date.now();
    if (now - lastFpsUpdate >= 1000) {
        currentFps = frameCount;
        frameCount = 0;
        lastFpsUpdate = now;
        if (fpsCounterEl) fpsCounterEl.textContent = `${currentFps} fps`;
    }

    // Extract fields
    const label = entry.content || 'unknown';
    const confidence = entry.confidence || 0;
    const stateName = entry.state_name || inferState(label, confidence);
    const stateNum = entry.state !== undefined ? entry.state : inferStateNum(label, confidence);
    const drowsyEpisodes = entry.drowsy_episodes !== undefined ? entry.drowsy_episodes : null;
    const dfr = entry.dfr !== undefined ? entry.dfr : null;

    // Update state display
    updateStateDisplay(stateName, stateNum, confidence);

    // Update metrics
    if (drowsyEpisodes !== null) updateDrowsyEpisodes(drowsyEpisodes);
    if (dfr !== null) updateDfr(dfr);

    // Count events (only on state transitions, not every frame)
    if (stateNum !== previousState) {
        if (stateNum === 1) warningCount++;
        if (stateNum === 2) alertCount++;
        previousState = stateNum;
    }
    if (warningCountEl) warningCountEl.textContent = warningCount;
    if (alertCountEl) alertCountEl.textContent = alertCount;

    // Alert overlay
    if (alertOverlay) {
        if (stateNum === 2) {
            alertOverlay.classList.add('active');
        } else {
            alertOverlay.classList.remove('active');
        }
    }

    // Detection log
    addLogEntry(label, confidence, stateName, entry.timestamp);
});

// ==================== STATE DISPLAY ====================
function updateStateDisplay(stateName, stateNum, confidence) {
    if (!statePanel) return;

    // Remove previous state classes
    statePanel.classList.remove('state-awake', 'state-warning', 'state-alert');

    // Icons
    if (iconAwake) iconAwake.style.display = 'none';
    if (iconWarning) iconWarning.style.display = 'none';
    if (iconAlert) iconAlert.style.display = 'none';

    switch (stateNum) {
        case 0:
            statePanel.classList.add('state-awake');
            if (iconAwake) iconAwake.style.display = 'block';
            break;
        case 1:
            statePanel.classList.add('state-warning');
            if (iconWarning) iconWarning.style.display = 'block';
            break;
        case 2:
            statePanel.classList.add('state-alert');
            if (iconAlert) iconAlert.style.display = 'block';
            break;
    }

    if (stateLabel) stateLabel.textContent = stateName;
    if (stateConfidence) stateConfidence.textContent = `${(confidence * 100).toFixed(1)}%`;
    if (stateBar) stateBar.style.width = `${confidence * 100}%`;
}

function updateDrowsyEpisodes(count) {
    if (drowsyEpisodesEl) drowsyEpisodesEl.textContent = count;
    if (drowsyEpisodesStatusEl) {
        // Status thresholds for drowsy episode count (session total)
        // 0 episodes: driver has not shown drowsy behavior
        // 1-3 episodes: moderate, some drowsy detections occurred
        // 4+ episodes: frequent, driver is repeatedly showing drowsy behavior
        if (count === 0) {
            drowsyEpisodesStatusEl.textContent = 'None';
            drowsyEpisodesStatusEl.className = 'metric-status status-normal';
        } else if (count <= 3) {
            drowsyEpisodesStatusEl.textContent = 'Moderate';
            drowsyEpisodesStatusEl.className = 'metric-status status-warning';
        } else {
            drowsyEpisodesStatusEl.textContent = 'Frequent';
            drowsyEpisodesStatusEl.className = 'metric-status status-alert';
        }
    }
}

function updateDfr(value) {
    if (dfrValueEl) dfrValueEl.textContent = value.toFixed(1) + '%';
    if (dfrStatusEl) {
        // FIX: Changed status-danger to status-alert, status-ok to status-normal
        if (value > 15) {
            dfrStatusEl.textContent = 'Fatigued';
            dfrStatusEl.className = 'metric-status status-alert';
        } else if (value > 8) {
            dfrStatusEl.textContent = 'Caution';
            dfrStatusEl.className = 'metric-status status-warning';
        } else {
            dfrStatusEl.textContent = 'Normal';
            dfrStatusEl.className = 'metric-status status-normal';
        }
    }
}

// ==================== DETECTION LOG ====================
function addLogEntry(label, confidence, stateName, timestamp) {
    if (!recentDetectionsElement) return;

    const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
    const pct = (confidence * 100).toFixed(1);

    detectionLog.unshift({ label, pct, stateName, time });
    if (detectionLog.length > MAX_LOG_ENTRIES) detectionLog.pop();

    // Render last 10 visible
    const visible = detectionLog.slice(0, 10);
    recentDetectionsElement.innerHTML = visible.map(d =>
        `<div class="log-entry log-${d.label}">
            <span class="log-label">${d.label}</span>
            <span class="log-conf">${d.pct}%</span>
            <span class="log-state">${d.stateName}</span>
            <span class="log-time">${d.time}</span>
        </div>`
    ).join('');
}

// ==================== FALLBACK STATE INFERENCE ====================
function inferState(label, confidence) {
    if (label === 'drowsy' && confidence >= 0.7) return 'ALERT';
    if (label === 'drowsy') return 'WARNING';
    return 'AWAKE';
}

function inferStateNum(label, confidence) {
    if (label === 'drowsy' && confidence >= 0.7) return 2;
    if (label === 'drowsy') return 1;
    return 0;
}

// ==================== CONFIDENCE SLIDER (FIXED) ====================
// FIX: The previous implementation referenced a nonexistent 'sliderValue'
// element, never updated the progress bar, never synced the text input,
// and had no reset button handler. All four issues are resolved below.
const slider = document.getElementById('confidenceSlider');
const confidenceInput = document.getElementById('confidenceInput');
const sliderProgress = document.getElementById('sliderProgress');
const confidenceResetBtn = document.getElementById('confidenceResetButton');

function syncConfidence() {
    if (!slider) return;
    const value = parseFloat(slider.value);

    // Update the progress bar fill
    if (sliderProgress) {
        const pct = ((value - slider.min) / (slider.max - slider.min)) * 100;
        sliderProgress.style.width = pct + '%';
    }

    // Update the text input (only if the input is not currently focused,
    // to avoid fighting the user's typing)
    if (confidenceInput && document.activeElement !== confidenceInput) {
        confidenceInput.value = value.toFixed(2);
    }

    // Emit to server -- this now updates BOTH the brick filter AND
    // the state machine threshold in main.py
    socket.emit('override_th', value);
}

if (slider) {
    // Slider drag
    slider.addEventListener('input', syncConfidence);

    // Text input manual entry
    if (confidenceInput) {
        confidenceInput.addEventListener('change', () => {
            let val = parseFloat(confidenceInput.value);
            if (isNaN(val)) val = 0.5;
            val = Math.max(0, Math.min(1, val));
            confidenceInput.value = val.toFixed(2);
            slider.value = val;
            syncConfidence();
        });
    }

    // Reset button
    if (confidenceResetBtn) {
        confidenceResetBtn.addEventListener('click', () => {
            slider.value = 0.5;
            if (confidenceInput) confidenceInput.value = '0.50';
            syncConfidence();
        });
    }

    // Initialize progress bar on page load
    syncConfidence();
}

// ==================== FATIGUE REPORT ====================
// This section handles the AI-generated fatigue report.
// The report is generated server-side using the configured LLM.
// It appears as a single "Fatigue Report" panel -- no separate
// "analysis" vs "report" sections, no LLM model branding.

if (btnRunAnalysis) {
    let analysisTimeout = null;
    btnRunAnalysis.addEventListener('click', () => {
        console.log('[UI] Generate Report clicked');
        // Instant visual feedback -- don't wait for server
        if (analysisPlaceholder) analysisPlaceholder.style.display = 'none';
        if (analysisContent) analysisContent.style.display = 'none';
        if (analysisLoading) analysisLoading.style.display = 'flex';
        btnRunAnalysis.disabled = true;
        // Emit to server
        socket.emit('request_analysis', {});
        // Safety timeout: re-enable button if server never responds
        if (analysisTimeout) clearTimeout(analysisTimeout);
        analysisTimeout = setTimeout(() => {
            if (btnRunAnalysis.disabled) {
                btnRunAnalysis.disabled = false;
                if (analysisLoading) analysisLoading.style.display = 'none';
                if (analysisContent) {
                    analysisContent.style.display = 'block';
                    analysisContent.innerHTML =
                        '<div class="report-error">No response from server. Check the App Lab console for errors.</div>';
                }
                console.warn('[UI] Analysis timed out -- no server response after 60s');
            }
        }, 60000);
    });

    // Clear timeout when any analysis_status response arrives
    socket.on('analysis_status', () => {
        if (analysisTimeout) { clearTimeout(analysisTimeout); analysisTimeout = null; }
    });
}

socket.on('analysis_status', (data) => {
    let msg;
    try {
        msg = typeof data === 'string' ? JSON.parse(data) : data;
    } catch (e) {
        return;
    }

    switch (msg.status) {
        case 'started':
            // Show loading, hide placeholder and content
            if (analysisPlaceholder) analysisPlaceholder.style.display = 'none';
            if (analysisContent) analysisContent.style.display = 'none';
            if (analysisLoading) analysisLoading.style.display = 'flex';
            if (btnRunAnalysis) btnRunAnalysis.disabled = true;
            break;

        case 'done':
            // Show the unified fatigue report
            if (analysisLoading) analysisLoading.style.display = 'none';
            if (analysisPlaceholder) analysisPlaceholder.style.display = 'none';
            if (analysisContent) {
                analysisContent.style.display = 'block';
                // Single unified report -- no model attribution, no separate headers
                analysisContent.innerHTML =
                    '<div class="report-text">' +
                    msg.text.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>') +
                    '</div>';
            }
            if (btnRunAnalysis) btnRunAnalysis.disabled = false;
            break;

        case 'error':
            if (analysisLoading) analysisLoading.style.display = 'none';
            if (analysisPlaceholder) analysisPlaceholder.style.display = 'none';
            if (analysisContent) {
                analysisContent.style.display = 'block';
                analysisContent.innerHTML =
                    '<div class="report-error">' + msg.text + '</div>';
            }
            if (btnRunAnalysis) btnRunAnalysis.disabled = false;
            break;

        case 'busy':
            // Show feedback that analysis is already in progress
            if (analysisPlaceholder) analysisPlaceholder.style.display = 'none';
            if (analysisLoading) analysisLoading.style.display = 'flex';
            break;

        case 'empty':
            if (analysisPlaceholder) analysisPlaceholder.style.display = 'none';
            if (analysisContent) {
                analysisContent.style.display = 'block';
                analysisContent.innerHTML =
                    '<div class="report-empty">' + msg.text + '</div>';
            }
            break;
    }
});

// Handle token-by-token streaming (if the LLM supports it)
socket.on('analysis_token', (data) => {
    let msg;
    try {
        msg = typeof data === 'string' ? JSON.parse(data) : data;
    } catch (e) {
        return;
    }

    if (analysisLoading) analysisLoading.style.display = 'none';
    if (analysisContent) {
        analysisContent.style.display = 'block';
        // Append token to existing content
        if (!analysisContent.querySelector('.report-text')) {
            analysisContent.innerHTML = '<div class="report-text"></div>';
        }
        const reportDiv = analysisContent.querySelector('.report-text');
        reportDiv.textContent += msg.token;
    }
});

// ==================== SESSION CLOCK ====================
setInterval(() => {
    const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
    const hrs = String(Math.floor(elapsed / 3600)).padStart(2, '0');
    const mins = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
    const secs = String(elapsed % 60).padStart(2, '0');
    if (sessionClockEl) sessionClockEl.textContent = `${hrs}:${mins}:${secs}`;
}, 1000);

// ==================== ERROR DISPLAY ====================
socket.on('error_message', (data) => {
    if (errorContainer) {
        errorContainer.textContent = typeof data === 'string' ? data : JSON.stringify(data);
        errorContainer.style.display = 'block';
        setTimeout(() => { errorContainer.style.display = 'none'; }, 5000);
    }
});
