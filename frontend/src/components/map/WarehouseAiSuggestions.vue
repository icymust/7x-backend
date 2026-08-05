<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Textarea from 'primevue/textarea'
import { warehouses } from '../../data/warehouseData'
import {
  fetchStoreRecommendations,
  type BackendRecommendationRow,
  type RecommendationPriority,
  type RecommendationReason,
} from '../../services/recommendationsApi'

const props = defineProps<{ warehouseName: string; storeId: string; isOpen: boolean }>()

type ActionId = 'transport' | 'outsource' | 'hire'

interface SuggestionAction {
  id: ActionId
  icon: string
  title: string
  description: string
}

const actions: SuggestionAction[] = [
  {
    id: 'transport',
    icon: 'pi pi-truck',
    title: 'Transfer Drivers',
    description: "Move available couriers in from a nearby branch to cover today's shortage.",
  },
  {
    id: 'outsource',
    icon: 'pi pi-briefcase',
    title: 'Hire Outsource',
    description: 'Bring in temporary outsourced couriers to absorb peak demand quickly.',
  },
  {
    id: 'hire',
    icon: 'pi pi-user-plus',
    title: 'Hire Drivers',
    description: 'Open a permanent hiring round for drivers based at this branch.',
  },
]

const otherWarehouseNames = computed(() =>
  warehouses.features.map((f) => f.properties.name).filter((name) => name !== props.warehouseName),
)

const agencyOptions = ['QuickStaff Logistics', 'FlexForce UAE', 'RapidHire Partners']
const durationOptions = ['1 Week', '2 Weeks', '1 Month']
const employmentOptions = ['Full-time', 'Part-time']

const transportForm = ref({
  source: otherWarehouseNames.value[0] ?? '',
  count: 3,
  date: null as Date | null,
  notes: '',
})
const outsourceForm = ref({
  agency: agencyOptions[0],
  count: 5,
  duration: durationOptions[1],
  startDate: null as Date | null,
})
const hireForm = ref({
  positions: 2,
  employmentType: employmentOptions[0],
  startDate: null as Date | null,
  notes: '',
})

// Backend-derived suggestions, rendered as readable messages above the
// manual actions below. Loaded lazily - see the isOpen watcher - rather
// than on mount, since this component stays mounted (just hidden) while
// its accordion panel is collapsed.
interface SuggestionMessage {
  id: string
  icon: string
  color: string
  priority: RecommendationPriority
  title: string
  text: string
}

const PRIORITY_COLOR: Record<RecommendationPriority, string> = {
  critical: '#dc2626',
  high: '#f97316',
  medium: '#2563eb',
  low: '#16a34a',
}

const REASON_ICON: Record<RecommendationReason, string> = {
  emergency_outsourcing_required: 'pi pi-exclamation-triangle',
  permanent_lead_time_missed: 'pi pi-clock',
  planned_hiring: 'pi pi-user-plus',
  capacity_is_sufficient: 'pi pi-check-circle',
}

const hasLoadedSuggestions = ref(false)
const loadingSuggestions = ref(false)
const suggestionsError = ref<string | null>(null)
const suggestionMessages = ref<SuggestionMessage[]>([])

function dateLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// The backend returns one recommendation row per day (up to ~90 for a
// future-forecast Planning Run) - collapsing consecutive days that share
// the same reason into one message keeps the tab to a handful of cards
// instead of a wall of near-identical daily entries.
function groupByReason(rows: BackendRecommendationRow[]): BackendRecommendationRow[][] {
  const groups: BackendRecommendationRow[][] = []
  for (const row of rows) {
    const current = groups[groups.length - 1]
    if (current && current[0].recommendation.reason === row.recommendation.reason) {
      current.push(row)
    } else {
      groups.push([row])
    }
  }
  return groups
}

