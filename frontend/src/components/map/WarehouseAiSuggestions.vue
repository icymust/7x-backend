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
import { explainDecisionAction, type SelectedActionExplanation } from '../../services/assistantApi'
import { actionById, useWarehouseActionDialog, type SuggestionAction } from '../../composables/useWarehouseActionDialog'

const props = defineProps<{ storeId: string; isOpen: boolean }>()

const { openAction } = useWarehouseActionDialog()

// The Decision Engine (GET .../decision-plan) computes *what* to do -
// rule-based, no natural-language attached. The "message" for each card
// comes from a separate call to POST /assistant/explain, which is what
// actually runs it through Ollama and returns the structured
// SelectedActionExplanation shape. Loaded lazily - see the isOpen watcher -
// rather than on mount, since this component stays mounted (just hidden)
// while its accordion panel is collapsed.
interface SuggestionMessage {
  id: string
  icon: string
  color: string
  priority: DecisionPriority
  // Shown as a plain "N couriers" tag straight from the Decision Engine's
  // own action - not asked of Ollama, since a plain headcount doesn't need
  // an LLM and free-form phrasing of it was error-prone (ambiguous signs,
  // duplicated wording across entries).
  couriers: number
  explanation: SelectedActionExplanation | null
  explaining: boolean
  // Reasons are collapsed by default - only the recommendation/impact/timing
  // show up front, see the toggle button in the template.
  reasonsExpanded: boolean
  // The action (managed in the "Manage" tab) that actually resolves this
  // case, with the numbers/date the Decision Engine itself calls for - null
  // for horizons the engine can't act on yet (schedule_reallocation and
  // overtime - see decision_stages.pending_input_data).
  resolveAction: { action: SuggestionAction; count: number; startDate: Date; source?: string } | null
}

const PRIORITY_COLOR: Record<DecisionPriority, string> = {
  critical: '#dc2626',
  high: '#f97316',
  medium: '#2563eb',
  low: '#16a34a',
}

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
  return {
    id: action.action_id,
    icon: ACTION_TYPE_META[action.action_type].icon,
    color: PRIORITY_COLOR[action.priority],
    priority: action.priority,
    couriers: action.couriers,
    explanation: null,
    explaining: true,
    reasonsExpanded: false,
    resolveAction: resolveActionFor(action),
  }
}

// Fallback for when Ollama is disabled/unavailable, the explain call fails,
// or the response didn't match the expected shape (backend already
// validates this - see _parse_selected_action_message in llm_service.py -
// so a non-null result.message can be trusted as-is). Built straight from
// the action's own fields so it never depends on the LLM being up.
function fallbackExplanation(action: DecisionAction): SelectedActionExplanation {
  const range = `${dateLabel(action.shortage_period.date_from)} - ${dateLabel(action.shortage_period.date_to)}`
  return {
    recommendation: `${action.couriers} couriers needed for ${ACTION_TYPE_META[action.action_type].title.toLowerCase()}.`,
    timing: `${range}, deadline ${dateLabel(action.deadline)}.`,
    reasons: [action.reason.replace(/_/g, ' ')],
  }
}

