import { useState } from 'react'
import { useSearchParams } from 'react-router'
import ThoughtLine from '../components/ThoughtLine'
import { classes, mockQuiz, quizGenerateSteps, quizGradeSteps, type QuizQuestion } from '../assets/assets'
import { runMockSteps } from '../utils/mockAgent'

type Phase = 'setup' | 'generating' | 'answering' | 'grading' | 'results'
type Answer = number | boolean | string

const typeLabels: Record<QuizQuestion['type'], string> = {
  multiple_choice: 'Multiple choice',
  true_false: 'True / False',
  open_ended: 'Open-ended',
}

const isCorrect = (q: QuizQuestion, a: Answer | undefined) => {
  if (a === undefined) return false
  if (q.type === 'open_ended') {
    const text = String(a).toLowerCase()
    return q.keywords.some((k) => text.includes(k))
  }
  return a === q.answer
}

export const Quiz = () => {
  const [searchParams] = useSearchParams()
  const course = classes.find((c) => c.id === searchParams.get('course')) ?? classes[0]

  const [phase, setPhase] = useState<Phase>('setup')
  const [mode, setMode] = useState<'random' | 'topic'>('random')
  const [topic, setTopic] = useState(course.topics[0])
  const [genSteps, setGenSteps] = useState<string[]>([])
  const [gradeSteps, setGradeSteps] = useState<string[]>([])
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [answers, setAnswers] = useState<Record<string, Answer>>({})

  const generate = async () => {
    setPhase('generating')
    setAnswers({})
    setGradeSteps([])
    // TODO: replace with a call to the backend Quiz agent (mode, topic, question counts).
    await runMockSteps(quizGenerateSteps, setGenSteps)
    setQuestions(mockQuiz)
    setPhase('answering')
  }

  const grade = async () => {
    setPhase('grading')
    // TODO: send answers to the backend for grading.
    await runMockSteps(quizGradeSteps, setGradeSteps)
    setPhase('results')
  }

  const setAnswer = (id: string, value: Answer) => setAnswers((prev) => ({ ...prev, [id]: value }))
  const locked = phase === 'grading' || phase === 'results'
  const score = questions.filter((q) => isCorrect(q, answers[q.id])).length
  const allAnswered = questions.every((q) => answers[q.id] !== undefined && answers[q.id] !== '')

  return (
    <div className='mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6'>
      <header>
        <p className='text-sm font-semibold text-blue-600'>{course.code}</p>
        <h1 className='text-3xl font-bold text-slate-900'>{course.name} Quiz</h1>
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
              <select
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className='px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm'
              >
                {course.topics.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
          )}

          <button
            onClick={generate}
            disabled={phase === 'generating' || phase === 'grading'}
            className='ml-auto px-5 py-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer'
          >
            {phase === 'setup' ? 'Generate quiz' : 'New quiz'}
          </button>
        </div>
        <p className='text-xs text-slate-500'>3 multiple choice · 2 true/false · 1 open-ended</p>

        {phase !== 'setup' && (
          <ThoughtLine
            working={phase === 'generating'}
            steps={genSteps}
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
            const answer = answers[q.id]
            const correct = isCorrect(q, answer)
            return (
              <section
                key={q.id}
                className={`p-6 rounded-2xl bg-white border shadow-sm flex flex-col gap-4 ${
                  phase === 'results' ? (correct ? 'border-green-400' : 'border-red-400') : 'border-slate-200'
                }`}
              >
                <div>
                  <p className='text-xs font-semibold uppercase tracking-wide text-slate-500'>
                    Question {i + 1} · {typeLabels[q.type]}
                  </p>
                  <h2 className='mt-1 text-lg font-semibold text-slate-900'>{q.prompt}</h2>
                </div>

                {q.type === 'multiple_choice' && (
                  <div className='flex flex-col gap-2'>
                    {q.options.map((opt, idx) => (
                      <OptionButton
                        key={opt}
                        label={opt}
                        selected={answer === idx}
                        state={phase === 'results' ? (idx === q.answer ? 'correct' : answer === idx ? 'wrong' : undefined) : undefined}
                        disabled={locked}
                        onClick={() => setAnswer(q.id, idx)}
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
                        state={phase === 'results' ? (val === q.answer ? 'correct' : answer === val ? 'wrong' : undefined) : undefined}
                        disabled={locked}
                        onClick={() => setAnswer(q.id, val)}
                      />
                    ))}
                  </div>
                )}

                {q.type === 'open_ended' && (
                  <textarea
                    value={typeof answer === 'string' ? answer : ''}
                    onChange={(e) => setAnswer(q.id, e.target.value)}
                    disabled={locked}
                    rows={4}
                    placeholder='Type your answer…'
                    className='px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50'
                  />
                )}

                {phase === 'results' && (
                  <div className={`p-3 rounded-lg text-sm ${correct ? 'bg-green-50 text-green-900' : 'bg-red-50 text-red-900'}`}>
                    <p className='font-semibold'>{correct ? 'Correct' : 'Not quite'}</p>
                    <p className='mt-1'>{q.explanation}</p>
                    <p className='mt-2 text-xs opacity-75'>
                      📄 {q.citation.source} · {q.citation.section}
                    </p>
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
                  Submit answers
                </button>
              </>
            ) : (
              <>
                <ThoughtLine
                  working={phase === 'grading'}
                  steps={gradeSteps}
                  label='Grading…'
                  doneLabel='Graded in'
                  fontSize={14}
                  color='#475569'
                  glyphColor='#2563eb'
                />
                {phase === 'results' && (
                  <p className='ml-auto text-2xl font-bold text-slate-900'>
                    {score} / {questions.length}
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
