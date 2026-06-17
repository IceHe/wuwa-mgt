// Keep account lists independent of each browser/OS default locale.
const ACCOUNT_ABBR_COLLATOR = new Intl.Collator('en-US', {
  usage: 'sort',
  sensitivity: 'variant',
  numeric: true,
  caseFirst: 'upper',
})

function normalizedString(value) {
  return String(value ?? '').normalize('NFKC')
}

function compareStringFallback(left, right) {
  const a = normalizedString(left)
  const b = normalizedString(right)
  if (a === b) return 0
  return a < b ? -1 : 1
}

function compareAccountId(left, right) {
  const a = Number(left)
  const b = Number(right)
  if (Number.isFinite(a) && Number.isFinite(b) && a !== b) return a - b
  return compareStringFallback(left, right)
}

export function compareAccountAbbr(left, right) {
  const abbrResult = ACCOUNT_ABBR_COLLATOR.compare(normalizedString(left?.abbr), normalizedString(right?.abbr))
  if (abbrResult !== 0) return abbrResult

  const exactAbbrResult = compareStringFallback(left?.abbr, right?.abbr)
  if (exactAbbrResult !== 0) return exactAbbrResult

  const accountIdResult = compareAccountId(left?.account_id, right?.account_id)
  if (accountIdResult !== 0) return accountIdResult

  return compareStringFallback(left?.id, right?.id)
}
