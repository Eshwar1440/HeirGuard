import { Box, Chip, Stack, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material';
import type { Scenario } from '../api/types';
import { formatMoney, scenarioLabel, toNumber } from '../lib/format';
import { tokens as t } from '../theme';

interface Props {
  scenarios: Scenario[];
  selected: string;
  onSelect: (name: string) => void;
  divisors?: Record<number, number>;
}

export default function ScheduleTable({ scenarios, selected, onSelect, divisors }: Props) {
  const s = scenarios.find((x) => x.name === selected) ?? scenarios[0];
  if (!s) return null;
  const sum = (k: 'withdrawal' | 'incremental_federal_tax' | 'state_tax') => s.years.reduce((a, y) => a + (toNumber(y[k]) ?? 0), 0);
  return (
    <Stack spacing={1.25} data-testid="schedule-table">
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ fontSize: 15, fontWeight: 600, color: t.navy }}>Year-by-year schedule</Box>
        <Stack direction="row" spacing={0.75}>
          {scenarios.map((x) => {
            const on = x.name === s.name;
            return <Chip key={x.name} label={scenarioLabel(x.name)} onClick={() => onSelect(x.name)}
              sx={{ fontWeight: 500, fontSize: 12.5, bgcolor: on ? t.navy : '#fff', color: on ? '#fff' : t.body, border: `1px solid ${on ? t.navy : t.inputBorder}`, '&:hover': { bgcolor: on ? t.navy : t.band } }} />;
          })}
        </Stack>
      </Stack>
      <Box sx={{ border: `1px solid ${t.rule}`, borderRadius: 1, overflow: 'hidden' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Year</TableCell>
              {divisors && <TableCell align="right">Divisor</TableCell>}
              <TableCell align="right">Minimum required</TableCell>
              <TableCell align="right">Withdrawal</TableCell>
              <TableCell align="right">Federal tax</TableCell>
              <TableCell align="right">State tax</TableCell>
              <TableCell align="right">Year-end balance</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {s.years.map((y, i) => (
              <TableRow key={y.year} sx={{ bgcolor: i % 2 ? '#FAFBFC' : '#fff' }}>
                <TableCell sx={{ fontWeight: 500 }}>{y.year}</TableCell>
                {divisors && <TableCell align="right" sx={{ color: t.muted }}>{divisors[y.year]?.toFixed(1) ?? '—'}</TableCell>}
                <TableCell align="right">{toNumber(y.rmd_required) ? formatMoney(y.rmd_required) : '—'}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(y.withdrawal)}</TableCell>
                <TableCell align="right">{formatMoney(y.incremental_federal_tax)}</TableCell>
                <TableCell align="right">{formatMoney(y.state_tax)}</TableCell>
                <TableCell align="right">{formatMoney(y.end_balance)}</TableCell>
              </TableRow>
            ))}
            <TableRow sx={{ bgcolor: t.band, '& td': { fontWeight: 600, borderTop: `1px solid ${t.inputBorder}` } }}>
              <TableCell>Total</TableCell>
              {divisors && <TableCell />}
              <TableCell />
              <TableCell align="right">{formatMoney(sum('withdrawal'))}</TableCell>
              <TableCell align="right">{formatMoney(sum('incremental_federal_tax'))}</TableCell>
              <TableCell align="right">{formatMoney(sum('state_tax'))}</TableCell>
              <TableCell />
            </TableRow>
          </TableBody>
        </Table>
      </Box>
    </Stack>
  );
}
