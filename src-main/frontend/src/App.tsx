import { useCallback, useEffect, useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

type TaskType = 'quiz' | 'code' | 'circuit'
type TaskStatus = 'draft' | 'submitted' | 'completed' | null

interface Task {
  id: string
  slug: string
  title: string
  module: string
  description: string
  instructions: string
  task_type: TaskType
  difficulty: string
  points: number
  position: number
  starter_code: string | null
  due_at: string | null
  status: TaskStatus
  score: number | null
}

interface Achievement {
  code: string
  name: string
  description: string
  icon: string
  earned_at: string | null
}

interface Progress {
  student_id: string
  display_name: string
  completed_tasks: number
  total_tasks: number
  completion_percent: number
  average_score: number
  points: number
  streak_days: number
  level: number
  level_progress: number
  achievements: Achievement[]
  module_progress: Record<string, number>
}

interface Recommendation {
  task_id: string
  title: string
  reason: string
  priority: 'high' | 'medium' | 'low'
}

interface Notification {
  id: string
  kind: 'reminder' | 'achievement' | 'feedback'
  title: string
  message: string
  is_read: boolean
  created_at: string
}

interface DashboardData {
  progress: Progress
  tasks: Task[]
  recommendations: Recommendation[]
  notifications: Notification[]
}

interface GateOperation {
  gate: 'h' | 'x' | 'cx'
  targets: number[]
}

interface Simulation {
  counts: Record<string, number>
  probabilities: Record<string, number>
  circuit_text: string
  engine: string
}

interface Submission {
  score: number
  feedback: string | null
  status: TaskStatus
}

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10M9 20v-6h6v6"/></>,
    book: <><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v16H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 4.5v16M8 6h8M8 10h6"/></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
    trophy: <><path d="M8 4h8v4a4 4 0 0 1-8 0zM10 12v4M14 12v4M8 20h8M9 16h6"/><path d="M8 6H4v1a4 4 0 0 0 4 4M16 6h4v1a4 4 0 0 1-4 4"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
    play: <path d="m8 5 11 7-11 7z"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    flame: <path d="M12 22c4 0 7-3 7-7 0-3-1.5-5.5-4-8 .2 3-1 4-2 4-1.5 0-2-1.4-1.5-4C8 9.5 5 12 5 16c0 3.3 3 6 7 6z"/>,
    spark: <><path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/><path d="m19 17 .6 2.4L22 20l-2.4.6L19 23l-.6-2.4L16 20l2.4-.6z"/></>,
    arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    code: <><path d="m9 18-6-6 6-6M15 6l6 6-6 6"/></>,
  }
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function ProgressRing({ value }: { value: number }) {
  return (
    <div className="progress-ring" style={{ '--progress': `${value * 3.6}deg` } as CSSProperties}>
      <div><strong>{value}%</strong><span>complete</span></div>
    </div>
  )
}

function LoadingScreen() {
  return <main className="state-screen"><div className="quantum-loader"><i/><i/><i/></div><h1>Preparing your learning space</h1><p>Loading tasks and progress…</p></main>
}

