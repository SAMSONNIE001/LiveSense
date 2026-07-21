const $ = (selector) => document.querySelector(selector);

function duration(seconds) {
  const total = Math.max(0, Math.floor(seconds));
  const hours = String(Math.floor(total / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const remaining = String(total % 60).padStart(2, "0");
  return `${hours}:${minutes}:${remaining}`;
}

function observation(name, value, level) {
  return `<div class="observation ${level}"><i></i><b>${name}</b><span>${value}</span></div>`;
}

function renderReport(report) {
  const current = report.current;
  const generated = new Date(report.generated_at * 1000);
  const sessionSeconds = report.generated_at - report.session_started_at;
  $("#generated").textContent = `Generated ${generated.toLocaleString()} • Current in-memory monitoring session`;

  const overallLevel = current.alarm_active || current.face_missing_warning ? "danger" : ["Dozing", "Drowsy"].includes(current.sleep_state) || current.eating_detected || current.drinking_detected || current.one_hand_visible ? "warning" : "";
  const overallTitle = current.alarm_active ? "Critical sleep danger detected" : overallLevel === "warning" ? "Safety attention is required" : current.face_detected ? "Monitoring signals are normal" : "Waiting for clear camera signals";
  const overallCopy = current.alarm_active ? "The report indicates sustained eye closure. Pull over immediately and stop safely." : overallLevel === "warning" ? "Review the highlighted findings below and restore full attention." : "No immediate critical event is active in the latest observation.";
  $("#overall").className = `overall ${overallLevel}`;
  $("#overall").querySelector("h2").textContent = overallTitle;
  $("#overall").querySelector("p").textContent = overallCopy;
  $("#quality").textContent = `${Math.round(current.signal_quality)}%`;

  const summaries = [["SESSION DURATION", duration(sessionSeconds)],["RECORDED SAMPLES", report.sample_count],["SAFETY ALERTS", report.alert_count],["CRITICAL EVENTS", report.critical_count]];
  $("#summary").innerHTML = summaries.map(([label,value]) => `<article class="summary-card"><small>${label}</small><strong>${value}</strong></article>`).join("");

  const sleepLevel = current.alarm_active ? "danger" : ["Dozing", "Drowsy"].includes(current.sleep_state) ? "warning" : current.sleep_state === "Awake" ? "good" : "";
  const observations = [
    observation("Sleep status", current.sleep_state, sleepLevel),
    observation("Face visibility", current.face_detected ? "Visible" : "Not detected", current.face_detected ? "good" : "danger"),
    observation("Eyes", current.eyes_closed ? `Closed ${current.eye_closure_seconds.toFixed(1)} seconds` : "Open", current.eyes_closed ? "warning" : "good"),
    observation("Hands safety", current.one_hand_visible ? "One hand visible" : "Ready", current.one_hand_visible ? "warning" : "good"),
    observation("Eating", current.eating_detected ? "Detected" : "Clear", current.eating_detected ? "warning" : "good"),
    observation("Drinking", current.drinking_detected ? "Detected" : "Clear", current.drinking_detected ? "warning" : "good"),
    observation("Seat belt", current.seatbelt_warning ? "Not confirmed" : current.seatbelt_visible ? "Visible" : "Checking", current.seatbelt_warning ? "danger" : current.seatbelt_visible ? "good" : ""),
    observation("Yawning", current.yawning ? "Detected" : "Clear", current.yawning ? "warning" : "good"),
    observation("Attention", `${Math.round(current.attention)}%`, current.attention >= 60 ? "good" : current.attention >= 35 ? "warning" : "danger"),
    observation("Readiness", `${Math.round(current.readiness)}%`, current.readiness >= 60 ? "good" : current.readiness >= 35 ? "warning" : "danger"),
  ];
  $("#observations").innerHTML = observations.join("");

  const averageNames = {attention:"Attention",drowsiness:"Drowsiness",readiness:"Readiness",signal_quality:"Signal Quality",tension:"Movement / Stress"};
  $("#averages").innerHTML = Object.entries(report.averages).map(([key,value]) => `<article class="average"><small>${averageNames[key]}</small><strong>${value}%</strong><div><i style="width:${Math.max(0,Math.min(100,value))}%"></i></div></article>`).join("");
  $("#samples").textContent = `${report.sample_count} recorded samples`;

  $("#event-count").textContent = `${report.events.length} events`;
  $("#report-events").innerHTML = report.events.length ? report.events.map((event) => `<div class="report-event"><time>${new Date(event.timestamp*1000).toLocaleTimeString()}</time><em class="${event.level}">${event.level}</em><b>${event.title}</b><p>${event.detail}</p></div>`).join("") : `<div class="empty"><strong>No reportable events yet.</strong><br>Start monitoring from the dashboard to create a session record.</div>`;
}

async function loadReport() {
  try {
    const response = await fetch("/api/report", { cache: "no-store" });
    if (!response.ok) throw new Error(`Report request failed (${response.status})`);
    renderReport(await response.json());
  } catch (error) {
    $("#overall").className = "overall danger";
    $("#overall").querySelector("h2").textContent = "Report unavailable";
    $("#overall").querySelector("p").textContent = error.message;
  }
}

$("#refresh").onclick = loadReport;
$("#print").onclick = () => window.print();
loadReport();