function messageFor(group: BackendRecommendationRow[]): SuggestionMessage {
  const first = group[0]
  const last = group[group.length - 1]
  const reason = first.recommendation.reason
  const range = group.length > 1 ? `${dateLabel(first.time_bucket)} - ${dateLabel(last.time_bucket)}` : dateLabel(first.time_bucket)
  const maxAddOutsourced = Math.max(...group.map((r) => r.recommendation.add_outsourced))
  const maxAddPermanent = Math.max(...group.map((r) => r.recommendation.add_permanent))
  const maxShortage = Math.max(...group.map((r) => r.shortage))
  const earliestOutsourcedStartBy = group.map((r) => r.recommendation.outsourced_start_by).sort()[0]
  const earliestPermanentStartBy = group.map((r) => r.recommendation.permanent_start_by).sort()[0]

  const base = {
    id: `${reason}-${first.time_bucket}`,
    icon: REASON_ICON[reason],
    color: PRIORITY_COLOR[first.recommendation.priority],
    priority: first.recommendation.priority,
  }

  switch (reason) {
    case 'emergency_outsourcing_required':
      return {
        ...base,
        title: 'Emergency outsourcing needed',
        text: `${range}: the outsourcing lead time has already passed - bring in up to ${maxAddOutsourced} outsourced couriers on an emergency basis to close a shortage of up to ${maxShortage} couriers.`,
      }
    case 'permanent_lead_time_missed':
      return {
        ...base,
        title: 'Bridge with outsourcing while hiring catches up',
        text: `${range}: the 60-day permanent-hiring lead time has already passed - cover the gap with up to ${maxAddOutsourced} outsourced couriers in the meantime.`,
      }
    case 'planned_hiring':
      return {
        ...base,
        title: 'Plan hiring ahead of demand',
        text: `${range}: there's still time to hire properly - add up to ${maxAddPermanent} permanent couriers (start by ${dateLabel(earliestPermanentStartBy)}) and ${maxAddOutsourced} outsourced couriers (start by ${dateLabel(earliestOutsourcedStartBy)}).`,
      }
    default:
      return {
        ...base,
        title: 'Capacity is sufficient',
        text: `${range}: no additional hiring or outsourcing action is needed.`,
      }
  }
}

async function loadSuggestions() {
  loadingSuggestions.value = true
  suggestionsError.value = null
  try {
    const rows = await fetchStoreRecommendations(props.storeId)
    suggestionMessages.value = groupByReason(rows).map(messageFor)
  } catch {
    suggestionsError.value = 'Could not load AI suggestions. Try again later.'
  } finally {
    loadingSuggestions.value = false
  }
}

watch(
  () => props.isOpen,
  (open) => {
    if (open && !hasLoadedSuggestions.value) {
      hasLoadedSuggestions.value = true
      loadSuggestions()
    }
  },
  { immediate: true },
)

const activeAction = ref<SuggestionAction | null>(null)
const dialogVisible = ref(false)
const submitting = ref(false)
const submitted = ref(false)

function openAction(action: SuggestionAction) {
  activeAction.value = action
  submitting.value = false
  submitted.value = false
  dialogVisible.value = true
}

function closeDialog() {
  dialogVisible.value = false
}

function handleSubmit() {
  if (submitting.value) return
  submitting.value = true
  // Mock request - no backend, just a believable delay before confirming.
  setTimeout(() => {
    submitting.value = false
    submitted.value = true
  }, 650)
}
</script>

