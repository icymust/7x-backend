import { ref } from 'vue'

export type ActionId = 'transport' | 'outsource' | 'hire'

export interface SuggestionAction {
  id: ActionId
  icon: string
  title: string
  description: string
}

export const actions: SuggestionAction[] = [
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

export const actionById = Object.fromEntries(actions.map((a) => [a.id, a])) as Record<ActionId, SuggestionAction>

export const agencyOptions = ['QuickStaff Logistics', 'FlexForce UAE', 'RapidHire Partners']
export const durationOptions = ['1 Week', '2 Weeks', '1 Month']
export const employmentOptions = ['Full-time', 'Part-time']

// Shared between WarehouseManageActions (owns the action list + dialog UI,
// in the "Manage" tab) and WarehouseAiSuggestions (whose cards open the
// same dialog, pre-filled, from the "AI Suggestions" tab) - both are
// mounted side by side in WarehousePanel, so this is module-scope state
// rather than per-component, the same pattern useWarehouseSelection uses.
const transportForm = ref({
  source: '',
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

const activeAction = ref<SuggestionAction | null>(null)
const dialogVisible = ref(false)
const submitting = ref(false)
const submitted = ref(false)

function openAction(action: SuggestionAction, prefill?: { count: number; startDate: Date; source?: string }) {
  activeAction.value = action
  submitting.value = false
  submitted.value = false

  if (prefill) {
    if (action.id === 'outsource') {
      outsourceForm.value = { ...outsourceForm.value, count: prefill.count, startDate: prefill.startDate }
    } else if (action.id === 'hire') {
      hireForm.value = { ...hireForm.value, positions: prefill.count, startDate: prefill.startDate }
    } else if (action.id === 'transport') {
      transportForm.value = {
        ...transportForm.value,
        count: prefill.count,
        date: prefill.startDate,
        source: prefill.source ?? transportForm.value.source,
      }
    }
  }

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

export function useWarehouseActionDialog() {
  return {
    transportForm,
    outsourceForm,
    hireForm,
    activeAction,
    dialogVisible,
    submitting,
    submitted,
    openAction,
    closeDialog,
    handleSubmit,
  }
}
