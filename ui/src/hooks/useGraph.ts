import { useCallback, useState } from "react";
import type { TraceResponse } from "../types";
import type { ElementDefinition } from "cytoscape";

const NODE_STYLES: Record<string, { color: string; shape: string }> = {
  VENDOR: { color: "#3B82F6", shape: "roundrectangle" },
  MATERIAL: { color: "#10B981", shape: "ellipse" },
  PURCHASE_ORDER: { color: "#F97316", shape: "rectangle" },
  CONTRACT: { color: "#8B5CF6", shape: "diamond" },
  INVOICE: { color: "#EF4444", shape: "rectangle" },
  GOODS_RECEIPT: { color: "#14B8A6", shape: "hexagon" },
  PAYMENT: { color: "#F59E0B", shape: "ellipse" },
  PLANT: { color: "#6B7280", shape: "triangle" },
  CATEGORY: { color: "#EC4899", shape: "roundrectangle" },
  PURCHASE_REQ: { color: "#06B6D4", shape: "rectangle" },
};

function entityType(id: string): string {
  if (id.startsWith("VND-")) return "VENDOR";
  if (id.startsWith("MAT-")) return "MATERIAL";
  if (id.startsWith("PO-")) return "PURCHASE_ORDER";
  if (id.startsWith("CTR-")) return "CONTRACT";
  if (id.startsWith("INV-")) return "INVOICE";
  if (id.startsWith("GR-")) return "GOODS_RECEIPT";
  if (id.startsWith("PAY-")) return "PAYMENT";
  if (id.startsWith("PR-")) return "PURCHASE_REQ";
  if (/^[A-Z]{2}\d{2}$/.test(id)) return "PLANT";
  if (/^[A-Z]{4}/.test(id)) return "CATEGORY";
  return "UNKNOWN";
}

export function useGraph() {
  const [elements, setElements] = useState<ElementDefinition[]>([]);
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());

  const addFromTrace = useCallback((trace: TraceResponse) => {
    setElements((prev) => {
      const existingNodeIds = new Set(
        prev.filter((e) => !("source" in (e.data ?? {}))).map((e) => e.data.id),
      );
      const existingEdgeIds = new Set(
        prev.filter((e) => "source" in (e.data ?? {})).map((e) => e.data.id),
      );

      const newElements: ElementDefinition[] = [...prev];
      const newIds = new Set<string>();

      // Add nodes
      for (const nodeId of trace.graph_nodes) {
        if (!existingNodeIds.has(nodeId)) {
          const type = entityType(nodeId);
          const style = NODE_STYLES[type] ?? {
            color: "#9CA3AF",
            shape: "ellipse",
          };
          newElements.push({
            data: {
              id: nodeId,
              label: nodeId,
              entityType: type,
              color: style.color,
              shape: style.shape,
            },
          });
          existingNodeIds.add(nodeId);
        }
        newIds.add(nodeId);
      }

      // Add edges
      for (const edge of trace.graph_edges) {
        const edgeId = `${edge.source}-${edge.edge_type}-${edge.target}`;
        if (
          !existingEdgeIds.has(edgeId) &&
          existingNodeIds.has(edge.source) &&
          existingNodeIds.has(edge.target)
        ) {
          newElements.push({
            data: {
              id: edgeId,
              source: edge.source,
              target: edge.target,
              label: edge.edge_type,
            },
          });
          existingEdgeIds.add(edgeId);
        }
      }

      return newElements;
    });

    setHighlightedIds(new Set(trace.graph_nodes));
  }, []);

  const clear = useCallback(() => {
    setElements([]);
    setHighlightedIds(new Set());
  }, []);

  return { elements, highlightedIds, addFromTrace, clear, nodeStyles: NODE_STYLES };
}
