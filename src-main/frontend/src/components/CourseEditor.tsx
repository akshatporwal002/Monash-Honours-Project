import { useEffect, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileText,
  Link2,
  Loader2,
  Sparkles,
  Upload,
} from 'lucide-react'

import { ApiError, api } from '../app/api'
import type { CourseModule, CourseSummary, GeneratedTaskPreview, LearningOutcome } from '../app/types'
import {
  AlertDialog,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Checkbox,
  PageHeader,
  Select,
  Stepper,
  Tag,
  Textarea,
  cx,
} from './ui'
import styles from './CourseEditor.module.css'

const steps = [
  { number: 1, label: 'Course details' },
  { number: 2, label: 'Materials' },
  { number: 3, label: 'Outcomes' },
  { number: 4, label: 'Generate tasks' },
] as const

const allowedExtensions = ['.pdf', '.docx', '.pptx']
const maximumFileSize = 20 * 1024 * 1024

const newCourseValue = 'new-course'

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
    <div className={styles.screen}>
      <PageHeader
        eyebrow="Course authoring"
        title={course ? course.title : 'Configure a grounded course'}
        description="A four-step path from course intent to educator-reviewed learning activities."
        actions={
          <div className={styles.headerActions}>
            <Select
              aria-label="Choose a course to edit"
              className={styles.coursePicker}
              value={course?.id ?? newCourseValue}
              onValueChange={(value) => void selectCourse(value === newCourseValue ? '' : value)}
              options={[
                { value: newCourseValue, label: 'New course' },
                ...courses.map((item) => ({ value: item.id, label: `${item.code} · ${item.title}` })),
              ]}
            />
            {course && <Tag>{course.status}</Tag>}
            {course?.status === 'draft' && (
              <Button variant="secondary" onClick={() => void publish()} disabled={busy}>
                Publish
              </Button>
            )}
            {course && course.status !== 'archived' && (
              <Button variant="quiet" onClick={() => setArchiveConfirm(true)} disabled={busy}>
                Archive
              </Button>
            )}
          </div>
        }
      />

      <nav aria-label="Course creation progress">
        <Stepper
          steps={steps.map((item) => ({
            label: item.label,
            disabled: item.number > step || (!course && item.number > 1),
          }))}
          current={step - 1}
          onSelectStep={(index) => setStep(index + 1)}
        />
      </nav>

      <Card className={styles.wizardCard}>
        {step === 1 && (
          <form className={styles.form} onSubmit={(event) => void saveDetails(event)}>
            <div className={styles.copy}>
              <p className={styles.eyebrow}>Step 1 of 4</p>
              <h2>Course details</h2>
              <p className={styles.copyText}>
                Give students a short, recognisable course identity. You can refine it before publishing.
              </p>
            </div>
            <div className={styles.formGrid}>
              <Field label="Course code" className={styles.fieldShort}>
                <Input
                  value={details.code}
                  onChange={(event) => setDetails({ ...details, code: event.target.value.toUpperCase() })}
                  placeholder="QTM101"
                  pattern="[A-Z0-9][A-Z0-9-]*"
                  maxLength={20}
                  required
                />
              </Field>
              <Field label="Course title">
                <Input
                  value={details.title}
                  onChange={(event) => setDetails({ ...details, title: event.target.value })}
                  placeholder="Foundations of Quantum Computing"
                  required
                />
              </Field>
              <Field
                label="Description"
                help={`${details.description.length} characters`}
                className={styles.fieldFull}
              >
                <Textarea
                  value={details.description}
                  onChange={(event) => setDetails({ ...details, description: event.target.value })}
                  placeholder="What will students learn and why does it matter?"
                  rows={5}
                  required
                />
              </Field>
              <Checkbox
                className={styles.fieldFull}
                label="Enrollment open"
                help="Allow eligible students to be enrolled in this course."
                checked={details.enrollment_open}
                onChange={(event) => setDetails({
                  ...details,
                  enrollment_open: event.target.checked,
                })}
              />
            </div>
            <div className={styles.actions}>
              <Button type="submit" variant="primary" loading={busy}>
                Save and add materials <ArrowRight size={16} aria-hidden="true" />
              </Button>
            </div>
          </form>
        )}

        {step === 2 && (
          <div className={styles.form}>
            <div className={styles.copy}>
              <p className={styles.eyebrow}>Step 2 of 4</p>
              <h2>Learning materials</h2>
              <p className={styles.copyText}>
                Upload educator-approved sources. LearnLens uses only authorised course material to ground generated tasks.
              </p>
            </div>
            <div className={styles.materialGrid}>
              <section className={styles.sourceCard}>
                <span className={styles.sourceIcon} aria-hidden="true"><Upload size={18} /></span>
                <h3 className={styles.sourceTitle}>Upload a source</h3>
                <p className={styles.sourceHint}>PDF, DOCX or PPTX · 20 MB maximum</p>
                <label className={styles.fileButton}>
                  Choose file
                  <input
                    className="ll-sr-only"
                    type="file"
                    accept=".pdf,.docx,.pptx"
                    onChange={chooseFile}
                  />
                </label>
                {selectedFile && (
                  <div className={styles.selectedFile}>
                    <span className={styles.selectedName}>
                      <FileText size={14} aria-hidden="true" /> {selectedFile.name}
                    </span>
                    <Button variant="primary" size="sm" onClick={() => void uploadFile()} loading={busy}>
                      Upload
                    </Button>
                  </div>
                )}
              </section>
              <section className={styles.sourceCard}>
                <span className={styles.sourceIcon} aria-hidden="true"><Link2 size={18} /></span>
                <h3 className={styles.sourceTitle}>Link a secure source</h3>
                <p className={styles.sourceHint}>
                  Use a public HTTPS PDF, DOCX or PPTX containing approved course content.
                </p>
                <Field label="HTTPS address">
                  <Input
                    type="url"
                    value={materialUrl}
                    onChange={(event) => setMaterialUrl(event.target.value)}
                    placeholder="https://example.edu/quantum-notes.pdf"
                  />
                </Field>
                <div>
                  <Button
                    variant="secondary"
                    onClick={() => void addLink()}
                    disabled={busy || !materialUrl.startsWith('https://')}
                  >
                    Add link
                  </Button>
                </div>
              </section>
            </div>
            {materials.length > 0 && (
              <div className={styles.materialList}>
                <h3 className={styles.materialHeading}>Course sources</h3>
                <ul className={styles.materials}>
                  {materials.map((material) => {
                    const processing = material.status !== 'indexed' && material.status !== 'failed'
                    return (
                      <li key={material.id} className={styles.material}>
                        <span
                          className={cx(
                            styles.materialIcon,
                            material.status === 'failed' && styles.materialIconFault,
                          )}
                          aria-hidden="true"
                        >
                          {material.status === 'indexed' ? (
                            <CheckCircle2 size={16} />
                          ) : processing ? (
                            <Loader2 size={16} className={styles.spin} />
                          ) : (
                            <AlertTriangle size={16} />
                          )}
                        </span>
                        <span className={styles.materialBody}>
                          <strong className={styles.materialName}>{material.filename}</strong>
                          <small className={styles.materialStatus}>{material.status}</small>
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}
            <div className={styles.actions}>
              <Button variant="quiet" onClick={() => setStep(1)}>Back</Button>
              <Button
                variant="primary"
                disabled={indexedMaterialCount === 0}
                onClick={() => setStep(3)}
              >
                Define outcomes <ArrowRight size={16} aria-hidden="true" />
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <form className={styles.form} onSubmit={(event) => void saveOutcomes(event)}>
            <div className={styles.copy}>
              <p className={styles.eyebrow}>Step 3 of 4</p>
              <h2>Module and outcomes</h2>
              <p className={styles.copyText}>
                Use observable language so each generated activity can be checked against a clear learning goal.
              </p>
            </div>
            {modules.length > 0 && (
              <div className={styles.modulePicker}>
                <Field label="Module to edit">
                  <Select
                    value={module?.id ?? ''}
                    onValueChange={(value) => void selectModule(value)}
                    placeholder="Select a module"
                    options={modules.map((item) => ({
                      value: item.id,
                      label: `${item.position}. ${item.title}`,
                    }))}
                  />
                </Field>
                <Button variant="secondary" onClick={startNewModule}>
                  Add another module
                </Button>
              </div>
            )}
            <div className={styles.formGrid}>
              <Field label="Module title">
                <Input
                  value={moduleTitle}
                  onChange={(event) => setModuleTitle(event.target.value)}
                  placeholder="Superposition and measurement"
                  required
                />
              </Field>
              <Field label="Module description">
                <Input
                  value={moduleDescription}
                  onChange={(event) => setModuleDescription(event.target.value)}
                  placeholder="Core single-qubit concepts"
                  required
                />
              </Field>
              <Field label="Outcome schedule">
                <Select
                  value={outcomeKind}
                  onValueChange={(value) => setOutcomeKind(value as 'topic' | 'weekly')}
                  options={[
                    { value: 'topic', label: 'Topic-based' },
                    { value: 'weekly', label: 'Weekly' },
                  ]}
                />
              </Field>
              {outcomeKind === 'weekly' && (
                <Field label="Week number">
                  <Input
                    type="number"
                    min="1"
                    value={weekNumber}
                    onChange={(event) => setWeekNumber(Number(event.target.value))}
                    required
                  />
                </Field>
              )}
              <Field
                label={editingOutcomeId ? 'Edit learning outcome' : 'Learning outcomes · one per line'}
                help={`${outcomeText.split('\n').filter((line) => line.trim()).length} outcomes`}
                className={styles.fieldFull}
              >
                <Textarea
                  rows={7}
                  value={outcomeText}
                  onChange={(event) => setOutcomeText(event.target.value)}
                  placeholder={'Explain how a Hadamard gate creates superposition.\nPredict measurement probabilities for a single-qubit circuit.\nBuild and test a Bell-state circuit.'}
                  required
                />
              </Field>
            </div>
            {outcomes.length > 0 && (
              <div className={styles.outcomeList} aria-label="Saved learning outcomes">
                <h3 className={styles.materialHeading}>Saved outcomes</h3>
                {outcomes.map((outcome) => (
                  <article key={outcome.id} className={styles.outcome}>
                    <div className={styles.outcomeBody}>
                      <Tag>
                        {outcome.kind === 'weekly'
                          ? `Week ${outcome.week_number}`
                          : 'Topic'}
                      </Tag>
                      <strong className={styles.outcomeTitle}>{outcome.title}</strong>
                      <p className={styles.outcomeStatement}>{outcome.statement}</p>
                    </div>
                    <div className={styles.outcomeActions}>
                      <Button variant="quiet" size="sm" onClick={() => editOutcome(outcome)}>
                        Edit
                      </Button>
                      <Button
                        variant="quiet"
                        size="sm"
                        onClick={() => void deleteOutcome(outcome)}
                        disabled={busy}
                      >
                        Delete
                      </Button>
                    </div>
                  </article>
                ))}
              </div>
            )}
            <div className={styles.actions}>
              <Button variant="quiet" onClick={() => setStep(2)}>Back</Button>
              <Button type="submit" variant="primary" loading={busy}>
                {editingOutcomeId ? 'Update outcome' : 'Save and generate'}
                <ArrowRight size={16} aria-hidden="true" />
              </Button>
            </div>
          </form>
        )}

        {step === 4 && (
          <div className={styles.form}>
            <div className={styles.generateHeader}>
              <div className={styles.copy}>
                <p className={styles.eyebrow}>Step 4 of 4</p>
                <h2>AI task generation</h2>
                <p className={styles.copyText}>
                  Generate a small scaffolded sequence, then review each task before the course is published.
                </p>
              </div>
              <div className={styles.generateControls}>
                <Field label="Outcome">
                  <Select
                    value={generationOutcomeId}
                    onValueChange={(value) => setGenerationOutcomeId(value)}
                    options={outcomes.map((outcome) => ({
                      value: outcome.id,
                      label: outcome.title,
                    }))}
                  />
                </Field>
                <Field label="Tasks">
                  <Select
                    value={String(taskCount)}
                    onValueChange={(value) => setTaskCount(Number(value))}
                    options={[3, 4, 5].map((count) => ({
                      value: String(count),
                      label: String(count),
                    }))}
                  />
                </Field>
                <Button
                  variant="primary"
                  onClick={() => void generate()}
                  loading={busy}
                  disabled={indexedMaterialCount === 0 || !generationOutcomeId}
                >
                  <Sparkles size={16} aria-hidden="true" />
                  {generatedTasks.length ? 'Regenerate tasks' : 'Generate tasks'}
                </Button>
              </div>
            </div>
            {generatedTasks.length === 0 ? (
              <EmptyState
                icon={<Sparkles size={20} />}
                title="Ready to build the scaffold"
                description={`LearnLens will use ${indexedMaterialCount} indexed source${indexedMaterialCount === 1 ? '' : 's'} and the selected learning outcome.`}
              />
            ) : (
              <ol className={styles.taskList}>
                {generatedTasks.map((task, index) => (
                  <li key={task.id ?? `${task.title}-${index}`} className={styles.task}>
                    <span className={styles.taskNumber} aria-hidden="true">{index + 1}</span>
                    <div className={styles.taskBody}>
                      <div className={styles.taskHead}>
                        <strong className={styles.taskTitle}>{task.title}</strong>
                        <Tag>{taskTypeLabel(task.task_type)}</Tag>
                        <Tag>{task.difficulty}</Tag>
                      </div>
                      <p className={styles.taskPrompt}>{task.prompt}</p>
                      {task.learning_outcome && (
                        <small className={styles.taskMeta}>Outcome: {task.learning_outcome}</small>
                      )}
                      {task.source_references && task.source_references.length > 0 && (
                        <small className={styles.taskMeta}>
                          Sources: {task.source_references.join(', ')}
                        </small>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
            <div className={styles.actions}>
              <Button variant="quiet" onClick={() => setStep(3)}>Back</Button>
              <Button
                variant="primary"
                onClick={() => void publish()}
                disabled={busy || course?.status === 'published' || course?.status === 'archived'}
              >
                {course?.status === 'published' ? 'Course published' : 'Approve and publish'}
                <CheckCircle2 size={16} aria-hidden="true" />
              </Button>
            </div>
          </div>
        )}

        {error && <p className={cx(styles.formMessage, styles.formError)} role="alert">{error}</p>}
        {message && <p className={cx(styles.formMessage, styles.formStatus)} role="status">{message}</p>}
      </Card>

      <AlertDialog
        open={archiveConfirm && Boolean(course)}
        onOpenChange={(open) => {
          if (!open) setArchiveConfirm(false)
        }}
        title={course ? `Archive ${course.title}?` : 'Archive course?'}
        description="Students will no longer see this course as active. Materials, outcomes, attempts and analytics will be retained."
        confirmLabel="Archive course"
        confirmLoading={busy}
        onConfirm={() => void archive()}
      />
    </div>
  )
}
