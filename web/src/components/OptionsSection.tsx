import { useEffect, useState } from 'react';
import { Box, Button, Card, InputAdornment, MenuItem, Stack, TextField, Typography } from '@mui/material';
import type { CaseState, FilingStatus, HeirInputs } from '../api/types';
import { useSimulate } from '../api/hooks';
import { heirOf, optionsSummary } from '../lib/case';
import { FILING_LABELS, formatMoney, formatPercent } from '../lib/format';
import ScenarioChart from './ScenarioChart';
import ScheduleTable from './ScheduleTable';
import { Banner, ErrorCard, HypotheticalChip, Placeholder, SectionHeader } from './common';
import { tokens as t } from '../theme';

interface Props { caseState: CaseState; chartVariant?: 'grouped' | 'stacked' }

export default function OptionsSection({ caseState, chartVariant }: Props) {
  const id = caseState.case_id;
  const sim = useSimulate(id);
  const simulation = caseState.simulation;
  const existing = caseState.heir_inputs;

  const [income, setIncome] = useState(String(existing?.annual_income ?? ''));
  const [filing, setFiling] = useState<FilingStatus>((existing?.filing_status as FilingStatus) ?? 'single');
  const [stateRate, setStateRate] = useState(existing?.state_tax_rate ? String(Number(existing.state_tax_rate) * 100) : '');
  // Empty growth means "use the backend's hypothetical default" (config.DEFAULT_GROWTH_RATE).
  const [growth, setGrowth] = useState(existing?.growth_rate ? String(Number(existing.growth_rate) * 100) : '');
  const [selected, setSelected] = useState('even_spread');

  const scenarios = caseState.scenarios ?? [];
  const summary = optionsSummary(caseState)?.text;
  useEffect(() => {
    if (scenarios.length && !scenarios.some((s) => s.name === selected)) setSelected(scenarios[0].name);
  }, [scenarios, selected]);

  const heir = heirOf(caseState);
  const balance = (caseState.accounts ?? [])[0]?.balance;
  const share = heir?.share_percent;
  const incomeOk = income.trim() !== '' && !Number.isNaN(Number(income.replace(/[,$]/g, '')));
  const ready = caseState.waiting_for === 'heir_inputs' || caseState.waiting_for === 'choice';

  function run() {
    const inputs: HeirInputs = {
      annual_income: income.replace(/[,$]/g, ''),
      filing_status: filing,
      state_tax_rate: stateRate ? String(Number(stateRate) / 100) : '0',
      ...(growth ? { growth_rate: String(Number(growth) / 100) } : {}),
    } as HeirInputs;
    sim.mutate(inputs);
  }

  if (!caseState.approved) {
    return (
      <Stack component="section" spacing={1.75}>
        <SectionHeader n="02" title="Your options" />
        <Placeholder>Unlocks after estate operations approves the documents.</Placeholder>
      </Stack>
    );
  }

  const divisors = simulation?.rules.annual_rmds_required
    ? Object.fromEntries(simulation.factors.map((f) => [f.year, Number(f.divisor)]))
    : undefined;

  return (
    <Stack component="section" spacing={1.75} data-testid="options-section">
      <SectionHeader n="02" title="Your options" />
      <Card sx={{ overflow: 'hidden' }}>
        <Box sx={{ bgcolor: t.band, borderBottom: `1px solid ${t.rule}`, px: 2.75, py: 2 }}>
          {balance && (
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1.75, fontSize: 13, color: t.muted }}>
              <span>
                Account balance <strong style={{ color: t.ink }}>{formatMoney(balance, { cents: true })}</strong>
                {heir && share ? ` · ${heir.name.split(' ')[0]}'s share ${formatPercent(share)}` : ''}
                {simulation ? <> · simulated on <strong style={{ color: t.ink }}>{formatMoney(simulation.balance, { cents: true })}</strong></> : ''}
              </span>
              <HypotheticalChip />
            </Stack>
          )}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1.2fr 1.3fr 1fr 1fr auto', gap: 1.75, alignItems: 'end' }}>
            <TextField label="Annual income" size="small" value={income} onChange={(e) => setIncome(e.target.value)}
              slotProps={{
                htmlInput: { inputMode: 'decimal', 'data-testid': 'input-income' },
                input: { startAdornment: <InputAdornment position="start">$</InputAdornment> },
              }} />
            <TextField select label="Filing status" size="small" value={filing} onChange={(e) => setFiling(e.target.value as FilingStatus)}>
              {Object.entries(FILING_LABELS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <TextField label="State tax rate (optional)" size="small" value={stateRate} onChange={(e) => setStateRate(e.target.value)} placeholder="0"
              slotProps={{ input: { endAdornment: <InputAdornment position="end">%</InputAdornment> } }} />
            <TextField size="small" value={growth} onChange={(e) => setGrowth(e.target.value)} placeholder="default"
              label={<Stack direction="row" spacing={0.75} component="span" sx={{ alignItems: 'center' }}><span>Growth</span><HypotheticalChip small /></Stack>}
              slotProps={{ input: { endAdornment: <InputAdornment position="end">%/yr</InputAdornment> } }} />
            <Button variant="contained" onClick={run} disabled={!incomeOk || !ready || sim.isPending} data-testid="compare-options" sx={{ py: 1.1 }}>
              {sim.isPending ? 'Comparing…' : scenarios.length ? 'Update' : 'Compare options'}
            </Button>
          </Box>
        </Box>

        {sim.isError && <Box sx={{ p: 2.75 }}><ErrorCard title="We couldn't compare options" message={(sim.error as Error).message} onRetry={run} /></Box>}

        {!scenarios.length && !sim.isError && !simulation && (
          <Typography variant="body2" sx={{ textAlign: 'center', py: 5, color: t.muted }}>
            Enter your income and filing status, then compare the four ways to take the money out.
          </Typography>
        )}

        {!scenarios.length && simulation && (
          <Box sx={{ p: 2.75 }}>
            <Banner tone="amber"><Box sx={{ color: t.ink }}>{simulation.rules.summary}</Box></Banner>
          </Box>
        )}

        {scenarios.length > 0 && (
          <Stack spacing={2.25} sx={{ p: 2.75 }}>
            {simulation?.rules.summary && (
              <Banner tone="amber">
                <Typography variant="overline" component="div" sx={{ color: t.amberText }}>The rule that applies</Typography>
                <Box sx={{ color: t.ink }}>{simulation.rules.summary}</Box>
              </Banner>
            )}
            <ScenarioChart scenarios={scenarios} selected={selected} onSelect={setSelected} variant={chartVariant} />
            {summary && (
              <Box sx={{ borderLeft: `3px solid ${t.accent}`, pl: 2, py: 0.5 }} data-testid="options-summary">
                <Typography variant="overline" component="div">In plain English</Typography>
                <Typography sx={{ maxWidth: 760, textWrap: 'pretty' }}>{summary}</Typography>
              </Box>
            )}
            <ScheduleTable scenarios={scenarios} selected={selected} onSelect={setSelected} divisors={divisors} />
            {!!simulation?.assumptions.length && (
              <Box sx={{ fontSize: 12.5, lineHeight: 1.55, color: t.muted, bgcolor: t.panel, border: `1px solid ${t.rowRule}`, borderRadius: 1, px: 1.75, py: 1.25 }}>
                <strong style={{ color: t.body }}>Assumptions ({simulation.tax_year} federal brackets).</strong> {simulation.assumptions.join(' ')}
              </Box>
            )}
          </Stack>
        )}
      </Card>
    </Stack>
  );
}
