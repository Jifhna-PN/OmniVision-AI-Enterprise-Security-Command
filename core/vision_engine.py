import os
import csv
import cv2
import numpy as np
from ultralytics import YOLO


class VisionEngine:
    def __init__(
        self,
        model_path="yolov8n.pt",
        employees_dir="data/employees",
        hr_whitelist_path="data/hr_master_list.csv"
    ):
        self.yolo = YOLO(model_path)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.threat_classes = {"knife", "scissors", "baseball bat", "cell phone", "backpack", "laptop"}
        self.employees_dir = employees_dir
        self.hr_whitelist_path = hr_whitelist_path

        os.makedirs(self.employees_dir, exist_ok=True)
        self._init_hr_whitelist()

        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        self.employee_db = self._load_employee_database()

    def _init_hr_whitelist(self):
        """Creates a starter HR payroll whitelist if none exists yet."""
        if not os.path.exists(self.hr_whitelist_path):
            os.makedirs(os.path.dirname(self.hr_whitelist_path), exist_ok=True)
            with open(self.hr_whitelist_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Employee_ID", "Full_Name", "Department", "Clearance_Level"])
                writer.writerow(["EMP-101", "Jifhna", "AI Engineering", "Zone-A & Zone-B"])
                writer.writerow(["EMP-102", "Nandhana", "Cloud Infrastructure", "Zone-A & Zone-B"])
                writer.writerow(["EMP-103", "Rahul", "Security Operations", "Zone-A & Zone-B"])
                writer.writerow(["EMP-104", "Ananya", "Data Science", "Zone-B Only"])

    def _get_hr_clearance_map(self):
        """Returns a dict mapping lowercase Employee_ID -> Clearance_Level from HR whitelist."""
        clearance_map = {}
        if not os.path.exists(self.hr_whitelist_path):
            return clearance_map

        with open(self.hr_whitelist_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                emp_id = row.get("Employee_ID", "").strip().lower()
                clearance = row.get("Clearance_Level", "Zone-B Only").strip()
                if emp_id:
                    clearance_map[emp_id] = clearance
        return clearance_map

    def _verify_hr_whitelist(self, emp_id: str, emp_name: str):
        """Checks if the Employee ID and Name exist in the official HR Master Whitelist."""
        if not os.path.exists(self.hr_whitelist_path):
            return False, "HR Master Whitelist file missing."

        target_id = emp_id.strip().lower()
        target_name = emp_name.strip().lower()

        with open(self.hr_whitelist_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_id = row.get("Employee_ID", "").strip().lower()
                row_name = row.get("Full_Name", "").strip().lower()
                if row_id == target_id:
                    if row_name == target_name:
                        dept = row.get("Department", "Staff")
                        clearance = row.get("Clearance_Level", "Zone-B Only")
                        return True, f"Verified against HR Payroll ({dept} | Clearance: {clearance})"
                    return False, f"HR Mismatch: ID '{emp_id}' does not belong to '{emp_name}'."

        return False, f"Rejected: Employee ID '{emp_id}' is not listed in HR Master Whitelist."

    def _preprocess_face(self, gray_face):
        """Crops inner facial features (eyes/nose/mouth) to ignore hair/headwear and normalizes lighting."""
        h, w = gray_face.shape[:2]
        pad_y, pad_x = int(h * 0.12), int(w * 0.10)
        inner = gray_face[pad_y:h - pad_y, pad_x:w - pad_x]
        if inner.size == 0:
            inner = gray_face

        resized = cv2.resize(inner, (100, 100))
        equalized = self.clahe.apply(resized)
        hist = cv2.calcHist([equalized], [0], None, [64], [0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return equalized, hist

    def _load_employee_database(self):
        """Loads HR photos, crops face regions, and attaches HR zone clearance levels."""
        db = []
        if not os.path.exists(self.employees_dir):
            return db

        clearance_map = self._get_hr_clearance_map()

        for fname in os.listdir(self.employees_dir):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                path = os.path.join(self.employees_dir, fname)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                faces = self.face_cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
                if len(faces) > 0:
                    x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
                    face_roi = img[y:y+h, x:x+w]
                else:
                    face_roi = img

                norm_img, hist = self._preprocess_face(face_roi)
                stem = os.path.splitext(fname)[0]
                emp_id_part = stem.split("_")[0].strip().lower()
                emp_label = stem.replace("_", " ")
                clearance = clearance_map.get(emp_id_part, "Zone-B Only")

                db.append({
                    "label": emp_label,
                    "clearance": clearance,
                    "file": fname,
                    "norm": norm_img,
                    "hist": hist
                })
        return db

    def enroll_employee(self, frame, emp_id: str, emp_name: str):
        """3-Gate Enrollment: Admin PIN (UI) -> HR Whitelist Verification -> Duplicate ID Check -> Face Capture."""
        safe_id = "".join(c for c in emp_id.strip() if c.isalnum() or c in ("-", "_"))
        safe_name = "".join(c for c in emp_name.strip() if c.isalnum() or c in ("-", "_"))
        if not safe_id or not safe_name:
            return False, "Invalid Employee ID or Name."

        # Gate 1: Verify against HR Master Whitelist
        hr_ok, hr_msg = self._verify_hr_whitelist(safe_id, safe_name)
        if not hr_ok:
            return False, hr_msg

        # Gate 2: Prevent overwriting an already-enrolled Employee ID
        for existing_file in os.listdir(self.employees_dir):
            if existing_file.lower().startswith(f"{safe_id.lower()}_"):
                return False, f"Employee ID '{safe_id}' is already enrolled. Revoke the existing record first."

        # Gate 3: Biometric Face Detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(50, 50))
        if len(faces) == 0:
            return False, "No face detected in frame. Look straight at the camera and try again."

        x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
        face_crop = frame[y:y+h, x:x+w]

        filename = f"{safe_id}_{safe_name}.jpg"
        save_path = os.path.join(self.employees_dir, filename)
        cv2.imwrite(save_path, face_crop)
        self.employee_db = self._load_employee_database()
        return True, f"Enrolled {safe_id} - {safe_name} ({hr_msg})."

    def _is_cleared_for_zone(self, clearance: str, selected_zone: str) -> bool:
        """Checks whether an employee's HR clearance permits entry into the active zone."""
        zone_tag = "Zone-A" if "Zone-A" in selected_zone else "Zone-B"
        return zone_tag.lower() in clearance.lower()

    def _identify_person(self, gray_face):
        """Matches live inner-face crop against the entire HR employee roster."""
        if not self.employee_db:
            return False, "UNKNOWN INTRUDER", "", 0.0

        live_norm, live_hist = self._preprocess_face(gray_face)
        best_score = -1.0
        best_emp = "UNKNOWN INTRUDER"
        best_clearance = ""

        for emp in self.employee_db:
            hist_score = cv2.compareHist(emp["hist"], live_hist, cv2.HISTCMP_CORREL)
            struct_score = cv2.matchTemplate(live_norm, emp["norm"], cv2.TM_CCOEFF_NORMED)[0][0]
            combined = (0.55 * hist_score) + (0.45 * struct_score)
            if combined > best_score:
                best_score = combined
                best_emp = emp["label"]
                best_clearance = emp["clearance"]

        if best_score >= 0.42:
            return True, best_emp, best_clearance, best_score
        return False, "UNKNOWN INTRUDER", "", best_score

    def analyze_frame(self, frame, selected_zone="Zone-A (Main Server Room)"):
        annotated = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(75, 75))

        person_status = "No Person Detected"
        has_unauthorized = False
        zone_code = "Zone-A" if "Zone-A" in selected_zone else "Zone-B"

        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            matched, identity, clearance, score = self._identify_person(face_roi)

            if matched:
                if self._is_cleared_for_zone(clearance, selected_zone):
                    color = (0, 200, 0)
                    label = f"AUTHORIZED: {identity} ({score:.2f})"
                    if not has_unauthorized:
                        person_status = f"AUTHORIZED ({identity} | {clearance})"
                else:
                    color = (0, 140, 255)
                    label = f"NO {zone_code.upper()} CLEARANCE: {identity} ({clearance})"
                    person_status = f"UNAUTHORIZED ZONE ACCESS ({identity} - {clearance})"
                    has_unauthorized = True
            else:
                color = (0, 0, 255)
                label = f"UNKNOWN INTRUDER ({score:.2f})"
                person_status = "UNKNOWN INTRUDER"
                has_unauthorized = True

            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv2.putText(annotated, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 2)

        # YOLOv8 Object Detection
        results = self.yolo(frame, verbose=False)[0]
        detected_objects = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = self.yolo.names[cls_id]
            conf = float(box.conf[0])

            if cls_name in self.threat_classes and conf > 0.45:
                detected_objects.append(cls_name)
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(
                    annotated,
                    f"OBJECT: {cls_name} ({conf:.2f})",
                    (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 0, 255),
                    2
                )

        is_threat = has_unauthorized or (len(detected_objects) > 0)

        telemetry = {
            "person_status": person_status,
            "detected_objects": list(set(detected_objects)),
            "is_threat": is_threat
        }
        return annotated, telemetry
