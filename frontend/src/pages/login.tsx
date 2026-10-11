import { useState, type SubmitEvent } from 'react'
import { useNavigate } from 'react-router'

export const Login = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleSubmit = (e: SubmitEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!username || !password) {
      setError('Please enter a username and password.')
      return
    }
    setError('')
    // TODO: send credentials to the backend. For now any username/password is accepted.
    sessionStorage.setItem('user', username)
    navigate('/home')
  }

  return (
    <div className='flex items-center justify-center min-h-screen px-4'>
      <form
        onSubmit={handleSubmit}
        className='w-full max-w-sm p-8 shadow bg-gray-300 shadow-lg rounded-xl flex flex-col gap-4'
      >
        <h1 className='text-2xl font-bold text-center'>Login</h1>

        <label className='flex flex-col gap-1'>
          <span className='text-sm font-medium'>Username</span>
          <input
            type='text'
            autoComplete='username'
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className='px-3 py-2 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
          />
        </label>

        <label className='flex flex-col gap-1'>
          <span className='text-sm font-medium'>Password</span>
          <input
            type='password'
            autoComplete='current-password'
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className='px-3 py-2 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
          />
        </label>

        {error && <p className='text-sm text-red-600'>{error}</p>}

        <button
          type='submit'
          className='py-2 rounded-md bg-slate-500 text-white font-semibold hover:bg-slate-600 hover:cursor-pointer'
        >
          Sign in
        </button>
      </form>
    </div>
  )
}
