import { APP_TITLE, FOOTER_NOTICE } from './lib/notice'

// Placeholder shell. The Heir Compass page and the under-the-hood panel are built in M9.
export default function App() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui, sans-serif' }}>
      <header style={{ padding: '16px 24px', borderBottom: '1px solid #e2e6ea' }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>{APP_TITLE}</h1>
      </header>
      <main style={{ flex: 1, padding: 24 }}>
        <p>HeritageGuard concept prototype. The guided flow is under construction.</p>
      </main>
      <footer style={{ padding: '12px 24px', fontSize: 13, color: '#5b6670', borderTop: '1px solid #e2e6ea' }}>
        {FOOTER_NOTICE}
      </footer>
    </div>
  )
}
