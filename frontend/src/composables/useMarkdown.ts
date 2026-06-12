import DOMPurify from 'dompurify'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import sql from 'highlight.js/lib/languages/sql'

// 按需注册语言 - 比整包 130KB 缩减到 ~30KB
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('sql', sql)

marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderer = new marked.Renderer()
renderer.code = ({ text, lang }) => {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = hljs.highlight(text, { language }).value
  return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`
}

marked.use({ renderer })

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('rel', 'noopener noreferrer')
    node.setAttribute('target', '_blank')
  }
})

export function useMarkdown() {
  function render(text: string): string {
    if (!text) return ''
    const html = marked.parse(text, { async: false }) as string
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [
        'a', 'b', 'i', 'em', 'strong', 'code', 'pre', 'br', 'p', 'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'table', 'thead', 'tbody',
        'tr', 'th', 'td', 'img', 'span', 'div', 'del',
      ],
      ALLOWED_ATTR: ['href', 'title', 'src', 'alt', 'class', 'rel', 'target'],
      // 只允许 http(s) / mailto / 相对 / 锚点
      ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[#/]|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    })
  }
  return { render }
}
