import { Box, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import type { CaseState } from '../../api/types';
import { FILING_LABELS, formatMoney, formatPercent, toNumber } from '../../lib/format';
import { KeyValueRows, Mono } from '../common';
import { tokens as t } from '../../theme';

const factor = (v: string | null | undefined) => (v == null ? '—' : Number(v).toFixed(1));

export default function SimulatorTab({ caseState }: { caseState: CaseState }) {
  const sim = caseState.simulation;
  const inp = caseState.heir_inputs;
  const scenarios = caseState.scenarios ?? [];
  if (!inp || !sim) return <Typography variant="body2">The simulator runs after approval, when the heir compares options.</Typography>;
  const mins = scenarios.find((s) => s.name === 'minimums_then_balloon') ?? scenarios[0];
  const factors = Object.fromEntries(sim.factors.map((f) => [f.year, f]));
  const flags = [
    sim.rules.year_of_death_rmd_may_be_due && 'year_of_death_rmd_may_be_due',
    sim.rules.needs_specialist && 'needs_specialist',
  ].filter(Boolean) as string[];

  return (
    <Stack spacing={1.75} data-testid="tab-simulator">
      <KeyValueRows rows={[
        ['annual_income', formatMoney(inp.annual_income)],
        ['filing_status', FILING_LABELS[inp.filing_status] ?? inp.filing_status],
        ['state_tax_rate', formatPercent(inp.state_tax_rate, { fraction: true })],
        ['growth_rate', <>{formatPercent(inp.growth_rate, { fraction: true })} <span style={{ color: t.amberText }}>(hypothetical)</span></>],
        ...(inp.bracket_to_fill ? [['bracket_to_fill', formatPercent(inp.bracket_to_fill, { fraction: true })] as [string, string]] : []),
        ['balance (heir share)', <>{formatMoney(sim.balance, { cents: true })} <span style={{ color: t.amberText }}>(hypothetical)</span></>],
        ['beneficiary_class', <Mono>{sim.rules.beneficiary_class}</Mono>],
        ['annual minimums', sim.rules.annual_rmds_required ? 'required' : 'not required'],
        ['federal brackets', `${sim.tax_year} (IRS Rev. Proc. 2025-32)`],
      ]} />
      <Typography variant="body2">
        Table factors per year (Single Life Table, Pub. 590-B App. B). The longer of the heir's and decedent's divisors is used
        when the decedent died on or after the required beginning date.
      </Typography>
      {mins && (
        <Box sx={{ border: `1px solid ${t.rule}`, borderRadius: 1, overflow: 'hidden' }}>
          <Table size="small">
            <TableHead><TableRow sx={{ '& th': { bgcolor: t.navyPanel } }}>
              <TableCell>Year</TableCell><TableCell align="right">Heir</TableCell><TableCell align="right">Decedent</TableCell><TableCell align="right">Used</TableCell><TableCell align="right">Minimum</TableCell>
            </TableRow></TableHead>
            <TableBody>
              {mins.years.map((y) => {
                const f = factors[y.year];
                return (
                  <TableRow key={y.year}>
                    <TableCell>{y.year}</TableCell>
                    <TableCell align="right">{factor(f?.beneficiary_factor)}</TableCell>
                    <TableCell align="right" sx={{ color: t.muted }}>{factor(f?.decedent_factor)}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{factor(f?.divisor)}</TableCell>
                    <TableCell align="right">{toNumber(y.rmd_required) ? formatMoney(y.rmd_required, { cents: true }) : '—'}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Box>
      )}
      {!!flags.length && (
        <Box sx={{ fontSize: 12, color: t.amberText, bgcolor: t.callout, border: `1px solid ${t.calloutBorder}`, borderRadius: 1, px: 1.25, py: 1 }}>
          {flags.map((f) => <div key={f}>flag: <Mono>{f}</Mono></div>)}
        </Box>
      )}
    </Stack>
  );
}
