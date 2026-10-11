import { Link } from 'react-router'

export type ClassInfo = {
  id: string
  code: string
  name: string
  description: string
  topics: string[]
}

export const ClassCard = ({ id, code, name, description, topics }: ClassInfo) => {
  return (
    <div className='flex flex-col gap-4 p-6 rounded-2xl bg-white shadow-sm border border-slate-200 hover:shadow-lg transition-shadow'>
      <div>
        <p className='text-sm font-semibold text-blue-600'>{code}</p>
        <h3 className='text-xl font-bold text-slate-900'>{name}</h3>
        <p className='mt-2 text-sm text-slate-600'>{description}</p>
      </div>

      <div className='flex flex-wrap gap-2'>
        {topics.map((t) => (
          <span key={t} className='px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-xs'>
            {t}
          </span>
        ))}
      </div>

      <div className='mt-auto flex gap-2'>
        <Link
          to={`/tutor?course=${id}`}
          className='flex-1 text-center py-2 rounded-md bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors'
        >
          Ask Tutor
        </Link>
        <Link
          to={`/quiz?course=${id}`}
          className='flex-1 text-center py-2 rounded-md border border-slate-300 text-slate-700 text-sm font-semibold hover:bg-slate-100 transition-colors'
        >
          Take Quiz
        </Link>
      </div>
    </div>
  )
}
