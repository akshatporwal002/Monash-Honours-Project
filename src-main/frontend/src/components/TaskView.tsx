import { ActivityContinuation } from './ActivityContinuation'
import { EpisodeSnapshot, EpisodeCircuitText } from "./EpisodeSnapshot"
import { EpisodeFields } from "./EpisodeFields"
import { EpisodeSupport } from './EpisodeSupport'
import { LearnerPreferences } from './LearnerPreferences'
import { baselinePreferences } from '../app/preferences'
import { PreferenceWorkspace } from './PreferenceWorkspace'
import type { ApiSchemas } from '../api/generated'
import type { EpisodePayload, EpisodeState, EpisodeCheckpointSnapshot } from "../app/types"
import { ArrowLeft, Play } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { DragEvent, ReactNode } from 'react'

import { ApiError, api, csrfToken } from '../app/api'
import type { GateOperation, LearningTask, SimulationResult, TaskSubmission } from '../app/types'
import { createFeedbackApiClient, FeedbackPanel } from '../features/feedback'
import {
  AlertDialog,
  Button,
  Card,
  DescriptionList,
  Field,
  Tag,
  Textarea,
  bloomKnowledgeLabels,
  bloomProcessPlain,
  cx,
} from './ui'
import type { DescriptionItem } from './ui'
import type { BloomKnowledge, BloomProcess } from '../features/assessment/types'
import styles from './TaskView.module.css'

const episodeTaskTypes = ['prediction', 'reasoning', 'explanation', 'revision', 'reflection', 'transfer']
const emptyEpisode = (): EpisodePayload => ({ schema_version: 'learnlens.episode.v1', supported: {} })

const defaultOptions = [
  { id: 'a', text: 'It creates an equal superposition of |0⟩ and |1⟩.' },
  { id: 'b', text: 'It measures the qubit immediately.' },
  { id: 'c', text: 'It always changes |0⟩ to |1⟩.' },
  { id: 'd', text: 'It removes all quantum interference.' },
]

function attemptLabel(attempt: TaskSubmission): string {
  if (attempt.formal_assessment) return 'Assessment response saved'
  return attempt.score === null ? 'Response saved' : `${attempt.score}%`
}

function taskMode(task: LearningTask): 'mcq' | 'multi' | 'code-explanation' | 'code-completion' | 'circuit' | 'text' | 'unsupported' {
  if (['multiple_choice', 'quiz'].includes(task.task_type)) return 'mcq'
  if (task.task_type === 'multiple_answer') return 'multi'
  if (task.task_type === 'code_explanation') return 'code-explanation'
  if (['code', 'code_completion'].includes(task.task_type)) return 'code-completion'
  if (['circuit', 'quantum_circuit'].includes(task.task_type)) return 'circuit'
  if (task.task_type === 'short_answer' || episodeTaskTypes.includes(task.task_type)) return 'text'
  return 'unsupported'
}

function codeTokens(code: string): ReactNode[] {
  const tokenPattern = /(\b(?:from|import|as|def|return|for|in|if|else|QuantumCircuit|AerSimulator)\b|'[^']*'|"[^"]*"|#[^\n]*)/g
  return code.split(tokenPattern).filter(Boolean).map((token, index) => {
    const className = token.startsWith('#')
      ? styles.tokenComment
      : token.startsWith("'") || token.startsWith('"')
        ? styles.tokenString
        : /^(from|import|as|def|return|for|in|if|else)$/.test(token)
          ? styles.tokenKeyword
          : /^(QuantumCircuit|AerSimulator)$/.test(token)
            ? styles.tokenClass
            : ''
    return <span className={className} key={`${token}-${index}`}>{token}</span>
  })
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'The learning service could not complete that action. Please try again.'
}

function blocksAssessmentWork(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409 && error.code !== 'assessment_write_busy'
}

function multipleAnswers(answer: string): string[] {
  try {
    const parsed: unknown = JSON.parse(answer)
    return Array.isArray(parsed)
      ? [...new Set(parsed.filter((item): item is string => typeof item === 'string'))]
      : []
  } catch {
    return []
  }
}

function isGateOperation(value: unknown): value is GateOperation {
  if (!value || typeof value !== 'object') return false
  const operation = value as { gate?: unknown; targets?: unknown }
  if (
    !['h', 'x', 'cx'].includes(String(operation.gate))
    || !Array.isArray(operation.targets)
    || !operation.targets.every((target) =>
      typeof target === 'number'
      && Number.isInteger(target)
      && target >= 0
      && target < 5)
  ) {
    return false
  }
  return operation.gate === 'cx'
    ? operation.targets.length === 2
    : operation.targets.length === 1
}

