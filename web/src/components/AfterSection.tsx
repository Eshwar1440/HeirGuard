import { Box, Card, Chip, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import type { CaseState } from '../api/types';
import { formatDate, formatMoney, rmdDates, toNumber } from '../lib/format';
import { heirOf } from '../lib/case';
import { Placeholder, SectionHeader } from './common';
import { tokens as t } from '../theme';

function optInStatus(c: CaseState): boolean | null {
  const f = (c.prefill ?? []).find((p) => p.name === 'opt_in_rmd_deposit' || p.name === 'rmd_deposit_opt_in');
  if (!f) return null;
  return String(f.value).toLowerCase() === 'true' || String(f.value).toLowerCase() === 'yes';
}

export default function AfterSection({ caseState }: { caseState: CaseState }) {
  const done = caseState.choice === 'keep' && (caseState.prefill?.length ?? 0) > 0;
  const mins = (caseState.scenarios ?? []).find((s) => s.name === 'minimums_then_balloon');
  const optIn = optInStatus(caseState);
  const ben = heirOf(caseState);

  return (
    <Stack component="section" spacing={1.75} data-testid="after-section">
      <SectionHeader n="04" title="After" />
      {!done || !mins ? (
        <Placeholder>Your yearly minimums and reminders appear here once the inherited account is set up.</Placeholder>
      ) : (
        <Card sx={{ overflow: 'hidden' }}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', px: 2.5, py: 1.75, bgcolor: t.band, borderBottom: `1px solid ${t.rule}` }}>
            <Typography variant="subtitle1">Required minimum schedule{ben ? ` for ${ben.name.split(' ')[0]}` : ''}</Typography>
            <Chip size="small" data-testid="optin-status"
              label={optIn ? 'RMD deposit: opted in' : 'RMD deposit: not opted in · reminders only'}
              sx={{ bgcolor: optIn ? t.accentTint : t.rowRule, color: optIn ? t.accentText : t.body }} />
          </Stack>
          {caseState.simulation?.rules.year_of_death_rmd_may_be_due && (
            <Box sx={{ px: 2.5, py: 1.25, fontSize: 13, color: t.amberText, bgcolor: t.callout, borderBottom: `1px solid ${t.calloutBorder}` }}>
              A year-of-death minimum may still be due{caseState.decedent ? ` for ${caseState.decedent.date_of_death.slice(0, 4)}` : ''}. Estate operations confirms whether it was taken.
            </Box>
          )}
          <Table size="small">
            <TableHead>
              <TableRow sx={{ '& th': { bgcolor: '#fff', color: t.muted, borderBottom: `1px solid ${t.rule}` } }}>
                <TableCell sx={{ pl: 2.5 }}>Year</TableCell><TableCell align="right">Estimated minimum</TableCell><TableCell>Due by</TableCell><TableCell>Reminders</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mins.years.map((y, i) => {
                const d = rmdDates(y.year);
                const last = i === mins.years.length - 1;
                return (
                  <TableRow key={y.year}>
                    <TableCell sx={{ pl: 2.5, fontWeight: 500 }}>{y.year}</TableCell>
                    <TableCell align="right">{last ? 'Remaining balance' : toNumber(y.rmd_required) ? formatMoney(y.rmd_required) : '—'}</TableCell>
                    <TableCell>{formatDate(d.due, { short: true })}</TableCell>
                    <TableCell sx={{ color: t.body }}>{d.reminders.map((r) => formatDate(r, { short: true })).join(' and ')}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </Stack>
  );
}
