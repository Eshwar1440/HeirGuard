import { Badge, Box, Button, Drawer, LinearProgress, Stack, Tab, Tabs, Typography } from '@mui/material';
import type { CaseState } from '../api/types';
import { isReading } from '../api/hooks';
import { blockedAttempts, failCount } from '../lib/case';
import ExtractionTab from './drawer/ExtractionTab';
import RulesTab from './drawer/RulesTab';
import CaseGraphTab from './drawer/CaseGraphTab';
import SimulatorTab from './drawer/SimulatorTab';
import SafetyTab from './drawer/SafetyTab';
import AuditTab from './drawer/AuditTab';
import EstateOpsTab from './drawer/EstateOpsTab';
import { tokens as t } from '../theme';

export const DRAWER_WIDTH = 540;
export type DrawerTab = 'extraction' | 'rules' | 'graph' | 'simulator' | 'safety' | 'audit' | 'ops';

interface Props {
  open: boolean;
  onClose: () => void;
  tab: DrawerTab;
  onTab: (t: DrawerTab) => void;
  caseState?: CaseState | null;
  topOffset: number;
}

export default function UnderTheHood({ open, onClose, tab, onTab, caseState, topOffset }: Props) {
  const reading = isReading(caseState ?? undefined);
  const fails = failCount(caseState);
  const blocks = blockedAttempts(caseState).length;
  const waiting = caseState?.waiting_for === 'approval';

  const tabs: { key: DrawerTab; label: string; badge?: number; color?: 'error' | 'warning' | 'secondary' }[] = [
    { key: 'extraction', label: 'Extraction' },
    { key: 'rules', label: 'Rules', badge: fails, color: 'error' },
    { key: 'graph', label: 'Case graph' },
    { key: 'simulator', label: 'Simulator' },
    { key: 'safety', label: 'Safety', badge: blocks, color: 'warning' },
    { key: 'audit', label: 'Audit' },
    { key: 'ops', label: 'Estate ops', badge: waiting ? 1 : 0, color: 'secondary' },
  ];

  return (
    <Drawer variant="persistent" anchor="right" open={open} data-testid="under-the-hood"
      slotProps={{ paper: { sx: { width: DRAWER_WIDTH, top: topOffset, height: `calc(100% - ${topOffset}px)`, borderLeft: `1px solid ${t.inputBorder}` } } }}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', px: 2.5, py: 1.75, bgcolor: t.navyPanel, flex: 'none' }}>
        <Box>
          <Typography sx={{ fontSize: 15, fontWeight: 600, color: '#fff' }}>Under the hood</Typography>
          <Typography sx={{ fontSize: 12, color: '#B8C7D6' }}>Every AI step and check for this case</Typography>
        </Box>
        <Button size="small" onClick={onClose} sx={{ color: '#fff', border: '1px solid rgba(255,255,255,.3)' }}>Close</Button>
      </Stack>
      <Tabs value={tab} onChange={(_, v) => onTab(v)} variant="scrollable" scrollButtons={false}
        sx={{ px: 1.5, bgcolor: t.band, borderBottom: `1px solid ${t.rule}`, flex: 'none' }}>
        {tabs.map((x) => (
          <Tab key={x.key} value={x.key} data-testid={`tab-btn-${x.key}`}
            label={x.badge ? <Badge badgeContent={x.badge} color={x.color} sx={{ '& .MuiBadge-badge': { position: 'static', transform: 'none', ml: 0.75 } }}>{x.label}</Badge> : x.label}
            sx={{ fontWeight: tab === x.key ? 600 : 500, color: tab === x.key ? `${t.navy} !important` : t.muted }} />
        ))}
      </Tabs>
      <Box sx={{ flex: 1, overflowY: 'auto', px: 2.5, pt: 2.25, pb: 3 }}>
        {!caseState ? (
          <Typography variant="body2" sx={{ textAlign: 'center', py: 5 }}>Start a case to see each step here.</Typography>
        ) : reading && (tab === 'extraction' || tab === 'rules' || tab === 'graph') ? (
          <Stack spacing={1.25}>
            <Typography variant="body2">Running <code>read_documents</code>. Results appear when reading finishes.</Typography>
            <LinearProgress color="secondary" />
          </Stack>
        ) : (
          <>
            {tab === 'extraction' && <ExtractionTab caseState={caseState} />}
            {tab === 'rules' && <RulesTab caseState={caseState} />}
            {tab === 'graph' && <CaseGraphTab caseId={caseState.case_id} />}
            {tab === 'simulator' && <SimulatorTab caseState={caseState} />}
            {tab === 'safety' && <SafetyTab caseState={caseState} />}
            {tab === 'audit' && <AuditTab caseId={caseState.case_id} />}
            {tab === 'ops' && <EstateOpsTab caseState={caseState} />}
          </>
        )}
      </Box>
    </Drawer>
  );
}
