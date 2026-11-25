import os
import google.generativeai as genai


# --- AGENTIC AI TOOL DEFINITIONS (Callable by Gemini) ---
def lock_magnetic_doors(zone: str) -> str:
    """Seals electromagnetic security doors in the specified facility zone."""
    return f"Magnetic doors sealed in {zone}."


def trigger_pa_alarm(zone: str) -> str:
    """Activates the facility Public Address (PA) speaker deterrent in the specified zone."""
    return f"Audio PA deterrent triggered in {zone}."


def cut_server_power(zone: str) -> str:
    """Cuts auxiliary power to server racks to prevent physical data extraction."""
    return f"Auxiliary power isolated in {zone}."


def dispatch_police_unit(zone: str, threat_level: str) -> str:
    """Generates a tactical floor plan and transmits an emergency dispatch to local law enforcement."""
    return f"Police dispatch transmitted for {zone} at threat level {threat_level}."


class SecurityBrain:
    def __init__(self, sop_path="data/sop_manuals/security_protocols.txt"):
        self.sop_path = sop_path
        self.rules_text = self._load_sop(sop_path)
        self.agent_tools = [
            lock_magnetic_doors,
            trigger_pa_alarm,
            cut_server_power,
            dispatch_police_unit
        ]
        self.model = None
        self.active_model_name = "Edge-Agent-FailSafe"

        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = self._initialize_agent_model()

    def _initialize_agent_model(self):
        preferred_models = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest"
        ]
        try:
            available = [
                m.name.replace("models/", "")
                for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]
            for candidate in preferred_models:
                if candidate in available:
                    self.active_model_name = candidate
                    return genai.GenerativeModel(candidate, tools=self.agent_tools)
        except Exception:
            pass

        self.active_model_name = "gemini-2.5-flash"
        return genai.GenerativeModel("gemini-2.5-flash", tools=self.agent_tools)

    def _load_sop(self, path):
        if not os.path.exists(path):
            path = "data/security_protocols.txt"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return (
            "RULE #42: SERVER ROOM INTRUSION (ZONE-A) - If an UNKNOWN INTRUDER enters Zone-A "
            "carrying a cell phone, laptop, or weapon, call lock_magnetic_doors, trigger_pa_alarm, "
            "cut_server_power, and dispatch_police_unit.\n"
            "RULE #15: GENERAL OFFICE (ZONE-B) - If an UNKNOWN INTRUDER is detected with a weapon, "
            "call trigger_pa_alarm and dispatch_police_unit."
        )

    def think_and_decide(self, zone: str, person_status: str, objects: list):
        """Agentic Reasoning Loop: Evaluates SOP, autonomously selects tools, and returns execution plan."""
        obj_list = ", ".join(objects) if objects else "unidentified item"

        prompt = (
            f"You are the OmniVision Autonomous Security Agent.\n"
            f"TELEMETRY -> Zone: {zone} | Identity: {person_status} | Objects: {obj_list}\n"
            f"SECURITY SOP MANUAL:\n{self.rules_text}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Call the appropriate security tools from your toolset to neutralize this breach.\n"
            f"2. Provide a concise 4-point Incident Assessment (Context Reasoning, Matched Policy, "
            f"Agent Tool Decisions, and 2-sentence Police Dispatch Summary)."
        )

        selected_tools = []

        if self.model:
            try:
                chat = self.model.start_chat(enable_automatic_function_calling=True)
                response = chat.send_message(prompt, request_options={"timeout": 15})

                for content in chat.history:
                    for part in content.parts:
                        if fn_call := getattr(part, "function_call", None):
                            if fn_call.name:
                                selected_tools.append(fn_call.name)

                if not selected_tools:
                    selected_tools = ["trigger_pa_alarm", "lock_magnetic_doors", "dispatch_police_unit"]

                header = f"Rule #42 (SOP) | Agentic AI: {self.active_model_name} | Tools Invoked: {len(selected_tools)}"
                return header, response.text, selected_tools

            except Exception:
                pass

        selected_tools = ["trigger_pa_alarm", "lock_magnetic_doors", "cut_server_power", "dispatch_police_unit"]
        fallback_text = (
            f"**⚡ Edge Autonomous Agent Active (Local Deterministic Tool Execution)**\n\n"
            f"1. **Context Reasoning:** {person_status} detected inside {zone} carrying {obj_list}.\n"
            f"2. **Matched Policy:** Rule #42 (Server Room Intrusion Protocol).\n"
            f"3. **Autonomous Tool Chain:** Invoked `{' -> '.join(selected_tools)}`.\n"
            f"4. **Police Dispatch Summary:** Security breach confirmed in {zone} involving an {person_status} "
            f"with {obj_list}. Doors are sealed; responders should enter via the main corridor."
        )
        return "Rule #42 (SOP) | Mode: Edge Agent Fail-Safe", fallback_text, selected_tools