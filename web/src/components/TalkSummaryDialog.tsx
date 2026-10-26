import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import type { CaseState } from '../api/types';
import { FOOTER_TEXT, SPECIALIST_HOURS, SPECIALIST_PHONE } from '../config';
import { heirOf, optionsSummary, summaryPoints } from '../lib/case';
import { ACCOUNT_TYPE_LABELS, FILING_LABELS, formatDate, formatMoney, formatPercent, plainValue, scenarioLabel } from '../lib/format';
import { KeyValueRows, SummaryPoints } from './common';
import { tokens as t } from '../theme';

/**
 * What "Talk to a professional" hands over: the heir's own numbers, the rule that applies,
 * the four options and the assumptions, ready to print or save as a PDF. Every figure comes
 * from the API; nothing is computed here.
 */
export default function TalkSummaryDialog({ caseState, open, onClose }: { caseState: CaseState; open: boolean; onClose: () => void }) {
  const heir = heirOf(caseState);
  const account = (caseState.accounts ?? [])[0];
  const sim = caseState.simulation;
  const inputs = caseState.heir_inputs;
  const points = summaryPoints(optionsSummary(caseState)?.text);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <Dialog open={open} onClose={onClose} maxWidth={false} slotProps={{ paper: { sx: { width: 720 } } }} data-testid="talk-summary">
      <DialogTitle sx={{ pb: 0.5 }}>
        <Typography variant="h3" component="div" sx={{ fontSize: 21 }}>Summary for your tax professional</Typography>
        <Typography variant="body2" sx={{ color: t.muted, mt: 0.5 }}>
          Prepared {formatDate(today)}. Estimates for comparison, not tax advice. All figures are hypothetical.
        </Typography>
      </DialogTitle>
      <DialogContent dividers sx={{ px: 3, py: 2, display: 'flex', flexDirection: 'column', gap: 2.25 }}>
        <Box sx={{ bgcolor: t.accentTint, border: `1px solid ${t.accentBorder}`, borderRadius: 1, px: 2, py: 1.5 }} data-testid="specialist-phone">
          <Typography sx={{ fontWeight: 600, color: t.accentText }}>Talk to an inheritance specialist: {SPECIALIST_PHONE}</Typography>
          <Typography variant="caption">{SPECIALIST_HOURS}. Hypothetical number and hours for this prototype. Bring this summary to the call.</Typography>
        </Box>
        <Section title="The inheritance">
          <KeyValueRows rows={[
            ['Account owner', caseState.decedent?.name ?? '—'],
            ['Date of death', formatDate(caseState.decedent?.date_of_death)],
            ['Account', account ? `${account.title} (${ACCOUNT_TYPE_LABELS[account.type] ?? account.type})` : '—'],
            ['Beneficiary', heir ? `${heir.name}, ${plainValue('relationship', heir.relationship).toLowerCase()} of the owner` : '—'],
            ['Share', heir ? `${formatPercent(heir.share_percent)}${sim ? `, about ${formatMoney(sim.balance, { cents: true })}` : ''}` : '—'],
          ]} />
        </Section>

        {sim && <Section title="The rule that applies"><Typography variant="body2">{sim.rules.summary}</Typography></Section>}

        {inputs && (
          <Section title="Inputs used">
            <KeyValueRows rows={[
              ['Annual income', formatMoney(inputs.annual_income)],
              ['Filing status', FILING_LABELS[inputs.filing_status] ?? inputs.filing_status],
              ['State tax rate', formatPercent(inputs.state_tax_rate, { fraction: true })],
              ['Growth rate', formatPercent(inputs.growth_rate, { fraction: true })],
            ]} />
          </Section>
        )}

        {caseState.scenarios.length > 0 && (
          <Section title="The four options">
            <Box sx={{ border: `1px solid ${t.rule}`, borderRadius: 1, overflow: 'hidden' }}>
              <Table size="small">
                <TableHead><TableRow>
                  <TableCell>Option</TableCell><TableCell align="right">Estimated total tax</TableCell><TableCell align="right">Kept after tax</TableCell>
                </TableRow></TableHead>
                <TableBody>
                  {caseState.scenarios.map((s) => (
                    <TableRow key={s.name}>
                      <TableCell>{scenarioLabel(s.name)}</TableCell>
                      <TableCell align="right">{formatMoney(s.total_tax, { cents: true })}</TableCell>
                      <TableCell align="right">{formatMoney(s.after_tax_total, { cents: true })}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
            {points.length > 0 && (
              <Box sx={{ mt: 1.5 }}><SummaryPoints points={points} size={13.5} /></Box>
            )}
          </Section>
        )}

        {!!sim?.assumptions.length && (
          <Section title={`Assumptions (${sim.tax_year} federal brackets)`}>
            <Box component="ul" sx={{ m: 0, pl: 2.25, '& li': { fontSize: 12.5, lineHeight: 1.5, color: t.muted } }}>
              {sim.assumptions.map((a) => <li key={a}>{a}</li>)}
            </Box>
          </Section>
        )}

        <Typography variant="caption">{FOOTER_TEXT}</Typography>
      </DialogContent>
      <DialogActions className="no-print" sx={{ px: 3, py: 1.75, bgcolor: t.panel }}>
        <Button variant="outlined" onClick={onClose} sx={{ borderColor: t.inputBorder, borderWidth: 1 }}>Close</Button>
        <Button variant="contained" onClick={() => window.print()} data-testid="print-summary">Print or save as PDF</Button>
      </DialogActions>
    </Dialog>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="overline" component="div" sx={{ mb: 0.75 }}>{title}</Typography>
      {children}
    </Box>
  );
}
