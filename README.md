# OmniVision AI — Enterprise Physical Security Command Center

**OmniVision AI** is a real-time, edge-assisted enterprise physical security dashboard built with **Streamlit**, **OpenCV**, **YOLOv8**, and **RAG-powered Agentic AI**. It combines live computer vision surveillance, HR-verified biometric facial recognition, zone-level access control, automated incident reporting, and cloud evidence vaulting.

---

## Key Features

* **Real-Time Threat & Perimeter Detection:** Uses **YOLOv8** (`yolov8n.pt`) to monitor live webcam feeds for unauthorized objects and security anomalies alongside OpenCV Haar-cascade facial detection.
* **HR-Verified Biometric Recognition & Zone Clearance:** Matches detected faces against enrolled employee portraits (`data/employees/`) cross-checked with `data/hr_master_list.csv` to enforce zone-level permissions (`Zone-A` / `Zone-B`).
* **PIN-Protected Biometric Enrollment:** Allows authorized supervisors to enroll new personnel directly from the live camera feed after validating against `hr_master_list.csv` and an administrator PIN.
* **Smart Debouncing & Cooldown Engine:** Confirms breaches only after a 6-frame continuous streak and applies a 20-second cooldown window to eliminate false alarms and duplicate alerts.
* **RAG-Driven Incident Response & AWS S3 Vaulting:** References internal Standard Operating Procedures (`data/sop_manuals/security_protocols.txt`) to generate contextual incident reports, saves evidence snapshots locally under `incident_logs/`, and syncs audit records to **AWS S3**.

---

## Project Structure

```text
OmniVision-AI-Enterprise-Security-Command/
├── app.py                      # Main Streamlit command center dashboard
├── core/
│   ├── __init__.py
│   ├── vision_engine.py        # YOLOv8 object detection & OpenCV biometric recognition
│   ├── rag_brain.py            # SOP retrieval & AI incident protocol analysis
│   └── agent_actions.py        # Automated logging, reporting, and AWS S3 syncing
├── data/
│   ├── employees/              # Enrolled employee reference images
│   ├── sop_manuals/            # Security SOPs and reference manuals
│   └── hr_master_list.csv      # Employee directory and zone clearance levels
├── requirements.txt            # Python dependencies
├── .gitignore                  # Excludes secrets, virtualenvs, and runtime logs
└── README.md
```

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

### 2. Create a Virtual Environment & Install Dependencies

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root directory and add your configuration values:

```env
ADMIN_PIN=your_supervisor_pin

# Optional: AWS S3 Evidence Vaulting
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=ap-south-1
S3_BUCKET_NAME=your_s3_bucket_name

# Optional: LLM API Key (if used by rag_brain.py)
OPENAI_API_KEY=your_api_key
```

### 4. Run the Application

```bash
streamlit run app.py
```

---

## Security & Privacy Notes

* Never commit `.env` files, API credentials, or live `incident_logs/` captures to version control.
* Ensure employee reference photos in `data/employees/` comply with your organization's data privacy guidelines before publishing to a public repository.
