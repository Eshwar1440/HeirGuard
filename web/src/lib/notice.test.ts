import { describe, expect, it } from 'vitest'
import { FOOTER_NOTICE, apiBaseUrl } from './notice'

describe('notice', () => {
  it('uses the required footer wording', () => {
    expect(FOOTER_NOTICE).toBe(
      'Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical.',
    )
  })

  it('normalizes the API base URL', () => {
    expect(apiBaseUrl('https://api.example.test/')).toBe('https://api.example.test')
    expect(apiBaseUrl('')).toBe('http://localhost:8000')
  })
})
