interface Props {
  nodeId: string | null;
  onClose: () => void;
}

export function NodeDetail({ nodeId, onClose }: Props) {
  if (!nodeId) return null;

  return (
    <div className="absolute bottom-0 left-0 right-0 bg-gray-900 border-t px-4 py-3 z-10">
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-sm text-gray-200">{nodeId}</span>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-300 text-sm px-2"
        >
          x
        </button>
      </div>
      <p className="text-xs text-gray-500">
        Click &quot;Send&quot; with a question about this entity to see details.
      </p>
    </div>
  );
}
