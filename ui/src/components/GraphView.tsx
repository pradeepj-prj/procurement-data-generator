import { useCallback, useRef } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import type { Core, ElementDefinition, LayoutOptions } from "cytoscape";

interface Props {
  elements: ElementDefinition[];
  highlightedIds: Set<string>;
  onNodeClick?: (nodeId: string) => void;
  onClear: () => void;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
const stylesheet: any[] = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "background-color": "data(color)",
      "background-opacity": 0.85,
      shape: "data(shape)",
      width: 28,
      height: 28,
      "font-size": 8,
      "text-valign": "bottom",
      "text-margin-y": 3,
      color: "#e5e7eb",
      "text-outline-color": "#111827",
      "text-outline-width": 1.5,
      "border-width": 1.5,
      "border-color": "#374151",
      "text-max-width": 80,
      "text-wrap": "ellipsis",
    },
  },
  {
    selector: "node.highlighted",
    style: {
      "border-width": 2.5,
      "border-color": "#fbbf24",
      width: 34,
      height: 34,
    },
  },
  {
    selector: "edge",
    style: {
      label: "data(label)",
      "line-color": "#4b5563",
      "target-arrow-color": "#6b7280",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      width: 1.5,
      "arrow-scale": 0.8,
      "font-size": 6,
      color: "#6b7280",
      "text-rotation": "autorotate",
      "text-outline-color": "#111827",
      "text-outline-width": 1,
      "text-margin-y": -8,
    },
  },
  {
    selector: "edge.highlighted",
    style: {
      "line-color": "#fbbf24",
      "target-arrow-color": "#fbbf24",
      width: 2.5,
    },
  },
];
/* eslint-enable @typescript-eslint/no-explicit-any */

export function GraphView({
  elements,
  highlightedIds,
  onNodeClick,
  onClear,
}: Props) {
  const cyRef = useRef<Core | null>(null);

  const handleCy = useCallback(
    (cy: Core) => {
      if (cyRef.current === cy) return;
      cyRef.current = cy;

      cy.on("tap", "node", (evt) => {
        const nodeId = evt.target.id();
        onNodeClick?.(nodeId);
      });
    },
    [onNodeClick],
  );

  // Apply highlight classes after render
  const applyHighlights = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("highlighted");
    highlightedIds.forEach((id) => {
      const node = cy.getElementById(id);
      if (node.length) {
        node.addClass("highlighted");
        // Also highlight connected edges
        node.connectedEdges().addClass("highlighted");
      }
    });
  }, [highlightedIds]);

  // Run highlights after elements update
  setTimeout(applyHighlights, 50);

  const nodeCount = elements.filter(
    (e) => !("source" in (e.data ?? {})),
  ).length;
  const edgeCount = elements.filter(
    (e) => "source" in (e.data ?? {}),
  ).length;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b bg-gray-900 text-sm">
        <span className="font-medium text-gray-300">
          Graph{" "}
          <span className="text-gray-500 font-normal">
            ({nodeCount} nodes, {edgeCount} edges)
          </span>
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => cyRef.current?.fit(undefined, 30)}
            className="px-2 py-0.5 text-xs bg-gray-800 hover:bg-gray-700 rounded"
          >
            Fit
          </button>
          <button
            onClick={onClear}
            className="px-2 py-0.5 text-xs bg-gray-800 hover:bg-gray-700 rounded text-red-400"
          >
            Clear
          </button>
        </div>
      </div>

      {elements.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
          Ask a question to see the graph
        </div>
      ) : (
        <CytoscapeComponent
          elements={elements}
          stylesheet={stylesheet}
          layout={
            {
              name: "cose",
              animate: false,
              padding: 40,
              nodeRepulsion: 8000,
              idealEdgeLength: 80,
              edgeElasticity: 100,
              gravity: 0.25,
            } as LayoutOptions
          }
          className="flex-1"
          cy={handleCy}
        />
      )}
    </div>
  );
}
