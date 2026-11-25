import os
import csv
import threading
from datetime import datetime
import cv2
import numpy as np
from dotenv import load_dotenv

try:
    import boto3
    AWS_SDK_INSTALLED = True
except ImportError:
    AWS_SDK_INSTALLED = False

try:
    import pyttsx3
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

load_dotenv(override=True)


class AutonomousResponder:
    def __init__(self, bucket_name="omnivision-security-vault"):
        self.bucket_name = os.getenv("AWS_S3_BUCKET", bucket_name)
        self.sns_topic_arn = os.getenv("AWS_SNS_TOPIC_ARN", "")
        self.region = os.getenv("AWS_DEFAULT_REGION", "")
        self.ledger_path = "incident_logs/audit_ledger.csv"

        self.s3 = None
        self.sns = None
        self.aws_connected = False
        self.aws_status_msg = "Simulated Edge Vault (Configure AWS_PROFILE or AWS keys)"

        aws_profile = os.getenv("AWS_PROFILE")
        has_aws_auth = bool(aws_profile or os.getenv("AWS_ACCESS_KEY_ID"))

        print(
            "DEBUG AWS AUTH:",
            bool(has_aws_auth),
            "PROFILE:",
            aws_profile,
            "BUCKET:",
            self.bucket_name,
            "REGION:",
            self.region,
        )

        if AWS_SDK_INSTALLED and has_aws_auth:
            try:
                session = (
                    boto3.Session(profile_name=aws_profile, region_name=self.region)
                    if aws_profile
                    else boto3.Session(region_name=self.region)
                )
                self.s3 = session.client("s3")
                self.sns = session.client("sns")
                self.s3.head_bucket(Bucket=self.bucket_name)
                self.aws_connected = True
                self.aws_status_msg = f"Connected: s3://{self.bucket_name} ({self.region})"
            except Exception as e:
                print("DEBUG INIT EXC TYPE:", type(e), "STR:", str(e))
                self.aws_status_msg = f"AWS Fallback Mode ({type(e).__name__})"

        os.makedirs("incident_logs", exist_ok=True)
        self._init_ledger()

    def _init_ledger(self):
        if not os.path.exists(self.ledger_path):
            with open(self.ledger_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Incident_ID", "Timestamp", "Zone", "Person_Status",
                    "Detected_Objects", "AWS_S3_URI", "Agent_Tools_Executed",
                    "Verification_Status", "Supervisor_Notes"
                ])

    def _speak_warning(self, message: str):
        if not VOICE_AVAILABLE:
            return
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.say(message)
            engine.runAndWait()
        except Exception:
            pass

    def draw_tactical_map(self, breached_zone="Zone-A (Main Server Room)"):
        blueprint = np.ones((420, 680, 3), dtype=np.uint8) * 245
        cv2.rectangle(blueprint, (30, 30), (650, 390), (40, 40, 40), 3)

        # Zone-B
        cv2.rectangle(blueprint, (30, 30), (380, 240), (120, 120, 120), 2)
        cv2.putText(blueprint, "ZONE-B: GENERAL OFFICE", (60, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 2)

        # Zone-A
        is_zone_a = "Zone-A" in breached_zone
        fill_color = (200, 200, 255) if is_zone_a else (230, 245, 230)
        border_color = (0, 0, 220) if is_zone_a else (0, 150, 0)

        cv2.rectangle(blueprint, (380, 30), (650, 240), fill_color, -1)
        cv2.rectangle(blueprint, (380, 30), (650, 240), border_color, 3)
        cv2.putText(blueprint, "ZONE-A: SERVER ROOM", (405, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.55, border_color, 2)

        if is_zone_a:
            cv2.putText(blueprint, "[DOORS LOCKED]", (425, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 220), 2)
            cv2.circle(blueprint, (515, 190), 12, (0, 0, 255), -1)
            cv2.putText(blueprint, "INTRUDER", (480, 222), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)

        # Police Route
        cv2.arrowedLine(blueprint, (90, 390), (90, 275), (0, 150, 0), 3)
        cv2.arrowedLine(blueprint, (90, 275), (515, 275), (0, 150, 0), 3)
        cv2.arrowedLine(blueprint, (515, 275), (515, 240), (0, 150, 0), 3)
        cv2.putText(blueprint, "POLICE ENTRY ROUTE", (45, 375), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 150, 0), 2)

        map_path = "incident_logs/tactical_blueprint.png"
        cv2.imwrite(map_path, blueprint)
        return map_path

    def execute_agent_plan(self, frame, report_text: str, zone: str, person_status: str, objects: list, selected_tools: list):
        """Executes the tools autonomously chosen by the Agentic AI Brain + AWS Cloud Sync."""
        now = datetime.now()
        ts = now.strftime("%Y%m%d_%H%M%S")
        readable_time = now.strftime("%Y-%m-%d %H:%M:%S")
        img_name = f"intruder_{ts}.jpg"
        txt_name = f"report_{ts}.txt"
        img_path = f"incident_logs/{img_name}"
        txt_path = f"incident_logs/{txt_name}"

        cv2.imwrite(img_path, frame)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        action_logs = []
        time_tag = now.strftime("%H:%M:%S")

        if "trigger_pa_alarm" in selected_tools:
            short_zone = "Zone A Server Room" if "Zone-A" in zone else "Zone B General Office"
            voice_msg = f"Security Alert. Unauthorized intrusion detected in {short_zone}. Autonomous lockdown initiated."
            threading.Thread(target=self._speak_warning, args=(voice_msg,), daemon=True).start()
            action_logs.append(f"[{time_tag}] 🤖 AGENT TOOL [trigger_pa_alarm]: Broadcasted live PA voice warning.")

        if "lock_magnetic_doors" in selected_tools:
            action_logs.append(f"[{time_tag}] 🤖 AGENT TOOL [lock_magnetic_doors]: Sealed electromagnetic locks on {zone}.")

        if "cut_server_power" in selected_tools:
            action_logs.append(f"[{time_tag}] 🤖 AGENT TOOL [cut_server_power]: Isolated auxiliary server rack power.")

        s3_uri = f"local://incident_logs/{img_name}"
        if self.aws_connected and self.s3:
            try:
                s3_img_key = f"evidence/{img_name}"
                s3_txt_key = f"evidence/{txt_name}"
                self.s3.upload_file(img_path, self.bucket_name, s3_img_key)
                self.s3.upload_file(txt_path, self.bucket_name, s3_txt_key)
                s3_uri = f"s3://{self.bucket_name}/{s3_img_key}"
                action_logs.append(f"[{time_tag}] ☁️ AWS S3 CLOUD SYNC: Uploaded tamper-proof evidence to {s3_uri}")

                if self.sns and self.sns_topic_arn:
                    self.sns.publish(
                        TopicArn=self.sns_topic_arn,
                        Subject=f"CRITICAL BREACH: {zone}",
                        Message=f"Incident INC-{ts}\nEvidence: {s3_uri}\n\n{report_text}"
                    )
                    action_logs.append(f"[{time_tag}] 📲 AWS SNS DISPATCH: Sent real-time SMS/Email alert to Security Chief.")
            except Exception as e:
                print("DEBUG UPLOAD EXC:", repr(e))
                action_logs.append(f"[{time_tag}] ⚠️ AWS SYNC FALLBACK: Stored locally at {img_path} ({type(e).__name__})")
        else:
            action_logs.append(f"[{time_tag}] ☁️ AWS S3 SIMULATOR: Staged evidence package at {img_path} (Ready for S3 bucket sync).")

        map_path = self.draw_tactical_map(zone)
        if "dispatch_police_unit" in selected_tools:
            action_logs.append(f"[{time_tag}] 🤖 AGENT TOOL [dispatch_police_unit]: Generated tactical map & transmitted police dispatch.")

        obj_str = ", ".join(objects) if objects else "Restricted Item"
        tools_str = " -> ".join(selected_tools)
        with open(self.ledger_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                f"INC-{ts}", readable_time, zone, person_status,
                obj_str, s3_uri, tools_str,
                "Pending Supervisor Review", "Awaiting verification"
            ])

        return action_logs, map_path