function circuitOperations(circuit: unknown): GateOperation[] {
  if (!circuit || typeof circuit !== 'object') return []
  const operations = (circuit as { operations?: unknown }).operations
  return Array.isArray(operations) ? operations.filter(isGateOperation) : []
}

function submissionKey(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  return `submission-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function readableConditions(value: Record<string, unknown> | unknown[]): string {
  const describe = (item: unknown): string => {
    if (Array.isArray(item)) return item.map(describe).join(', ')
    if (item && typeof item === 'object') {
      return Object.entries(item).map(([key, nested]) =>
        `${key.replaceAll('_', ' ')}: ${describe(nested)}`).join('; ')
    }
    if (typeof item === 'boolean') return item ? 'yes' : 'no'
    return item === null ? 'None declared' : String(item).replaceAll('_', ' ')
  }
  const values = Array.isArray(value) ? value : Object.values(value)
  return values.map(describe).join(', ') || 'None declared'
}

function readablePurpose(purpose: string): string {
  const lower = purpose.replaceAll('_', ' ').toLowerCase()
  return lower.charAt(0).toUpperCase() + lower.slice(1)
}

export function TaskView({
  task,
  onClose,
  onSubmitted,
}: {
  task: LearningTask
  onClose: () => void
  onSubmitted: () => Promise<void>
}) {
  const [checkpointHistory, setCheckpointHistory] = useState<EpisodeCheckpointSnapshot[]>([])
  const [checkpointOffset, setCheckpointOffset] = useState<number | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const mode = taskMode(task)
  const [episode, setEpisode] = useState<EpisodePayload>(emptyEpisode)
  const [episodeState, setEpisodeState] = useState<EpisodeState | null>(task.episode_plan ?? null)
  const [preferenceVersion, setPreferenceVersion] = useState(0)
  const [effective, setEffective] = useState<ApiSchemas['EffectivePreferences'] | null>(null)
  const [preferenceError, setPreferenceError] = useState('')
  const [preferenceReload, setPreferenceReload] = useState(0)
  const transferActive = Boolean(episodeState?.transfer)
  useEffect(() => {
    const controller = new AbortController()
    Promise.resolve().then(() => api.student.effectivePreferences(task.id, controller.signal)).then(value => {
      if (typeof value?.version !== 'number' || !value.values || !Array.isArray(value.limitations)) throw new Error('Invalid effective preference response')
      if (!controller.signal.aborted) { setEffective(value); setPreferenceError('') }
    }).catch(() => { if (!controller.signal.aborted) { setEffective(null); setPreferenceError('Workspace preferences could not be applied. Baseline controls remain available.') } })
    return () => controller.abort()
  }, [task.id, preferenceVersion, transferActive, preferenceReload])
  const presentation = effective?.values ?? baselinePreferences
  const hasEpisode = Boolean(task.episode_plan) || episodeTaskTypes.includes(task.task_type)
  const [qubits, setQubits] = useState(task.episode_plan ? 1 : 2)
  const [circuitExtras, setCircuitExtras] = useState<Record<string, unknown>>({})
  const idempotencyKeyRef = useRef<string | null>(null)
  const restoredDraftTaskRef = useRef<string | null>(null)
  const feedbackClient = useMemo(
    () => createFeedbackApiClient({ getCsrfToken: csrfToken }),
    [],
  )
  const [selectedOption, setSelectedOption] = useState('')
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])
  const [answer, setAnswer] = useState('')
  const [code, setCode] = useState(task.starter_code ?? '')
  const [savedEpisodeCode, setSavedEpisodeCode] = useState<string | null>(null)
  const [operations, setOperations] = useState<GateOperation[]>([])
  const [simulation, setSimulation] = useState<SimulationResult | null>(null)
  const [submission, setSubmission] = useState<TaskSubmission | null>(null)
  const [attempts, setAttempts] = useState<TaskSubmission[] | null>(null)
  const [attemptsError, setAttemptsError] = useState('')
  const [workStartId, setWorkStartId] = useState<string | null>(null)
  const [workConflict, setWorkConflict] = useState(false)
  const [draftLoading, setDraftLoading] = useState(true)
  const [draftError, setDraftError] = useState('')
  const [draftReload, setDraftReload] = useState(0)
  const [statusMessage, setStatusMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [confirmLeave, setConfirmLeave] = useState(false)
  const options = task.options?.length ? task.options : defaultOptions
  const qiskitCode = task.starter_code || [
    'from qiskit import QuantumCircuit',
    'from qiskit_aer import AerSimulator',
    '',
    'circuit = QuantumCircuit(2, 2)',
    'circuit.h(0)',
    'circuit.cx(0, 1)',
    'circuit.measure([0, 1], [0, 1])',
  ].join('\n')

  useEffect(() => {
    const controller = new AbortController()
    const restore = async () => {
      // A retry after a successful restore must not replace unsaved local edits.
      const draft = restoredDraftTaskRef.current === task.id
        ? null
        : await api.student.draft(task.id, controller.signal)
      if (controller.signal.aborted) return null
      restoredDraftTaskRef.current = task.id
      if (task.assessment) {
        try {
          const started = await api.student.startAssessment(
            task.id, task.assessment.task_form_version_id, controller.signal,
          )
          if (!controller.signal.aborted) {
            setWorkStartId(started.assessment_work_start_id ?? null)
            setWorkConflict(false)
            if (task.episode_plan) setEpisodeState(await api.student.episodeState(task.id, controller.signal))
          }
        } catch (error) {
          if (!controller.signal.aborted) {
            setWorkConflict(blocksAssessmentWork(error))
            setDraftError(messageFor(error))
          }
        }
      }
      return draft
    }
    restore().then((draft) => {
        if (!draft) return
        setAnswer(draft.answer)
        if (draft.code !== null) setCode(draft.code)
        setSavedEpisodeCode(draft.code)
        if (draft.circuit) { setCircuitExtras(draft.circuit); setQubits(draft.circuit.qubits) }
        const optionIds = new Set(options.map((option) => option.id))
        if (mode === 'mcq') {
          setSelectedOption(optionIds.has(draft.answer) ? draft.answer : '')
        } else if (mode === 'multi') {
          setSelectedOptions(
            multipleAnswers(draft.answer).filter((answerId) => optionIds.has(answerId)),
          )
        } else if (mode === 'code-completion') setCode(draft.code ?? task.starter_code ?? '')
        else if (mode === 'circuit') setOperations(circuitOperations(draft.circuit))
        else setAnswer(draft.answer)
        if (draft.episode) setEpisode(draft.episode)
        setStatusMessage('Saved draft restored.')
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setDraftError(`Saved work could not be restored. ${messageFor(error)}`)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setDraftLoading(false)
      })
    return () => controller.abort()
  }, [draftReload, mode, options, task.id, task.starter_code, task.assessment, task.episode_plan])

  useEffect(() => {
    const controller = new AbortController()
    api.student.attempts(task.id, controller.signal)
      .then((items) => {
        setAttempts(items)
        setAttemptsError('')
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setAttempts([])
          setAttemptsError(messageFor(error))
        }
      })
    return () => controller.abort()
  }, [task.id])

  const latestFeedbackReference = submission?.feedback_reference
    ?? attempts?.find((attempt) => attempt.feedback_reference)?.feedback_reference

  useEffect(() => {
    if (!task.episode_plan || draftLoading) return
    const controller = new AbortController()
    api.student.checkpointHistory(task.id, controller.signal).then(page => { if (!controller.signal.aborted) { setCheckpointHistory(page.items); setCheckpointOffset(page.next_offset) } }).catch(() => { if (!controller.signal.aborted) setStatusMessage('Earlier predictions could not be loaded. Your current work remains available.') })
    return () => controller.abort()
  }, [task.id, task.episode_plan, draftLoading, episode.supported.prediction_checkpoint_id, episode.transfer?.process.prediction_checkpoint_id])

  const savedRunId = episode.transfer?.process.simulation_references?.at(-1)?.run_id ?? episode.supported.simulation_references?.at(-1)?.run_id
  useEffect(() => {
    if (!savedRunId || draftLoading) return
    let cancelled = false
    api.student.savedSimulation(savedRunId).then(result => { if (!cancelled) setSimulation(result) }).catch(() => { if (!cancelled) setStatusMessage('Saved simulation could not be loaded. Your response remains saved; try again.') })
    return () => { cancelled = true }
  }, [savedRunId, draftLoading])

  const payload = useMemo(() => ({
    assessment_work_start_id: workStartId,
    ...(hasEpisode ? { episode } : {}),
    answer: mode === 'mcq'
      ? selectedOption
      : mode === 'multi'
        ? JSON.stringify(selectedOptions)
        : answer,
    code: mode === 'code-completion' ? code : hasEpisode ? savedEpisodeCode : undefined,
    circuit: mode === 'circuit' ? { ...circuitExtras, qubits, operations } : hasEpisode && Object.keys(circuitExtras).length ? circuitExtras : undefined,
  }), [answer, code, mode, operations, selectedOption, selectedOptions, workStartId, episode, hasEpisode, qubits, circuitExtras, savedEpisodeCode])

  const valid = mode === 'unsupported' ? false : hasEpisode ? Boolean(episode.supported.prediction?.answer?.trim() || episode.supported.reasoning?.trim() || episode.supported.explanation?.trim() || episode.supported.reflection?.trim()) : mode === 'mcq'
    ? Boolean(selectedOption)
    : mode === 'multi'
      ? selectedOptions.length > 0
    : mode === 'circuit'
      ? operations.length > 0
      : mode === 'code-completion'
        ? Boolean(code.trim())
      : Boolean(answer.trim())

  const touch = () => { idempotencyKeyRef.current = null; setDirty(true) }
  const changeSupportedInput = () => {
    setSimulation(null)
    if (hasEpisode) setEpisode(current => ({ ...current, supported: { ...current.supported, prediction_checkpoint_id: null, simulation_references: [] } }))
    touch()
  }

  const requestClose = () => {
    if (dirty) setConfirmLeave(true)
    else onClose()
  }

  const changeOperations = (next: GateOperation[] | ((current: GateOperation[]) => GateOperation[])) => {
    setOperations(next)
    setSimulation(null)
    changeSupportedInput()
  }

  const addGate = (gate: GateOperation['gate'], target = 0) => {
    changeOperations((current) => [
      ...current,
      { gate, targets: gate === 'cx' ? [0, 1] : [target] },
    ])
  }

  const dropGate = (event: DragEvent<HTMLDivElement>, target: number) => {
    event.preventDefault()
    const gate = event.dataTransfer.getData('application/x-quantum-gate') as GateOperation['gate']
    if (gate === 'h' || gate === 'x' || gate === 'cx') addGate(gate, target)
  }

  const runSimulation = async () => {
    if (workConflict || (task.assessment && !workStartId)) return
    setBusy(true)
    setSimulation(null)
    setStatusMessage('')
    try {
      await api.student.saveDraft(task.id, payload)
      const result = await api.student.simulate(operations, task.id, episode.supported.prediction_checkpoint_id, undefined, episodeState?.supported_part_id, qubits)
      setSimulation(result)
      if (hasEpisode && result.circuit_version_id) {
        const next = { ...episode, supported: { ...episode.supported, simulation_references: [...(episode.supported.simulation_references ?? []), { run_id: result.run_id, circuit_version_id: result.circuit_version_id }] } }
        setEpisode(next)
        await api.student.saveDraft(task.id, { ...payload, episode: next })
      }
      setStatusMessage('Simulation completed and saved with 1,024 shots.')
    } catch (error) {
      if (blocksAssessmentWork(error)) setWorkConflict(true)
      setStatusMessage(messageFor(error))
    } finally {
      setBusy(false)
    }
  }

  const save = async (submit: boolean) => {
    if (workConflict || (task.assessment && !workStartId)) return
    setBusy(true)
    setStatusMessage('')
    try {
      if (submit) {
        const idempotency_key = task.assessment
          ? (idempotencyKeyRef.current ??= submissionKey())
          : undefined
        const result = await api.student.submit(task.id, { ...payload, idempotency_key })
        idempotencyKeyRef.current = null
        setSubmission(result)
        setAttempts((current) => [
          result,
          ...(current ?? []).filter((item) => item.id !== result.id),
        ])
        setStatusMessage('Activity submitted. Your grounded feedback is ready below.')
        setDirty(false)
        await onSubmitted()
      } else {
        await api.student.saveDraft(task.id, payload)
        setStatusMessage('Draft saved.')
        setDirty(false)
      }
    } catch (error) {
      if (blocksAssessmentWork(error)) setWorkConflict(true)
      setStatusMessage(messageFor(error))
    } finally {
      setBusy(false)
    }
  }

  const saveBreak = async () => {
    setBusy(true)
    try {
      await api.student.saveDraft(task.id, payload)
      setDirty(false)
      setStatusMessage('Draft saved. You can take a break and return to your saved work. Deadlines are unchanged.')
    } catch (error) { if (blocksAssessmentWork(error)) setWorkConflict(true); setStatusMessage(messageFor(error)) }
    finally { setBusy(false) }
  }
  const repeatPractice = async () => {
    if (dirty || task.assessment || hasEpisode) return
    setBusy(true)
    try {
      const current = await api.student.effectivePreferences(task.id)
      setEffective(current)
      if (!current.repeat_allowed || !current.values.repeat_practice) { setStatusMessage('Repeat practice is not available for this task. Your work is unchanged.'); return }
      setAnswer(''); setCode(task.starter_code ?? ''); setSelectedOption(''); setSelectedOptions([])
      setOperations([]); setSimulation(null); touch()
      setStatusMessage('New practice draft started. Earlier responses and feedback remain in your records.')
    } catch { setStatusMessage('Practice permission could not be checked. Your work is unchanged. Try again.') }
    finally { setBusy(false) }
  }

  const recordPrediction = async (transfer = false) => {
    setBusy(true)
    try {
      const result = await api.student.checkpoint(task.id, payload, transfer ? episodeState!.transfer!.part_id : episodeState?.supported_part_id ?? 'supported', transfer ? episodeState!.transfer!.stage_start_id : undefined)
      if (result.draft.episode) setEpisode(result.draft.episode)
      setStatusMessage('Prediction and current input saved before results.')
      setDirty(false)
    } catch (error) { setStatusMessage(messageFor(error)) } finally { setBusy(false) }
  }
  const runTransferSimulation = async () => {
    if (!episode.transfer?.content.circuit) return
    setBusy(true)
    try {
      await api.student.saveDraft(task.id, payload)
      const circuit = episode.transfer.content.circuit
      const result = await api.student.simulate(circuitOperations(circuit), task.id, episode.transfer.process.prediction_checkpoint_id, episode.transfer.stage_start_id, episode.transfer.part_id, Number(circuit.qubits))
      setSimulation(result)
      if (result.circuit_version_id) {
        const updated: EpisodePayload = { ...episode, transfer: { ...episode.transfer, process: { ...episode.transfer.process, simulation_references: [{ run_id: result.run_id, circuit_version_id: result.circuit_version_id }] } } }
        setEpisode(updated)
        await api.student.saveDraft(task.id, { ...payload, episode: updated })
      }
      setStatusMessage('Fresh application simulation saved. Results are shown in this workspace.')
    } catch (error) { setStatusMessage(messageFor(error)) } finally { setBusy(false) }
  }
  const enterTransfer = async () => {
    setBusy(true)
    try {
      const next = await api.student.enterTransfer(task.id, payload)
      setEpisodeState(next)
      if (next.transfer) {
        const transfer = next.transfer
        const updated: EpisodePayload = { ...episode, transfer: { stage_start_id: transfer.stage_start_id, part_id: transfer.part_id, content: { answer: '', code: transfer.starter_code, circuit: transfer.starter_circuit }, process: {} } }
        setEpisode(updated)
        await api.student.saveDraft(task.id, { ...payload, episode: updated })
      }
      setStatusMessage('Fresh application opened. Accessibility support remains available.')
    } catch (error) { setStatusMessage(messageFor(error)) } finally { setBusy(false) }
  }

  const assessmentItems: DescriptionItem[] = task.assessment
    ? [
        { term: 'Purpose', description: readablePurpose(task.assessment.purpose) },
        {
          term: 'Target',
          description: `${bloomProcessPlain(task.assessment.bloom_process as BloomProcess)} (${
            bloomKnowledgeLabels[task.assessment.knowledge_dimension as BloomKnowledge] ?? task.assessment.knowledge_dimension
          })`,
        },
        { term: 'Claim', description: task.assessment.claim },
        { term: 'Task conditions', description: readableConditions(task.assessment.task_conditions) },
        { term: 'Instructional support', description: readableConditions(task.assessment.instructional_support) },
        { term: 'Transfer stage', description: readableConditions(task.assessment.transfer_rule) },
        { term: 'Permitted tools', description: readableConditions(task.assessment.permitted_tools) },
        { term: 'Access conditions', description: readableConditions(task.assessment.access_conditions) },
        { term: 'Review', description: task.assessment.review_rule },
      ]
    : []

  return (
    <article className={cx('ll-root', styles.page)} aria-labelledby="task-title">
      <header className={styles.header}>
        <Button variant="quiet" onClick={requestClose} aria-label="Close task">
          <ArrowLeft size={16} aria-hidden="true" /> Back
        </Button>
        <div className={styles.headerText}>
          <p className={styles.eyebrow}>
            {task.module} · {task.difficulty}
          </p>
          <h1 id="task-title" className={styles.title}>{task.title}</h1>
        </div>
      </header>

      <details><summary>Change learning preferences</summary><LearnerPreferences onSaved={value => { setPreferenceVersion(value.version); setEffective(null); setPreferenceReload(current => current + 1) }} /></details>
      {preferenceError && <p role="status">{preferenceError} <Button onClick={() => setPreferenceReload(value => value + 1)}>Retry workspace preferences</Button></p>}
      {effective && <PreferenceWorkspace effective={transferActive ? { ...effective, transfer: true, repeat_allowed: false } : effective} disabled={busy || draftLoading || workConflict || Boolean(task.assessment && !workStartId)} onBreak={() => void saveBreak()} onRepeat={() => { if (dirty) setStatusMessage('Save your current draft before starting another practice draft.'); else void repeatPractice() }} />}

      <div id="task-response" tabIndex={-1} className={styles.layout}>
        <aside className={styles.brief}>
          <Card eyebrow="Your mission">
            <h2 className={styles.briefTitle}>{task.description}</h2>
            <p className={styles.briefText}>{task.instructions}</p>
            <p className={styles.briefNote}>
              {task.assessment
                ? 'Read the assessment conditions before you submit. Your response will be saved as evidence.'
                : 'Try an answer first. Your feedback will explain the next useful step.'}
            </p>
          </Card>
          {task.assessment ? (
            <Card eyebrow="Before you attempt" heading="Assessment conditions">
              <DescriptionList items={assessmentItems} className={styles.assessmentConditions} />
              <h3 className={styles.criteriaTitle}>Evidence criteria</h3>
              <ul className={styles.criteria}>
                {task.assessment.criteria.map((criterion) => (
                  <li key={criterion.description} className={cx(styles.criterion, !criterion.mandatory && styles.criterionSupporting)}>
                    {criterion.mandatory ? 'Required: ' : 'Supporting: '}
                    {criterion.description}
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
          {task.source_references && task.source_references.length > 0 ? (
            <Card eyebrow="Grounded in">
              <ul className={styles.sources}>
                {task.source_references.map((source) => (
                  <li key={source}>{source}</li>
                ))}
              </ul>
            </Card>
          ) : null}
        </aside>

        <section id="task-response" tabIndex={-1} className={styles.interaction} aria-label="Activity">
          {draftLoading ? (
            <p className={styles.stateNote} role="status">Restoring your saved work…</p>
          ) : (
            <>
              {(mode === 'mcq' || mode === 'multi') && (
                <fieldset className={styles.choices}>
                  <legend className={styles.legend}>
                    {mode === 'mcq' ? 'Select the best answer' : 'Select every correct answer'}
                  </legend>
                  {options.map((option, index) => {
                    const selected = mode === 'mcq'
                      ? selectedOption === option.id
                      : selectedOptions.includes(option.id)
                    return (
                      <label key={option.id} className={cx(styles.choice, selected && styles.choiceSelected)}>
                        <input
                          type={mode === 'mcq' ? 'radio' : 'checkbox'}
                          name={mode === 'mcq' ? 'answer' : 'answers'}
                          value={option.id}
                          checked={selected}
                          onChange={() => {
                            if (mode === 'mcq') setSelectedOption(option.id)
                            else {
                              setSelectedOptions((current) =>
                                current.includes(option.id)
                                  ? current.filter((id) => id !== option.id)
                                  : [...current, option.id])
                            }
                            touch()
                          }}
                          className={styles.choiceInput}
                        />
                        <span className={styles.letter} aria-hidden="true">{String.fromCharCode(65 + index)}</span>
                        <span className={styles.choiceText}>{option.text}</span>
                      </label>
                    )
                  })}
                </fieldset>
              )}

              {mode === 'code-explanation' && (
                <div className={styles.codeStack}>
                  <div className={styles.codeWindow}>
                    <div className={styles.codeBar}>
                      <span>entanglement.py</span>
                      <Tag>Python · Qiskit</Tag>
                    </div>
                    <pre className={styles.codePre} aria-label="Qiskit code example"><code>{codeTokens(qiskitCode)}</code></pre>
                  </div>
                  <Field label="Explain what this circuit does" help={`${answer.length} characters`}>
                    <Textarea
                      rows={6}
                      value={answer}
                      onChange={(event) => { setAnswer(event.target.value); changeSupportedInput() }}
                      placeholder="Describe the state after the H and CX gates, then explain the expected measurements."
                    />
                  </Field>
                </div>
              )}

              {mode === 'code-completion' && (
                <div className={styles.codeWindow}>
                  <div className={styles.codeBar}>
                    <span>solution.py</span>
                    <Tag>Python · Qiskit</Tag>
                  </div>
                  <textarea
                    className={styles.codeEditor}
                    aria-label="Qiskit code editor"
                    spellCheck={false}
                    value={code}
                    onChange={(event) => { setCode(event.target.value); changeSupportedInput() }}
                  />
                </div>
              )}

              {mode === 'text' && (
                <Field label="Your response" help={`${answer.length} characters`}>
                  <Textarea
                    rows={12}
                    value={answer}
                    onChange={(event) => { setAnswer(event.target.value); changeSupportedInput() }}
                    placeholder="Explain your reasoning in your own words."
                  />
                </Field>
              )}

              {mode === 'circuit' && (
                <div className={styles.circuit}>
                  <div className={styles.palette} aria-label="Quantum gate palette">
                    <div className={styles.paletteIntro}>
                      <strong>Gate palette</strong>
                      <small>Drag a gate to a wire or use its add button.</small>
                    </div>
                    {(['h', 'x', 'cx'] as const).filter(gate => qubits > 1 || gate !== 'cx').map((gate) => (
                      <button
                        key={gate}
                        type="button"
                        className={styles.gateButton}
                        draggable
                        onDragStart={(event) => event.dataTransfer.setData('application/x-quantum-gate', gate)}
                        onClick={() => addGate(gate)}
                        aria-label={`Add ${gate.toUpperCase()} gate`}
                      >
                        {gate.toUpperCase()}
                      </button>
                    ))}
                    <Button variant="quiet" size="sm" onClick={() => { changeOperations([]) }}>
                      Clear
                    </Button>
                  </div>
                  <div className={styles.board} aria-label={`${qubits} qubit circuit`}>
                    {Array.from({ length: qubits }, (_, index) => index).map((qubit) => (
                      <div
                        className={styles.wireRow}
                        key={qubit}
                        onDragOver={(event) => event.preventDefault()}
                        onDrop={(event) => dropGate(event, qubit)}
                      >
                        <code className={styles.wireLabel}>|0⟩ q{qubit}</code>
                        <div className={styles.wire}>
                          {operations.map((operation, index) => (
                            operation.targets.includes(qubit)
                              ? (
                                <button
                                  key={`${operation.gate}-${index}`}
                                  type="button"
                                  className={styles.gateChip}
                                  title="Remove gate"
                                  onClick={() => { changeOperations((current) => current.filter((_, itemIndex) => itemIndex !== index)) }}
                                >
                                  {operation.gate === 'cx' ? (qubit === 0 ? '●' : '⊕') : operation.gate.toUpperCase()}
                                </button>
                              )
                              : <i key={`${operation.gate}-${index}`} className={styles.wireGap} />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                  <Button variant="secondary" onClick={() => void runSimulation()} disabled={Boolean(draftError) || workConflict || draftLoading || busy || operations.length === 0}>
                    <Play size={15} aria-hidden="true" /> Run 1,024 shots
                  </Button>
                </div>
              )}
                  {simulation && (
                    <div className={styles.simulation}>
                      <div className={styles.simulationHead}>
                        <strong>Simulation result</strong>
                        <small>{simulation.engine}</small>
                      </div>
                      <p>Counts show sampled measurements. Exact probabilities describe the ideal circuit before measurement.</p>
                      {Object.entries(simulation.counts).map(([state, count]) => (
                        <div className={styles.resultRow} key={state}>
                          <code>|{state}⟩</code>
                          <span className={styles.resultTrack}>
                            <i className={styles.resultFill} style={{ width: `${Math.min(100, Math.max(2, count / simulation.shots * 100))}%` }} />
                          </span>
                          <strong className={styles.resultCount}>{count}</strong>
                        </div>
                      ))}
                      <table>
                        <caption>Exact probabilities and sampled frequencies</caption>
                        <thead><tr><th>State</th><th>Exact probability</th><th>Sampled frequency</th></tr></thead>
                        <tbody>{Object.entries(simulation.probabilities).map(([state, probability]) => (
                          <tr key={state}><th>{state}</th><td>{(probability * 100).toFixed(2)}%</td>
                            <td>{((simulation.sampled_frequencies[state] ?? 0) * 100).toFixed(2)}%</td></tr>
                        ))}</tbody>
                      </table>
                      <p>Matching these probabilities alone does not prove that two quantum states are the same.</p>
                      <small>Saved run: {simulation.run_id}</small>
                      <pre className={styles.circuitText}>{simulation.circuit_text}</pre>
                    </div>
                  )}
            </>
          )}

          {mode === 'unsupported' && <p role="alert">This task type is not supported yet. Ask your educator for a supported task.</p>}
          {hasEpisode && <EpisodeFields value={episode} state={episodeState} attempts={attempts ?? []} disabled={busy || draftLoading || workConflict} onChange={value => { setEpisode(value); touch() }} onCheckpoint={() => void recordPrediction()} onTransfer={() => void enterTransfer()} onTransferCheckpoint={() => void recordPrediction(true)} onTransferSimulation={() => void runTransferSimulation()} support={episodeState && <EpisodeSupport onRequest={presentation.support_amount === 'on_request'} taskId={task.id} workId={workStartId} state={episodeState} disabled={busy || draftLoading || workConflict} />} />}
          {checkpointHistory.length > 0 && <Card heading="Earlier predictions"><details><summary>View saved predictions and inputs</summary>{checkpointHistory.map((checkpoint, index) => <section key={`${checkpoint.created_at}-${index}`}><h3>{checkpoint.part_id === episodeState?.transfer_part_id ? 'Fresh application' : 'Supported'} prediction, {new Date(checkpoint.created_at).toLocaleString()}</h3><EpisodeSnapshot episode={{ schema_version: 'learnlens.episode.v1', supported: { prediction: checkpoint.prediction } }} />{checkpoint.input_content.answer && <pre style={{ whiteSpace: 'pre-wrap' }}>{checkpoint.input_content.answer}</pre>}{checkpoint.input_content.code && <pre>{checkpoint.input_content.code}</pre>}{checkpoint.input_content.circuit && <EpisodeCircuitText circuit={checkpoint.input_content.circuit} />}</section>)}{checkpointOffset !== null && <Button variant="secondary" disabled={historyLoading} onClick={() => { setHistoryLoading(true); api.student.checkpointHistory(task.id, undefined, checkpointOffset).then(page => { setCheckpointHistory(current => [...current, ...page.items]); setCheckpointOffset(page.next_offset) }).catch(() => setStatusMessage('Earlier predictions could not be loaded. Try again.')).finally(() => setHistoryLoading(false)) }}>{historyLoading ? 'Loading earlier predictions...' : 'Load earlier predictions'}</Button>}</details></Card>}
          {draftError && (
            <div className={styles.alert} role="alert">
              {draftError}{' '}
              <Button
                variant="quiet"
                size="sm"
                onClick={() => {
                  setDraftLoading(true)
                  setDraftError('')
                  setDraftReload((current) => current + 1)
                }}
              >
                Try restoring again
              </Button>
            </div>
          )}

          {submission && (
            <Card eyebrow="Attempt recorded" className={styles.submissionCard} role="status">
              <h2 className={styles.submissionTitle}>
                {attemptLabel(submission)}
              </h2>
              <p className={styles.submissionText}>
                {submission.formal_assessment
                  ? 'Your response is saved for assessment and review. The formal result is not available.'
                  : 'Your response is saved. Validated AI feedback is prepared separately below.'}
              </p>
            </Card>
          )}
          {latestFeedbackReference && (
            <><FeedbackPanel submissionId={latestFeedbackReference} client={feedbackClient} explanationForm={presentation.feedback_form} /><ActivityContinuation key={latestFeedbackReference} submissionId={latestFeedbackReference} /></>
          )}
          <Card id="task-records" tabIndex={-1} eyebrow="Your records" heading="Attempt history" actions={attempts ? <span className={styles.attemptCount}>{attempts.length} {attempts.length === 1 ? 'attempt' : 'attempts'}</span> : undefined}>
            {attempts === null ? (
              <p className={styles.stateNote}>Loading previous attempts…</p>
            ) : attempts.length === 0 ? (
              <p className={styles.stateNote}>
                {attemptsError || 'No attempts yet. Submit this activity when you are ready.'}
              </p>
            ) : (
              <ol className={styles.attempts}>
                {attempts.map((item, index) => (
                  <li key={item.id ?? `${item.attempt_number}-${item.submitted_at}`} className={styles.attempt}>
                    <span className={styles.attemptNumber}>#{item.attempt_number ?? attempts.length - index}</span>
                    <div className={styles.attemptBody}>
                      <strong>{attemptLabel(item)}</strong>
                      {item.formal_assessment && <small>Formal result unavailable.</small>}
                      <small className={styles.attemptStatus}>{item.status.replace('_', ' ')}</small>
                      <details><summary>Saved response</summary>
                        {item.answer && <pre style={{ whiteSpace: 'pre-wrap' }}>{item.answer}</pre>}
                        {item.code && <pre>{item.code}</pre>}
                        {item.episode && <EpisodeSnapshot episode={item.episode} />}
                      </details>
                    </div>
                    {item.submitted_at ? (
                      <time dateTime={item.submitted_at} className={styles.attemptTime}>
                        {new Date(item.submitted_at).toLocaleString('en-AU', {
                          dateStyle: 'medium',
                          timeStyle: 'short',
                        })}
                      </time>
                    ) : <time className={styles.attemptTime}>Just now</time>}
                  </li>
                ))}
              </ol>
            )}
          </Card>
          {statusMessage && <p className={styles.status} role="status">{statusMessage}</p>}
        </section>
      </div>

      <footer className={styles.footer}>
        <Button variant="quiet" onClick={requestClose}>Close</Button>
        <Button variant="secondary" onClick={() => void save(false)} disabled={Boolean(draftError) || workConflict || busy || draftLoading || !valid}>
          Save draft
        </Button>
        <Button variant="primary" onClick={() => void save(true)} disabled={Boolean(draftError) || workConflict || busy || draftLoading || !valid} loading={busy}>
          Submit activity
        </Button>
      </footer>

      <AlertDialog
        open={confirmLeave}
        onOpenChange={setConfirmLeave}
        title="Leave this activity?"
        description="Your unsaved changes will be lost. Save a draft first to keep them."
        confirmLabel="Leave activity"
        onConfirm={() => {
          setConfirmLeave(false)
          onClose()
        }}
      />
    </article>
  )
}
