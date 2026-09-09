import type { ApiSchemas } from '../api/generated'

export type PreferenceValues = ApiSchemas['PreferenceValues']
export const baselinePreferences: PreferenceValues = {
  pace: 'self_paced', format: 'text', explanation_detail: 'brief', breaks: false,
  repeat_practice: false, personalisation_enabled: true, support_amount: 'standard', feedback_form: 'inline',
}
