import { useState } from 'react';
import { Box, Button, Card, Stack, Typography } from '@mui/material';
import type { CaseState, Choice } from '../api/types';
import { useChoice } from '../api/hooks';
import KeepDialog from './KeepDialog';
import { Placeholder, SectionHeader } from './common';
import { tokens as t } from '../theme';

const CARDS: { key: Choice; title: string; body: string; note: string }[] = [
  { key: 'keep', title: 'Keep at Schwab', body: 'Open an inherited IRA with your share. The application is prefilled from your verified documents, and you review every field.', note: 'Application prepared.' },
  { key: 'talk', title: 'Talk to a professional', body: 'Share this summary with a tax professional or advisor before deciding. Nothing moves until you choose.', note: 'A shareable summary is ready. Your options stay open.' },
  { key: 'transfer', title: 'Transfer out', body: 'Move your share to another firm with a trustee-to-trustee transfer. The paperwork is prepared for you and nothing is held.', note: 'Transfer paperwork is ready. Your options stay open.' },
];

export default function NextStep({ caseState }: { caseState: CaseState }) {
  const choice = useChoice(caseState.case_id);
  const [dialog, setDialog] = useState(false);
  const ready = (caseState.scenarios?.length ?? 0) > 0 && caseState.waiting_for === 'choice';

  return (
    <Stack component="section" spacing={1.75} data-testid="next-step">
      <SectionHeader n="03" title="Next step" />
      {!ready ? <Placeholder>Available after you compare your options.</Placeholder> : (
        <>
          {/* Equal weight by design (AGENTS.md rule 8): same card, same button style, no default. */}
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 2 }}>
            {CARDS.map((c) => {
              const on = caseState.choice === c.key;
              return (
                <Card key={c.key} sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.25, borderColor: on ? t.accent : t.rule, boxShadow: on ? `0 0 0 2px ${t.accent}` : 'none' }}>
                  <Typography variant="h3">{c.title}</Typography>
                  <Typography variant="body2" sx={{ flex: 1, textWrap: 'pretty' }}>{c.body}</Typography>
                  {on && <Box sx={{ fontSize: 12.5, color: t.accentText, bgcolor: t.accentTint, borderRadius: 1, px: 1.25, py: 1 }}>{c.note}</Box>}
                  <Button variant="outlined" data-testid={`choice-${c.key}`} disabled={choice.isPending}
                    onClick={() => (c.key === 'keep' ? setDialog(true) : choice.mutate({ choice: c.key, opt_in_rmd_deposit: false }))}
                    sx={{ mt: 0.5, py: 1.1, fontWeight: 600, '&:hover': { bgcolor: t.navy, color: '#fff' } }}>
                    {c.title}
                  </Button>
                </Card>
              );
            })}
          </Box>
          <Typography variant="caption">All three choices are available at any time. Transfers out are never held up.</Typography>
        </>
      )}
      <KeepDialog caseState={caseState} open={dialog} onClose={() => setDialog(false)} />
    </Stack>
  );
}
