import os
import csv
import time
import importlib
from datetime import datetime
import cv2
import streamlit as st
from dotenv import load_dotenv

import core.vision_engine
import core.rag_brain
import core.agent_actions

importlib.reload(core.vision_engine)
importlib.reload(core.rag_brain)
importlib.reload(core.agent_actions)

from core.vision_engine import VisionEngine
from core.rag_brain import SecurityBrain
from core.agent_actions import AutonomousResponder

# Force reload .env so changes like ADMIN_PIN are picked up instantly
load_dotenv(override=True)
ADMIN_PIN = os.getenv("ADMIN_PIN", "9999").strip()
ALERT_COOLDOWN_SECONDS = 20

st.set_page_config(
    page_title="OmniVision AI | Enterprise Security Command",
    page_icon="🛡️",
    layout="wide"
)

# --- SESSION STATE INITIALIZATION ---
for key, default in {
    "alert_triggered": False,
    "last_alert_time": 0.0,
    "threat_streak": 0,
    "last_report": None,
    "last_rule": None,
    "last_actions": [],
    "last_map": None,
    "camera_cap": None,
    "camera_active": False,
    "admin_unlocked": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def reset_system_state():
    st.session_state.alert_triggered = False
    st.session_state.last_alert_time = 0.0
    st.session_state.threat_streak = 0
    st.session_state.last_report = None
    st.session_state.last_rule = None
    st.session_state.last_actions = []
    st.session_state.last_map = None
    st.session_state.camera_active = False
    if st.session_state.camera_cap is not None:
        st.session_state.camera_cap.release()
        st.session_state.camera_cap = None


@st.cache_resource
def init_models():
    return VisionEngine(), SecurityBrain()


vision, brain = init_models()
responder = AutonomousResponder()

print("DEBUG APP RESPONDER:", id(responder), responder.aws_connected, responder.aws_status_msg)

import inspect
print("AGENT ACTIONS FILE:", inspect.getfile(AutonomousResponder))


# --- HEADER WITH LIVE TICKING FACILITY CLOCK ---
@st.fragment(run_every=1)
def live_facility_clock():
    now = datetime.now()
    st.metric(
        label="🕒 Facility System Clock",
        value=now.strftime("%H:%M:%S"),
        delta=now.strftime("%d %b %Y")
    )


head_col1, head_col2 = st.columns([3, 1])
with head_col1:
    st.title("🛡️ OmniVision AI — Enterprise Security Command")
    st.markdown("Edge Computer Vision + HR Biometric Roster + Agentic AI Tool Calling + AWS S3 Vault")
with head_col2:
    live_facility_clock()

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🎛️ Command Center Controls")

if responder.aws_connected:
    st.sidebar.success(f"☁️ AWS Cloud: {responder.aws_status_msg}")
else:
    st.sidebar.info(f"☁️ AWS Cloud: {responder.aws_status_msg}")

run_camera = st.sidebar.toggle("🟢 Activate Live Security Camera", key="camera_active")
selected_zone = st.sidebar.selectbox(
    "Select Monitored Zone:",
    ["Zone-A (Main Server Room)", "Zone-B (General Office)"]
)

st.sidebar.divider()
st.sidebar.subheader("🔐 HR Biometric Admin Portal")
st.sidebar.caption(f"Active HR Roster: **{len(vision.employee_db)} Authorized Staff**")

if not st.session_state.admin_unlocked:
    with st.sidebar.form("admin_login_form"):
        entered_pin = st.text_input(
            "Enter Security Admin PIN to Manage Staff:",
            type="password",
            placeholder="Enter confidential PIN"
        )
        unlock_submitted = st.form_submit_button("🔓 Unlock Admin Portal")

    if unlock_submitted:
        if entered_pin.strip() == ADMIN_PIN:
            st.session_state.admin_unlocked = True
            st.rerun()
        else:
            st.sidebar.error("⛔ Access Denied: Invalid Admin PIN.")
else:
    st.sidebar.success("🔓 Admin Session Active")
    emp_id = st.sidebar.text_input("Employee ID:", placeholder="e.g., EMP-105")
    emp_name = st.sidebar.text_input("Full Name:", placeholder="e.g., Aswathy")

    capture_clicked = st.sidebar.button("📸 Capture & Enroll Employee")

    if capture_clicked:
        if not emp_id.strip() or not emp_name.strip():
            st.sidebar.warning("Enter both Employee ID and Name first.")
        else:
            temp_cap = cv2.VideoCapture(0)
            success = False
            snap_frame = None

            for _ in range(10):
                ret, frame = temp_cap.read()
                if ret:
                    snap_frame = frame
                    success = True
                    break
            temp_cap.release()

            if success and snap_frame is not None:
                ok, msg = vision.enroll_employee(snap_frame, emp_id, emp_name)
                if ok:
                    st.cache_resource.clear()
                    st.sidebar.success(f"✅ {msg}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.sidebar.error(f"⚠️ {msg}")
            else:
                st.sidebar.error("⚠️ Unable to access webcam. Check camera permissions.")

    if vision.employee_db:
        st.sidebar.markdown("**Enrolled Staff Roster:**")
        for emp in vision.employee_db:
            col_e1, col_e2 = st.sidebar.columns([3, 1])
            col_e1.caption(f"🪪 {emp['label']} ({emp['clearance']})")
            if col_e2.button("🗑️", key=f"del_{emp['file']}", help="Revoke Access"):
                os.remove(os.path.join("data/employees", emp["file"]))
                st.cache_resource.clear()
                st.rerun()

    if st.sidebar.button("🔒 Lock Admin Portal"):
        st.session_state.admin_unlocked = False
        st.rerun()

st.sidebar.divider()
st.sidebar.button(
    "🔄 Reset Alert State",
    on_click=reset_system_state,
    type="primary",
    use_container_width=True
)

if not run_camera and st.session_state.camera_cap is not None:
    st.session_state.camera_cap.release()
    st.session_state.camera_cap = None

# --- MAIN COMMAND DASHBOARD ---
col_cam, col_brain = st.columns([1.2, 1])

with col_cam:
    st.subheader(f"📹 Live Feed: {selected_zone}")
    frame_placeholder = st.empty()
    telemetry_placeholder = st.empty()

with col_brain:
    st.subheader("🧠 Agentic AI Brain & AWS Cloud Response")
    status_placeholder = st.empty()
    rule_placeholder = st.empty()
    report_placeholder = st.empty()
    actions_placeholder = st.empty()
    map_placeholder = st.empty()


def render_ai_panels():
    if st.session_state.alert_triggered and st.session_state.last_report:
        status_placeholder.error("🚨 CRITICAL SECURITY BREACH CONFIRMED — AUTONOMOUS LOCKDOWN ACTIVE")
        rule_placeholder.info(f"**Matched Policy & Agent Mode:** {st.session_state.last_rule}")
        report_placeholder.markdown(st.session_state.last_report)

        if st.session_state.last_actions:
            actions_text = "\n".join([f"- {act}" for act in st.session_state.last_actions])
            actions_placeholder.success(f"**Executed Agent Tools & AWS Sync:**\n{actions_text}")

        if st.session_state.last_map and os.path.exists(st.session_state.last_map):
            map_placeholder.image(
                st.session_state.last_map,
                caption="Generated First-Responder Tactical Floor Plan",
                use_container_width=True
            )
    else:
        status_placeholder.success("✅ PERIMETER SECURE — Monitoring live telemetry...")
        rule_placeholder.empty()
        report_placeholder.empty()
        actions_placeholder.empty()
        map_placeholder.empty()


render_ai_panels()

# --- LIVE CAMERA LOOP ---
if run_camera:
    if st.session_state.camera_cap is None or not st.session_state.camera_cap.isOpened():
        st.session_state.camera_cap = cv2.VideoCapture(0)

    cap = st.session_state.camera_cap

    if not cap.isOpened():
        st.error("❌ Unable to access webcam.")
    else:
        try:
            while st.session_state.camera_active:
                ret, frame = cap.read()
                if not ret:
                    break

                annotated_frame, telemetry = vision.analyze_frame(frame, selected_zone)

                live_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.rectangle(annotated_frame, (10, 10), (265, 38), (0, 0, 0), -1)
                cv2.putText(
                    annotated_frame,
                    f"REC | {live_ts}",
                    (16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 0),
                    2
                )

                rgb_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
                frame_placeholder.image(rgb_frame, channels="RGB", use_container_width=True)

                detected_str = ", ".join(telemetry["detected_objects"]) if telemetry["detected_objects"] else "None"
                remaining_cd = max(0, int(ALERT_COOLDOWN_SECONDS - (time.time() - st.session_state.last_alert_time))) if st.session_state.alert_triggered else 0
                cd_text = f" | **Cooldown:** {remaining_cd}s" if st.session_state.alert_triggered else ""

                telemetry_placeholder.caption(
                    f"**Time:** {live_ts} | "
                    f"**Identity:** {telemetry['person_status']} | "
                    f"**Objects:** {detected_str} | "
                    f"**Threat Streak:** {min(st.session_state.threat_streak, 6)}/6 frames"
                    f"{cd_text}"
                )

                is_zone_a = "Zone-A" in selected_zone
                active_threat = telemetry["is_threat"] and is_zone_a

                if active_threat:
                    st.session_state.threat_streak += 1
                else:
                    st.session_state.threat_streak = max(0, st.session_state.threat_streak - 1)

                cooldown_elapsed = (time.time() - st.session_state.last_alert_time) >= ALERT_COOLDOWN_SECONDS

                if st.session_state.threat_streak >= 6 and (not st.session_state.alert_triggered or cooldown_elapsed):
                    st.session_state.alert_triggered = True
                    st.session_state.last_alert_time = time.time()
                    st.session_state.threat_streak = 0
                    status_placeholder.warning("⏳ Threat confirmed! Agentic AI selecting tools & syncing with AWS S3...")

                    matched_rule, cot_report, selected_tools = brain.think_and_decide(
                        zone=selected_zone,
                        person_status=telemetry["person_status"],
                        objects=telemetry["detected_objects"]
                    )

                    action_logs, map_path = responder.execute_agent_plan(
                        frame=annotated_frame,
                        report_text=cot_report,
                        zone=selected_zone,
                        person_status=telemetry["person_status"],
                        objects=telemetry["detected_objects"],
                        selected_tools=selected_tools
                    )

                    st.session_state.last_rule = matched_rule
                    st.session_state.last_report = cot_report
                    st.session_state.last_actions = action_logs
                    st.session_state.last_map = map_path

                    render_ai_panels()

                time.sleep(0.03)
        finally:
            if st.session_state.camera_cap is not None:
                st.session_state.camera_cap.release()
                st.session_state.camera_cap = None
else:
    frame_placeholder.info("👈 Toggle **Activate Live Security Camera** in the sidebar to begin live surveillance.")

# --- EVIDENCE VAULT & COMPLIANCE AUDIT LEDGER ---
st.divider()
st.subheader("🗄️ Evidence Vault & AWS / Compliance Audit Ledger")

ledger_file = "incident_logs/audit_ledger.csv"

if os.path.exists("incident_logs"):
    saved_images = sorted(
        [f for f in os.listdir("incident_logs") if f.startswith("intruder_") and f.endswith(".jpg")],
        reverse=True
    )

    if saved_images:
        selected_img = st.selectbox("Select Recorded Incident Snapshot to Verify:", saved_images)
        ts_part = selected_img.replace("intruder_", "").replace(".jpg", "")
        report_file = f"incident_logs/report_{ts_part}.txt"

        hist_col1, hist_col2 = st.columns([1, 1.5])
        with hist_col1:
            st.image(
                f"incident_logs/{selected_img}",
                caption=f"Captured Evidence ({ts_part})",
                use_container_width=True
            )
        with hist_col2:
            if os.path.exists(report_file):
                with open(report_file, "r", encoding="utf-8") as f:
                    st.markdown(f.read())

            st.markdown("---")
            st.markdown("**📋 Supervisor Case Verification & Escalation**")
            ver_status = st.selectbox(
                "Update Case Disposition:",
                [
                    "Pending Supervisor Review",
                    "✅ Verified Breach — Escalated to Police/HR",
                    "🟡 False Alarm — Authorized Staff / Lighting Issue",
                    "🔒 Closed — Incident Resolved"
                ],
                key=f"status_{ts_part}"
            )
            sup_notes = st.text_input(
                "Verification / Clarification Notes:",
                placeholder="e.g., Confirmed identity via badge log; escalated to facility head...",
                key=f"notes_{ts_part}"
            )
            if st.button("💾 Save Verification Decision", key=f"save_{ts_part}"):
                if os.path.exists(ledger_file):
                    rows = []
                    with open(ledger_file, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        header = next(reader)
                        rows.append(header)
                        for row in reader:
                            if len(row) >= 9 and ts_part in row[0]:
                                row[7] = ver_status
                                row[8] = sup_notes if sup_notes else row[8]
                            rows.append(row)
                    with open(ledger_file, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerows(rows)
                    st.success(f"Saved decision for INC-{ts_part} to permanent audit ledger.")

        if os.path.exists(ledger_file):
            st.markdown("#### 📊 Master Security Audit Log (All Recorded Incidents)")
            with open(ledger_file, "r", encoding="utf-8") as f:
                ledger_data = list(csv.DictReader(f))
            if ledger_data:
                st.dataframe(ledger_data, use_container_width=True)
                with open(ledger_file, "rb") as f:
                    st.download_button(
                        label="📥 Download Audit Ledger (CSV for Compliance / Police)",
                        data=f,
                        file_name="omnivision_security_audit_ledger.csv",
                        mime="text/csv"
                    )
    else:
        st.info("No security breaches recorded yet. Trigger a threat simulation above to populate the evidence vault.")
