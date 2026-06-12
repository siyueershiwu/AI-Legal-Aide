<script setup lang="ts">
import { computed, ref } from 'vue'
import { useUploadStore } from '@/stores/upload'
import { useKnowledgeStore } from '@/stores/knowledge'
import {
  DOC_TYPE_LABELS,
  LAW_CODE_LABELS,
  type DocTypeEnum,
  type LawCodeEnum,
} from '@/types/api'

const emit = defineEmits<{
  uploaded: [docId: string]
  cancel: []
}>()

const upload = useUploadStore()
const kb = useKnowledgeStore()

const LAW_OPTIONS: LawCodeEnum[] = [
  '民法典', '刑法', '劳动法', '劳动合同法', '治安管理处罚法',
  '个人信息保护法', '网络安全法', '数据安全法', '宪法',
  '行政处罚法', '民事诉讼法', '刑事诉讼法', '公司法', '其他',
]

const DOC_TYPE_OPTIONS: DocTypeEnum[] = [
  'statute', 'interpretation', 'commentary',
  'scenario', 'boundary', 'diff', 'repeal_note', 'other',
]

// 表单状态
const pickedFile = ref<File | null>(null)
const title = ref('')
const lawCode = ref<LawCodeEnum>('民法典')
const docType = ref<DocTypeEnum>('statute')
const version = ref('现行')
const isCurrent = ref(true)
const effectiveDate = ref('')
const repealedDate = ref('')
const issuingBody = ref('')
const articleRange = ref('')
const localError = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

const isBusy = computed(() => upload.isUploading || kb.uploading)
const canSubmit = computed(
  () => !!pickedFile.value
    && !!title.value.trim()
    && !!lawCode.value
    && !!docType.value
    && !isBusy.value,
)

function pickFile() {
  fileInputRef.value?.click()
}

function onFileChange(e: Event) {
  const t = e.target as HTMLInputElement
  if (!t.files || t.files.length === 0) return
  const f = t.files[0]
  if (!f) return
  pickedFile.value = f
  // 自动用文件名做 title 默认值（去后缀）
  if (!title.value) {
    title.value = f.name.replace(/\.[^.]+$/, '')
  }
  // 同一文件重复选要能再次触发
  t.value = ''
}

function removeFile() {
  pickedFile.value = null
}

async function submit() {
  if (!canSubmit.value || !pickedFile.value) return
  localError.value = ''
  try {
    const file = pickedFile.value
    // 先调 uploadStore 上传文件拿到 id，再让 store 把它和元数据一起入库
    await kb.uploadDocument(
      async () => {
        await upload.upload(file)
        const uploaded = upload.files.find((x) => x.name === file.name)
        if (!uploaded) throw new Error('文件上传后未拿到 file_id')
        return { id: uploaded.id }
      },
      {
        title: title.value.trim(),
        law_code: lawCode.value,
        doc_type: docType.value,
        version: version.value.trim() || 'latest',
        is_current: isCurrent.value,
        effective_date: effectiveDate.value || null,
        repealed_date: repealedDate.value || null,
        issuing_body: issuingBody.value.trim() || null,
        article_range: articleRange.value.trim() || null,
        source_type: 'upload',
      },
    )
    emit('uploaded', '')
    // 清空表单
    pickedFile.value = null
    title.value = ''
    version.value = '现行'
    isCurrent.value = true
    effectiveDate.value = ''
    repealedDate.value = ''
    issuingBody.value = ''
    articleRange.value = ''
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '入库失败'
    localError.value = msg
  }
}

function cancel() {
  emit('cancel')
}
</script>

