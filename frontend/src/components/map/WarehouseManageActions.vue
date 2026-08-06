<script setup lang="ts">
import { computed, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Textarea from 'primevue/textarea'
import { warehouses } from '../../data/warehouseData'
import {
  actions,
  agencyOptions,
  durationOptions,
  employmentOptions,
  useWarehouseActionDialog,
  type ActionId,
} from '../../composables/useWarehouseActionDialog'
import transferIllustration from '../../assets/illustrations/transfer.jpeg'
import outsourceIllustration from '../../assets/illustrations/outsource.jpeg'
import interviewIllustration from '../../assets/illustrations/interview.jpeg'

const ACTION_ILLUSTRATION: Record<ActionId, string> = {
  transport: transferIllustration,
  outsource: outsourceIllustration,
  hire: interviewIllustration,
}

const props = defineProps<{ warehouseName: string }>()

const {
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
} = useWarehouseActionDialog()

const otherWarehouseNames = computed(() =>
  warehouses.features.map((f) => f.properties.name).filter((name) => name !== props.warehouseName),
)

// transportForm.source is shared module-wide (see the composable), so it
// can be left pointing at a branch that's no longer valid - either it's
// empty (first load) or it now matches the warehouse being viewed (whoever
// picked it was looking at a different one).
watch(
  otherWarehouseNames,
  (names) => {
    if (!transportForm.value.source || !names.includes(transportForm.value.source)) {
      transportForm.value.source = names[0] ?? ''
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="manage-actions">
    <p class="manage-actions__subtitle">Actions to help stabilize this branch</p>

    <div class="manage-actions__list">
      <button
        v-for="action in actions"
        :key="action.id"
        type="button"
        class="manage-actions__item"
        @click="openAction(action)"
      >
        <span class="manage-actions__item-icon"><i :class="action.icon" /></span>
        <div class="manage-actions__item-body">
          <span class="manage-actions__item-title">{{ action.title }}</span>
          <span class="manage-actions__item-desc">{{ action.description }}</span>
        </div>
        <i class="pi pi-chevron-right manage-actions__item-chevron" />
      </button>
    </div>

    <Dialog
      v-model:visible="dialogVisible"
      modal
      :show-header="false"
      :style="{ width: '40rem' }"
      :pt="{ content: { style: { padding: 0 } } }"
      class="manage-actions__dialog"
    >
      <div class="manage-actions__dialog-body">
        <Button
          icon="pi pi-times"
          text
          rounded
          size="small"
          aria-label="Close"
          class="manage-actions__close"
          @click="closeDialog"
        />

        <Transition name="dialog-swap" mode="out-in">
          <div v-if="!submitted" key="form" class="manage-actions__split">
            <div class="manage-actions__illustration-side">
              <img v-if="activeAction" :src="ACTION_ILLUSTRATION[activeAction.id]" alt="" class="manage-actions__illustration" />
            </div>

            <div class="manage-actions__form-side">
              <h3 class="manage-actions__title">{{ activeAction?.title }}</h3>

              <div class="manage-actions__fields">
              <template v-if="activeAction?.id === 'transport'">
                <div class="manage-actions__field">
                  <label>Source Warehouse</label>
                  <Select v-model="transportForm.source" :options="otherWarehouseNames" fluid placeholder="Select a branch" />
                </div>
                <div class="manage-actions__field">
                  <label>Drivers to Transfer</label>
                  <InputNumber v-model="transportForm.count" :min="1" :max="20" fluid />
                </div>
                <div class="manage-actions__field">
                  <label>Transfer Date</label>
                  <DatePicker v-model="transportForm.date" date-format="M dd, yy" placeholder="Select a date" fluid />
                </div>
                <div class="manage-actions__field">
                  <label>Notes <span class="manage-actions__optional">(optional)</span></label>
                  <Textarea v-model="transportForm.notes" rows="2" fluid placeholder="Any special instructions..." />
                </div>
              </template>

              <template v-else-if="activeAction?.id === 'outsource'">
                <div class="manage-actions__field">
                  <label>Staffing Agency</label>
                  <Select v-model="outsourceForm.agency" :options="agencyOptions" fluid />
                </div>
                <div class="manage-actions__field">
                  <label>Workers Needed</label>
                  <InputNumber v-model="outsourceForm.count" :min="1" :max="50" fluid />
                </div>
                <div class="manage-actions__field">
                  <label>Contract Duration</label>
                  <Select v-model="outsourceForm.duration" :options="durationOptions" fluid />
                </div>
                <div class="manage-actions__field">
                  <label>Start Date</label>
                  <DatePicker v-model="outsourceForm.startDate" date-format="M dd, yy" placeholder="Select a date" fluid />
                </div>
              </template>

              <template v-else-if="activeAction?.id === 'hire'">
                <div class="manage-actions__field">
                  <label>Positions to Open</label>
                  <InputNumber v-model="hireForm.positions" :min="1" :max="20" fluid />
                </div>
                <div class="manage-actions__field">
                  <label>Employment Type</label>
                  <Select v-model="hireForm.employmentType" :options="employmentOptions" fluid />
                </div>
                <div class="manage-actions__field">
                  <label>Target Start Date</label>
                  <DatePicker v-model="hireForm.startDate" date-format="M dd, yy" placeholder="Select a date" fluid />
                </div>
                <div class="manage-actions__field">
                  <label>Notes <span class="manage-actions__optional">(optional)</span></label>
                  <Textarea v-model="hireForm.notes" rows="2" fluid placeholder="Role requirements, shift, etc." />
                </div>
              </template>
              </div>

              <Button
                label="Submit Request"
                icon="pi pi-send"
                class="manage-actions__submit"
                :loading="submitting"
                @click="handleSubmit"
              />
            </div>
          </div>

          <div v-else key="success" class="manage-actions__success">
            <span class="manage-actions__success-icon"><i class="pi pi-check" /></span>
            <h4 class="manage-actions__success-title">Form submitted successfully</h4>
            <p class="manage-actions__success-text">
              Your {{ activeAction?.title.toLowerCase() }} request has been sent for review.
            </p>
            <Button label="Done" text class="manage-actions__done" @click="closeDialog" />
          </div>
        </Transition>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.manage-actions__subtitle {
  margin: 0 0 0.85rem;
  font-size: 0.76rem;
  color: var(--p-text-muted-color);
}

.manage-actions__list {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.manage-actions__item {
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
  animation: manage-item-in 0.4s ease forwards;
  transition: border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}

.manage-actions__item:nth-child(1) {
  animation-delay: 0.05s;
}

.manage-actions__item:nth-child(2) {
  animation-delay: 0.15s;
}

.manage-actions__item:nth-child(3) {
  animation-delay: 0.25s;
}

.manage-actions__item:hover {
  border-color: var(--brand-blue);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(15, 21, 32, 0.08);
}

.manage-actions__item-icon {
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

.manage-actions__item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.manage-actions__item-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.manage-actions__item-desc {
  font-size: 0.74rem;
  line-height: 1.4;
  color: var(--p-text-muted-color);
}

.manage-actions__item-chevron {
  flex-shrink: 0;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  transition: transform 0.15s ease;
}

.manage-actions__item:hover .manage-actions__item-chevron {
  transform: translateX(3px);
}

/* The default Dialog header is turned off (see :show-header="false" in the
   template) specifically so the picture can run the dialog's full height,
   top edge to bottom edge, instead of starting below a header row shared
   with the form side. The title moves down into the form column instead -
   see .manage-actions__title. */
.manage-actions__dialog-body {
  position: relative;
  /* .p-dialog itself doesn't clip its content to its own rounded corners
     (overflow: visible), so without this the illustration's square corners
     poke past the panel's rounded shape at the top-left/bottom-left. */
  overflow: hidden;
  border-radius: var(--p-dialog-border-radius);
}

.manage-actions__close.p-button {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  z-index: 1;
  color: var(--p-text-muted-color);
}

/* 50/50 split, edge to edge - the Dialog's own content padding is zeroed
   via :pt (see template) so the picture side can bleed flush to all four
   of the panel's edges instead of sitting in an inset thumbnail. */
.manage-actions__split {
  display: flex;
  align-items: stretch;
  min-height: 24rem;
}

.manage-actions__illustration-side {
  position: relative;
  flex: 1 1 50%;
  min-width: 0;
  overflow: hidden;
}

/* A soft shadow standing in for a hard border line along the seam between
   the picture and the form - reads as the picture receding slightly rather
   than the two halves just butting into each other. */
.manage-actions__illustration-side::after {
  content: '';
  position: absolute;
  inset: 0;
  box-shadow: inset -14px 0 18px -14px rgba(0, 0, 0, 0.45);
  pointer-events: none;
}

.manage-actions__illustration {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.manage-actions__form-side {
  flex: 1 1 50%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 1.75rem 1.5rem 1.5rem;
}

.manage-actions__title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.01em;
}

.manage-actions__fields {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.manage-actions__field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.manage-actions__field label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.manage-actions__optional {
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.manage-actions__submit.p-button {
  margin-top: 0.35rem;
  justify-content: center;
}

.manage-actions__success {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 1.75rem 1.5rem 1.5rem;
}

.manage-actions__success-icon {
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
  animation: manage-success-pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.manage-actions__success-title {
  margin: 0 0 0.35rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.manage-actions__success-text {
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

@keyframes manage-item-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes manage-success-pop {
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
