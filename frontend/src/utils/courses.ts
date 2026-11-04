import { useEffect, useState } from 'react'

// Courses are the folders in the backend's data/ directory that have been indexed.
export const useCourses = () => {
  const [courses, setCourses] = useState<string[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/courses', { credentials: 'same-origin' })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`Request failed (${res.status})`))))
      .then((data: { courses: string[] }) => setCourses(data.courses))
      .catch(() => setError('Could not load your courses. Is the backend running?'))
  }, [])

  return { courses, error }
}