<template>
  <div class="ai-suggestions">
    <p class="ai-suggestions__subtitle">AI-generated suggestions for this branch</p>

    <div v-if="loadingSuggestions" class="ai-suggestions__status">Loading suggestions…</div>
    <p v-else-if="suggestionsError" class="ai-suggestions__status ai-suggestions__status--error">
      {{ suggestionsError }}
    </p>
    <p v-else-if="hasLoadedSuggestions && suggestionMessages.length === 0" class="ai-suggestions__status">
      No suggestions right now - capacity looks sufficient.
    </p>
    <div v-else-if="suggestionMessages.length" class="ai-suggestions__messages">
      <div
        v-for="message in suggestionMessages"
        :key="message.id"
        class="ai-suggestions__message"
        :style="{ '--msg-color': message.color }"
      >
        <span class="ai-suggestions__message-icon"><i :class="message.icon" /></span>
        <div class="ai-suggestions__message-body">
          <span class="ai-suggestions__message-title">{{ message.title }}</span>
          <p class="ai-suggestions__message-text">{{ message.text }}</p>
        </div>
      </div>
    </div>

    <p class="ai-suggestions__section-label">Actions</p>
    <div class="ai-suggestions__list">
      <button
        v-for="action in actions"
        :key="action.id"
        type="button"
        class="ai-suggestions__item"
        @click="openAction(action)"
      >
        <span class="ai-suggestions__item-icon"><i :class="action.icon" /></span>
        <div class="ai-suggestions__item-body">
          <span class="ai-suggestions__item-title">{{ action.title }}</span>
          <span class="ai-suggestions__item-desc">{{ action.description }}</span>
        </div>
        <i class="pi pi-chevron-right ai-suggestions__item-chevron" />
      </button>
    </div>

    <Dialog
      v-model:visible="dialogVisible"
      modal
      :header="activeAction?.title"
      :style="{ width: '26rem' }"
      class="ai-suggestions__dialog"
    >
      <Transition name="dialog-swap" mode="out-in">
        <div v-if="!submitted" key="form" class="ai-suggestions__form">
          <template v-if="activeAction?.id === 'transport'">
            <div class="ai-suggestions__field">
              <label>Source Warehouse</label>
              <Select v-model="transportForm.source" :options="otherWarehouseNames" fluid placeholder="Select a branch" />
            </div>
            <div class="ai-suggestions__field">
              <label>Drivers to Transfer</label>
              <InputNumber v-model="transportForm.count" :min="1" :max="20" fluid />
            </div>
            <div class="ai-suggestions__field">
              <label>Transfer Date</label>
              <DatePicker v-model="transportForm.date" date-format="M dd, yy" placeholder="Select a date" fluid />
            </div>
            <div class="ai-suggestions__field">
              <label>Notes <span class="ai-suggestions__optional">(optional)</span></label>
              <Textarea v-model="transportForm.notes" rows="2" fluid placeholder="Any special instructions..." />
            </div>
          </template>

          <template v-else-if="activeAction?.id === 'outsource'">
            <div class="ai-suggestions__field">
              <label>Staffing Agency</label>
              <Select v-model="outsourceForm.agency" :options="agencyOptions" fluid />
            </div>
            <div class="ai-suggestions__field">
              <label>Workers Needed</label>
              <InputNumber v-model="outsourceForm.count" :min="1" :max="50" fluid />
            </div>
            <div class="ai-suggestions__field">
              <label>Contract Duration</label>
              <Select v-model="outsourceForm.duration" :options="durationOptions" fluid />
            </div>
            <div class="ai-suggestions__field">
              <label>Start Date</label>
              <DatePicker v-model="outsourceForm.startDate" date-format="M dd, yy" placeholder="Select a date" fluid />
            </div>
          </template>

          <template v-else-if="activeAction?.id === 'hire'">
            <div class="ai-suggestions__field">
              <label>Positions to Open</label>
              <InputNumber v-model="hireForm.positions" :min="1" :max="20" fluid />
            </div>
            <div class="ai-suggestions__field">
              <label>Employment Type</label>
              <Select v-model="hireForm.employmentType" :options="employmentOptions" fluid />
            </div>
            <div class="ai-suggestions__field">
              <label>Target Start Date</label>
              <DatePicker v-model="hireForm.startDate" date-format="M dd, yy" placeholder="Select a date" fluid />
            </div>
            <div class="ai-suggestions__field">
              <label>Notes <span class="ai-suggestions__optional">(optional)</span></label>
              <Textarea v-model="hireForm.notes" rows="2" fluid placeholder="Role requirements, shift, etc." />
            </div>
          </template>

          <Button
            label="Submit Request"
            icon="pi pi-send"
            class="ai-suggestions__submit"
            :loading="submitting"
            @click="handleSubmit"
          />
        </div>

        <div v-else key="success" class="ai-suggestions__success">
          <span class="ai-suggestions__success-icon"><i class="pi pi-check" /></span>
          <h4 class="ai-suggestions__success-title">Form submitted successfully</h4>
          <p class="ai-suggestions__success-text">
            Your {{ activeAction?.title.toLowerCase() }} request has been sent for review.
          </p>
          <Button label="Done" text class="ai-suggestions__done" @click="closeDialog" />
        </div>
      </Transition>
    </Dialog>
  </div>
