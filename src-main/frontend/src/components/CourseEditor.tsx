import { useEffect, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { ApiError, api } from '../app/api'
import type { CourseModule, CourseSummary, GeneratedTaskPreview, LearningOutcome } from '../app/types'
import { Icon, PageHeading } from './ScreenPrimitives'

const steps = [
  { number: 1, label: 'Course details' },
  { number: 2, label: 'Materials' },
  { number: 3, label: 'Outcomes' },
  { number: 4, label: 'Generate tasks' },
] as const

const allowedExtensions = ['.pdf', '.docx', '.pptx']
const maximumFileSize = 20 * 1024 * 1024

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'The course could not be updated. Please try again.'
}

function taskTypeLabel(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function CourseEditor() {
  const [step, setStep] = useState(1)
  const [courses, setCourses] = useState<CourseSummary[]>([])
  const [course, setCourse] = useState<CourseSummary | null>(null)
  const [details, setDetails] = useState({
    code: '',
    title: '',
    description: '',
    enrollment_open: true,
  })
  const [materialUrl, setMaterialUrl] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [materials, setMaterials] = useState<Array<{ id: string; filename: string; status: string }>>([])
  const [moduleTitle, setModuleTitle] = useState('')
  const [moduleDescription, setModuleDescription] = useState('')
  const [modules, setModules] = useState<CourseModule[]>([])
  const [outcomeText, setOutcomeText] = useState('')
  const [outcomeKind, setOutcomeKind] = useState<'topic' | 'weekly'>('topic')
  const [weekNumber, setWeekNumber] = useState(1)
  const [editingOutcomeId, setEditingOutcomeId] = useState<string | null>(null)
  const [module, setModule] = useState<CourseModule | null>(null)
  const [outcomes, setOutcomes] = useState<LearningOutcome[]>([])
  const [generationOutcomeId, setGenerationOutcomeId] = useState('')
  const [taskCount, setTaskCount] = useState(3)
  const [generatedTasks, setGeneratedTasks] = useState<GeneratedTaskPreview[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [archiveConfirm, setArchiveConfirm] = useState(false)
  const indexedMaterialCount = materials.filter(
    (material) => material.status === 'indexed',
  ).length

  useEffect(() => {
    const controller = new AbortController()
    async function loadCourses() {
      try {
        setCourses(await api.courses.list(controller.signal))
      } catch (caught) {
        if (!controller.signal.aborted) setError(errorMessage(caught))
      }
    }
    void loadCourses()
    return () => controller.abort()
  }, [])

  const resetMessages = () => {
    setError('')
    setMessage('')
  }

  const saveDetails = async (event: FormEvent) => {
    event.preventDefault()
    resetMessages()
    setBusy(true)
    try {
      const saved = course
        ? await api.courses.update(course.id, details)
        : await api.courses.create(details)
      setCourse(saved)
      setCourses((current) => current.some((item) => item.id === saved.id)
        ? current.map((item) => item.id === saved.id ? saved : item)
        : [saved, ...current])
      setStep(2)
      setMessage('Course details saved.')
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const chooseFile = (event: ChangeEvent<HTMLInputElement>) => {
    resetMessages()
    const file = event.target.files?.[0] ?? null
    if (!file) {
      setSelectedFile(null)
      return
    }
    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!allowedExtensions.includes(extension)) {
      setError('Choose a PDF, DOCX or PPTX file.')
      event.target.value = ''
      return
    }
    if (file.size > maximumFileSize) {
      setError('Learning materials must be 20 MB or smaller.')
      event.target.value = ''
      return
    }
    setSelectedFile(file)
  }

  const uploadFile = async () => {
    if (!course || !selectedFile) return
    resetMessages()
    setBusy(true)
    try {
      const saved = await api.courses.uploadMaterial(course.id, selectedFile)
      setMaterials((current) => [...current, saved])
      setSelectedFile(null)
      setMessage(
        saved.status === 'indexed'
          ? `${saved.filename} uploaded and indexed.`
          : `${saved.filename} uploaded with status: ${saved.status}.`,
      )
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const addLink = async () => {
    if (!course || !materialUrl.trim()) return
    resetMessages()
    setBusy(true)
    try {
      const saved = await api.courses.linkMaterial(course.id, materialUrl.trim())
      setMaterials((current) => [...current, saved])
      setMaterialUrl('')
      setMessage('Secure learning-material link fetched and indexed.')
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const saveOutcomes = async (event: FormEvent) => {
    event.preventDefault()
    if (!course) return
    resetMessages()
    const statements = editingOutcomeId
      ? [outcomeText.trim()].filter(Boolean)
      : outcomeText.split('\n').map((line) => line.trim()).filter(Boolean)
    if (statements.length === 0) {
      setError('Add at least one measurable learning outcome.')
      return
    }
    setBusy(true)
    try {
      const savedModule = module
        ? await api.courses.updateModule(module.id, {
          title: moduleTitle,
          description: moduleDescription,
          position: module.position,
        })
        : await api.courses.createModule(course.id, {
          title: moduleTitle,
          description: moduleDescription,
          position: modules.length + 1,
        })
      setModules((current) => current.some((item) => item.id === savedModule.id)
        ? current.map((item) => item.id === savedModule.id ? savedModule : item)
        : [...current, savedModule])

      const payload = (statement: string, position: number) => ({
        title: statement.slice(0, 120),
        statement,
        kind: outcomeKind,
        week_number: outcomeKind === 'weekly' ? weekNumber : null,
        position,
      })
      let savedOutcomes: LearningOutcome[]
      if (editingOutcomeId) {
        const existing = outcomes.find((outcome) => outcome.id === editingOutcomeId)
        if (!existing) throw new Error('The selected learning outcome is no longer available.')
        const updated = await api.courses.updateOutcome(
          editingOutcomeId,
          payload(statements[0], existing.position),
        )
        savedOutcomes = outcomes.map((outcome) =>
          outcome.id === updated.id ? updated : outcome)
      } else {
        const created = await Promise.all(
          statements.map((statement, index) =>
            api.courses.createOutcome(
              savedModule.id,
              payload(statement, outcomes.length + index + 1),
            )),
        )
        savedOutcomes = [...outcomes, ...created]
      }
      setModule(savedModule)
      setOutcomes(savedOutcomes)
      setGenerationOutcomeId((current) =>
        savedOutcomes.some((outcome) => outcome.id === current)
          ? current
          : (savedOutcomes[0]?.id ?? ''))
      setOutcomeText('')
      setEditingOutcomeId(null)
      setStep(4)
      setMessage('Module and learning outcomes saved.')
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const generate = async () => {
    if (!course || !module || !generationOutcomeId) return
    resetMessages()
    setBusy(true)
    try {
      const tasks = await api.courses.generateTasks(course.id, {
        module_id: module.id,
        learning_outcome_ids: [generationOutcomeId],
        count: taskCount,
      })
      setGeneratedTasks(tasks)
      setMessage(`${tasks.length} grounded task${tasks.length === 1 ? '' : 's'} generated for educator review.`)
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const publish = async () => {
    if (!course) return
    resetMessages()
    setBusy(true)
    try {
      const published = await api.courses.publish(course.id)
      setCourse(published)
      setCourses((current) => current.map((item) => item.id === published.id ? published : item))
      setMessage('Course published. Students can now access the pathway.')
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const archive = async () => {
    if (!course) return
    resetMessages()
    setBusy(true)
    try {
      const archived = await api.courses.archive(course.id)
      setCourse(archived)
      setCourses((current) => current.map((item) => item.id === archived.id ? archived : item))
      setArchiveConfirm(false)
      setMessage('Course archived. Existing learning records remain available.')
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const selectCourse = async (courseId: string) => {
    resetMessages()
    setStep(1)
    setModule(null)
    setModules([])
    setOutcomes([])
    setGenerationOutcomeId('')
    setGeneratedTasks([])
    setModuleTitle('')
    setModuleDescription('')
    setOutcomeText('')
    setOutcomeKind('topic')
    setWeekNumber(1)
    setEditingOutcomeId(null)
    if (!courseId) {
      setCourse(null)
      setDetails({
        code: '',
        title: '',
        description: '',
        enrollment_open: true,
      })
      setMaterials([])
      return
    }
    const selected = courses.find((item) => item.id === courseId)
    if (!selected) return
    setCourse(selected)
    setDetails({
      code: selected.code,
      title: selected.title,
      description: selected.description ?? '',
      enrollment_open: selected.enrollment_open,
    })
    setBusy(true)
    try {
      const [savedMaterials, savedModules] = await Promise.all([
        api.courses.listMaterials(selected.id),
        api.courses.listModules(selected.id),
      ])
      setMaterials(savedMaterials)
      setModules(savedModules)
      const firstModule = savedModules[0] ?? null
      setModule(firstModule)
      if (firstModule) {
        setModuleTitle(firstModule.title)
        setModuleDescription(firstModule.description ?? '')
        const savedOutcomes = await api.courses.listOutcomes(firstModule.id)
        setOutcomes(savedOutcomes)
        setGenerationOutcomeId(savedOutcomes[0]?.id ?? '')
      }
      setMessage('Existing course loaded. Changes will be saved to this course.')
    } catch (caught) {
      setMaterials([])
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const selectModule = async (moduleId: string) => {
    resetMessages()
    const selected = modules.find((item) => item.id === moduleId)
    if (!selected) return
    setBusy(true)
    try {
      setModule(selected)
      setModuleTitle(selected.title)
      setModuleDescription(selected.description ?? '')
      const savedOutcomes = await api.courses.listOutcomes(selected.id)
      setOutcomes(savedOutcomes)
      setGenerationOutcomeId(savedOutcomes[0]?.id ?? '')
      setOutcomeText('')
      setOutcomeKind('topic')
      setWeekNumber(1)
      setEditingOutcomeId(null)
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const startNewModule = () => {
    resetMessages()
    setModule(null)
    setModuleTitle('')
    setModuleDescription('')
    setOutcomes([])
    setGenerationOutcomeId('')
    setOutcomeText('')
    setOutcomeKind('topic')
    setWeekNumber(1)
    setEditingOutcomeId(null)
  }

  const editOutcome = (outcome: LearningOutcome) => {
    resetMessages()
    setOutcomeText(outcome.statement)
    setOutcomeKind(outcome.kind)
    setWeekNumber(outcome.week_number ?? 1)
    setEditingOutcomeId(outcome.id)
  }

  const deleteOutcome = async (outcome: LearningOutcome) => {
    resetMessages()
    setBusy(true)
    try {
      await api.courses.deleteOutcome(outcome.id)
      const remaining = outcomes.filter((item) => item.id !== outcome.id)
      setOutcomes(remaining)
      if (generationOutcomeId === outcome.id) {
        setGenerationOutcomeId(remaining[0]?.id ?? '')
      }
      if (editingOutcomeId === outcome.id) {
        setOutcomeText('')
        setEditingOutcomeId(null)
      }
      setMessage('Learning outcome deleted.')
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="Course authoring"
        title={course ? course.title : 'Configure a grounded course'}
        description="A four-step path from course intent to educator-reviewed learning activities."
        actions={
          <div className="course-editor-actions">
            <label>
              <span className="sr-only">Choose a course to edit</span>
              <select value={course?.id ?? ''} onChange={(event) => void selectCourse(event.target.value)}>
                <option value="">New course</option>
                {courses.map((item) => <option value={item.id} key={item.id}>{item.code} · {item.title}</option>)}
              </select>
            </label>
            {course && <span className={`status-chip status-chip--${course.status}`}>{course.status}</span>}
            {course?.status === 'draft' && <button className="button button--secondary" onClick={() => void publish()} disabled={busy}>Publish</button>}
            {course && course.status !== 'archived' && <button className="button button--ghost" onClick={() => setArchiveConfirm(true)} disabled={busy}>Archive</button>}
          </div>
        }
      />

      <nav className="wizard-steps" aria-label="Course creation progress">
        {steps.map((item) => (
          <button
            key={item.number}
            className={step === item.number ? 'active' : step > item.number ? 'complete' : ''}
            disabled={item.number > step || (!course && item.number > 1)}
            onClick={() => setStep(item.number)}
            aria-current={step === item.number ? 'step' : undefined}
          >
            <span>{step > item.number ? <Icon name="check" size={16} /> : item.number}</span>
            <div><small>Step {item.number}</small><strong>{item.label}</strong></div>
          </button>
        ))}
      </nav>

      <section className="wizard-card">
        {step === 1 && (
          <form className="wizard-form" onSubmit={(event) => void saveDetails(event)}>
            <div className="wizard-copy">
              <p className="eyebrow">Step 1 of 4</p>
              <h2>Course details</h2>
              <p>Give students a short, recognisable course identity. You can refine it before publishing.</p>
            </div>
            <div className="form-grid">
              <label className="field field--short">
                <span>Course code</span>
                <input value={details.code} onChange={(event) => setDetails({ ...details, code: event.target.value.toUpperCase() })} placeholder="QTM101" pattern="[A-Z0-9][A-Z0-9-]*" maxLength={20} required />
              </label>
              <label className="field">
                <span>Course title</span>
                <input value={details.title} onChange={(event) => setDetails({ ...details, title: event.target.value })} placeholder="Foundations of Quantum Computing" required />
              </label>
              <label className="field field--full">
                <span>Description</span>
                <textarea value={details.description} onChange={(event) => setDetails({ ...details, description: event.target.value })} placeholder="What will students learn and why does it matter?" rows={5} required />
                <small>{details.description.length} characters</small>
              </label>
              <label className="switch-field field--full">
                <input
                  type="checkbox"
                  checked={details.enrollment_open}
                  onChange={(event) => setDetails({
                    ...details,
                    enrollment_open: event.target.checked,
                  })}
                />
                <span><i /></span>
                <div>
                  <strong>Enrollment open</strong>
                  <small>Allow eligible students to be enrolled in this course.</small>
                </div>
              </label>
            </div>
            <div className="wizard-actions">
              <button className="button button--primary" disabled={busy}>
                {busy ? 'Saving…' : 'Save and add materials'} <Icon name="arrow" size={17} />
              </button>
            </div>
          </form>
        )}

        {step === 2 && (
          <div className="wizard-form">
            <div className="wizard-copy">
              <p className="eyebrow">Step 2 of 4</p>
              <h2>Learning materials</h2>
              <p>Upload educator-approved sources. QuantumLearn uses only authorised course material to ground generated tasks.</p>
            </div>
            <div className="material-grid">
              <section className="upload-zone">
                <span className="icon-chip"><Icon name="book" /></span>
                <h3>Upload a source</h3>
                <p>PDF, DOCX or PPTX · 20 MB maximum</p>
                <label className="button button--secondary">
                  Choose file
                  <input className="sr-only" type="file" accept=".pdf,.docx,.pptx" onChange={chooseFile} />
                </label>
                {selectedFile && (
                  <div className="selected-file">
                    <span><Icon name="check" size={16} /> {selectedFile.name}</span>
                    <button className="button button--primary" onClick={() => void uploadFile()} disabled={busy}>Upload</button>
                  </div>
                )}
              </section>
              <section className="link-source">
                <span className="icon-chip"><Icon name="course" /></span>
                <h3>Link a secure source</h3>
                <p>Use a public HTTPS PDF, DOCX or PPTX containing approved course content.</p>
                <label className="field">
                  <span>HTTPS address</span>
                  <input type="url" value={materialUrl} onChange={(event) => setMaterialUrl(event.target.value)} placeholder="https://example.edu/quantum-notes.pdf" />
                </label>
                <button className="button button--secondary" onClick={() => void addLink()} disabled={busy || !materialUrl.startsWith('https://')}>Add link</button>
              </section>
            </div>
            {materials.length > 0 && (
              <div className="material-list">
                <h3>Course sources</h3>
                {materials.map((material) => (
                  <div key={material.id}><Icon name="check" size={17} /><span><strong>{material.filename}</strong><small>{material.status}</small></span></div>
                ))}
              </div>
            )}
            <div className="wizard-actions">
              <button className="button button--ghost" onClick={() => setStep(1)}>Back</button>
              <button className="button button--primary" disabled={indexedMaterialCount === 0} onClick={() => setStep(3)}>Define outcomes <Icon name="arrow" size={17} /></button>
            </div>
          </div>
        )}

        {step === 3 && (
          <form className="wizard-form" onSubmit={(event) => void saveOutcomes(event)}>
            <div className="wizard-copy">
              <p className="eyebrow">Step 3 of 4</p>
              <h2>Module and outcomes</h2>
              <p>Use observable language so each generated activity can be checked against a clear learning goal.</p>
            </div>
            {modules.length > 0 && (
              <div className="module-picker">
                <label className="field">
                  <span>Module to edit</span>
                  <select
                    value={module?.id ?? ''}
                    onChange={(event) => void selectModule(event.target.value)}
                  >
                    <option value="" disabled>Select a module</option>
                    {modules.map((item) => (
                      <option value={item.id} key={item.id}>
                        {item.position}. {item.title}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={startNewModule}
                >
                  Add another module
                </button>
              </div>
            )}
            <div className="form-grid">
              <label className="field">
                <span>Module title</span>
                <input value={moduleTitle} onChange={(event) => setModuleTitle(event.target.value)} placeholder="Superposition and measurement" required />
              </label>
              <label className="field">
                <span>Module description</span>
                <input value={moduleDescription} onChange={(event) => setModuleDescription(event.target.value)} placeholder="Core single-qubit concepts" required />
              </label>
              <label className="field">
                <span>Outcome schedule</span>
                <select
                  value={outcomeKind}
                  onChange={(event) =>
                    setOutcomeKind(event.target.value as 'topic' | 'weekly')}
                >
                  <option value="topic">Topic-based</option>
                  <option value="weekly">Weekly</option>
                </select>
              </label>
              {outcomeKind === 'weekly' && (
                <label className="field">
                  <span>Week number</span>
                  <input
                    type="number"
                    min="1"
                    value={weekNumber}
                    onChange={(event) => setWeekNumber(Number(event.target.value))}
                    required
                  />
                </label>
              )}
              <label className="field field--full">
                <span>
                  {editingOutcomeId ? 'Edit learning outcome' : 'Learning outcomes · one per line'}
                </span>
                <textarea
                  rows={7}
                  value={outcomeText}
                  onChange={(event) => setOutcomeText(event.target.value)}
                  placeholder={'Explain how a Hadamard gate creates superposition.\nPredict measurement probabilities for a single-qubit circuit.\nBuild and test a Bell-state circuit.'}
                  required
                />
                <small>{outcomeText.split('\n').filter((line) => line.trim()).length} outcomes</small>
              </label>
            </div>
            {outcomes.length > 0 && (
              <div className="outcome-list" aria-label="Saved learning outcomes">
                <h3>Saved outcomes</h3>
                {outcomes.map((outcome) => (
                  <article key={outcome.id}>
                    <div>
                      <span className="status-chip">
                        {outcome.kind === 'weekly'
                          ? `Week ${outcome.week_number}`
                          : 'Topic'}
                      </span>
                      <strong>{outcome.title}</strong>
                      <p>{outcome.statement}</p>
                    </div>
                    <div>
                      <button
                        type="button"
                        className="button button--ghost"
                        onClick={() => editOutcome(outcome)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="button button--ghost"
                        onClick={() => void deleteOutcome(outcome)}
                        disabled={busy}
                      >
                        Delete
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
            <div className="wizard-actions">
              <button type="button" className="button button--ghost" onClick={() => setStep(2)}>Back</button>
              <button className="button button--primary" disabled={busy}>
                {busy ? 'Saving…' : editingOutcomeId ? 'Update outcome' : 'Save and generate'}
                <Icon name="arrow" size={17} />
              </button>
            </div>
          </form>
        )}

        {step === 4 && (
          <div className="wizard-form">
            <div className="wizard-copy wizard-copy--generate">
              <div>
                <p className="eyebrow">Step 4 of 4</p>
                <h2>AI task generation</h2>
                <p>Generate a small scaffolded sequence, then review each task before the course is published.</p>
              </div>
              <label className="task-count">
                <span>Outcome</span>
                <select
                  value={generationOutcomeId}
                  onChange={(event) => setGenerationOutcomeId(event.target.value)}
                >
                  {outcomes.map((outcome) => (
                    <option key={outcome.id} value={outcome.id}>
                      {outcome.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="task-count">
                <span>Tasks</span>
                <select value={taskCount} onChange={(event) => setTaskCount(Number(event.target.value))}>
                  {[3, 4, 5].map((count) => <option key={count}>{count}</option>)}
                </select>
              </label>
              <button className="button button--primary" onClick={() => void generate()} disabled={busy || indexedMaterialCount === 0 || !generationOutcomeId}>
                <Icon name="spark" size={17} /> {busy ? 'Generating…' : generatedTasks.length ? 'Regenerate tasks' : 'Generate tasks'}
              </button>
            </div>
            {generatedTasks.length === 0 ? (
              <div className="generation-empty">
                <div className="hero-atom hero-atom--small" aria-hidden="true"><i /><i /><i /><b /></div>
                <h3>Ready to build the scaffold</h3>
                <p>QuantumLearn will use {indexedMaterialCount} indexed source{indexedMaterialCount === 1 ? '' : 's'} and the selected learning outcome.</p>
              </div>
            ) : (
              <ol className="generated-task-list">
                {generatedTasks.map((task, index) => (
                  <li key={task.id ?? `${task.title}-${index}`}>
                    <span>{index + 1}</span>
                    <div>
                      <div><strong>{task.title}</strong><span className="status-chip">{taskTypeLabel(task.task_type)}</span><span className="status-chip">{task.difficulty}</span></div>
                      <p>{task.prompt}</p>
                      {task.learning_outcome && <small>Outcome: {task.learning_outcome}</small>}
                      {task.source_references && task.source_references.length > 0 && <small>Sources: {task.source_references.join(', ')}</small>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
            <div className="wizard-actions">
              <button className="button button--ghost" onClick={() => setStep(3)}>Back</button>
              <button className="button button--primary" onClick={() => void publish()} disabled={busy || course?.status === 'published' || course?.status === 'archived'}>
                {course?.status === 'published' ? 'Course published' : 'Approve and publish'} <Icon name="check" size={17} />
              </button>
            </div>
          </div>
        )}

        {error && <p className="form-error wizard-message" role="alert">{error}</p>}
        {message && <p className="form-status wizard-message" role="status">{message}</p>}
      </section>
      {archiveConfirm && course && (
        <div className="confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="archive-course-title">
          <section className="confirm-dialog">
            <span className="icon-chip icon-chip--warning"><Icon name="warning" /></span>
            <h2 id="archive-course-title">Archive {course.title}?</h2>
            <p>Students will no longer see this course as active. Materials, outcomes, attempts and analytics will be retained.</p>
            <div>
              <button autoFocus className="button button--ghost" onClick={() => setArchiveConfirm(false)}>Cancel</button>
              <button className="button button--primary" onClick={() => void archive()} disabled={busy}>Archive course</button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
