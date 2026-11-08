import { useState } from 'react'
import { useSearchParams } from 'react-router'
import ThoughtLine from '../components/ThoughtLine'
import type { Quiz as QuizData, QuizQuestion, QuizResult } from '../assets/assets'
import { useCourses } from '../utils/courses'
import { ApiError, createQuiz, retryGrading, submitAnswers, type AgentStep, type QuizAnswer } from '../utils/quizApi'

type Phase = 'setup' | 'generating' | 'answering' | 'grading' | 'results'

const questionCounts = { multiple_choice: 3, true_false: 2, open_ended: 1 }

const typeLabels: Record<QuizQuestion['type'], string> = {
  multiple_choice: 'Multiple choice',
  true_false: 'True / False',
  open_ended: 'Open-ended',
}

export const Quiz = () => {
  const [searchParams] = useSearchParams()
  const { courses } = useCourses()
  const course = searchParams.get('course') ?? courses?.[0] ?? ''

  const [phase, setPhase] = useState<Phase>('setup')
  const [mode, setMode] = useState<'random' | 'topic'>('random')
  const [topic, setTopic] = useState('')
  // Live backend calls streamed while generating and grading.
  const [genSteps, setGenSteps] = useState<AgentStep[]>([])
  const [gradeSteps, setGradeSteps] = useState<AgentStep[]>([])
  const [quiz, setQuiz] = useState<QuizData | null>(null)
  const [answers, setAnswers] = useState<Record<string, QuizAnswer>>({})
  const [result, setResult] = useState<QuizResult | null>(null)
  const [error, setError] = useState('')
  // Set when grading failed after the backend locked the submitted answers.
  const [gradingFailed, setGradingFailed] = useState(false)

  const questions: QuizQuestion[] = quiz?.questions ?? []

  const generate = async () => {
    setPhase('generating')
    setError('')
    setAnswers({})
    setResult(null)
    setGradingFailed(false)
    setGenSteps([])
    setGradeSteps([])
    try {
      const newQuiz = await createQuiz(
        course,
        mode,
        mode === 'topic' ? topic.trim().toLowerCase() : null,
        questionCounts,
        setGenSteps,
      )
      setQuiz(newQuiz)
      setPhase('answering')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not generate a quiz.')
      setQuiz(null)
      setPhase('setup')
    }
  }

  // Retry reuses the answers the backend locked; fall back to submit if nothing was locked.
  const send = async (attemptId: string) => {
    if (!gradingFailed) return submitAnswers(attemptId, answers, setGradeSteps)
    try {
      return await retryGrading(attemptId, setGradeSteps)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) return submitAnswers(attemptId, answers, setGradeSteps)
      throw e
    }
  }

  const grade = async () => {
    if (!quiz) return
    setPhase('grading')
    setError('')
    setGradeSteps([])
    try {
      const graded = await send(quiz.attempt_id)
      setResult(graded)
      setGradingFailed(false)
      setPhase('results')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not grade the quiz.')
      setGradingFailed(true)
      setPhase('answering')
    }
  }

  const setAnswer = (id: string, value: QuizAnswer) => setAnswers((prev) => ({ ...prev, [id]: value }))
  const locked = phase === 'grading' || phase === 'results' || gradingFailed
  const allAnswered = questions.every((q) => answers[q.question_id] !== undefined && answers[q.question_id] !== '')

  return (
    <div className='mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6'>
      <header>
        <h1 className='text-3xl font-bold text-slate-900'>{course} Quiz</h1>
      </header>

      <section className='p-6 rounded-2xl bg-white/80 backdrop-blur border border-slate-200 shadow-sm flex flex-col gap-4'>
        <div className='flex flex-wrap items-end gap-4'>
          <div className='flex flex-col gap-1'>
            <span className='text-sm font-medium text-slate-700'>Mode</span>
            <div className='inline-flex rounded-lg border border-slate-300 overflow-hidden'>
              {(['random', 'topic'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  disabled={phase === 'generating'}
                  className={`px-4 py-2 text-sm font-medium capitalize transition-colors cursor-pointer ${
                    mode === m ? 'bg-blue-600 text-white' : 'bg-white text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          {mode === 'topic' && (
            <label className='flex flex-col gap-1'>
              <span className='text-sm font-medium text-slate-700'>Topic</span>
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder='e.g. firewalls'
                className='px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm'
              />
            </label>
          )}

          <button
            onClick={generate}
            disabled={phase === 'generating' || phase === 'grading' || !course || (mode === 'topic' && !topic.trim())}
            className='ml-auto px-5 py-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer'
          >
            {phase === 'setup' ? 'Generate quiz' : 'New quiz'}
          </button>
        </div>
        <p className='text-xs text-slate-500'>3 multiple choice · 2 true/false · 1 open-ended</p>
        {error && <p className='p-3 rounded-lg bg-red-50 text-sm text-red-800'>{error}</p>}

        {phase !== 'setup' && (
          <ThoughtLine
            working={phase === 'generating'}
            steps={genSteps.map((s) => s.text)}
            stepsDone={genSteps.map((s) => s.done)}
            wrapSteps
            label={mode === 'topic' ? `Building a ${topic} quiz…` : 'Building your quiz…'}
            doneLabel='Quiz ready in'
            fontSize={14}
            color='#475569'
            glyphColor='#2563eb'
          />
        )}
      </section>

      {phase !== 'setup' && phase !== 'generating' && (
        <>
          {questions.map((q, i) => {
            const answer = answers[q.question_id]
            const graded = result?.results.find((r) => r.question_id === q.question_id)
            const correct = graded !== undefined && graded.points_awarded === graded.max_points
            // The backend never reveals the answer key, so only the chosen option is marked.
            const optionState = (selected: boolean) =>
              phase === 'results' && selected ? (correct ? 'correct' : 'wrong') : undefined
            return (
              <section
                key={q.question_id}
                className={`p-6 rounded-2xl bg-white border shadow-sm flex flex-col gap-4 ${
                  phase === 'results' ? (correct ? 'border-green-400' : 'border-red-400') : 'border-slate-200'
                }`}
              >
                <div>
                  <p className='text-xs font-semibold uppercase tracking-wide text-slate-500'>
                    Question {i + 1} · {typeLabels[q.type]}
                  </p>
                  <h2 className='mt-1 text-lg font-semibold text-slate-900'>{q.text}</h2>
                </div>

                {q.type === 'multiple_choice' && (
                  <div className='flex flex-col gap-2'>
                    {Object.entries(q.options).map(([letter, opt]) => (
                      <OptionButton
                        key={letter}
                        label={`${letter}. ${opt}`}
                        selected={answer === letter}
                        state={optionState(answer === letter)}
                        disabled={locked}
                        onClick={() => setAnswer(q.question_id, letter)}
                      />
                    ))}
                  </div>
                )}

                {q.type === 'true_false' && (
                  <div className='grid grid-cols-2 gap-2'>
                    {[true, false].map((val) => (
                      <OptionButton
                        key={String(val)}
                        label={val ? 'True' : 'False'}
                        selected={answer === val}
                        state={optionState(answer === val)}
                        disabled={locked}
                        onClick={() => setAnswer(q.question_id, val)}
                      />
                    ))}
                  </div>
                )}

                {q.type === 'open_ended' && (
                  <textarea
                    value={typeof answer === 'string' ? answer : ''}
                    onChange={(e) => setAnswer(q.question_id, e.target.value)}
                    disabled={locked}
                    rows={4}
                    placeholder='Type your answer…'
                    className='px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50'
                  />
                )}

                {phase === 'results' && graded && (
                  <div className={`p-3 rounded-lg text-sm ${correct ? 'bg-green-50 text-green-900' : 'bg-red-50 text-red-900'}`}>
                    <p className='font-semibold'>
                      {correct ? 'Correct' : 'Not quite'} · {graded.points_awarded}/{graded.max_points} points
                    </p>
                    <p className='mt-1 whitespace-pre-line'>{graded.feedback}</p>
                    {graded.citations.map((c) => (
                      <p key={c.chunk_id} className='mt-2 text-xs opacity-75'>
                        {' '}
                        {c.source_url ? (
                          <a href={c.source_url} target='_blank' rel='noreferrer' className='underline'>
                            {c.title}
                          </a>
                        ) : (
                          c.title
                        )}{' '}
                        · p. {c.page}
                      </p>
                    ))}
                  </div>
                )}
              </section>
            )
          })}

          <section className='p-6 rounded-2xl bg-white/80 backdrop-blur border border-slate-200 shadow-sm flex flex-wrap items-center gap-4'>
            {phase === 'answering' ? (
              <>
                <p className='text-sm text-slate-600'>
                  {Object.keys(answers).length} of {questions.length} answered
                </p>
                <button
                  onClick={grade}
                  disabled={!allAnswered}
                  className='ml-auto px-5 py-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer'
                >
                  {gradingFailed ? 'Retry grading' : 'Submit answers'}
                </button>
              </>
            ) : (
              <>
                <div className='min-w-0 flex-1'>
                  <ThoughtLine
                    working={phase === 'grading'}
                    steps={gradeSteps.map((s) => s.text)}
                    stepsDone={gradeSteps.map((s) => s.done)}
                    wrapSteps
                    label='Grading…'
                    doneLabel='Graded in'
                    fontSize={14}
                    color='#475569'
                    glyphColor='#2563eb'
                  />
                </div>
                {phase === 'results' && result && (
                  <p className='ml-auto text-2xl font-bold text-slate-900'>
                    {result.points_awarded} / {result.max_points}
                  </p>
                )}
              </>
            )}
          </section>
        </>
      )}
    </div>
  )
}

type OptionButtonProps = {
  label: string
  selected: boolean
  state?: 'correct' | 'wrong'
  disabled: boolean
  onClick: () => void
}

const OptionButton = ({ label, selected, state, disabled, onClick }: OptionButtonProps) => {
  const style =
    state === 'correct'
      ? 'border-green-500 bg-green-50 text-green-900'
      : state === 'wrong'
        ? 'border-red-500 bg-red-50 text-red-900'
        : selected
          ? 'border-blue-500 bg-blue-50 text-blue-900'
          : 'border-slate-200 bg-white text-slate-700 hover:border-blue-300'
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`px-4 py-3 rounded-lg border text-left text-sm transition-colors cursor-pointer disabled:cursor-default ${style}`}
    >
      {label}
    </button>
  )
}
