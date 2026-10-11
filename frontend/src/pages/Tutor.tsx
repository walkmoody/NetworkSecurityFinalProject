import { useEffect, useRef, useState, type SubmitEvent } from 'react'
import { useSearchParams } from 'react-router'
import ThoughtLine from '../components/ThoughtLine'
import {
  classes,
  tutorAnswers,
  tutorFallback,
  tutorSteps,
  tutorSuggestions,
  type Citation,
} from '../assets/assets'
import { runMockSteps } from '../utils/mockAgent'

type Message =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; text: string; citations: Citation[]; steps: string[]; working: boolean }

const pickAnswer = (question: string) => {
  const q = question.toLowerCase()
  return tutorAnswers.find((a) => a.keywords.some((k) => q.includes(k))) ?? tutorFallback
}

export const Tutor = () => {
  const [searchParams] = useSearchParams()
  const course = classes.find((c) => c.id === searchParams.get('course')) ?? classes[0]

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const updateAssistant = (id: number, patch: Partial<Extract<Message, { role: 'assistant' }>>) =>
    setMessages((prev) => prev.map((m) => (m.id === id && m.role === 'assistant' ? { ...m, ...patch } : m)))

  const ask = async (question: string) => {
    const text = question.trim()
    if (!text || busy) return
    setBusy(true)
    setInput('')

    const assistantId = Date.now() + 1
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: 'user', text },
      { id: assistantId, role: 'assistant', text: '', citations: [], steps: [], working: true },
    ])

    // TODO: replace with a call to the backend Tutor agent.
    await runMockSteps(tutorSteps, (steps) => updateAssistant(assistantId, { steps }))
    const answer = pickAnswer(text)
    updateAssistant(assistantId, { text: answer.text, citations: answer.citations, working: false })
    setBusy(false)
  }

  const handleSubmit = (e: SubmitEvent<HTMLFormElement>) => {
    e.preventDefault()
    ask(input)
  }

  return (
    <div className='mx-auto max-w-4xl px-4 py-8'>
      <div className='flex flex-col h-[calc(100vh-8rem)] rounded-2xl bg-white/80 backdrop-blur border border-slate-200 shadow-sm overflow-hidden'>
        <header className='px-6 py-4 border-b border-slate-200'>
          <p className='text-sm font-semibold text-blue-600'>{course.code}</p>
          <h1 className='text-xl font-bold text-slate-900'>{course.name} Tutor</h1>
        </header>

        <div className='flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-6'>
          {messages.length === 0 && (
            <div className='m-auto text-center flex flex-col items-center gap-4 max-w-lg'>
              <h2 className='text-2xl font-bold text-slate-900'>Ask anything about {course.name}</h2>
              <p className='text-slate-600'>Answers come from your course materials and include citations.</p>
              <div className='flex flex-col gap-2 w-full'>
                {tutorSuggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s)}
                    className='px-4 py-3 rounded-xl border border-slate-200 bg-white text-left text-sm text-slate-700 hover:border-blue-400 hover:bg-blue-50 transition-colors cursor-pointer'
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) =>
            m.role === 'user' ? (
              <div key={m.id} className='self-end max-w-[80%] px-4 py-3 rounded-2xl rounded-br-sm bg-blue-600 text-white'>
                {m.text}
              </div>
            ) : (
              <div key={m.id} className='self-start max-w-[85%] flex flex-col gap-3'>
                <ThoughtLine
                  working={m.working}
                  steps={m.steps}
                  label='Thinking…'
                  fontSize={14}
                  color='#475569'
                  glyphColor='#2563eb'
                />
                {!m.working && (
                  <div className='px-4 py-3 rounded-2xl rounded-bl-sm bg-white border border-slate-200 text-slate-800 shadow-sm'>
                    <p>{m.text}</p>
                    {m.citations.length > 0 && (
                      <div className='mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-2'>
                        {m.citations.map((c) => (
                          <span
                            key={c.source + c.section}
                            className='px-2 py-1 rounded-md bg-slate-100 text-xs text-slate-600'
                          >
                            📄 {c.source} · {c.section}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ),
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSubmit} className='p-4 border-t border-slate-200 flex gap-2'>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask about ${course.name}…`}
            className='flex-1 px-4 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
          />
          <button
            type='submit'
            disabled={busy || !input.trim()}
            className='px-5 py-2 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer'
          >
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
