<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Skeleton from 'primevue/skeleton'
import { warehouses } from '../../data/warehouseData'
import {
  fetchDecisionPlanActions,
  type DecisionAction,
  type DecisionActionType,
  type DecisionPriority,
} from '../../services/decisionPlanApi'
import { explainDecisionAction } from '../../services/assistantApi'
import { actionById, useWarehouseActionDialog, type SuggestionAction } from '../../composables/useWarehouseActionDialog'

const props = defineProps<{ storeId: string; isOpen: boolean }>()

const { openAction } = useWarehouseActionDialog()

// The Decision Engine (GET .../decision-plan) computes *what* to do -
// rule-based, no natural-language attached. The "message" for each card
// comes from a separate call to POST /assistant/explain, which is what
// actually runs it through Ollama. Loaded lazily - see the isOpen watcher -
// rather than on mount, since this component stays mounted (just hidden)
// while its accordion panel is collapsed.
// One parsed bullet from the explain message - "label" is the leading
// "Recommendation"/"Evidence"/"Timing"/"Reason" tag the prompt asks Ollama
// for (see SELECTED_ACTION_PROMPT in llm_service.py), null for lines that
// don't match that shape (e.g. the plain-sentence fallback).
interface ExplanationLine {
  label: string | null
  text: string
}

interface SuggestionMessage {
  id: string
  icon: string
  color: string
  priority: DecisionPriority
  title: string
  lines: ExplanationLine[]
  explaining: boolean
  // The action (managed in the "Manage" tab) that actually resolves this
  // case, with the numbers/date the Decision Engine itself calls for - null
  // for horizons the engine can't act on yet (schedule_reallocation,
  // overtime - see decision_stages.pending_input_data) or a transfer where
  // this store is the surplus source rather than the recipient.
  resolveAction: { action: SuggestionAction; count: number; startDate: Date; source?: string } | null
}

const PRIORITY_COLOR: Record<DecisionPriority, string> = {
  critical: '#dc2626',
  high: '#f97316',
  medium: '#2563eb',
  low: '#16a34a',
}

// Placeholder line widths for the skeleton, one entry per eventual bullet
// (Recommendation/Evidence/Timing/Reason - see SELECTED_ACTION_PROMPT in
// llm_service.py) shaped to roughly match how those bullets actually wrap.
const SKELETON_SECTIONS: string[][] = [
  ['55%'],
  ['100%', '80%'],
  ['70%'],
  ['100%', '60%'],
]

const ACTION_TYPE_META: Record<DecisionActionType, { icon: string; title: string }> = {
  emergency_outsourcing: { icon: 'pi pi-exclamation-triangle', title: 'Emergency outsourcing' },
  planned_outsourcing: { icon: 'pi pi-briefcase', title: 'Planned outsourcing' },
  permanent_hiring: { icon: 'pi pi-user-plus', title: 'Permanent hiring' },
  store_transfer: { icon: 'pi pi-truck', title: 'Transfer couriers' },
  schedule_reallocation: { icon: 'pi pi-calendar', title: 'Schedule reallocation' },
  overtime: { icon: 'pi pi-clock', title: 'Overtime' },
}

const hasLoadedSuggestions = ref(false)
const loadingActions = ref(false)
const suggestionsError = ref<string | null>(null)
const suggestionMessages = ref<SuggestionMessage[]>([])
let planningRunId = 0

function dateLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function resolveActionFor(action: DecisionAction): SuggestionMessage['resolveAction'] {
  const startDate = new Date(action.deadline)

  switch (action.action_type) {
    case 'emergency_outsourcing':
    case 'planned_outsourcing':
      return { action: actionById.outsource, count: action.couriers, startDate }
    case 'permanent_hiring':
      return { action: actionById.hire, count: action.couriers, startDate }
    case 'store_transfer':
      // This store is the surplus source, not the one receiving couriers -
      // nothing for its own Manage tab to trigger.
      if (action.store_id !== props.storeId) return null
      return {
        action: actionById.transport,
        count: action.couriers,
        startDate,
        source: warehouses.features.find((f) => f.properties.storeId === action.from_store_id)?.properties.name,
      }
    default:
      return null
  }
}

function messageFor(action: DecisionAction): SuggestionMessage {
  const meta = ACTION_TYPE_META[action.action_type]
  return {
    id: action.action_id,
    icon: meta.icon,
    color: PRIORITY_COLOR[action.priority],
    priority: action.priority,
    title: meta.title,
    lines: [],
    explaining: true,
    resolveAction: resolveActionFor(action),
  }
}

// Ollama is prompted (see SELECTED_ACTION_PROMPT in llm_service.py) for
// exactly four "- Label: sentence." bullets, but returns them joined by a
// literal "\n" - not an actual line break - so a plain newline split does
// nothing; this splits on both to be safe either way, strips the leading
// "- " markdown bullet, and pulls the label out of each line so it can be
// rendered as its own list item instead of one run-on paragraph.
function parseExplanation(raw: string): ExplanationLine[] {
  return raw
    .split(/\\n|\n/)
    .map((line) => line.trim().replace(/^-+\s*/, ''))
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^([A-Za-z][A-Za-z\s]{1,24}):\s*(.+)$/)
      return match ? { label: match[1].trim(), text: match[2].trim() } : { label: null, text: line }
    })
}

