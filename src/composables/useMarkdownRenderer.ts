import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import 'highlight.js/styles/github-dark.css'
import MarkdownIt from 'markdown-it'
import markdownItKatex from 'markdown-it-katex'
import 'katex/dist/katex.min.css'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('c', c)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('css', css)
hljs.registerLanguage('java', java)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('python', python)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('xml', xml)

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function highlightCodeBlock(code: string, language: string): string {
  const normalizedLanguage = String(language || '').trim().toLowerCase()
  const languageAliases: Record<string, string> = {
    cplusplus: 'cpp',
    js: 'javascript',
    py: 'python',
    shell: 'bash',
    sh: 'bash',
    ts: 'typescript',
  }
  const resolvedLanguage = languageAliases[normalizedLanguage] || normalizedLanguage
  if (resolvedLanguage && hljs.getLanguage(resolvedLanguage)) {
    const highlighted = hljs.highlight(code, {
      language: resolvedLanguage,
      ignoreIllegals: true,
    }).value
    return `<pre class="hljs code-block"><code>${highlighted}</code></pre>`
  }
  return `<pre class="hljs code-block"><code>${escapeHtml(code)}</code></pre>`
}

const markdownRenderer = new MarkdownIt({
  breaks: true,
  highlight: highlightCodeBlock,
  html: false,
  linkify: true,
  typographer: true,
}).use(markdownItKatex)

const FENCE_LINE_PATTERN = /^\s*(```|~~~)/
const LATEX_WORD_COMMANDS = [
  'frac',
  'dfrac',
  'tfrac',
  'sqrt',
  'int',
  'sum',
  'prod',
  'lim',
  'ln',
  'log',
  'sin',
  'cos',
  'tan',
  'cot',
  'sec',
  'csc',
  'neq',
  'leq',
  'geq',
  'approx',
  'cdot',
  'times',
  'pm',
  'mp',
  'infty',
  'alpha',
  'beta',
  'gamma',
  'delta',
  'theta',
  'lambda',
  'mu',
  'pi',
  'sigma',
  'omega',
  'partial',
  'nabla',
  'left',
  'right',
  'text',
  'mathrm',
  'mathbf',
  'mathbb',
].join('|')
const LATEX_COMMAND_PATTERN = new RegExp(String.raw`\\{1,2}(?:${LATEX_WORD_COMMANDS}\b|[,;!])`)
const LATEX_DOUBLE_BACKSLASH_PATTERN = new RegExp(
  String.raw`\\\\(?=(?:${LATEX_WORD_COMMANDS})\b|[,;!])`,
  'g',
)
const INLINE_LATEX_PATTERN = new RegExp(
  String.raw`(^|[\s([{，。；：、])((?:[A-Za-z0-9{}|+\-*/=^_.,:;!]*\s*)*\\{1,2}(?:${LATEX_WORD_COMMANDS}\b|[,;!])(?:\s*[A-Za-z0-9{}|+\-*/=^_.,:;!\\]*)*)`,
  'g',
)

function normalizeLatexBackslashes(text: string): string {
  return text.replace(LATEX_DOUBLE_BACKSLASH_PATTERN, '\\')
}

function looksLikeStandaloneLatex(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('$') || trimmed.endsWith('$')) return false
  if (/[一-鿿]/.test(trimmed)) return false
  if (!LATEX_COMMAND_PATTERN.test(trimmed)) return false
  if (!trimmed.startsWith('\\') && !trimmed.includes('=')) return false
  return /(?:=|[+\-*/^]|\\{1,2}(?:int|sum|prod|frac|dfrac|tfrac|sqrt|lim|ln|log|sin|cos|tan|neq|leq|geq|approx|cdot|times))/.test(trimmed)
}

function wrapInlineLatex(text: string): string {
  const normalized = normalizeLatexBackslashes(text)
  const mathSegments = normalized.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/g)
  return mathSegments
    .map((segment) => {
      if (segment.startsWith('$')) return segment
      return segment.replace(INLINE_LATEX_PATTERN, (_match, prefix: string, expression: string) => {
        const formula = normalizeLatexBackslashes(expression).trim()
        if (!formula || formula.includes('$')) return `${prefix}${expression}`
        return `${prefix}$${formula}$`
      })
    })
    .join('')
}

function normalizeMathMarkdownLine(line: string): string {
  const delimiterNormalized = line
    .replace(/\\\[(.+?)\\\]/g, (_match, expression: string) => `$$\n${normalizeLatexBackslashes(expression).trim()}\n$$`)
    .replace(/\\\((.+?)\\\)/g, (_match, expression: string) => `$${normalizeLatexBackslashes(expression).trim()}$`)

  const indent = delimiterNormalized.match(/^\s*/)?.[0] || ''
  const trimmed = delimiterNormalized.trim()
  if (looksLikeStandaloneLatex(trimmed)) {
    return `${indent}$$\n${normalizeLatexBackslashes(trimmed)}\n${indent}$$`
  }
  return wrapInlineLatex(delimiterNormalized)
}

function normalizeRichTextMarkdown(text: string): string {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n')
  let inFence = false
  return lines
    .map((line) => {
      if (FENCE_LINE_PATTERN.test(line)) {
        inFence = !inFence
        return line
      }
      if (inFence) return line
      return normalizeMathMarkdownLine(line)
    })
    .join('\n')
}

function renderAssistantText(text: string): string {
  return markdownRenderer.render(normalizeRichTextMarkdown(text))
}

type ChatLineLike = {
  role: string
  renderMode?: string
}

function shouldRenderRichMessage(line: ChatLineLike): boolean {
  return line.role === 'assistant' && (line.renderMode || 'rich_text') === 'rich_text'
}

function normalizeAssistantContent(text: string): string {
  return String(text ?? '').replace(/\r\n/g, '\n')
}

export function useMarkdownRenderer() {
  return {
    renderAssistantText,
    normalizeAssistantContent,
    shouldRenderRichMessage,
    markdownRenderer,
  }
}
