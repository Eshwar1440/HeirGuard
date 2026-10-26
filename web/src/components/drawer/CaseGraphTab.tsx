import CytoscapeComponent from 'react-cytoscapejs';
import type { NodeSingular, StylesheetStyle } from 'cytoscape';
import { Box, Stack, Typography } from '@mui/material';
import { useGraph } from '../../api/hooks';
import { ErrorCard } from '../common';
import { tokens as t } from '../../theme';

const TYPE_COLORS: Record<string, string> = {
  Decedent: t.navy, Person: t.navy, Account: t.navy, Designation: t.accent, Trust: t.accent,
  Document: t.muted, Fact: t.muted, Check: t.pass, PrefillField: t.amber,
};

const stylesheet: StylesheetStyle[] = [
  { selector: 'node', style: {
    shape: 'round-rectangle', 'background-color': '#fff', 'border-width': 1.5, 'border-color': (n: NodeSingular) => TYPE_COLORS[n.data('type')] ?? t.muted,
    label: (n: NodeSingular) => `${n.data('type') ?? ''}\n${n.data('label') ?? n.id()}`, 'text-wrap': 'wrap', 'text-valign': 'center', 'text-halign': 'center',
    'font-family': 'IBM Plex Sans', 'font-size': 10, color: t.ink, width: 'label', height: 'label', padding: '7px',
  } },
  { selector: 'node[status = "fail"]', style: { 'border-color': t.fail, 'border-width': 2 } },
  { selector: 'edge', style: {
    width: 1.5, 'line-color': '#8A97A6', 'target-arrow-color': '#8A97A6', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier',
    label: 'data(label)', 'font-family': 'IBM Plex Mono', 'font-size': 8, color: t.muted, 'text-background-color': t.panel, 'text-background-opacity': 1, 'text-background-padding': '2px',
  } },
  { selector: 'edge[status = "fail"]', style: { width: 3, 'line-color': t.fail, 'target-arrow-color': t.fail, color: t.fail } },
];

export default function CaseGraphTab({ caseId }: { caseId: string }) {
  const { data, isLoading, error, refetch } = useGraph(caseId);
  if (isLoading) return <Typography variant="body2">Loading the case graph…</Typography>;
  if (error) return <ErrorCard title="Couldn't load the case graph" message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data?.nodes?.length) return <Typography variant="body2">The graph is empty until documents are read.</Typography>;
  const failed = data.edges.filter((e) => e.data.status === 'fail').length;
  return (
    <Stack spacing={1.25} data-testid="tab-graph">
      <Typography variant="caption">GET /cases/{caseId}/graph · {data.nodes.length} nodes · {data.edges.length} edges{failed ? ` · ${failed} failed` : ''}</Typography>
      <Box sx={{ height: 440, bgcolor: t.panel, border: `1px solid ${t.rule}`, borderRadius: 1 }}>
        <CytoscapeComponent elements={CytoscapeComponent.normalizeElements(data)} stylesheet={stylesheet}
          layout={{ name: 'breadthfirst', directed: true, padding: 16, spacingFactor: 1.1 }} style={{ width: '100%', height: '100%' }} wheelSensitivity={0.2} />
      </Box>
      <Stack direction="row" spacing={2} sx={{ fontSize: 11.5, color: t.muted }}>
        <Stack direction="row" spacing={0.6} sx={{ alignItems: 'center' }}><Box sx={{ width: 16, height: 2, bgcolor: '#8A97A6' }} /><span>relationship</span></Stack>
        <Stack direction="row" spacing={0.6} sx={{ alignItems: 'center' }}><Box sx={{ width: 16, height: 3, bgcolor: t.fail }} /><span>status=fail</span></Stack>
      </Stack>
    </Stack>
  );
}
