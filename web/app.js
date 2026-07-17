const $ = (selector) => document.querySelector(selector);
const video = $("#camera");
const overlay = $("#overlay");
const overlayContext = overlay.getContext("2d");
const capture = $("#capture");
const captureContext = capture.getContext("2d", { alpha: false });
const startedAt = Date.now();

let stream = null;
let socket = null;
let cameraActive = false;
let framePending = false;
let reconnectTimer = null;
let poseLandmarker = null;
let poseBusy = false;
let lastPoseAt = 0;
let lastVideoTime = -1;
let alarmWasActive = false;
let latest = null;

const colors = { green: "#20dda3", cyan: "#22bfe8", amber: "#f0a31c", red: "#ef4b4b", purple: "#a460df" };
const metricDefinitions = [
  ["Attention", "attention", colors.cyan], ["Drowsiness", "drowsiness", colors.amber],
  ["Readiness", "readiness", colors.green], ["Stress", "tension", colors.purple],
  ["Eye Openness", "eye", colors.cyan], ["Blink Rate", "blink", colors.amber],
  ["Yawning", "yawn", colors.amber], ["Face Visibility", "face", colors.purple],
];

function setConnection(connected, text) {
  const node = $(".system-status");
  node.classList.toggle("off", !connected);
  $("#system-status").textContent = text;
}

