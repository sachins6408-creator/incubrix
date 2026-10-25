// IncuBrix Frontend Application Controller
// Strictly connects UI controls to FastAPI backend routes

let currentAssetId = null;
let currentSessionId = null;
let currentTimeline = null;
let currentRenderJobId = null;
let renderPollInterval = null;

// DOM Elements
const videoFileInput = document.getElementById("videoFileInput");
const videoPlayer = document.getElementById("videoPlayer");
const emptyPlayerState = document.getElementById("emptyPlayerState");
const captionOverlay = document.getElementById("captionOverlay");
const timelineTrack = document.getElementById("timelineTrack");
const timelineMeta = document.getElementById("timelineMeta");
const renderBtn = document.getElementById("renderBtn");
const undoBtn = document.getElementById("undoBtn");
const redoBtn = document.getElementById("redoBtn");
const restoreIntroBtn = document.getElementById("restoreIntroBtn");
const sendBtn = document.getElementById("sendBtn");
const instructionInput = document.getElementById("instructionInput");
const instructionForm = document.getElementById("instructionForm");

// Metadata elements
const metaAssetId = document.getElementById("metaAssetId");
const metaDuration = document.getElementById("metaDuration");
const metaResolution = document.getElementById("metaResolution");
const metaCodec = document.getElementById("metaCodec");
const metaSha = document.getElementById("metaSha");
const metaTimelineHash = document.getElementById("metaTimelineHash");

// Outcome and clarification elements
const outcomeBox = document.getElementById("outcomeBox");
const outcomeTag = document.getElementById("outcomeTag");
const outcomeTime = document.getElementById("outcomeTime");
const outcomeMessage = document.getElementById("outcomeMessage");
const clarificationContainer = document.getElementById("clarificationContainer");
const clarificationPrompt = document.getElementById("clarificationPrompt");
const clarificationChoices = document.getElementById("clarificationChoices");
const clarificationInput = document.getElementById("clarificationInput");
const clarificationSubmitBtn = document.getElementById("clarificationSubmitBtn");

// Render panel elements
const renderPanel = document.getElementById("renderPanel");
const renderStatus = document.getElementById("renderStatus");
const renderProgressBar = document.getElementById("renderProgressBar");
const renderDetails = document.getElementById("renderDetails");
const renderActions = document.getElementById("renderActions");
const downloadRenderBtn = document.getElementById("downloadRenderBtn");
const previewRenderBtn = document.getElementById("previewRenderBtn");

// Check Health & Readiness
async function checkReadiness() {
  try {
    const res = await fetch("/ready");
    const data = await res.json();
    const dot = document.querySelector(".status-dot");
    const text = document.getElementById("backendStatus");
    if (data.status === "READY") {
      dot.className = "status-dot active";
      text.textContent = "Engine Ready";
    } else {
      dot.className = "status-dot";
      text.textContent = "Dependencies Missing";
    }
  } catch (e) {
    console.error("Health check error:", e);
  }
}