// Fallback for when Ollama is disabled/unavailable or the explain call
// fails - built straight from the action's own fields so it never depends
// on the LLM being up.
function fallbackLines(action: DecisionAction): ExplanationLine[] {
  return [{ label: null, text: `${action.couriers} couriers needed by ${dateLabel(action.deadline)} (${action.priority} priority).` }]
}

async function explainInto(action: DecisionAction, message: SuggestionMessage) {
  try {
    const result = await explainDecisionAction(planningRunId, action.action_id)
    message.lines = result.message ? parseExplanation(result.message) : fallbackLines(action)
  } catch {
    message.lines = fallbackLines(action)
  } finally {
    message.explaining = false
  }
}

async function loadSuggestions() {
  loadingActions.value = true
  suggestionsError.value = null
  try {
    const { planningRunId: runId, actions: decisionActions } = await fetchDecisionPlanActions(props.storeId)
    planningRunId = runId
    suggestionMessages.value = decisionActions.map(messageFor)
    loadingActions.value = false

    // Each card's explanation streams in independently - a slow or failed
    // Ollama call on one action shouldn't hold up the others.
    decisionActions.forEach((action, index) => {
      const message = suggestionMessages.value[index]
      if (message) explainInto(action, message)
    })
  } catch {
    suggestionsError.value = 'Could not load AI suggestions. Try again later.'
    loadingActions.value = false
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
</script>

<template>
  <div class="ai-suggestions">
    <p class="ai-suggestions__subtitle">AI-generated suggestions for this branch</p>

    <div v-if="loadingActions" class="ai-suggestions__status">Loading suggestions…</div>
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
        :style="{ '--msg-icon-color': message.color }"
      >
        <span class="ai-suggestions__message-icon"><i :class="message.icon" /></span>
        <div class="ai-suggestions__message-body">
          <span class="ai-suggestions__message-title">{{ message.title }}</span>
          <div v-if="message.explaining" class="ai-suggestions__skeleton">
            <div
              v-for="(widths, sectionIndex) in SKELETON_SECTIONS"
              :key="sectionIndex"
              class="ai-suggestions__skeleton-section"
            >
              <Skeleton
                v-for="(width, lineIndex) in widths"
                :key="lineIndex"
                height="0.65rem"
                :width="width"
                class="ai-suggestions__skeleton-line"
              />
            </div>
            <Skeleton width="7.5rem" height="1.9rem" border-radius="6px" class="ai-suggestions__skeleton-button" />
          </div>
          <template v-else>
            <ul class="ai-suggestions__message-lines">
              <li
                v-for="(line, index) in message.lines"
                :key="index"
                class="ai-suggestions__message-line ai-suggestions__message-line--fade-in"
                :style="{ animationDelay: `${index * 0.12}s` }"
              >
                <strong v-if="line.label">{{ line.label }}:</strong> {{ line.text }}
              </li>
            </ul>
            <Button
              v-if="message.resolveAction"
              size="small"
              outlined
              :icon="message.resolveAction.action.icon"
              :label="message.resolveAction.action.title"
              class="ai-suggestions__message-action ai-suggestions__message-action--fade-in"
              :style="{ animationDelay: `${message.lines.length * 0.12}s` }"
              @click="
                openAction(message.resolveAction.action, {
                  count: message.resolveAction.count,
                  startDate: message.resolveAction.startDate,
                  source: message.resolveAction.source,
                })
              "
            />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-suggestions__subtitle {
  margin: 0 0 0.85rem;
  font-size: 0.76rem;
  color: var(--p-text-muted-color);
}

.ai-suggestions__status {
  margin: 0;
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
}

.ai-suggestions__message {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--p-content-border-color);
  border-left: 3px solid var(--brand-blue);
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
  background: color-mix(in srgb, var(--msg-icon-color) 12%, transparent);
  color: var(--msg-icon-color);
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

.ai-suggestions__skeleton {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.ai-suggestions__skeleton-section {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.ai-suggestions__skeleton-button {
  margin-top: 0.15rem;
}

.ai-suggestions__message-lines {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.ai-suggestions__message-line {
  position: relative;
  padding-left: 0.85rem;
  font-size: 0.78rem;
  line-height: 1.5;
  color: var(--p-text-muted-color);
}

.ai-suggestions__message-line::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.55em;
  width: 0.3rem;
  height: 0.3rem;
  border-radius: 50%;
  background: var(--brand-blue);
}

.ai-suggestions__message-line strong {
  color: var(--p-text-color);
  font-weight: 700;
}

/* Each bullet (and the button after them) fades/slides in on its own,
   staggered via an inline animation-delay - see the template - so the
   explanation reads as arriving block by block rather than popping in at
   once. */
.ai-suggestions__message-line--fade-in,
.ai-suggestions__message-action--fade-in.p-button {
  opacity: 0;
  animation: ai-block-fade-in 0.35s ease forwards;
}

@keyframes ai-block-fade-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.ai-suggestions__message-action.p-button {
  align-self: flex-start;
  margin-top: 0.55rem;
  font-size: 0.76rem;
  padding: 0.35rem 0.7rem;
  color: var(--brand-blue);
  border-color: var(--brand-blue);
}

.ai-suggestions__message-action.p-button:hover {
  background: color-mix(in srgb, var(--brand-blue) 10%, transparent);
}
</style>
