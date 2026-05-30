import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './lib/auth';
import { Login } from './pages/Login';
import { Shell } from './pages/Shell';
import { Spinner } from './components/Spinner';
import { ALL_NAV } from './lib/nav';

export function App() {
  const { state } = useAuth();

  if (state === null) {
    return (
      <div className="boot">
        <Spinner />
      </div>
    );
  }

  if (!state.authenticated) {
    return <Login />;
  }

  return (
    <Routes>
      <Route element={<Shell />}>
        {ALL_NAV.map((item) =>
          item.path === '' ? (
            <Route key="index" index element={item.element} />
          ) : (
            <Route key={item.path} path={item.path} element={item.element} />
          ),
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
