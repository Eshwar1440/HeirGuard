import { BarChart } from '@mui/x-charts/BarChart';
import { Box, Stack } from '@mui/material';
import type { Scenario } from '../api/types';
import { formatMoney, scenarioLabel, toNumber } from '../lib/format';
import { tokens as t } from '../theme';

interface Props { scenarios: Scenario[]; selected: string; onSelect: (name: string) => void; variant?: 'grouped' | 'stacked' }

export default function ScenarioChart({ scenarios, selected, onSelect, variant = 'grouped' }: Props) {
  const names = scenarios.map((s) => scenarioLabel(s.name));
  const tax = scenarios.map((s) => toNumber(s.total_tax) ?? 0);
  const kept = scenarios.map((s) => toNumber(s.after_tax_total) ?? 0);

  return (
    <Stack spacing={1}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ fontSize: 15, fontWeight: 600, color: t.navy }}>Estimated total tax and amount kept</Box>
        <Stack direction="row" spacing={2} sx={{ fontSize: 12.5, color: t.body }}>
          <Legend color={t.amberBar} label="Total tax" />
          <Legend color={t.accent} label="Amount kept" />
        </Stack>
      </Stack>
      <BarChart
        height={variant === 'stacked' ? 230 : 280}
        layout={variant === 'stacked' ? 'horizontal' : 'vertical'}
        {...(variant === 'stacked'
          ? { yAxis: [{ scaleType: 'band' as const, data: names, width: 170 }], xAxis: [{ valueFormatter: (v: number) => formatMoney(v) }] }
          : { xAxis: [{ scaleType: 'band' as const, data: names }], yAxis: [{ valueFormatter: (v: number) => formatMoney(v), width: 80 }] })}
        series={[
          { data: tax, label: 'Total tax', color: t.amberBar, valueFormatter: (v) => formatMoney(v), ...(variant === 'stacked' ? { stack: 'total' } : {}) },
          { data: kept, label: 'Amount kept', color: t.accent, valueFormatter: (v) => formatMoney(v), ...(variant === 'stacked' ? { stack: 'total' } : {}) },
        ]}
        hideLegend
        onAxisClick={(_, d) => { if (d?.dataIndex !== undefined) onSelect(scenarios[d.dataIndex].name); }}
        grid={variant === 'stacked' ? { vertical: true } : { horizontal: true }}
      />
      <Box sx={{ fontSize: 12, color: t.muted }}>Selected: {scenarioLabel(selected)}. Click a scenario to show its schedule.</Box>
    </Stack>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}><Box sx={{ width: 10, height: 10, bgcolor: color, borderRadius: '2px' }} /><span>{label}</span></Stack>;
}
