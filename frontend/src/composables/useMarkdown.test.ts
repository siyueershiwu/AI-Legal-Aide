import { describe, expect, it } from 'vitest'
import { useMarkdown } from './useMarkdown'

const { render } = useMarkdown()

describe('useMarkdown', () => {
  it('空串返回空', () => {
    expect(render('')).toBe('')
  })

  it('渲染普通段落', () => {
    const html = render('hello world')
    expect(html).toContain('<p>hello world</p>')
  })

  it('代码块语法高亮', () => {
    const html = render('```js\nconst x = 1\n```')
    expect(html).toContain('<pre>')
    expect(html).toContain('hljs')
    expect(html).toContain('language-js')
  })

  it('禁止 javascript: 链接', () => {
    const html = render('[click](javascript:alert(1))')
    expect(html).not.toContain('javascript:')
  })

  it('允许 https 链接', () => {
    const html = render('[ok](https://example.com)')
    expect(html).toContain('href="https://example.com"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('inline code 渲染', () => {
    const html = render('`x = 1`')
    expect(html).toContain('<code')
  })

  it('GFM 表格渲染', () => {
    const md = '| a | b |\n|---|---|\n| 1 | 2 |'
    const html = render(md)
    expect(html).toContain('<table>')
    expect(html).toContain('<th')
  })
})
