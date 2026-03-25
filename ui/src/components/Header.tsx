import { useEffect, useState } from "react";
import { health } from "../api/client";

export function Header() {
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    const check = () =>
      health()
        .then(() => setHealthy(true))
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