function connect() {
  if (socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState)) return;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${location.host}/ws/analyze`);
  socket.binaryType = "arraybuffer";
  socket.onopen = () => {
    setConnection(true, "Analysis server connected");
    if (cameraActive) scheduleFrame();
  };
  socket.onmessage = (event) => {
    framePending = false;
    const payload = JSON.parse(event.data);
    if (payload.type === "signals") updateDashboard(payload);
    if (cameraActive) scheduleFrame();
  };
  socket.onerror = () => setConnection(false, "Analysis connection interrupted");
  socket.onclose = () => {
    framePending = false;
    setConnection(false, "Reconnecting analysis…");
    if (cameraActive) reconnectTimer = setTimeout(connect, 900);
  };
}

function scheduleFrame() {
  if (!cameraActive || framePending) return;
  setTimeout(sendFrame, 70);
}

function sendFrame() {
  if (!cameraActive || framePending || !socket || socket.readyState !== WebSocket.OPEN || video.readyState < 2) return;
  captureContext.drawImage(video, 0, 0, capture.width, capture.height);
  capture.toBlob((blob) => {
    if (!blob || !cameraActive || socket.readyState !== WebSocket.OPEN) return;
    framePending = true;
    socket.send(blob);
  }, "image/jpeg", 0.68);
}

async function startCamera() {
  if (cameraActive) return stopCamera();
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 360 }, frameRate: { ideal: 20, max: 24 }, facingMode: "user" }, audio: false });
    video.srcObject = stream;
    await video.play();
    cameraActive = true;
    $("#camera-placeholder").style.display = "none";
    $("#tracking-badge").style.display = "block";
    $("#camera-button").textContent = "Stop Camera";
    $("#camera-state").textContent = "Live";
    $("#monitoring-copy").textContent = "AI systems are running smoothly";
    connect();
    initializePose();
    requestAnimationFrame(trackPose);
  } catch (error) {
    showNotice("danger", "CAMERA UNAVAILABLE", error.message);
  }
}

function stopCamera() {
  cameraActive = false;
  framePending = false;
  clearTimeout(reconnectTimer);
  if (stream) stream.getTracks().forEach((track) => track.stop());
  stream = null;
  video.srcObject = null;
  overlayContext.clearRect(0, 0, overlay.width, overlay.height);
  $("#camera-placeholder").style.display = "grid";
  $("#tracking-badge").style.display = "none";
  $("#camera-button").textContent = "Start Camera";
  $("#camera-state").textContent = "Off";
  $("#monitoring-copy").textContent = "Camera stopped; dashboard remains available";
  showNotice("normal", "MONITORING PAUSED", "Start the camera when you are ready.");
}

async function initializePose() {
  if (poseLandmarker) return;
  try {
    const vision = await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/+esm");
    const files = await vision.FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm");
    const options = { baseOptions: { modelAssetPath: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task", delegate: "GPU" }, runningMode: "VIDEO", numPoses: 1, minPoseDetectionConfidence: .45, minPosePresenceConfidence: .45, minTrackingConfidence: .45 };
    try { poseLandmarker = await vision.PoseLandmarker.createFromOptions(files, options); }
    catch { options.baseOptions.delegate = "CPU"; poseLandmarker = await vision.PoseLandmarker.createFromOptions(files, options); }
  } catch { $("#tracking-badge").textContent = "TRACKING OVERLAY UNAVAILABLE"; }
}

function syncOverlay() {
  const rect = video.getBoundingClientRect();
  overlay.width = Math.max(1, Math.round(rect.width));
  overlay.height = Math.max(1, Math.round(rect.height));
}

function drawPose(points) {
  syncOverlay();
  const width = overlay.width, height = overlay.height;
  const mapped = points.map((p) => ({ x: width - p.x * width, y: p.y * height, visibility: p.visibility ?? 1 }));
  const face = mapped.slice(0, 11), xs = face.map((p) => p.x), ys = face.map((p) => p.y);
  const centerX = (Math.min(...xs) + Math.max(...xs)) / 2, centerY = (Math.min(...ys) + Math.max(...ys)) / 2;
  const boxWidth = Math.min(width * .38, Math.max(30, Math.max(...xs) - Math.min(...xs)) * 1.72), boxHeight = boxWidth * 1.2;
  const left = Math.max(2, centerX - boxWidth / 2), top = Math.max(2, centerY - boxHeight * .44);
  overlayContext.clearRect(0, 0, width, height);
  overlayContext.strokeStyle = colors.green; overlayContext.lineWidth = 2; overlayContext.strokeRect(left, top, boxWidth, boxHeight);
  overlayContext.strokeStyle = colors.cyan; overlayContext.lineWidth = 2.2; overlayContext.lineCap = "round";
  for (const [a, b] of [[11,12],[11,13],[13,15],[15,17],[15,19],[12,14],[14,16],[16,18],[16,20]]) {
    const from = mapped[a], to = mapped[b]; if (!from || !to || from.visibility < .3 || to.visibility < .3) continue;
    overlayContext.beginPath(); overlayContext.moveTo(from.x, from.y); overlayContext.lineTo(to.x, to.y); overlayContext.stroke();
  }
  overlayContext.fillStyle = "#07131de8"; overlayContext.fillRect(left, Math.max(0, top - 16), 76, 15);
  overlayContext.fillStyle = colors.green; overlayContext.font = "700 9px Segoe UI"; overlayContext.fillText("FACE DETECTED", left + 4, Math.max(11, top - 5));
  $("#tracking-badge").textContent = "● FACE + ARMS DETECTED";
}

function trackPose(now) {
  if (!cameraActive) return;
  if (poseLandmarker && !poseBusy && video.readyState >= 2 && video.currentTime !== lastVideoTime && now - lastPoseAt >= 330) {
    lastVideoTime = video.currentTime; lastPoseAt = now; poseBusy = true;
    poseLandmarker.detectForVideo(video, now, (result) => {
      poseBusy = false;
      if (result.landmarks?.length) drawPose(result.landmarks[0]);
      else { overlayContext.clearRect(0, 0, overlay.width, overlay.height); $("#tracking-badge").textContent = "● SEARCHING FOR FACE + ARMS"; }
    });
  }
  requestAnimationFrame(trackPose);
}

function metricValue(key, current) {
  if (key === "eye") return current.eyes_closed ? 8 : current.face_detected ? 94 : 0;
  if (key === "blink") return current.eyes_closed ? 100 : 0;
  if (key === "yawn") return current.yawning ? 100 : 0;
  if (key === "face") return current.face_detected ? 100 : 0;
  return current[key] || 0;
}

function updateDashboard(payload) {
  latest = payload.current;
  const current = payload.current;
  $("#header-fps").textContent = current.fps.toFixed(0);
  $("#signal-fps").textContent = `${current.fps.toFixed(1)} FPS`;
  const cards = metricDefinitions.map(([label, key, color]) => {
    const value = metricValue(key, current), state = value > 70 ? "Good" : value > 25 ? "Observe" : "Low";
    return `<div class="signal-card" style="color:${color}"><small>${label}</small><strong>${Math.round(value)}%</strong><em>${state}</em><div class="mini-line"><i style="width:${value}%"></i></div></div>`;
  });
  $("#signal-cards").innerHTML = cards.join("");
  const activities = [["Face Detected",current.face_detected],["Eyes Closed",current.eyes_closed],["Looking Forward",current.attention>=48],["Phone Use",current.phone_at_ear],["Eating",current.eating_detected],["Drinking",current.drinking_detected],["Seat Belt",current.seatbelt_visible],["Yawning",current.yawning]];
  $("#activity-list").innerHTML = activities.map(([name, active]) => `<div class="activity-row"><span>${name}</span><b class="${active?'yes':''}">${active?'Yes':'No'}</b></div>`).join("");
  updateQuality(current); updateNotice(current); updateEvents(payload.events); updateSummary(current, payload.events); updateCharts(payload.history); alarm(current.alarm_active);
  $("#nav-alerts").textContent = payload.events.filter((event) => event.level !== "info").length;
}

function updateQuality(current) {
  const quality = Math.round(current.signal_quality), label = quality >= 72 ? "Excellent" : quality >= 45 ? "Adjusting" : "Weak";
  $("#quality-gauge").innerHTML = `<strong>${quality}%</strong><small>${label}</small>`;
  $("#quality-list").innerHTML = [["Lighting",current.brightness>55],["Sharpness",current.signal_quality>45],["Stability",current.tension<35],["Face",current.face_detected]].map(([name, good]) => `<div><span>● ${name}</span><b>${good?'Good':'Adjust'}</b></div>`).join("");
}

function showNotice(level, title, detail) { const node=$("#notice"); node.className=`notice ${level}`; node.innerHTML=`<span>${level==='danger'?'!':level==='warning'?'!':'✓'}</span><div><strong>${title}</strong><small>${detail}</small></div>`; }
function updateNotice(c) {
  if (c.alarm_active) return showNotice("danger","DANGER: SLEEP DETECTED — PULL OVER NOW","Stop driving, move to a safe place, and rest before continuing.");
  if (c.phone_at_ear) return showNotice("danger","PHONE USE DETECTED","Put the phone down and keep both hands available.");
  if (c.face_missing_warning) return showNotice("danger","FACE NOT DETECTED","Return your face to camera view.");
  if (c.drinking_detected) return showNotice("warning","DRINKING DETECTED","Keep your hands and attention available for driving.");
  if (c.eating_detected) return showNotice("warning","EATING DETECTED","Stop eating and restore full attention.");
  if (c.sleep_state === "Dozing" || c.sleep_state === "Drowsy") return showNotice("warning",`${c.sleep_state.toUpperCase()} WARNING`,"Pull over at the next safe place and rest.");
  showNotice("normal","MONITORING STATUS: NORMAL",c.face_detected?"Live analysis is active.":"Position your face clearly in the camera.");
}

function updateEvents(events) { $("#events").innerHTML = events.length ? events.map((e) => `<div class="event ${e.level}"><i></i><span>${new Date(e.timestamp*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span><b>${e.title}</b></div>`).join("") : "<p>No active events</p>"; }
function updateSummary(c, events) { const duration=Math.floor((Date.now()-startedAt)/1000); $("#summary").innerHTML = [["Duration",formatDuration(duration)],["Active Time",cameraActive?"Live":"Paused"],["Alerts",events.filter((e)=>e.level!=="info").length],["Avg. Signal",`${Math.round(c.signal_quality)}%`]].map(([a,b])=>`<div class="summary-item"><span>${a}</span><b>${b}</b></div>`).join(""); }

function drawChart(canvas, history, series) {
  const ratio=devicePixelRatio||1, rect=canvas.getBoundingClientRect(); canvas.width=Math.max(1,rect.width*ratio); canvas.height=Math.max(1,rect.height*ratio); const ctx=canvas.getContext("2d"); ctx.scale(ratio,ratio); const w=rect.width,h=rect.height;
  ctx.strokeStyle="#17303b"; ctx.lineWidth=1; for(let y=15;y<h;y+=30){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
  for(const [key,color] of series){ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.beginPath();history.forEach((p,i)=>{const x=history.length<2?0:i*w/(history.length-1),value=key==="phone_at_ear"?(p[key]?100:0):key==="yawning"?(p[key]?100:0):(p[key]||0),y=h-8-Math.max(0,Math.min(100,value))*(h-16)/100;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();}
}
function updateCharts(history) { const activity=[["attention",colors.cyan],["drowsiness",colors.amber],["readiness",colors.green],["phone_at_ear",colors.purple]], drowsy=[["drowsiness",colors.amber],["yawning",colors.red]]; drawChart($("#activity-chart"),history,activity);drawChart($("#drowsy-chart"),history,drowsy);$("#activity-legend").innerHTML=activity.map(([n,c])=>`<span><i style="background:${c}"></i>${n}</span>`).join("");$("#drowsy-legend").innerHTML=drowsy.map(([n,c])=>`<span><i style="background:${c}"></i>${n}</span>`).join(""); }

function alarm(active) { if(active&&!alarmWasActive){if(Notification.permission==="granted")new Notification("LiveSense sleep alarm",{body:"Sleep detected. Pull over now."});const AudioContext=window.AudioContext||window.webkitAudioContext;if(AudioContext){const ctx=new AudioContext();[0,.3,.6].forEach((delay)=>{const osc=ctx.createOscillator(),gain=ctx.createGain();osc.frequency.value=880;gain.gain.value=.16;osc.connect(gain).connect(ctx.destination);osc.start(ctx.currentTime+delay);osc.stop(ctx.currentTime+delay+.2)})}}alarmWasActive=active; }
function formatDuration(total){const h=String(Math.floor(total/3600)).padStart(2,"0"),m=String(Math.floor(total%3600/60)).padStart(2,"0"),s=String(total%60).padStart(2,"0");return `${h}:${m}:${s}`;}

$("#camera-button").onclick=startCamera; $("#mini-stop").onclick=stopCamera;
$("#calibrate-button").onclick=()=>socket?.readyState===WebSocket.OPEN&&socket.send(JSON.stringify({action:"calibrate"}));
$("#reset-button").onclick=()=>socket?.readyState===WebSocket.OPEN&&socket.send(JSON.stringify({action:"reset"}));
$("#notifications-button").onclick=async()=>{if("Notification" in window)await Notification.requestPermission();};
$("#snapshot-button").onclick=()=>{if(!cameraActive)return;const link=document.createElement("a");captureContext.drawImage(video,0,0,capture.width,capture.height);link.href=capture.toDataURL("image/jpeg",.9);link.download="livesense-snapshot.jpg";link.click();};
window.addEventListener("beforeunload",()=>{if(stream)stream.getTracks().forEach((track)=>track.stop());socket?.close();poseLandmarker?.close();});
setInterval(()=>{const now=new Date();$("#date").textContent=now.toLocaleDateString([], {month:"short",day:"2-digit",year:"numeric"});$("#time").textContent=now.toLocaleTimeString();$("#uptime").textContent=formatDuration(Math.floor((Date.now()-startedAt)/1000));},1000);
connect();