// 1. Real Video Upload
videoFileInput.addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file, file.name || "uploaded_video");

  const uploadLabel = document.getElementById("uploadLabel");
  uploadLabel.innerHTML = "<span>⏳ Uploading...</span>";

  try {
    const res = await fetch("/api/v1/media/upload", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Upload failed: ${err.error?.message || res.statusText}`);
      return;
    }

    const assetData = await res.json();
    currentAssetId = assetData.asset_id;

    // Display asset metadata safely
    metaAssetId.textContent = currentAssetId ? currentAssetId.slice(0, 12) + "..." : "—";
    const durVal = typeof assetData.duration === "number" ? assetData.duration.toFixed(2) : (assetData.duration || "—");
    metaDuration.textContent = `${durVal}s`;
    metaResolution.textContent = (assetData.width && assetData.height) ? `${assetData.width}x${assetData.height}` : "Unknown";
    const fpsVal = typeof assetData.fps === "number" ? `${assetData.fps} fps` : (assetData.fps || "");
    const codecVal = assetData.video_codec || "unknown";
    metaCodec.textContent = fpsVal ? `${fpsVal} / ${codecVal}` : codecVal;
    metaSha.textContent = assetData.sha256 || "—";

    // Initialize editing session strictly bound to assetData.asset_id
    await createSession(currentAssetId);

    // Stream uploaded original
    videoPlayer.src = assetData.stream_url;
    emptyPlayerState.style.display = "none";
    videoPlayer.style.display = "block";
    videoPlayer.load();

    renderBtn.disabled = false;
    sendBtn.disabled = false;
    restoreIntroBtn.disabled = false;
  } catch (err) {
    alert(`Upload error: ${err.message}`);
  } finally {
    uploadLabel.innerHTML = "<span>📁 Upload Video</span>";
    videoFileInput.value = ""; // Reset file input so re-selecting same file works
  }
});

// 2. Editing Session Creation
async function createSession(assetId) {
  const res = await fetch("/api/v1/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_id: assetId }),
  });
  const data = await res.json();
  currentSessionId = data.session_id;
  currentTimeline = data.timeline;
  metaTimelineHash.textContent = data.timeline_hash;
  renderTimeline(currentTimeline);
}

// 3. Render Timeline Segments Visual Representation
function renderTimeline(timeline) {
  if (!timeline || !timeline.segments || timeline.segments.length === 0) {
    timelineTrack.innerHTML = '<div class="empty-track-msg">Timeline is empty.</div>';
    timelineMeta.textContent = "0.00s | 0 segments";
    return;
  }

  timelineTrack.innerHTML = "";
  const totalDur = typeof timeline.total_duration === "number" ? timeline.total_duration.toFixed(2) : (timeline.total_duration || "0.00");
  timelineMeta.textContent = `${totalDur}s | ${timeline.segments.length} segment(s)`;

  timeline.segments.forEach((seg, idx) => {
    const block = document.createElement("div");
    block.className = "timeline-segment-block";

    // Calculate segment duration safely
    let segDur = 0;
    if (typeof seg.duration === "number") {
      segDur = seg.duration;
    } else if (typeof seg.source_start === "number" && typeof seg.source_end === "number") {
      const speed = (typeof seg.speed === "number" && seg.speed > 0) ? seg.speed : 1.0;
      segDur = (seg.source_end - seg.source_start) / speed;
    }

    const totalDurNum = typeof timeline.total_duration === "number" ? timeline.total_duration : 1;
    const widthPct = Math.max(10, (segDur / (totalDurNum || 1)) * 100);
    block.style.flex = `${widthPct} 0 auto`;

    const label = seg.label || `Seg ${idx + 1} (${seg.source_start}s - ${seg.source_end}s)`;
    const speedLabel = (seg.speed && seg.speed !== 1.0) ? ` [${seg.speed}x]` : "";
    const capCount = seg.captions?.length ? ` 💬 ${seg.captions.length}` : "";

    block.innerHTML = `
      <div class="segment-label">${label}${speedLabel}</div>
      <div class="segment-duration">${segDur.toFixed(2)}s${capCount}</div>
    `;

    block.addEventListener("click", () => {
      // Seek video to corresponding segment in preview
      videoPlayer.currentTime = seg.source_start;
      videoPlayer.play();
    });

    timelineTrack.appendChild(block);
  });

  undoBtn.disabled = false;
  redoBtn.disabled = false;
}

// 4. Instructions Engine (Unified Pipeline for typed inputs and sample pills)
instructionForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = instructionInput.value.trim();
  if (!text) return;
  await dispatchInstruction(text);
  instructionInput.value = "";
});

// Sample prompt buttons populate and trigger the same submission pipeline
document.querySelectorAll(".pill-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const prompt = btn.getAttribute("data-prompt");
    instructionInput.value = prompt;
    dispatchInstruction(prompt);
  });
});

async function dispatchInstruction(instructionText) {
  if (!currentSessionId) {
    alert("Please upload a video to start a session before applying instructions.");
    return;
  }

  sendBtn.disabled = true;
  try {
    const res = await fetch(`/api/v1/sessions/${currentSessionId}/instructions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction: instructionText }),
    });

    const result = await res.json();
    displayOutcome(result);

    if (result.status === "APPLIED" && result.timeline) {
      currentTimeline = result.timeline;
      metaTimelineHash.textContent = result.timeline_hash || "—";
      renderTimeline(currentTimeline);
    }
  } catch (err) {
    displayOutcome({
      status: "REJECTED",
      message: `Execution failed: ${err.message}`,
    });
  } finally {
    sendBtn.disabled = false;
  }
}

