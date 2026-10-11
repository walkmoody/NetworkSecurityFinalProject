import { Route, Routes, Navigate, Outlet } from 'react-router';
import { Login } from './pages/login';
import { Home } from './pages/Home';
import { Quiz } from './pages/Quiz';
import { Tutor } from './pages/Tutor';
import { Navbar } from './components/Navbar';

// Layout for pages that need a login: shows the Navbar above the page.
// Temporary guard until the backend handles auth: only checks that someone has logged in.
const LoggedInLayout = () => {
  if (!sessionStorage.getItem('user')) return <Navigate to='/login' replace />;
  return (
    <>
      <Navbar />
      <Outlet />
    </>
  );
};

const App = () => {
  return (
    <div className="bg-linear-to-br from-paper to-purple-100 min-h-screen flex flex-col">
      <main className="flex-grow">
        <Routes>
          <Route path='/' element={<Navigate to='/login' replace />} />
          <Route path='/login' element={<Login />} />
          <Route element={<LoggedInLayout />}>
            <Route path='/home' element={<Home />} />
            <Route path='/quiz' element={<Quiz />} />
            <Route path='/tutor' element={<Tutor />} />
          </Route>
          <Route path='*' element={<Navigate to='/' replace />} />
        </Routes>
      </main>
    </div>
  );
};

export default App;
