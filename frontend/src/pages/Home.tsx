import { Link } from 'react-router'
import { ClassCard } from '../components/ClassCard'
import { classes } from '../assets/assets'

const features = [
  {
    to: '/tutor',
    title: 'Q&A Tutor',
    description:
      'Ask questions about your course and get answers grounded in your class materials, with citations.',
  },
  {
    to: '/quiz',
    title: 'Quiz Agent',
    description:
      'Generate random or topic-specific quizzes with multiple-choice, true/false, and open-ended questions, then get graded feedback.',
  },
]

export const Home = () => {
  const user = sessionStorage.getItem('user')

  return (
    <div className='mx-auto max-w-6xl px-4 py-10 flex flex-col gap-12'>
      <section className='text-center flex flex-col items-center gap-4 pt-6'>
        <h1 className='text-4xl sm:text-5xl font-bold tracking-tight text-slate-900'>
          {user ? `Welcome back, ${user}` : 'Welcome to TutorBot'}
        </h1>
        <p className='max-w-2xl text-sm text-slate-600'>
          TutorBot helps you learn by answering questions and quizzing you on your coursework. Everything
          runs on a local model and is grounded in your course materials, so answers stay accurate and
          your data stays private.
        </p>
      </section>

      <section className='grid gap-6 sm:grid-cols-2'>
        {features.map((f) => (
          <Link
            key={f.to}
            to={f.to}
            className='group p-6 rounded-2xl bg-white/70 backdrop-blur border border-white shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all'
          >
            <h2 className='text-xl font-semibold text-slate-900 group-hover:text-blue-600 transition-colors'>
              {f.title} →
            </h2>
            <p className='mt-2 text-sm text-slate-600'>{f.description}</p>
          </Link>
        ))}
      </section>

      <section className='flex flex-col gap-4'>
        <h2 className='text-2xl font-bold text-slate-900'>Your classes</h2>
        <div className='grid gap-6 sm:grid-cols-2 lg:grid-cols-3'>
          {classes.map((c) => (
            <ClassCard key={c.id} {...c} />
          ))}
        </div>
      </section>
    </div>
  )
}