function TaskWorkspace({ task, studentId, onClose, onComplete }: {
  task: Task
  studentId: string
  onClose: () => void
  onComplete: () => Promise<void>
}) {
  const [answer, setAnswer] = useState('')
  const [code, setCode] = useState(task.starter_code ?? '')
  const [operations, setOperations] = useState<GateOperation[]>([])
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [submission, setSubmission] = useState<Submission | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const addGate = (gate: GateOperation['gate']) => {
    const targets = gate === 'cx' ? [0, 1] : [0]
    setOperations((current) => [...current, { gate, targets }])
    setSimulation(null)
  }

  const runSimulation = async () => {
    setBusy(true)
    setMessage('')
    try {
      const response = await fetch(`${API_URL}/students/${studentId}/simulate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qubits: 2, operations, shots: 1024 }),
      })
      if (!response.ok) throw new Error('The simulator could not run this circuit.')
      setSimulation(await response.json())
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Simulation failed.')
    } finally { setBusy(false) }
  }

  const save = async (submit: boolean) => {
    setBusy(true)
    setMessage('')
    try {
      const response = await fetch(`${API_URL}/students/${studentId}/tasks/${task.id}/submission`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer, code: task.task_type === 'code' ? code : null,
          circuit: task.task_type === 'circuit' ? { qubits: 2, operations } : null, submit }),
      })
      if (!response.ok) throw new Error('Your work could not be saved. Please try again.')
      const result: Submission = await response.json()
      setSubmission(result)
      setMessage(submit ? 'Activity submitted successfully.' : 'Draft saved.')
      if (submit) await onComplete()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to save.')
    } finally { setBusy(false) }
  }

  return (
    <div className="workspace-layer" role="dialog" aria-modal="true" aria-label={task.title}>
      <div className="workspace">
        <header className="workspace-header">
          <button className="icon-button" onClick={onClose} aria-label="Close activity"><Icon name="close" /></button>
          <div><span className={`type-pill ${task.task_type}`}>{task.task_type}</span><h2>{task.title}</h2></div>
          <div className="points-pill">+{task.points} XP</div>
        </header>
        <div className="workspace-body">
          <aside className="task-brief">
            <p className="eyebrow">{task.module} · {task.difficulty}</p>
            <h3>Your mission</h3>
            <p>{task.description}</p>
            <div className="instruction"><Icon name="spark" /><p>{task.instructions}</p></div>
            <div className="learning-tip"><strong>Learning tip</strong><p>Test your idea, inspect the result, and revise before submitting.</p></div>
          </aside>
          <section className="task-doing">
            {task.task_type === 'quiz' && <label className="answer-field"><span>Your answer</span><textarea value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="Explain the concept in your own words…" rows={10}/><small>{answer.length} characters</small></label>}
            {task.task_type === 'code' && <div className="code-panel"><div className="editor-bar"><span><Icon name="code" size={16}/> solution.py</span><span>Python · Qiskit</span></div><textarea spellCheck={false} value={code} onChange={(event) => setCode(event.target.value)} aria-label="Qiskit code editor" /></div>}
            {task.task_type === 'circuit' && <div className="circuit-panel">
              <div className="gate-palette"><span>Add a gate</span><button onClick={() => addGate('h')}>H</button><button onClick={() => addGate('x')}>X</button><button className="wide-gate" onClick={() => addGate('cx')}>CX</button><button className="text-button" onClick={() => { setOperations([]); setSimulation(null) }}>Clear</button></div>
              <div className="circuit-board">
                {[0, 1].map((qubit) => <div className="qubit-line" key={qubit}><span>|0⟩ q{qubit}</span><div className="wire">{operations.map((operation, index) => operation.targets.includes(qubit) ? <b key={index} title={`${operation.gate.toUpperCase()} gate`}>{operation.gate === 'cx' ? (operation.targets[0] === qubit ? '●' : '⊕') : operation.gate.toUpperCase()}</b> : <i key={index}/>)}</div></div>)}
              </div>
              <button className="secondary action-run" onClick={runSimulation} disabled={busy || operations.length === 0}><Icon name="play" size={17}/> Run 1,024 shots</button>
            </div>}
            {simulation && <div className="results"><div className="results-heading"><div><span className="success-dot"/> Simulation complete</div><small>{simulation.engine}</small></div><div className="histogram">{Object.entries(simulation.counts).map(([state, count]) => <div className="bar-row" key={state}><code>|{state}⟩</code><div><i style={{ width: `${Math.max(3, count / 10.24)}%` }}/></div><strong>{count}</strong></div>)}</div><p className="circuit-text">{simulation.circuit_text}</p></div>}
            {submission?.feedback && <div className={`feedback ${submission.score === 100 ? 'great' : ''}`}><strong>{submission.score}% · Feedback</strong><p>{submission.feedback}</p></div>}
            {message && <p className="form-message" role="status">{message}</p>}
          </section>
        </div>
        <footer className="workspace-footer"><button className="secondary" onClick={() => save(false)} disabled={busy}>Save draft</button><button className="primary" onClick={() => save(true)} disabled={busy || (task.task_type === 'quiz' && !answer.trim()) || (task.task_type === 'circuit' && operations.length === 0)}>{busy ? 'Working…' : 'Submit activity'} <Icon name="arrow" size={17}/></button></footer>
      </div>
    </div>
  )
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [activeTask, setActiveTask] = useState<Task | null>(null)
  const [activeSection, setActiveSection] = useState('Overview')
  const [showNotifications, setShowNotifications] = useState(false)
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/students/demo`)
      if (!response.ok) throw new Error('Dashboard API unavailable')
      setDashboard(await response.json())
      setError('')
    } catch {
      setError(`Cannot reach the QuantumLearn API at ${API_URL}. Start the backend, then retry.`)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetch(`${API_URL}/students/demo`)
      .then((response) => {
        if (!response.ok) throw new Error('Dashboard API unavailable')
        return response.json() as Promise<DashboardData>
      })
      .then((data) => { if (!cancelled) setDashboard(data) })
      .catch(() => {
        if (!cancelled) setError(`Cannot reach the QuantumLearn API at ${API_URL}. Start the backend, then retry.`)
      })
    return () => { cancelled = true }
  }, [])

  const unread = useMemo(() => dashboard?.notifications.filter((item) => !item.is_read).length ?? 0, [dashboard])
  const recommendedTask = dashboard?.recommendations[0]

  const openTask = (taskId: string) => {
    const task = dashboard?.tasks.find((item) => item.id === taskId)
    if (task) setActiveTask(task)
  }

  const markRead = async (notification: Notification) => {
    if (!dashboard || notification.is_read) return
    await fetch(`${API_URL}/students/${dashboard.progress.student_id}/notifications/${notification.id}/read`, { method: 'PATCH' })
    await loadDashboard()
  }

  if (error) return <main className="state-screen error-state"><div className="error-orbit">!</div><h1>We couldn’t load your dashboard</h1><p>{error}</p><button className="primary" onClick={loadDashboard}>Try again</button></main>
  if (!dashboard) return <LoadingScreen />

  const { progress, tasks, recommendations, notifications } = dashboard

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" aria-label="QuantumLearn home"><span className="brand-mark"><i/><i/><b/></span><span>Quantum<strong>Learn</strong></span></a>
        <nav>{[['Overview', 'home'], ['My learning', 'book'], ['Progress', 'chart'], ['Achievements', 'trophy']].map(([label, icon]) => <button key={label} className={activeSection === label ? 'active' : ''} onClick={() => setActiveSection(label)}><Icon name={icon}/><span>{label}</span></button>)}</nav>
        <div className="sidebar-streak"><span><Icon name="flame"/></span><div><strong>{progress.streak_days} day streak</strong><small>Keep it going!</small></div></div>
        <div className="profile"><span>{progress.display_name.split(' ').map((part) => part[0]).join('')}</span><div><strong>{progress.display_name}</strong><small>Level {progress.level} learner</small></div></div>
      </aside>

      <main className="main-content" id="top">
        <header className="topbar">
          <div className="mobile-brand">Quantum<strong>Learn</strong></div>
          <div className="top-actions"><div className="xp-chip"><Icon name="spark" size={17}/><strong>{progress.points}</strong> XP</div><div className="notification-wrap"><button className="icon-button" onClick={() => setShowNotifications(!showNotifications)} aria-label={`${unread} unread notifications`}><Icon name="bell"/>{unread > 0 && <b>{unread}</b>}</button>{showNotifications && <div className="notification-menu"><div><strong>Notifications</strong><span>{unread} unread</span></div>{notifications.map((item) => <button key={item.id} className={item.is_read ? 'read' : ''} onClick={() => markRead(item)}><i/><span><strong>{item.title}</strong><small>{item.message}</small></span></button>)}</div>}</div></div>
        </header>

        <div className="content-wrap">
          <section className="welcome"><div><p className="eyebrow">{new Date().toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}</p><h1>Welcome back, {progress.display_name.split(' ')[0]} <span>✦</span></h1><p>Every circuit brings you closer to thinking quantum.</p></div><div className="level-card"><div><span>LEVEL {progress.level}</span><strong>{progress.points % 500} / 500 XP</strong></div><div className="thin-progress"><i style={{ width: `${progress.level_progress}%` }}/></div></div></section>

          <section className="hero-grid">
            <article className="continue-card">
              <div className="card-copy"><p className="eyebrow">Continue learning</p><span className="module-tag">MODULE {tasks.findIndex((task) => task.id === recommendedTask?.task_id) + 1}</span><h2>{recommendedTask?.title ?? 'All activities complete!'}</h2><p>{recommendedTask?.reason ?? 'You have completed every activity. Excellent work.'}</p>{recommendedTask && <button className="primary light" onClick={() => openTask(recommendedTask.task_id)}>Continue activity <Icon name="arrow" size={17}/></button>}</div>
              <div className="quantum-art" aria-hidden="true"><div className="orbit one"><i/></div><div className="orbit two"><i/></div><div className="orbit three"><i/></div><b/></div>
            </article>
            <article className="progress-card"><div className="section-heading"><div><p className="eyebrow">Course progress</p><h2>Your momentum</h2></div><ProgressRing value={progress.completion_percent}/></div><div className="stat-row"><div><strong>{progress.completed_tasks}<small>/{progress.total_tasks}</small></strong><span>Activities</span></div><div><strong>{progress.average_score}<small>%</small></strong><span>Avg. score</span></div><div><strong>{progress.achievements.length}</strong><span>Badges</span></div></div></article>
          </section>

          <section className="activities-section">
            <div className="section-title"><div><p className="eyebrow">Your path</p><h2>Learning activities</h2></div><button className="text-link" onClick={() => setActiveSection('My learning')}>View all <Icon name="arrow" size={16}/></button></div>
            <div className="task-grid">{tasks.map((task, index) => <article className={`task-card ${task.status === 'completed' ? 'completed' : ''}`} key={task.id}>
              <div className="task-top"><span className={`task-icon ${task.task_type}`}>{task.status === 'completed' ? <Icon name="check"/> : task.task_type === 'code' ? <Icon name="code"/> : index + 1}</span><span className={`difficulty ${task.difficulty.toLowerCase()}`}>{task.difficulty}</span></div>
              <p>{task.module}</p><h3>{task.title}</h3><span className="task-kind">{task.task_type === 'circuit' ? 'Interactive circuit' : task.task_type === 'code' ? 'Coding activity' : 'Knowledge check'} · {task.points} XP</span>
              <div className="task-bottom">{task.status === 'completed' ? <span className="done-label"><Icon name="check" size={15}/> Completed · {task.score}%</span> : <button onClick={() => setActiveTask(task)}>{task.status === 'draft' ? 'Resume' : 'Start'} <Icon name="arrow" size={15}/></button>}</div>
            </article>)}</div>
          </section>

          <section className="lower-grid">
            <article className="recommendation-card"><div className="section-title"><div><p className="eyebrow">Picked for you</p><h2>Recommended next</h2></div><span className="ai-badge"><Icon name="spark" size={15}/> Personalised</span></div>{recommendations.slice(0, 2).map((item) => <button className="recommendation" key={item.task_id} onClick={() => openTask(item.task_id)}><span className={`priority ${item.priority}`}/><div><strong>{item.title}</strong><small>{item.reason}</small></div><Icon name="arrow"/></button>)}</article>
            <article className="achievement-card"><div className="section-title"><div><p className="eyebrow">Milestones</p><h2>Achievements</h2></div></div>{progress.achievements.length ? <div className="earned-list">{progress.achievements.slice(0, 3).map((award) => <div key={award.code}><span>{award.icon}</span><div><strong>{award.name}</strong><small>{award.description}</small></div></div>)}</div> : <div className="empty-awards"><span>✦</span><div><strong>Your first badge is close</strong><p>Complete an activity to unlock it.</p></div></div>}</article>
          </section>
        </div>
      </main>
      {activeTask && <TaskWorkspace task={activeTask} studentId={progress.student_id} onClose={() => setActiveTask(null)} onComplete={loadDashboard}/>} 
    </div>
  )
}

export default App
