import { useEffect, useState } from 'react';
import { AppBar, Box, Button, MenuItem, Select, Stack, Switch, Toolbar, Typography } from '@mui/material';
import { Analytics } from '@vercel/analytics/react';
import { useCase, useCreateCase, useSamples } from './api/hooks';
import { APP_NAME, FOOTER_TEXT } from './config';
import { activeStage, caseName, failCount } from './lib/case';
import { formatMoney } from './lib/format';
import ProgressTracker from './components/ProgressTracker';
import ReadingProgress from './components/ReadingProgress';
import UploadDocuments from './components/UploadDocuments';
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
  const samples = useSamples();
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
      <Analytics />
      <AppBar position="fixed" sx={{ zIndex: (th) => th.zIndex.drawer + 1 }}>
        <Toolbar sx={{ minHeight: '60px !important', px: '28px !important', justifyContent: 'space-between' }}>
          <Stack direction="row" spacing={1.75} sx={{ alignItems: 'center' }}>
            <Box
              component="img"
              src="/heirguard-white.png?v=3"
              alt=""
              aria-hidden
              sx={{ width: 38, height: 38, objectFit: 'contain' }}
            />
            <Stack spacing={0.1} sx={{ whiteSpace: 'nowrap' }}>
              <Typography
                component="h1"
                sx={{ color: '#fff', fontSize: 17, fontWeight: 650, letterSpacing: 1.4, lineHeight: 1.1 }}
              >
                {APP_NAME.toUpperCase()}
              </Typography>
              <Typography sx={{ color: '#9FC7EC', fontSize: 9.5, fontWeight: 600, letterSpacing: 1.65, lineHeight: 1.2 }}>
                INHERITED SERVICES
              </Typography>
            </Stack>
            <Box sx={{ width: '1px', height: 22, bgcolor: 'rgba(255,255,255,.25)' }} />
            <Typography sx={{ fontSize: 13, color: '#C9D6E3', whiteSpace: 'nowrap' }}>A guided account transition experience</Typography>
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
        <Typography variant="overline" sx={{ whiteSpace: 'nowrap' }}>Case</Typography>
        <Select size="small" value={sampleId ?? ''} displayEmpty disabled={create.isPending}
          onChange={(e) => e.target.value && start(String(e.target.value))}
          SelectDisplayProps={{ 'data-testid': 'case-select' } as React.HTMLAttributes<HTMLDivElement>}
          sx={{ minWidth: 170, fontSize: 13.5, '& .MuiSelect-select': { py: 0.75 } }}>
          <MenuItem value="" disabled>Choose a case</MenuItem>
          {(samples.data ?? []).map((s) => (
            <MenuItem key={s.sample_id} value={s.sample_id} data-testid={`sample-${s.sample_id}`}>{caseName(s.sample_id)}</MenuItem>
          ))}
        </Select>
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

          {!caseId && !create.isPending && <UploadDocuments onCase={setCaseId} />}

          {c && (
            <>
              <DocumentsSection caseState={c} />
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
