export const APP_TITLE = 'Heir Compass'

export const FOOTER_NOTICE =
  'Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical.'

/** Base URL of the HeritageGuard API, without a trailing slash. */
export function apiBaseUrl(raw: string | undefined = import.meta.env.VITE_API_URL): string {
  return (raw || 'http://localhost:8000').replace(/\/+$/, '')
}
