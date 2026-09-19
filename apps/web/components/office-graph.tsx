"use client";

import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const miraStyle = {
  background: "#C4A574",
  color: "#0A0E14",
  border: "none",
  borderRadius: 999,
  padding: 12,
  fontFamily: "Newsreader, serif",
  fontSize: 16,
};

const roleStyle = {
  background: "#161D27",
  color: "#E8E4DC",
  border: "1px solid #243040",
  borderRadius: 12,
  padding: 10,
  fontSize: 13,
};

const engineStyle = {
  background: "#10151C",
  color: "#7D9B78",
  border: "1px dashed #7D9B78",
  borderRadius: 12,
  padding: 10,
  width: 280,
  fontSize: 12,
};

const nodes: Node[] = [
  { id: "mira", position: { x: 320, y: 40 }, data: { label: "Mira · Digital CFO" }, style: miraStyle },
  { id: "ap", position: { x: 40, y: 220 }, data: { label: "AP / AR specialist" }, style: roleStyle },
  { id: "proc", position: { x: 220, y: 220 }, data: { label: "Procurement" }, style: roleStyle },
  { id: "treas", position: { x: 400, y: 220 }, data: { label: "Treasury" }, style: roleStyle },
  { id: "ctrl", position: { x: 40, y: 340 }, data: { label: "Controller" }, style: roleStyle },
  { id: "audit", position: { x: 580, y: 220 }, data: { label: "Auditor" }, style: roleStyle },
  { id: "fpna", position: { x: 310, y: 360 }, data: { label: "FP&A / Board" }, style: roleStyle },
  {
    id: "engines",
    position: { x: 250, y: 500 },
    data: { label: "Deterministic engines (math, match, risk, policy)" },
    style: engineStyle,
  },
];

const edges: Edge[] = [
  { id: "e1", source: "mira", target: "ap", animated: true },
  { id: "e2", source: "mira", target: "proc", animated: true },
  { id: "e3", source: "mira", target: "treas", animated: true },
  { id: "e4", source: "mira", target: "audit", animated: true },
  { id: "e11", source: "mira", target: "ctrl", animated: true },
  { id: "e5", source: "mira", target: "fpna" },
  { id: "e6", source: "ap", target: "engines" },
  { id: "e7", source: "proc", target: "engines" },
  { id: "e8", source: "treas", target: "engines" },
  { id: "e9", source: "audit", target: "engines" },
  { id: "e12", source: "ctrl", target: "engines" },
  { id: "e10", source: "fpna", target: "engines" },
];

export function OfficeGraph() {
  return (
    <div className="h-[560px] overflow-hidden rounded-2xl border border-line bg-paper">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <MiniMap pannable style={{ background: "#10151C" }} maskColor="rgba(10,14,20,0.6)" />
        <Controls />
        <Background color="#243040" gap={18} />
      </ReactFlow>
    </div>
  );
}
