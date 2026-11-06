import type { Quiz, QuizResult } from '../assets/assets'

export type QuizAnswer = string | boolean

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

// One backend call (RAG, model, or agent function) reported while a request runs.
export type AgentStep = { id: number; text: string; done: boolean }
export type OnSteps = (steps: AgentStep[]) => void

type StreamEvent =
  | { type: 'step'; id: number; text: string; done?: boolean }
  | { type: 'result'; data: unknown }
  | { type: 'error'; status: number; detail: string }

// POSTs JSON to the backend (proxied by Vite). The response streams one JSON event per line:
// progress steps while the agent works, then the result or an error.
const post = async <T>(path: string, body: unknown, onSteps: OnSteps): Promise<T> => {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => null)
    throw new ApiError(data?.detail ?? `Request failed (${res.status})`, res.status)
  }

  const steps: AgentStep[] = []
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines.filter((l) => l.trim())) {
      const event = JSON.parse(line) as StreamEvent
      if (event.type === 'result') return event.data as T
      if (event.type === 'error') throw new ApiError(event.detail, event.status)
      const step = { id: event.id, text: event.text, done: Boolean(event.done) }
      const index = steps.findIndex((s) => s.id === step.id)
      if (index >= 0) steps[index] = step
      else steps.push(step)
      onSteps([...steps])
    }
  }
  throw new ApiError('The connection to the backend closed before it finished.', 0)
}

export const createQuiz = (
  courseId: string,
  mode: 'random' | 'topic',
  topicId: string | null,
  questionCounts: Record<string, number>,
  onSteps: OnSteps,
) => post<Quiz>('/quiz', { course_id: courseId, mode, topic_id: topicId, question_counts: questionCounts }, onSteps)

export const submitAnswers = (attemptId: string, answers: Record<string, QuizAnswer>, onSteps: OnSteps) =>
  post<QuizResult>(`/quiz/${encodeURIComponent(attemptId)}/submit`, { answers }, onSteps)

export const retryGrading = (attemptId: string, onSteps: OnSteps) =>
  post<QuizResult>(`/quiz/${encodeURIComponent(attemptId)}/retry`, undefined, onSteps)