<template>
  <Teleport to="body">
    <div class="dialog-mask" @click.self="cancel">
      <div class="dialog-box" role="dialog" aria-modal="true">
        <h3 class="dialog-title">📚 入库法律文档</h3>
        <p class="dialog-hint">
          支持 TXT / Markdown / PDF / DOCX，提交后按「第N条」切片并向量化入库。
        </p>

        <div class="form">
          <div class="form-field">
            <label>选择文件</label>
            <input
              ref="fileInputRef"
              type="file"
              accept=".txt,.md,.markdown,.pdf,.docx,.doc"
              @change="onFileChange"
              hidden
            />
            <div v-if="!pickedFile" class="file-pick-zone" @click="pickFile">
              <span class="file-pick-icon">📁</span>
              <span>点击选择文件</span>
            </div>
            <div v-else class="file-picked">
              <span class="file-picked-name">{{ pickedFile.name }}</span>
              <span class="file-picked-size">
                {{ Math.round(pickedFile.size / 1024) }} KB
              </span>
              <button class="file-remove" @click="removeFile" type="button">✕</button>
            </div>
          </div>

          <div class="form-field">
            <label>标题</label>
            <input
              v-model="title"
              type="text"
              placeholder="例：中华人民共和国民法典（2021 修正）"
              class="text-input"
              :disabled="isBusy"
            />
          </div>

          <div class="form-row">
            <div class="form-field">
              <label>法律</label>
              <select v-model="lawCode" class="text-input" :disabled="isBusy">
                <option v-for="opt in LAW_OPTIONS" :key="opt" :value="opt">
                  {{ LAW_CODE_LABELS[opt] }}
                </option>
              </select>
            </div>

            <div class="form-field">
              <label>资料类型</label>
              <select v-model="docType" class="text-input" :disabled="isBusy">
                <option v-for="opt in DOC_TYPE_OPTIONS" :key="opt" :value="opt">
                  {{ DOC_TYPE_LABELS[opt] }}
                </option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-field">
              <label>版本 / 发布日期说明</label>
              <input
                v-model="version"
                type="text"
                placeholder="例：2021 修正 / 2020 版"
                class="text-input"
                :disabled="isBusy"
              />
            </div>
            <div class="form-field">
              <label>状态</label>
              <label class="checkbox-row">
                <input v-model="isCurrent" type="checkbox" :disabled="isBusy" />
                <span>现行有效</span>
              </label>
            </div>
          </div>

          <div class="form-row">
            <div class="form-field">
              <label>施行日期</label>
              <input
                v-model="effectiveDate"
                type="date"
                class="text-input"
                :disabled="isBusy"
              />
            </div>
            <div class="form-field">
              <label>废止日期</label>
              <input
                v-model="repealedDate"
                type="date"
                class="text-input"
                :disabled="isBusy || isCurrent"
              />
            </div>
          </div>

          <div class="form-field">
            <label>发布机关（可选）</label>
            <input
              v-model="issuingBody"
              type="text"
              placeholder="例：全国人民代表大会常务委员会"
              class="text-input"
              :disabled="isBusy"
            />
          </div>

          <div class="form-field">
            <label>条款范围（可选）</label>
            <input
              v-model="articleRange"
              type="text"
              placeholder="例：第1条 - 第1260条 / 第一编 总则"
              class="text-input"
              :disabled="isBusy"
            />
          </div>

          <div v-if="localError" class="form-error">{{ localError }}</div>
        </div>

        <div class="dialog-actions">
          <button class="btn btn-secondary" :disabled="isBusy" @click="cancel">取消</button>
          <button class="btn btn-primary" :disabled="!canSubmit" @click="submit">
            <span v-if="isBusy">{{ upload.isUploading ? '上传文件中…' : '入库中…' }}</span>
            <span v-else>入库</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

.dialog-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 28px;
  width: 560px;
  max-width: 92vw;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
  animation: fadeInUp 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.dialog-title {
  margin: 0 0 6px;
  color: var(--text-primary);
  font-size: 1.1rem;
  font-weight: 600;
}

.dialog-hint {
  margin: 0 0 20px;
  color: var(--text-secondary);
  font-size: 0.85rem;
  line-height: 1.5;
}

.form { display: flex; flex-direction: column; gap: 14px; }

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-field { display: flex; flex-direction: column; gap: 6px; }
.form-field label {
  font-size: 0.85rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.text-input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--input-bg, var(--bg-tertiary));
  color: var(--text-primary);
  font-size: 0.9rem;
  font-family: inherit;
  transition: all var(--transition);
  box-sizing: border-box;
}
.text-input:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.text-input:disabled { opacity: 0.6; cursor: not-allowed; }

.checkbox-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 0;
  font-size: 0.9rem;
  color: var(--text-primary);
  cursor: pointer;
}
.checkbox-row input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--accent-color);
}
.checkbox-row input[type="checkbox"]:disabled { cursor: not-allowed; }

.file-pick-zone {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 18px;
  border: 2px dashed var(--border-color);
  border-radius: var(--radius);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition);
  justify-content: center;
}
.file-pick-zone:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
  background: var(--accent-soft);
}
.file-pick-icon { font-size: 1.4rem; }

.file-picked {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--accent-soft);
  border: 1px solid var(--accent-color);
  border-radius: var(--radius);
  color: var(--text-primary);
}
.file-picked-name { flex: 1; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-picked-size { font-size: 0.8rem; color: var(--text-secondary); }
.file-remove {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 1rem;
  padding: 0 4px;
}
.file-remove:hover { color: #ef4444; }

.form-error {
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius);
  color: #ef4444;
  font-size: 0.85rem;
}

.dialog-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px; }
.btn {
  padding: 9px 20px;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all var(--transition);
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary {
  background: var(--gradient-primary);
  color: white;
  box-shadow: var(--shadow-glow);
}
.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 28px rgba(108, 92, 231, 0.4);
}
.btn-secondary { background: var(--bg-tertiary); color: var(--text-primary); }
.btn-secondary:hover:not(:disabled) { background: var(--border-color); }
</style>
