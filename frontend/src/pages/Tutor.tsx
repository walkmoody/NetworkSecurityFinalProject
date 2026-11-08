import { useEffect, useRef, useState, type SubmitEvent } from 'react'
import { useSearchParams } from 'react-router'
import ThoughtLine from '../components/ThoughtLine'
import { tutorSuggestions } from '../assets/assets'

type Citation = { id: string; source: string; section: string }
type ResponseData = { answer: string; supported: boolean; citations: Citation[] }
type Message =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; text: string; citations: Citation[]; working: boolean; steps: string[] }

export const Tutor = () => {
  const [params] = useSearchParams()
  const course = params.get('course') ?? ''
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const counter = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const ask = async (question: string) => {
    const text = question.trim()
    if (!text || busy || !course) return
    setBusy(true)
    setInput('')
    const userId = ++counter.current
    const answerId = ++counter.current
    setMessages(prev => [...prev,
      { id: userId, role: 'user', text },
      { id: answerId, role: 'assistant', text: '', citations: [], working: true, steps: ['Searching course materials'] },
    ])
    try {
      const response = await fetch('/api/tutor/ask', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, course_id: course }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail ?? data.error ?? 'Tutor request failed.')
      const result = data as ResponseData
      setMessages(prev => prev.map(m => m.id === answerId && m.role === 'assistant'
        ? { ...m, text: result.answer, citations: result.citations, working: false,
            steps: ['Retrieved evidence', 'Checked citations'] }
        : m))
    } catch (error) {
      setMessages(prev => prev.map(m => m.id === answerId && m.role === 'assistant'
        ? { ...m, text: error instanceof Error ? error.message : 'Tutor is unavailable.',
            citations: [], working: false, steps: ['Request failed'] }
        : m))
    } finally { setBusy(false) }
  }

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    void ask(input)
  }
  return (
    <div className='mx-auto max-w-4xl px-4 py-8'>
      <div className='flex flex-col h-[calc(100vh-8rem)] rounded-2xl bg-white/80 backdrop-blur border border-slate-200 shadow-sm overflow-hidden'>
        <header className='px-6 py-4 border-b border-slate-200'>
          <p className='text-sm font-semibold text-blue-600'>{course || "No course selected"}</p>
          <h1 className='text-xl font-bold text-slate-900'>{course || 'your course'} Tutor</h1>
        </header>
        <div className='flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-6'>
          {messages.length === 0 && (
            <div className='m-auto text-center flex flex-col items-center gap-4 max-w-lg'>
              <h2 className='text-2xl font-bold text-slate-900'>Ask anything about {course || 'your course'}</h2>
              <p className='text-slate-600'>Answers use course materials and include source citations.</p>
              <div className='flex flex-col gap-2 w-full'>
                {tutorSuggestions.map(s => (
                  <button key={s} onClick={() => void ask(s)}
                    className='px-4 py-3 rounded-xl border border-slate-200 bg-white text-left text-sm text-slate-700 hover:border-blue-400 hover:bg-blue-50 cursor-pointer'>{s}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map(m => m.role === 'user' ? (
            <div key={m.id} className='self-end max-w-[80%] px-4 py-3 rounded-2xl rounded-br-sm bg-blue-600 text-white'>{m.text}</div>
          ) : (
            <div key={m.id} className='self-start max-w-[85%] flex flex-col gap-3'>
              <ThoughtLine working={m.working} steps={m.steps} label='Thinking…' fontSize={14} color='#475569' glyphColor='#2563eb' />
              {!m.working && (
                <div className='px-4 py-3 rounded-2xl rounded-bl-sm bg-white border border-slate-200 text-slate-800 shadow-sm'>
                  <p className='whitespace-pre-wrap'>{m.text}</p>
                  {m.citations.length > 0 && (
                    <div className='mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-2'>
                      {m.citations.map(c => (
                        <span key={c.id} className='px-2 py-1 rounded-md bg-slate-100 text-xs text-slate-600'>
                          {c.source} · {c.section}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <form onSubmit={submit} className='p-4 border-t border-slate-200 flex gap-2'>
          <input value={input} onChange={e => setInput(e.target.value)} placeholder={`Ask about ${course || 'your course'}…`}
            className='flex-1 px-4 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500' />
          <button type='submit' disabled={busy || !input.trim() || !course}
            className='px-5 py-2 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed'>
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
