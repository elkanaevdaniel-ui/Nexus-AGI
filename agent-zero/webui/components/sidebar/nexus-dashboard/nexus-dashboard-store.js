/**
 * Nexus Dashboard Store — tracks service health and provides quick actions.
 * Uses the /nexus_health API endpoint to check all services at once.
 */

const DEFAULT_SERVICES = [
  { id: "claude-adapter", name: "Claude Code", detail: "Code generation adapter" },
  { id: "linkedin-bot", name: "LinkedIn Bot", detail: "Content & posting" },
  { id: "trading", name: "Trading Agent", detail: "Polymarket trading" },
  { id: "lead-gen", name: "Lead Gen", detail: "Lead generation pipeline" },
  { id: "llm-router", name: "LLM Router", detail: "Unified model routing" },
  { id: "cost-tracker", name: "Cost Tracker", detail: "Budget monitoring" },
];

export const store = Alpine.store("nexusDashboard", {
  isExpanded: false,
  isRefreshing: false,
  lastCheck: null,
  lastCheckText: "Not checked yet",
  services: DEFAULT_SERVICES.map((s) => ({ ...s, status: "offline" })),

  toggle() {
    this.isExpanded = !this.isExpanded;
    if (this.isExpanded && !this.lastCheck) {
      this.refreshAll();
    }
  },

  async refreshAll() {
    this.isRefreshing = true;
    // Mark all as checking
    this.services = this.services.map((s) => ({ ...s, status: "checking" }));

    try {
      const resp = await fetch("/nexus_health", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "all" }),
        signal: AbortSignal.timeout(10000),
      });

      if (resp.ok) {
        const json = await resp.json();
        if (json.ok && Array.isArray(json.data)) {
          this.services = json.data.map((svc) => ({
            id: svc.id,
            name: svc.name,
            detail: svc.status === "online"
              ? (DEFAULT_SERVICES.find((d) => d.id === svc.id)?.detail || svc.url)
              : (svc.error || svc.status),
            status: svc.status,
          }));
        }
      }
    } catch {
      // Keep services as-is with offline status
      this.services = DEFAULT_SERVICES.map((s) => ({ ...s, status: "offline", detail: "Health check failed" }));
    }

    this.lastCheck = new Date();
    this.lastCheckText = "Just now";
    this.isRefreshing = false;
    this._startLastCheckTimer();
  },

  _lastCheckInterval: null,
  _startLastCheckTimer() {
    if (this._lastCheckInterval) clearInterval(this._lastCheckInterval);
    this._lastCheckInterval = setInterval(() => {
      if (!this.lastCheck) return;
      const seconds = Math.floor((Date.now() - this.lastCheck.getTime()) / 1000);
      if (seconds < 60) this.lastCheckText = `${seconds}s ago`;
      else if (seconds < 3600) this.lastCheckText = `${Math.floor(seconds / 60)}m ago`;
      else this.lastCheckText = `${Math.floor(seconds / 3600)}h ago`;
    }, 30000);
  },

  openService(serviceId) {
    const service = this.services.find((s) => s.id === serviceId);
    if (!service) return;
    this.sendCommand(`Show me detailed status and logs for the ${service.name} service`);
  },

  restartService(serviceId) {
    const service = this.services.find((s) => s.id === serviceId);
    if (!service) return;
    if (confirm(`Restart ${service.name}?`)) {
      this.sendCommand(`Restart the ${service.name} service and report its status`);
    }
  },

  sendCommand(text) {
    const chatInput = document.querySelector("#chat-input");
    if (chatInput) {
      chatInput.value = text;
      chatInput.dispatchEvent(new Event("input", { bubbles: true }));
      const sendBtn = document.querySelector("#btn-send");
      if (sendBtn) sendBtn.click();
    }
  },
});
