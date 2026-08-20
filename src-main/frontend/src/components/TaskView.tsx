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

const defaultOptions = [
  { id: 'a', text: 'It creates an equal superposition of |0⟩ and |1⟩.' },
  { id: 'b', text: 'It measures the qubit immediately.' },
  { id: 'c', text: 'It always changes |0⟩ to |1⟩.' },
  { id: 'd', text: 'It removes all quantum interference.' },
]

function taskMode(task: LearningTask): 'mcq' | 'multi' | 'code-explanation' | 'code-completion' | 'circuit' | 'text' {
  if (['multiple_choice', 'quiz'].includes(task.task_type)) return 'mcq'
  if (task.task_type === 'multiple_answer') return 'multi'
  if (task.task_type === 'code_explanation') return 'code-explanation'
  if (['code', 'code_completion'].includes(task.task_type)) return 'code-completion'
  if (['circuit', 'quantum_circuit'].includes(task.task_type)) return 'circuit'
  return 'text'
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
      && target < 2)
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
  if (Array.isArray(value)) return value.map(String).join(', ') || 'None declared'
  const values = Object.values(value).flatMap((item) => Array.isArray(item) ? item : [item])
  return values.map(String).join(', ') || 'None declared'
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
  const mode = taskMode(task)
  const idempotencyKeyRef = useRef<string | null>(null)
  const feedbackClient = useMemo(
    () => createFeedbackApiClient({ getCsrfToken: csrfToken }),
    [],
  )
  const [selectedOption, setSelectedOption] = useState('')
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])
  const [answer, setAnswer] = useState('')
  const [code, setCode] = useState(task.starter_code ?? '')
  const [operations, setOperations] = useState<GateOperation[]>([])
  const [simulation, setSimulation] = useState<SimulationResult | null>(null)
  const [submission, setSubmission] = useState<TaskSubmission | null>(null)
  const [attempts, setAttempts] = useState<TaskSubmission[] | null>(null)
  const [attemptsError, setAttemptsError] = useState('')
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
    api.student.draft(task.id, controller.signal)
      .then((draft) => {
        if (!draft) return
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
  }, [draftReload, mode, options, task.id, task.starter_code])

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

  const payload = useMemo(() => ({
    answer: mode === 'mcq'
      ? selectedOption
      : mode === 'multi'
        ? JSON.stringify(selectedOptions)
        : answer,
    code: mode === 'code-completion' ? code : undefined,
    circuit: mode === 'circuit' ? { qubits: 2, operations } : undefined,
  }), [answer, code, mode, operations, selectedOption, selectedOptions])

  const valid = mode === 'mcq'
    ? Boolean(selectedOption)
    : mode === 'multi'
      ? selectedOptions.length > 0
    : mode === 'circuit'
      ? operations.length > 0
      : mode === 'code-completion'
        ? Boolean(code.trim())
      : Boolean(answer.trim())

  const touch = () => setDirty(true)

  const requestClose = () => {
    if (dirty) setConfirmLeave(true)
    else onClose()
  }

  const addGate = (gate: GateOperation['gate'], target = 0) => {
    setOperations((current) => [
      ...current,
      { gate, targets: gate === 'cx' ? [0, 1] : [target] },
    ])
    setSimulation(null)
    touch()
  }

  const dropGate = (event: DragEvent<HTMLDivElement>, target: number) => {
    event.preventDefault()
    const gate = event.dataTransfer.getData('application/x-quantum-gate') as GateOperation['gate']
    if (gate === 'h' || gate === 'x' || gate === 'cx') addGate(gate, target)
  }

  const runSimulation = async () => {
    setBusy(true)
    setStatusMessage('')
    try {
      await api.student.saveDraft(task.id, {
        answer: '',
        circuit: { qubits: 2, operations },
      })
      setSimulation(await api.student.simulate(operations))
      setStatusMessage('Simulation completed with 1,024 shots.')
    } catch (error) {
      setStatusMessage(messageFor(error))
    } finally {
      setBusy(false)
    }
  }

  const save = async (submit: boolean) => {
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
      setStatusMessage(messageFor(error))
    } finally {
      setBusy(false)
    }
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

      <div className={styles.layout}>
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
              <DescriptionList items={assessmentItems} />
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

        <section className={styles.interaction} aria-label="Activity">
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
                      onChange={(event) => { setAnswer(event.target.value); touch() }}
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
                    onChange={(event) => { setCode(event.target.value); touch() }}
                  />
                </div>
              )}

              {mode === 'text' && (
                <Field label="Your response" help={`${answer.length} characters`}>
                  <Textarea
                    rows={12}
                    value={answer}
                    onChange={(event) => { setAnswer(event.target.value); touch() }}
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
                    {(['h', 'x', 'cx'] as const).map((gate) => (
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
                    <Button variant="quiet" size="sm" onClick={() => { setOperations([]); setSimulation(null); touch() }}>
                      Clear
                    </Button>
                  </div>
                  <div className={styles.board} aria-label="Two qubit circuit">
                    {[0, 1].map((qubit) => (
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
                                  onClick={() => { setOperations((current) => current.filter((_, itemIndex) => itemIndex !== index)); touch() }}
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
                  <Button variant="secondary" onClick={() => void runSimulation()} disabled={busy || operations.length === 0}>
                    <Play size={15} aria-hidden="true" /> Run 1,024 shots
                  </Button>
                  {simulation && (
                    <div className={styles.simulation}>
                      <div className={styles.simulationHead}>
                        <strong>Simulation result</strong>
                        <small>{simulation.engine}</small>
                      </div>
                      {Object.entries(simulation.counts).map(([state, count]) => (
                        <div className={styles.resultRow} key={state}>
                          <code>|{state}⟩</code>
                          <span className={styles.resultTrack}>
                            <i className={styles.resultFill} style={{ width: `${Math.min(100, Math.max(2, count / 10.24))}%` }} />
                          </span>
                          <strong className={styles.resultCount}>{count}</strong>
                        </div>
                      ))}
                      <pre className={styles.circuitText}>{simulation.circuit_text}</pre>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

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
                {submission.score === null ? 'Assessment response saved' : `${submission.score}%`}
              </h2>
              <p className={styles.submissionText}>
                {submission.score === null
                  ? 'Your response is saved for assessment and review.'
                  : 'Your response is saved. Validated AI feedback is prepared separately below.'}
              </p>
            </Card>
          )}
          {latestFeedbackReference && (
            <FeedbackPanel submissionId={latestFeedbackReference} client={feedbackClient} />
          )}
          <Card eyebrow="Your records" heading="Attempt history" actions={attempts ? <span className={styles.attemptCount}>{attempts.length} {attempts.length === 1 ? 'attempt' : 'attempts'}</span> : undefined}>
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
                      <strong>{item.score === null ? 'Assessment response saved' : `${item.score}%`}</strong>
                      <small className={styles.attemptStatus}>{item.status.replace('_', ' ')}</small>
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
        <Button variant="secondary" onClick={() => void save(false)} disabled={busy || draftLoading || !valid}>
          Save draft
        </Button>
        <Button variant="primary" onClick={() => void save(true)} disabled={busy || draftLoading || !valid} loading={busy}>
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
