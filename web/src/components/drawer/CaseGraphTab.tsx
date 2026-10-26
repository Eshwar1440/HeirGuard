import CytoscapeComponent from 'react-cytoscapejs';
import type { NodeSingular, StylesheetStyle } from 'cytoscape';
import { useState } from 'react';
import { Box, FormControlLabel, Stack, Switch, Typography } from '@mui/material';
import { useGraph } from '../../api/hooks';
import type { CaseGraph } from '../../api/types';
import { ErrorCard } from '../common';
import { tokens as t } from '../../theme';

const TYPE_COLORS: Record<string, string> = {
  Decedent: t.navy, Person: t.navy, Account: t.navy, Designation: t.accent, Trust: t.accent,
  Document: t.muted, Fact: t.muted, Check: t.pass, PrefillField: t.amber,
};
const LEGEND: Record<string, string> = {
  'Person / account': t.navy, Designation: t.accent, 'Document / fact': t.muted, Check: t.pass, 'Prefill field': t.amber,
};

// Short captions keep nodes narrow, so the fitted graph stays legible; the border color gives the type.
const short = (s: string) => (s.length > 24 ? `${s.slice(0, 23)}…` : s);

const stylesheet: StylesheetStyle[] = [
  { selector: 'node', style: {
    shape: 'round-rectangle', 'background-color': '#fff', 'border-width': 2, 'border-color': (n: NodeSingular) => TYPE_COLORS[n.data('type')] ?? t.muted,
    label: (n: NodeSingular) => short(String(n.data('label') || n.data('type') || n.id())), 'text-valign': 'center', 'text-halign': 'center',
    'font-family': 'IBM Plex Sans', 'font-size': 13, color: t.ink, width: 'label', height: 'label', padding: '6px',
  } },
  { selector: 'node[status = "fail"]', style: { 'border-color': t.fail, 'border-width': 3 } },
  { selector: 'edge', style: {
    width: 1.5, 'line-color': '#8A97A6', 'target-arrow-color': '#8A97A6', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier',
    // Relationship names appear once zoomed in far enough to read them.
    label: 'data(label)', 'font-family': 'IBM Plex Mono', 'font-size': 9, 'min-zoomed-font-size': 8, color: t.muted,
    'text-background-color': t.panel, 'text-background-opacity': 1, 'text-background-padding': '2px',
  } },
  { selector: 'edge[status = "fail"]', style: { width: 3, 'line-color': t.fail, 'target-arrow-color': t.fail, color: t.fail } },
];

// Force-directed: a case graph has ~50 nodes (people, documents, one fact per field, checks),
// too many for one breadth-first row.
const LAYOUT = { name: 'cose', animate: false, fit: true, padding: 20, nodeRepulsion: () => 9000, idealEdgeLength: () => 70, componentSpacing: 80 };

/** Keep only the facts that matter: ones a failing check points at, and ones a prefill came from. */
function compact(g: CaseGraph): CaseGraph {
  const keep = new Set(g.edges
    .filter((e) => e.data.status === 'fail' || e.data.label === 'SOURCED_FROM')
    .flatMap((e) => [e.data.source, e.data.target]));
  const nodes = g.nodes.filter((n) => n.data.type !== 'Fact' || keep.has(n.data.id));
  const ids = new Set(nodes.map((n) => n.data.id));
  return { nodes, edges: g.edges.filter((e) => ids.has(e.data.source!) && ids.has(e.data.target!)) };
}

export default function CaseGraphTab({ caseId }: { caseId: string }) {
  const { data: full, isLoading, error, refetch } = useGraph(caseId);
  const [everyField, setEveryField] = useState(false);
  const data = full && !everyField ? compact(full) : full;
  if (isLoading) return <Typography variant="body2">Loading the case graph…</Typography>;
  if (error) return <ErrorCard title="Couldn't load the case graph" message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data?.nodes?.length) return <Typography variant="body2">The graph is empty until documents are read.</Typography>;
  const failed = data.edges.filter((e) => e.data.status === 'fail').length;
  return (
    <Stack spacing={1.25} data-testid="tab-graph">
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="caption">GET /cases/{caseId}/graph · {data.nodes.length} of {full!.nodes.length} nodes · {data.edges.length} edges{failed ? ` · ${failed} failed` : ''}</Typography>
        <FormControlLabel control={<Switch size="small" checked={everyField} onChange={(e) => setEveryField(e.target.checked)} />}
          label={<Typography variant="caption">Show every field</Typography>} sx={{ mr: 0 }} />
      </Stack>
      <Box sx={{ height: 560, bgcolor: t.panel, border: `1px solid ${t.rule}`, borderRadius: 1 }}>
        <CytoscapeComponent elements={CytoscapeComponent.normalizeElements(data)} stylesheet={stylesheet}
          key={everyField ? 'all' : 'compact'} layout={LAYOUT} style={{ width: '100%', height: '100%' }} wheelSensitivity={0.2} />
      </Box>
      <Stack direction="row" spacing={2} sx={{ fontSize: 11.5, color: t.muted }}>
        <Stack direction="row" spacing={0.6} sx={{ alignItems: 'center' }}><Box sx={{ width: 16, height: 2, bgcolor: '#8A97A6' }} /><span>relationship</span></Stack>
        <Stack direction="row" spacing={0.6} sx={{ alignItems: 'center' }}><Box sx={{ width: 16, height: 3, bgcolor: t.fail }} /><span>status=fail</span></Stack>
        <Box component="span" sx={{ ml: 'auto !important' }}>Scroll to zoom, drag to pan</Box>
      </Stack>
      <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap', fontSize: 11.5, color: t.muted }}>
        {Object.entries(LEGEND).map(([k, c]) => (
          <Stack key={k} direction="row" spacing={0.6} sx={{ alignItems: 'center' }}>
            <Box sx={{ width: 12, height: 10, border: `2px solid ${c}`, borderRadius: '3px', bgcolor: '#fff' }} /><span>{k}</span>
          </Stack>
        ))}
      </Stack>
    </Stack>
  );
}
