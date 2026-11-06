import { Link } from 'react-router'

// A course is a folder in the backend's data/ directory; its name is the course ID.
export const ClassCard = ({ id }: { id: string }) => {
  return (
    <div className='flex flex-col gap-4 p-6 rounded-2xl bg-white shadow-sm border border-slate-200 hover:shadow-lg transition-shadow'>
      <div>
        <h3 className='text-xl font-bold text-slate-900'>{id}</h3>
        <p className='mt-2 text-sm text-slate-600'>Course materials from data/{id}/</p>
      </div>

      <div className='mt-auto flex gap-2'>
        <Link
          to={`/tutor?course=${encodeURIComponent(id)}`}
          className='flex-1 text-center py-2 rounded-md bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors'
        >
          Ask Tutor
        </Link>
        <Link
          to={`/quiz?course=${encodeURIComponent(id)}`}
          className='flex-1 text-center py-2 rounded-md border border-slate-300 text-slate-700 text-sm font-semibold hover:bg-slate-100 transition-colors'
        >
          Take Quiz
        </Link>
      </div>
    </div>
  )
}
