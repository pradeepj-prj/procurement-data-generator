import { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { ChatPanel } from "./components/ChatPanel";
import { GraphView } from "./components/GraphView";
import { TracePanel } from "./components/TracePanel";
import { NodeDetail } from "./components/NodeDetail";
import { useChat } from "./hooks/useChat";
import { useGraph } from "./hooks/useGraph";

export default function App() {
  const { messages, loading, agentSteps, send, clearChat, currentTrace, mode, setMode } = useChat();
  const { elements, highlightedIds, setFromTrace, clear } = useGraph();
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // When a new trace arrives, replace the graph with this trace's data
  useEffect(() => {
    if (currentTrace) setFromTrace(currentTrace);
  }, [currentTrace, setFromTrace]);

  const handleNewChat = () => {
    clearChat();
    clear();
  };

  return (
    <div className="h-screen flex flex-col">
      <Header mode={mode} onModeChange={setMode} />
      <div className="flex-1 grid grid-cols-[350px_1fr_350px] min-h-0 relative">
        <ChatPanel
          messages={messages}
          loading={loading}
          agentSteps={agentSteps}
          onSend={send}
          onNewChat={handleNewChat}
          onEntityClick={setSelectedNode}
        />
        <GraphView
          elements={elements}
          highlightedIds={highlightedIds}
          onNodeClick={setSelectedNode}
          onClear={clear}
        />
        <TracePanel trace={currentTrace} />
        <NodeDetail
          nodeId={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      </div>
    </div>
  );
}
