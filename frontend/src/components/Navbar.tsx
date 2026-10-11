import { NavLink, useNavigate } from 'react-router'

const links = [
  { to: '/home', label: 'Home' },
  { to: '/tutor', label: 'Tutor' },
  { to: '/quiz', label: 'Quiz' },
]

export const Navbar = () => {
  const navigate = useNavigate()
  const user = sessionStorage.getItem('user')

  const handleLogout = () => {
    sessionStorage.removeItem('user')
    navigate('/login', { replace: true })
  }

  return (
    <nav className='sticky top-0 z-10 text-black'>
      <div className='mx-auto max-w-6xl px-4 h-16 flex items-center justify-between gap-4'>
        <span className='text-lg font-bold tracking-tight'>
          Tutor<span className='text-blue-400'>Bot</span>
        </span>

        <div className='flex items-center gap-1 sm:gap-2'>
          {links.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-4 py-1 rounded-md  hover:bg-slate-200 text-sm font-medium transition-colors ${
                  isActive
                    ? 'text-blue-600'
                    : 'text-slate-700'
                }`
                
              }
            >
              {label}
            </NavLink>
          ))}
        </div>

        <div className='flex items-center gap-3'>
          {user && <span className='hidden sm:inline text-sm text-slate-400'>{user}</span>}
          <button
            onClick={handleLogout}
            className='hover:cursor-pointer px-3 py-2 rounded-md text-sm font-medium border border-slate-600 text-slate-70 hover:bg-red-600 hover:border-red-600 hover:text-white transition-colors'
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  )
}
