<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ProgressSpinner from 'primevue/progressspinner'
import {
  calculateWorkbook,
  type PlanningCalculationResult,
} from '../services/planningApi'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const fileInput = ref<HTMLInputElement>()
const selectedFile = ref<File | null>(null)
const dragging = ref(false)
const calculating = ref(false)
const errorMessage = ref<string | null>(null)
const result = ref<PlanningCalculationResult | null>(null)
const statusIndex = ref(0)
let statusTimer: number | undefined

const processingMessages = [
  'Uploading workbook to the backend...',
  'Validating sheets, columns and data quality...',
  'Normalizing demand, stores and courier availability...',
  'Running the CatBoost 90-day demand forecast...',
  'Calculating workforce capacity, shortages and surplus...',
  'Building recommendations and saving the planning run...',
]

const statusMessage = computed(() => processingMessages[statusIndex.value])

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.ceil(bytes / 1024)} KB`
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function resetDialog() {
  if (calculating.value) return

  selectedFile.value = null
  dragging.value = false
  errorMessage.value = null
  result.value = null
  statusIndex.value = 0

  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

function setFile(file?: File) {
  errorMessage.value = null
  result.value = null

  if (!file) return

  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    selectedFile.value = null
    errorMessage.value = 'Please select an .xlsx Excel workbook.'
    return
  }

  selectedFile.value = file
  void calculate()
}

function selectFromInput(event: Event) {
  const input = event.target as HTMLInputElement
  setFile(input.files?.[0])
}

function dropFile(event: DragEvent) {
  dragging.value = false
  setFile(event.dataTransfer?.files[0])
}

function clearStatusTimer() {
  if (statusTimer !== undefined) {
    window.clearInterval(statusTimer)
    statusTimer = undefined
  }
}

async function calculate() {
  if (!selectedFile.value || calculating.value) return

  calculating.value = true
  errorMessage.value = null
  result.value = null
  statusIndex.value = 0
  statusTimer = window.setInterval(() => {
    statusIndex.value = Math.min(
      statusIndex.value + 1,
      processingMessages.length - 1,
    )
  }, 2300)

  try {
    result.value = await calculateWorkbook(selectedFile.value)
  } catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : 'The workbook could not be calculated.'
  } finally {
    clearStatusTimer()
    calculating.value = false
  }
}

function openUpdatedDashboard() {
  window.location.assign('/')
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) resetDialog()
  },
)

onUnmounted(clearStatusTimer)
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :closable="!calculating"
    :close-on-escape="!calculating"
    :dismissable-mask="!calculating"
    :style="{ width: '34rem' }"
    header="Upload workforce data"
    class="dataset-upload"
    @update:visible="emit('update:visible', $event)"
    @hide="resetDialog"
  >
    <div class="dataset-upload__body">
      <div
        v-if="!calculating && !result"
        class="dataset-upload__dropzone"
        :class="{
          'dataset-upload__dropzone--dragging': dragging,
          'dataset-upload__dropzone--selected': selectedFile,
        }"
        role="button"
        tabindex="0"
        @click="fileInput?.click()"
        @keydown.enter="fileInput?.click()"
        @dragenter.prevent="dragging = true"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="dropFile"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          @change="selectFromInput"
        />

        <span class="dataset-upload__drop-icon">
          <i :class="selectedFile ? 'pi pi-file-excel' : 'pi pi-cloud-upload'" />
        </span>

        <template v-if="selectedFile">
          <strong class="dataset-upload__file-name">{{ selectedFile.name }}</strong>
          <span class="dataset-upload__file-meta">
            {{ formatFileSize(selectedFile.size) }} · Ready to calculate
          </span>
          <span class="dataset-upload__browse">Choose another file</span>
        </template>

        <template v-else>
          <strong>Drop your Excel file here</strong>
          <span>or <span class="dataset-upload__browse">browse your computer</span></span>
          <small>Only .xlsx workbooks are supported</small>
        </template>
      </div>

      <div v-if="calculating" class="dataset-upload__processing">
        <ProgressSpinner
          stroke-width="4"
          class="dataset-upload__spinner"
          aria-label="Calculating workforce plan"
        />
        <strong>Calculating workforce plan</strong>
        <p>{{ statusMessage }}</p>
        <small>This can take a few moments. Please keep this window open.</small>
      </div>

      <div v-if="result" class="dataset-upload__success">
        <span class="dataset-upload__success-icon"><i class="pi pi-check" /></span>
        <strong>Planning run completed</strong>
        <p>
          {{ result.row_count }} store-day rows calculated with
          {{ result.model_version ?? 'the workforce model' }}.
        </p>
        <small>Planning Run #{{ result.planning_run_id }}</small>
      </div>

      <div v-if="errorMessage" class="dataset-upload__error">
        <i class="pi pi-exclamation-circle" />
        <span>{{ errorMessage }}</span>
      </div>
    </div>

    <template v-if="result" #footer>
      <Button
        label="View updated dashboard"
        icon="pi pi-arrow-right"
        icon-pos="right"
        @click="openUpdatedDashboard"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.dataset-upload__body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.dataset-upload__dropzone {
  min-height: 15rem;
  padding: 1.5rem;
  border: 1.5px dashed var(--p-content-border-color);
  border-radius: 0.9rem;
  background: var(--p-surface-50);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  color: var(--p-text-color);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.dataset-upload__dropzone:hover,
.dataset-upload__dropzone--dragging {
  border-color: var(--p-primary-color);
  background: color-mix(in srgb, var(--p-primary-color) 7%, var(--p-content-background));
}

.dataset-upload__dropzone--selected {
  border-style: solid;
}

.dataset-upload__drop-icon,
.dataset-upload__success-icon {
  width: 3.4rem;
  height: 3.4rem;
  border-radius: 1rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--p-primary-color) 12%, transparent);
  color: var(--p-primary-color);
  font-size: 1.45rem;
  margin-bottom: 0.25rem;
}

.dataset-upload__dropzone > span,
.dataset-upload__dropzone small,
.dataset-upload__file-meta {
  color: var(--p-text-muted-color);
  font-size: 0.78rem;
}

.dataset-upload__browse {
  color: var(--p-primary-color) !important;
  font-weight: 600;
}

.dataset-upload__file-name {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataset-upload__processing,
.dataset-upload__success {
  min-height: 15rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  text-align: center;
}

.dataset-upload__spinner {
  width: 3.6rem;
  height: 3.6rem;
  margin-bottom: 0.4rem;
}

.dataset-upload__processing p,
.dataset-upload__success p {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: 0.82rem;
}

.dataset-upload__processing small,
.dataset-upload__success small {
  color: var(--p-text-muted-color);
  font-size: 0.72rem;
}

.dataset-upload__success-icon {
  background: color-mix(in srgb, #16a34a 13%, transparent);
  color: #16a34a;
}

.dataset-upload__error {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding: 0.75rem 0.85rem;
  border-radius: 0.65rem;
  background: color-mix(in srgb, var(--p-red-500) 10%, transparent);
  color: var(--p-red-500);
  font-size: 0.78rem;
  line-height: 1.4;
}
</style>
