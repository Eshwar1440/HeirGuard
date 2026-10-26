import { Card, Step, StepLabel, Stepper, Typography } from '@mui/material';
import { STAGES } from '../lib/case';
import { tokens as t } from '../theme';

export default function ProgressTracker({ active }: { active: number }) {
  return (
    <Card sx={{ px: 2.75, py: 2.25 }} data-testid="progress-tracker">
      <Stepper activeStep={active} alternativeLabel>
        {STAGES.map((s, i) => (
          <Step key={s.label} completed={i < active}>
            <StepLabel optional={<Typography variant="caption" sx={{ display: 'block', textAlign: 'center' }}>{s.caption}</Typography>}
              sx={{ '& .MuiStepLabel-label': { fontSize: 13, whiteSpace: 'nowrap', mt: '6px !important', fontWeight: i === active ? 600 : 500, color: i === active ? t.navy : t.ink } }}>
              {s.label}
            </StepLabel>
          </Step>
        ))}
      </Stepper>
    </Card>
  );
}