</template>

<style scoped>
.ai-suggestions__subtitle {
  margin: 0 0 0.85rem;
  font-size: 0.76rem;
  color: var(--p-text-muted-color);
}

.ai-suggestions__status {
  margin: 0 0 1rem;
  padding: 0.75rem 0.85rem;
  border: 1px dashed var(--p-content-border-color);
  border-radius: 0.75rem;
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  text-align: center;
}

.ai-suggestions__status--error {
  border-color: rgba(220, 38, 38, 0.35);
  color: #dc2626;
}

.ai-suggestions__messages {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  margin-bottom: 1.1rem;
}

.ai-suggestions__message {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--p-content-border-color);
  border-left: 3px solid var(--msg-color);
  border-radius: 0.75rem;
  background: var(--p-content-background);
}

.ai-suggestions__message-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 2.1rem;
  height: 2.1rem;
  border-radius: 0.6rem;
  background: color-mix(in srgb, var(--msg-color) 12%, transparent);
  color: var(--msg-color);
  font-size: 0.9rem;
}

.ai-suggestions__message-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.ai-suggestions__message-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.ai-suggestions__message-text {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.5;
  color: var(--p-text-muted-color);
}

.ai-suggestions__section-label {
  margin: 0 0 0.65rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.ai-suggestions__list {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.ai-suggestions__item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.75rem;
  background: var(--p-content-background);
  font-family: var(--font-sans);
  text-align: left;
  cursor: pointer;
  opacity: 0;
  transform: translateY(6px);
  animation: ai-item-in 0.4s ease forwards;
  transition: border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}

.ai-suggestions__item:nth-child(1) {
  animation-delay: 0.05s;
}

.ai-suggestions__item:nth-child(2) {
  animation-delay: 0.15s;
}

.ai-suggestions__item:nth-child(3) {
  animation-delay: 0.25s;
}

.ai-suggestions__item:hover {
  border-color: var(--brand-blue);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(15, 21, 32, 0.08);
}

.ai-suggestions__item-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 2.1rem;
  height: 2.1rem;
  border-radius: 0.6rem;
  background: rgba(74, 125, 255, 0.1);
  color: var(--brand-blue);
  font-size: 0.9rem;
}

.ai-suggestions__item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.ai-suggestions__item-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.ai-suggestions__item-desc {
  font-size: 0.74rem;
  line-height: 1.4;
  color: var(--p-text-muted-color);
}

.ai-suggestions__item-chevron {
  flex-shrink: 0;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  transition: transform 0.15s ease;
}

.ai-suggestions__item:hover .ai-suggestions__item-chevron {
  transform: translateX(3px);
}

.ai-suggestions__form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.ai-suggestions__field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.ai-suggestions__field label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.ai-suggestions__optional {
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.ai-suggestions__submit.p-button {
  margin-top: 0.35rem;
  justify-content: center;
}

.ai-suggestions__success {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 0.75rem 0.5rem 0.25rem;
}

.ai-suggestions__success-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3rem;
  height: 3rem;
  margin-bottom: 0.9rem;
  border-radius: 50%;
  background: rgba(22, 163, 74, 0.14);
  color: #16a34a;
  font-size: 1.3rem;
  animation: ai-success-pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.ai-suggestions__success-title {
  margin: 0 0 0.35rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.ai-suggestions__success-text {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--p-text-muted-color);
}

.dialog-swap-enter-active,
.dialog-swap-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.dialog-swap-enter-from {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.dialog-swap-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}

@keyframes ai-item-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}


@keyframes ai-success-pop {
  0% {
    opacity: 0;
    transform: scale(0.4);
  }
  70% {
    opacity: 1;
    transform: scale(1.08);
  }
  100% {
    transform: scale(1);
  }
}
</style>