// 5. Outcome & Clarification Display
function displayOutcome(res) {
  outcomeBox.style.display = "flex";
  outcomeTag.className = `outcome-tag ${res.status}`;
  outcomeTag.textContent = res.status;
  outcomeTime.textContent = new Date().toLocaleTimeString();
  outcomeMessage.textContent = res.message;

  if (res.status === "NEEDS_CLARIFICATION" && res.clarification) {
    clarificationContainer.style.display = "block";
    clarificationPrompt.textContent = res.clarification.prompt;
    clarificationChoices.innerHTML = "";

    res.clarification.options.forEach((opt) => {
      const btn = document.createElement("button");
      btn.className = "choice-btn";
      btn.textContent = `${opt.index}. ${opt.label} [${opt.source_range[0]}s - ${opt.source_range[1]}s]`;
      btn.addEventListener("click", () => {
        dispatchInstruction(`Remove occurrence ${opt.index}`);
      });
      clarificationChoices.appendChild(btn);
    });

    // Add option to remove all
    const allBtn = document.createElement("button");
    allBtn.className = "choice-btn";
    allBtn.style.color = "#58a6ff";
    allBtn.textContent = "⚡ Remove all occurrences";
    allBtn.addEventListener("click", () => {
      dispatchInstruction("Remove all occurrences");
    });
    clarificationChoices.appendChild(allBtn);
  } else {
    clarificationContainer.style.display = "none";
  }
}

clarificationSubmitBtn.addEventListener("click", () => {
  const text = clarificationInput.value.trim();
  if (text) {
    dispatchInstruction(text);
    clarificationInput.value = "";
  }
});

// 6. Undo, Redo, and Restore Intro
undoBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;
  try {
    const res = await fetch(`/api/v1/sessions/${currentSessionId}/undo`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      currentTimeline = data.timeline;
      metaTimelineHash.textContent = data.timeline_hash;
      renderTimeline(currentTimeline);
      displayOutcome({ status: "APPLIED", message: "Undo applied: Reverted 1 edit." });
    } else {
      displayOutcome({ status: "REJECTED", message: data.error?.message || "Undo failed." });
    }
  } catch (e) {
    alert(`Undo error: ${e.message}`);
  }
});

redoBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;
  try {
    const res = await fetch(`/api/v1/sessions/${currentSessionId}/redo`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      currentTimeline = data.timeline;
      metaTimelineHash.textContent = data.timeline_hash;
      renderTimeline(currentTimeline);
      displayOutcome({ status: "APPLIED", message: "Redo applied." });
    } else {
      displayOutcome({ status: "REJECTED", message: data.error?.message || "Redo failed." });
    }
  } catch (e) {
    alert(`Redo error: ${e.message}`);
  }
});

restoreIntroBtn.addEventListener("click", () => {
  dispatchInstruction("Restore the intro");
});

// 7. Real FFmpeg Rendering Pipeline
renderBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;

  renderBtn.disabled = true;
  renderPanel.style.display = "flex";
  renderStatus.textContent = "QUEUED";
  renderProgressBar.style.width = "10%";
  renderDetails.textContent = "Submitting render job to FFmpeg...";
  renderActions.style.display = "none";

  try {
    const res = await fetch(`/api/v1/sessions/${currentSessionId}/render`, { method: "POST" });
    const data = await res.json();
    currentRenderJobId = data.job_id;
    pollRenderJob(currentRenderJobId);
  } catch (err) {
    renderStatus.textContent = "FAILED";
    renderDetails.textContent = `Error: ${err.message}`;
    renderBtn.disabled = false;
  }
});

function pollRenderJob(jobId) {
  if (renderPollInterval) clearInterval(renderPollInterval);

  renderPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}`);
      const job = await res.json();

      renderStatus.textContent = job.status;
      renderProgressBar.style.width = `${Math.round((job.progress || 0) * 100)}%`;

      if (job.status === "COMPLETED") {
        clearInterval(renderPollInterval);
        renderBtn.disabled = false;
        renderDetails.textContent = `Render completed in FFmpeg! Output duration: ${job.manifest?.output_duration}s.`;
        renderActions.style.display = "flex";
        downloadRenderBtn.href = job.download_url;

        previewRenderBtn.onclick = () => {
          videoPlayer.src = job.stream_url;
          videoPlayer.play();
        };
      } else if (job.status === "FAILED") {
        clearInterval(renderPollInterval);
        renderBtn.disabled = false;
        renderDetails.textContent = `FFmpeg render failed: ${job.error_message}`;
      } else {
        renderDetails.textContent = "Executing FFmpeg filter_complex concat and encoding...";
      }
    } catch (e) {
      console.error("Polling error:", e);
    }
  }, 1000);
}

// Initialize on page load
checkReadiness();