async function explainInto(action: DecisionAction, message: SuggestionMessage) {
  try {
    const result = await explainDecisionAction(planningRunId, action.action_id)
    message.explanation = result.message ?? fallbackExplanation(action)
  } catch {
    message.explanation = fallbackExplanation(action)
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
    suggestionMessages.value = decisionActions.slice(0, 4).map(messageFor)
    loadingActions.value = false

    // Each card's explanation streams in independently - a slow or failed
    // Ollama call on one action shouldn't hold up the others.
    decisionActions.slice(0, 4).forEach((action, index) => {
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
          <div v-if="message.explaining" class="ai-suggestions__skeleton">
            <Skeleton height="0.7rem" width="92%" class="ai-suggestions__skeleton-line" />
            <div class="ai-suggestions__skeleton-pills">
              <Skeleton height="1.3rem" width="38%" border-radius="999px" />
              <Skeleton height="1.3rem" width="30%" border-radius="999px" />
            </div>
            <Skeleton height="0.65rem" width="70%" class="ai-suggestions__skeleton-line" />
            <div class="ai-suggestions__skeleton-section">
              <Skeleton height="0.65rem" width="100%" class="ai-suggestions__skeleton-line" />
              <Skeleton height="0.65rem" width="55%" class="ai-suggestions__skeleton-line" />
            </div>
            <Skeleton width="7.5rem" height="1.9rem" border-radius="6px" class="ai-suggestions__skeleton-button" />
          </div>
          <template v-else-if="message.explanation">
            <p class="ai-suggestions__recommendation ai-suggestions__block--fade-in">
              {{ message.explanation.recommendation }}
            </p>

            <div class="ai-suggestions__impact ai-suggestions__block--fade-in" style="animation-delay: 0.1s">
              <span class="ai-suggestions__impact-chip">
                <i class="pi pi-users" />
                {{ message.couriers }} {{ message.couriers === 1 ? 'courier' : 'couriers' }}
              </span>
            </div>

            <p class="ai-suggestions__timing ai-suggestions__block--fade-in" style="animation-delay: 0.2s">
              <i class="pi pi-calendar" /> {{ message.explanation.timing }}
            </p>

            <button
              v-if="message.explanation.reasons.length"
              type="button"
              class="ai-suggestions__reasons-toggle ai-suggestions__block--fade-in"
              style="animation-delay: 0.25s"
              @click="message.reasonsExpanded = !message.reasonsExpanded"
            >
              <i :class="message.reasonsExpanded ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
              {{ message.reasonsExpanded ? 'Hide reasons' : `Show reasons (${message.explanation.reasons.length})` }}
            </button>

            <Transition name="ai-suggestions__reasons">
              <div v-if="message.reasonsExpanded" class="ai-suggestions__reasons-collapse">
                <ul class="ai-suggestions__message-lines">
                  <li
                    v-for="(reason, index) in message.explanation.reasons"
                    :key="index"
                    class="ai-suggestions__message-line ai-suggestions__block--fade-in"
                    :style="{ animationDelay: `${index * 0.1}s` }"
                  >
                    {{ reason }}
                  </li>
                </ul>
              </div>
            </Transition>

            <Button
              v-if="message.resolveAction"
              size="small"
              outlined
              :icon="message.resolveAction.action.icon"
              :label="message.resolveAction.action.title"
              class="ai-suggestions__message-action ai-suggestions__block--fade-in"
              style="animation-delay: 0.3s"
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
  gap: 0.9rem;
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
  gap: 0.55rem;
}

.ai-suggestions__skeleton {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.ai-suggestions__skeleton-pills {
  display: flex;
  gap: 0.4rem;
}

.ai-suggestions__skeleton-section {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.ai-suggestions__skeleton-button {
  margin-top: 0.15rem;
}

.ai-suggestions__recommendation {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 600;
  line-height: 1.5;
  color: var(--p-text-color);
}

.ai-suggestions__impact {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.ai-suggestions__impact-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  border: 1px solid var(--p-content-border-color);
  background: transparent;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--p-text-color);
  white-space: nowrap;
}

.ai-suggestions__impact-chip .pi {
  font-size: 0.65rem;
  color: var(--brand-blue);
}

.ai-suggestions__timing {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  font-size: 0.76rem;
  color: var(--p-text-muted-color);
}

.ai-suggestions__timing .pi {
  font-size: 0.72rem;
  color: var(--brand-blue);
}

.ai-suggestions__reasons-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  align-self: flex-start;
  padding: 0;
  border: none;
  background: none;
  font-family: var(--font-sans);
  font-size: 0.74rem;
  font-weight: 600;
  color: var(--brand-blue);
  cursor: pointer;
}

.ai-suggestions__reasons-toggle .pi {
  font-size: 0.65rem;
}

.ai-suggestions__message-lines {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

/* Grow/shrink + fade for the reasons list as a whole (see the toggle
   button in the template), via the CSS grid 0fr/1fr row-sizing trick -
   animating to/from an intrinsic "auto" height isn't otherwise possible
   without measuring in JS. The per-item stagger on each <li> still runs on
   top of this every time it opens. */
.ai-suggestions__reasons-collapse {
  display: grid;
  grid-template-rows: 1fr;
}

.ai-suggestions__reasons-enter-active,
.ai-suggestions__reasons-leave-active {
  transition: grid-template-rows 0.25s ease, opacity 0.2s ease;
}

.ai-suggestions__reasons-enter-from,
.ai-suggestions__reasons-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
}

.ai-suggestions__reasons-collapse > .ai-suggestions__message-lines {
  overflow: hidden;
  min-height: 0;
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

/* Each block (recommendation, impact chips, timing, each reason, and the
   button after them) fades/slides in on its own, staggered via an inline
   animation-delay - see the template - so the explanation reads as
   arriving piece by piece rather than popping in at once. */
.ai-suggestions__block--fade-in {
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
