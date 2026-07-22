const escapeMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (char) => escapeMap[char])
}

export function renderInlineMarkdown(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''

  const tokens = []
  const stash = (html) => {
    const key = `\u0000MD${tokens.length}\u0000`
    tokens.push(html)
    return key
  }

  let html = raw.replace(/`([^`\n]+)`/g, (_, code) => stash(`<code>${escapeHTML(code)}</code>`))
  html = escapeHTML(html)
  html = html.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/__([^_\n]+?)__/g, '<strong>$1</strong>')
  html = html.replace(/(^|[^*])\*([^*\n]+?)\*/g, '$1<em>$2</em>')
  html = html.replace(/(^|[^_])_([^_\n]+?)_/g, '$1<em>$2</em>')
  html = html.replace(/\n/g, '<br>')
  return html.replace(/\u0000MD(\d+)\u0000/g, (_, index) => tokens[Number(index)] || '')
}
