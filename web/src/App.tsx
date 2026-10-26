import { useEffect, useState } from 'react';
import { AppBar, Box, Button, Card, Stack, Switch, Toolbar, Typography } from '@mui/material';
import { useCase, useCreateCase } from './api/hooks';
import { APP_NAME, DEMO_SAMPLES, FOOTER_TEXT } from './config';
import { activeStage, failCount } from './lib/case';
import { formatMoney } from './lib/format';
import ProgressTracker from './components/ProgressTracker';
import ReadingProgress from './components/ReadingProgress';
import DocumentsSection from './components/DocumentsSection';
import OptionsSection from './components/OptionsSection';
import NextStep from './components/NextStep';
import AfterSection from './components/AfterSection';
import UnderTheHood, { DRAWER_WIDTH, type DrawerTab } from './components/UnderTheHood';
import { ErrorCard, HypotheticalChip } from './components/common';
import { tokens as t } from './theme';

const APPBAR_H = 63; // 60 + 3px accent border
const CASEBAR_H = 52;

export default function App() {
  const [caseId, setCaseId] = useState<string | null>(() => new URLSearchParams(location.search).get('case'));
  const [sampleId, setSampleId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tab, setTab] = useState<DrawerTab>('extraction');

  const create = useCreateCase();
  const caseQ = useCase(caseId);
  const c = caseQ.data;

  useEffect(() => {
    const u = new URL(location.href);
    if (caseId) u.searchParams.set('case', caseId); else u.searchParams.delete('case');
    history.replaceState(null, '', u);
  }, [caseId]);

  // POST /cases reads and checks the packet before it answers, so the reading view
  // shows while that request is in flight. Failures open the drawer's Rules tab.
  async function start(sample: string) {
    setSampleId(sample);
    setCaseId(null);
    setTab('extraction');
    const created = await create.mutateAsync(sample);
    if (failCount(created) > 0) setTab('rules');
    setCaseId(created.case_id);
  }

  const decedent = c?.decedent;
  const account = c?.accounts?.[0];

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', minWidth: 1360 }}>
      <AppBar position="fixed" sx={{ zIndex: (th) => th.zIndex.drawer + 1 }}>
        <Toolbar sx={{ minHeight: '60px !important', px: '28px !important', justifyContent: 'space-between' }}>
          <Stack direction="row" spacing={1.75} sx={{ alignItems: 'center' }}>
            <Box aria-hidden sx={{ width: 22, height: 22, transform: 'rotate(45deg)', border: '2px solid #6BBBEF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Box sx={{ width: 6, height: 6, bgcolor: '#E8B45A' }} />
            </Box>
            <Typography component="h1" sx={{ fontFamily: t.serif, fontSize: 21, fontWeight: 600, whiteSpace: 'nowrap' }}>{APP_NAME}</Typography>
            <Box sx={{ width: '1px', height: 22, bgcolor: 'rgba(255,255,255,.25)' }} />
            <Typography sx={{ fontSize: 13, color: '#C9D6E3', whiteSpace: 'nowrap' }}>Inherited account guide</Typography>
          </Stack>
          <Button onClick={() => setDrawerOpen((o) => !o)} data-testid="toggle-under-the-hood" aria-pressed={drawerOpen}
            sx={{ color: '#fff', border: '1px solid rgba(255,255,255,.3)', pl: 1.5, pr: 0.5, '&:hover': { bgcolor: 'rgba(255,255,255,.08)' } }}>
            Under the hood
            <Switch size="small" checked={drawerOpen} tabIndex={-1} color="secondary" sx={{ pointerEvents: 'none' }} />
          </Button>
        </Toolbar>
      </AppBar>

      <Box sx={{ height: APPBAR_H, flex: 'none' }} />
      <Stack direction="row" spacing={2} sx={{ alignItems: 'center', height: CASEBAR_H, flex: 'none', bgcolor: '#fff', borderBottom: `1px solid ${t.rule}`, px: 3.5, mr: drawerOpen ? `${DRAWER_WIDTH}px` : 0 }}>
        <Typography variant="overline" sx={{ whiteSpace: 'nowrap' }}>Demo case</Typography>
        <Stack direction="row" spacing={1}>
          {DEMO_SAMPLES.map((s) => {
            const on = sampleId === s.id;
            return (
              <Button key={s.id} size="small" variant={on ? 'contained' : 'outlined'} onClick={() => start(s.id)} disabled={create.isPending}
                data-testid={`sample-${s.id}`} sx={{ fontFamily: t.mono, fontSize: 12.5, borderWidth: on ? 0 : 1, borderColor: t.inputBorder }}>
                {s.label}
              </Button>
            );
          })}
        </Stack>
        {decedent && (
          <Stack direction="row" spacing={1.75} sx={{ alignItems: 'center', ml: 'auto !important', fontSize: 13, color: t.muted, whiteSpace: 'nowrap' }}>
            <span>Decedent <strong style={{ color: t.ink }}>{decedent.name}</strong></span>
            {account && <>{!drawerOpen && <><Box sx={{ width: '1px', height: 14, bgcolor: t.rule }} /><span>{account.title || account.type}</span></>}
              <Box sx={{ width: '1px', height: 14, bgcolor: t.rule }} />
              <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}><strong style={{ color: t.ink }}>{formatMoney(account.balance, { cents: true })}</strong><HypotheticalChip /></Stack></>}
          </Stack>
        )}
      </Stack>

      <Box component="main" sx={{ flex: 1, minHeight: 0, overflowY: 'auto', mr: drawerOpen ? `${DRAWER_WIDTH}px` : 0, transition: 'margin .2s' }}>
        <Stack spacing={2.75} sx={{ maxWidth: 1080, mx: 'auto', px: 4.5, pt: 3.5, pb: 5 }}>
          <ProgressTracker active={activeStage(c)} />

          {create.isError && <ErrorCard title="Couldn't start the case" message={(create.error as Error).message} onRetry={() => sampleId && start(sampleId)} />}
          {caseQ.isError && <ErrorCard title="Couldn't load the case" message={(caseQ.error as Error).message} onRetry={() => caseQ.refetch()} />}

          {create.isPending && <ReadingProgress />}

          {!caseId && !create.isPending && (
            <Card sx={{ borderStyle: 'dashed', borderColor: '#B9C4D0', py: 6, px: 4, textAlign: 'center' }} data-testid="empty-state">
              <Typography variant="h3" sx={{ fontSize: 22 }}>No case open yet</Typography>
              <Typography variant="body2" sx={{ color: t.muted, maxWidth: 460, mx: 'auto', mt: 1.25 }}>
                Choose a sample packet to start. {APP_NAME} reads the documents, checks them per beneficiary, and walks through the options.
              </Typography>
              <Stack direction="row" spacing={1.25} sx={{ justifyContent: 'center', mt: 2 }}>
                <Button variant="contained" onClick={() => start('packet_01_fixed')}>Start best case</Button>
                <Button variant="outlined" onClick={() => start('packet_01_flawed')}>Start flawed case</Button>
              </Stack>
            </Card>
          )}

          {c && (
            <>
              <DocumentsSection caseState={c} onOpenOps={() => { setDrawerOpen(true); setTab('ops'); }} />
              <OptionsSection caseState={c} />
              <NextStep caseState={c} />
              <AfterSection caseState={c} />
            </>
          )}
        </Stack>
      </Box>

      <Box component="footer" sx={{ flex: 'none', bgcolor: '#fff', borderTop: `1px solid ${t.rule}`, py: 1.1, px: 3.5, fontSize: 12, color: t.muted, textAlign: 'center', zIndex: (th) => th.zIndex.drawer + 1 }}>
        {FOOTER_TEXT}
      </Box>

      <UnderTheHood open={drawerOpen} onClose={() => setDrawerOpen(false)} tab={tab} onTab={setTab} caseState={c} topOffset={APPBAR_H} />
    </Box>
  );
}
