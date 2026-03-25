import { useEffect, useState } from "react";
import { health, type Mode } from "../api/client";

interface Props {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
}

export function Header({ mode, onModeChange }: Props) {
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [agentAvailable, setAgentAvailable] = useState(false);

  useEffect(() => {
    const check = () =>
      health()
        .then((h) => {
          setHealthy(true);
          setAgentAvailable(h.agent_available);
        })
        .catch(() => setHealthy(false));
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b">
      <h1 className="text-lg font-semibold text-gray-100">
        Procurement Knowledge Graph
      </h1>
      <div className="flex items-center gap-3 text-sm">
        {/* Mode toggle */}
        <div className="flex bg-gray-800 rounded overflow-hidden">
          <button
            onClick={() => onModeChange("router")}
            className={`px-2.5 py-1 text-xs font-medium transition-colors ${
              mode === "router"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Router
          </button>
          <button
            onClick={() => agentAvailable && onModeChange("agent")}
            className={`px-2.5 py-1 text-xs font-medium transition-colors ${
              mode === "agent"
                ? "bg-purple-600 text-white"
                : agentAvailable
                  ? "text-gray-400 hover:text-gray-200"
                  : "text-gray-600 cursor-not-allowed"
            }`}
            title={agentAvailable ? "ReAct agent mode" : "Agent mode unavailable (langgraph not installed)"}
          >
            Agent
          </button>
        </div>

        <span className="px-2 py-0.5 bg-gray-800 rounded text-xs font-mono">
          GraphRAG
        </span>
        <span className="flex items-center gap-1">
          <span
            className={`w-2 h-2 rounded-full ${
              healthy === true
                ? "bg-green-400"
                : healthy === false
                  ? "bg-red-400"
                  : "bg-gray-500"
            }`}
          />
          <span className="text-gray-400">
            {healthy === true ? "Connected" : healthy === false ? "Offline" : "..."}
          </span>
        </span>
      </div>
    </header>
  );
}
