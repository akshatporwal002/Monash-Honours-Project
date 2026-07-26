import { useEffect, useMemo, useRef, useState } from 'react'
import type { DragEvent, ReactNode } from 'react'
import { ApiError, api, csrfToken } from '../app/api'
import type { GateOperation, LearningTask, SimulationResult, TaskSubmission } from '../app/types'
import { createFeedbackApiClient, FeedbackPanel } from '../features/feedback'
import { Icon } from './ScreenPrimitives'

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
      ? 'token-comment'
      : token.startsWith("'") || token.startsWith('"')
        ? 'token-string'
        : /^(from|import|as|def|return|for|in|if|else)$/.test(token)
          ? 'token-keyword'
          : /^(QuantumCircuit|AerSimulator)$/.test(token)
            ? 'token-class'
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
  const workspaceRef = useRef<HTMLElement>(null)
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
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const workspace = workspaceRef.current
    const focusableSelector = 'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [href]'
    workspace?.querySelector<HTMLElement>(focusableSelector)?.focus()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab' || !workspace) return
      const focusable = Array.from(workspace.querySelectorAll<HTMLElement>(focusableSelector))
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previousFocus?.focus()
    }
  }, [onClose])

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

  const addGate = (gate: GateOperation['gate'], target = 0) => {
    setOperations((current) => [
      ...current,
      { gate, targets: gate === 'cx' ? [0, 1] : [target] },
    ])
    setSimulation(null)
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
        const result = await api.student.submit(task.id, payload)
        setSubmission(result)
        setAttempts((current) => [
          result,
          ...(current ?? []).filter((item) => item.id !== result.id),
        ])
        setStatusMessage('Activity submitted. Your grounded feedback is ready below.')
        await onSubmitted()
      } else {
        await api.student.saveDraft(task.id, payload)
        setStatusMessage('Draft saved.')
      }
    } catch (error) {
      setStatusMessage(messageFor(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="task-overlay" role="dialog" aria-modal="true" aria-labelledby="task-title">
      <article className="task-workspace" ref={workspaceRef}>
        <header className="task-header">
          <button className="icon-button" onClick={onClose} aria-label="Close task"><Icon name="close" /></button>
          <div>
            <p className="eyebrow">{task.module} · {task.difficulty}</p>
            <h1 id="task-title">{task.title}</h1>
          </div>
          <span className="xp-pill"><Icon name="spark" size={15} /> {task.points} XP</span>
        </header>

        <div className="task-layout">
          <aside className="task-brief">
            <span className="icon-chip"><Icon name={mode.startsWith('code') ? 'code' : mode === 'circuit' ? 'circuit' : 'book'} /></span>
            <p className="eyebrow">Your mission</p>
            <h2>{task.description}</h2>
            <p>{task.instructions}</p>
            <div className="learning-note">
              <Icon name="spark" size={18} />
              <p>Try an answer first. Your feedback will explain the next useful step, not just the score.</p>
            </div>
            {task.source_references && task.source_references.length > 0 && (
              <div className="source-list">
                <strong>Grounded in</strong>
                {task.source_references.map((source) => <span key={source}>{source}</span>)}
              </div>
            )}
          </aside>

          <section className="task-interaction" aria-label="Activity">
            {draftLoading ? (
              <p className="attempt-history__state" role="status">Restoring your saved work…</p>
            ) : (
              <>
                {mode === 'mcq' && (
              <fieldset className="mcq">
                <legend>Select the best answer</legend>
                {options.map((option, index) => (
                  <label key={option.id} className={selectedOption === option.id ? 'selected' : ''}>
                    <input
                      type="radio"
                      name="answer"
                      value={option.id}
                      checked={selectedOption === option.id}
                      onChange={() => setSelectedOption(option.id)}
                    />
                    <span className="option-letter">{String.fromCharCode(65 + index)}</span>
                    <span>{option.text}</span>
                  </label>
                ))}
              </fieldset>
                )}

                {mode === 'multi' && (
              <fieldset className="mcq">
                <legend>Select every correct answer</legend>
                {options.map((option, index) => (
                  <label key={option.id} className={selectedOptions.includes(option.id) ? 'selected' : ''}>
                    <input
                      type="checkbox"
                      name="answers"
                      value={option.id}
                      checked={selectedOptions.includes(option.id)}
                      onChange={() => setSelectedOptions((current) =>
                        current.includes(option.id)
                          ? current.filter((id) => id !== option.id)
                          : [...current, option.id])}
                    />
                    <span className="option-letter">{String.fromCharCode(65 + index)}</span>
                    <span>{option.text}</span>
                  </label>
                ))}
              </fieldset>
                )}

                {mode === 'code-explanation' && (
              <div className="code-explanation">
                <div className="code-window">
                  <div className="code-window__bar"><span>entanglement.py</span><span>Python · Qiskit</span></div>
                  <pre aria-label="Qiskit code example"><code>{codeTokens(qiskitCode)}</code></pre>
                </div>
                <label className="field">
                  <span>Explain what this circuit does</span>
                  <textarea
                    rows={6}
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    placeholder="Describe the state after the H and CX gates, then explain the expected measurements."
                  />
                  <small>{answer.length} characters</small>
                </label>
              </div>
                )}

                {mode === 'code-completion' && (
              <div className="code-explanation">
                <div className="code-window">
                  <div className="code-window__bar"><span>solution.py</span><span>Python · Qiskit</span></div>
                  <textarea
                    className="code-editor"
                    aria-label="Qiskit code editor"
                    spellCheck={false}
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                  />
                </div>
              </div>
                )}

                {mode === 'text' && (
              <label className="field">
                <span>Your response</span>
                <textarea
                  rows={12}
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  placeholder="Explain your reasoning in your own words."
                />
                <small>{answer.length} characters</small>
              </label>
                )}

                {mode === 'circuit' && (
              <div className="circuit-builder">
                <div className="gate-palette" aria-label="Quantum gate palette">
                  <div><strong>Gate palette</strong><small>Drag a gate to a wire or use its add button.</small></div>
                  {(['h', 'x', 'cx'] as const).map((gate) => (
                    <button
                      key={gate}
                      draggable
                      onDragStart={(event) => event.dataTransfer.setData('application/x-quantum-gate', gate)}
                      onClick={() => addGate(gate)}
                      aria-label={`Add ${gate.toUpperCase()} gate`}
                    >
                      {gate.toUpperCase()}
                    </button>
                  ))}
                  <button className="clear-gates" onClick={() => { setOperations([]); setSimulation(null) }}>Clear</button>
                </div>
                <div className="circuit-board" aria-label="Two qubit circuit">
                  {[0, 1].map((qubit) => (
                    <div
                      className="qubit-wire"
                      key={qubit}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => dropGate(event, qubit)}
                    >
                      <code>|0⟩ q{qubit}</code>
                      <div className="wire">
                        {operations.map((operation, index) => (
                          operation.targets.includes(qubit)
                            ? (
                              <button
                                key={`${operation.gate}-${index}`}
                                title="Remove gate"
                                onClick={() => setOperations((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                              >
                                {operation.gate === 'cx' ? (qubit === 0 ? '●' : '⊕') : operation.gate.toUpperCase()}
                              </button>
                            )
                            : <i key={`${operation.gate}-${index}`} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                <button className="button button--secondary" onClick={() => void runSimulation()} disabled={busy || operations.length === 0}>
                  <Icon name="circuit" size={17} /> Run 1,024 shots
                </button>
                {simulation && (
                  <div className="simulation-results">
                    <div><strong>Simulation result</strong><small>{simulation.engine}</small></div>
                    {Object.entries(simulation.counts).map(([state, count]) => (
                      <div className="result-bar" key={state}>
                        <code>|{state}⟩</code>
                        <span><i style={{ width: `${Math.max(2, count / 10.24)}%` }} /></span>
                        <strong>{count}</strong>
                      </div>
                    ))}
                    <pre>{simulation.circuit_text}</pre>
                  </div>
                )}
              </div>
                )}
              </>
            )}

            {draftError && (
              <div className="form-status" role="alert">
                {draftError}{' '}
                <button
                  className="button button--ghost"
                  onClick={() => {
                    setDraftLoading(true)
                    setDraftError('')
                    setDraftReload((current) => current + 1)
                  }}
                >
                  Try restoring again
                </button>
              </div>
            )}

            {submission && (
              <div className={`submission-result ${submission.score >= 70 ? 'submission-result--success' : ''}`} role="status">
                <div>
                  <span><Icon name={submission.score >= 70 ? 'check' : 'spark'} /></span>
                  <div><p className="eyebrow">Attempt recorded</p><h2>{submission.score}%</h2></div>
                </div>
                <p>Your response is saved. Validated AI feedback is prepared separately below.</p>
              </div>
            )}
            {latestFeedbackReference && (
              <FeedbackPanel submissionId={latestFeedbackReference} client={feedbackClient} />
            )}
            <section className="attempt-history" aria-labelledby="attempt-history-title">
              <header>
                <div>
                  <p className="eyebrow">Your records</p>
                  <h2 id="attempt-history-title">Attempt history</h2>
                </div>
                {attempts && <span>{attempts.length} {attempts.length === 1 ? 'attempt' : 'attempts'}</span>}
              </header>
              {attempts === null ? (
                <p className="attempt-history__state">Loading previous attempts…</p>
              ) : attempts.length === 0 ? (
                <p className="attempt-history__state">
                  {attemptsError || 'No attempts yet. Submit this activity when you are ready.'}
                </p>
              ) : (
                <ol>
                  {attempts.map((item, index) => (
                    <li key={item.id ?? `${item.attempt_number}-${item.submitted_at}`}>
                      <span className="attempt-number">#{item.attempt_number ?? attempts.length - index}</span>
                      <div>
                        <strong>{item.score}%</strong>
                        <small>{item.status.replace('_', ' ')}</small>
                      </div>
                      {item.submitted_at ? (
                        <time dateTime={item.submitted_at}>
                          {new Date(item.submitted_at).toLocaleString('en-AU', {
                            dateStyle: 'medium',
                            timeStyle: 'short',
                          })}
                        </time>
                      ) : <time>Just now</time>}
                    </li>
                  ))}
                </ol>
              )}
            </section>
            {statusMessage && <p className="form-status" role="status">{statusMessage}</p>}
          </section>
        </div>

        <footer className="task-footer">
          <button className="button button--ghost" onClick={onClose}>Close</button>
          <button className="button button--secondary" onClick={() => void save(false)} disabled={busy || draftLoading || !valid}>Save draft</button>
          <button className="button button--primary" onClick={() => void save(true)} disabled={busy || draftLoading || !valid}>
            {busy ? 'Working…' : 'Submit activity'} <Icon name="arrow" size={17} />
          </button>
        </footer>
      </article>
    </div>
  )
}
