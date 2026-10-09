import { useState, type SubmitEvent } from 'react'

export const Login = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e: SubmitEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!username || !password) {
      setError('Please enter a username and password.')
      return
    }
    setError('')
    // TODO: send credentials to the backend
    console.log('login', { username })
  }

  return (
    <div className='flex items-center justify-center min-h-screen px-4'>
      <form
        onSubmit={handleSubmit}
        className='w-full max-w-sm p-8 border-3 shadow bg-gray-300 rounded-xl flex flex-col gap-4'
      >
        <h1 className='text-2xl font-bold text-center'>Login</h1>

        <label className='flex flex-col gap-1'>
          <span className='text-sm font-medium'>Username</span>
          <input
            type='text'
            autoComplete='username'
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className='px-3 py-2 rounded-md border bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
          />
        </label>

        <label className='flex flex-col gap-1'>
          <span className='text-sm font-medium'>Password</span>
          <input
            type='password'
            autoComplete='current-password'
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className='px-3 py-2 rounded-md border bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
          />
        </label>

        {error && <p className='text-sm text-red-600'>{error}</p>}

        <button
          type='submit'
          className='py-2 rounded-md bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors'
        >
          Sign in
        </button>
      </form>
    </div>
  )
}
