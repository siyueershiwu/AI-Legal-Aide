import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatInput from '@/components/ChatInput.vue'

describe('ChatInput', () => {
  it('有 hasAttachments + 文本为空时仍可发送', async () => {
    const wrapper = mount(ChatInput, { props: { hasAttachments: true } })
    const button = wrapper.find('button.send-button')
    expect((button.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('无 hasAttachments 且无文本时禁发', () => {
    const wrapper = mount(ChatInput, { props: { hasAttachments: false } })
    const button = wrapper.find('button.send-button')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('Enter 触发 send 事件', async () => {
    const wrapper = mount(ChatInput, { props: { hasAttachments: false } })
    await wrapper.find('textarea').setValue('hello')
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('send')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['hello'])
  })

  it('Shift+Enter 不触发 send', async () => {
    const wrapper = mount(ChatInput, { props: { hasAttachments: false } })
    await wrapper.find('textarea').setValue('hello')
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(wrapper.emitted('send')).toBeFalsy()
  })
})
